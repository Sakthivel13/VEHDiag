"""Thread-safe publish/subscribe event bus.

The event bus is the backbone of the application: the communication layer, the
diagnostic layer, the test runner and the UI all exchange information through
it instead of holding direct references to each other.

Example:
    >>> bus = EventBus()
    >>> received = []
    >>> token = bus.subscribe(EventType.COMM_CONNECTED, received.append)
    >>> _ = bus.publish(EventType.COMM_CONNECTED, {"vci": "VIRTUAL"})
    >>> received[0].data["vci"]
    'VIRTUAL'
"""
from __future__ import annotations

import asyncio
import itertools
import logging
import threading
import time
import weakref
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable

_logger = logging.getLogger(__name__)

#: Signature of a synchronous event handler.
EventHandler = Callable[["Event"], Any]


class EventCategory(str, Enum):
    """Broad grouping used for coarse subscriptions and filtering."""

    COMMUNICATION = "COMMUNICATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    UI = "UI"
    LOG = "LOG"
    SYSTEM = "SYSTEM"
    TEST = "TEST"
    FILE = "FILE"


class EventType(str, Enum):
    """Every event the platform can publish."""

    # -- communication --------------------------------------------------
    COMM_CONNECTING = "COMM_CONNECTING"
    COMM_CONNECTED = "COMM_CONNECTED"
    COMM_DISCONNECTED = "COMM_DISCONNECTED"
    COMM_ERROR = "COMM_ERROR"
    COMM_MESSAGE_TX = "COMM_MESSAGE_TX"
    COMM_MESSAGE_RX = "COMM_MESSAGE_RX"
    COMM_BUS_ERROR = "COMM_BUS_ERROR"
    COMM_VCI_DETECTED = "COMM_VCI_DETECTED"

    # -- diagnostics -----------------------------------------------------
    DIAG_REQUEST_SENT = "DIAG_REQUEST_SENT"
    DIAG_RESPONSE_RECEIVED = "DIAG_RESPONSE_RECEIVED"
    DIAG_NRC_RECEIVED = "DIAG_NRC_RECEIVED"
    DIAG_SESSION_CHANGED = "DIAG_SESSION_CHANGED"
    DIAG_SECURITY_UNLOCKED = "DIAG_SECURITY_UNLOCKED"
    DIAG_SECURITY_FAILED = "DIAG_SECURITY_FAILED"
    DIAG_DTC_READ = "DIAG_DTC_READ"
    DIAG_DTC_CLEARED = "DIAG_DTC_CLEARED"
    DIAG_TRANSFER_STARTED = "DIAG_TRANSFER_STARTED"
    DIAG_TRANSFER_PROGRESS = "DIAG_TRANSFER_PROGRESS"
    DIAG_TRANSFER_COMPLETE = "DIAG_TRANSFER_COMPLETE"
    DIAG_TRANSFER_FAILED = "DIAG_TRANSFER_FAILED"
    DIAG_ECU_RESET = "DIAG_ECU_RESET"

    # -- test execution ---------------------------------------------------
    TEST_STARTED = "TEST_STARTED"
    TEST_STEP_STARTED = "TEST_STEP_STARTED"
    TEST_STEP_COMPLETED = "TEST_STEP_COMPLETED"
    TEST_COMPLETED = "TEST_COMPLETED"
    TEST_FAILED = "TEST_FAILED"
    TEST_CANCELLED = "TEST_CANCELLED"
    TEST_SEQUENCE_COMPLETE = "TEST_SEQUENCE_COMPLETE"

    # -- logging -----------------------------------------------------------
    LOG_ENTRY_ADDED = "LOG_ENTRY_ADDED"
    LOG_CLEARED = "LOG_CLEARED"
    LOG_EXPORTED = "LOG_EXPORTED"

    # -- user interface ------------------------------------------------------
    UI_THEME_CHANGED = "UI_THEME_CHANGED"
    UI_DPI_CHANGED = "UI_DPI_CHANGED"
    UI_BREAKPOINT_CHANGED = "UI_BREAKPOINT_CHANGED"
    UI_PANEL_TOGGLED = "UI_PANEL_TOGGLED"
    UI_PANEL_CHANGED = "UI_PANEL_CHANGED"
    UI_NOTIFICATION = "UI_NOTIFICATION"

    # -- system --------------------------------------------------------------
    SYSTEM_STARTUP = "SYSTEM_STARTUP"
    SYSTEM_READY = "SYSTEM_READY"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    SYSTEM_CONFIG_CHANGED = "SYSTEM_CONFIG_CHANGED"
    SYSTEM_PLUGIN_LOADED = "SYSTEM_PLUGIN_LOADED"
    SYSTEM_ERROR = "SYSTEM_ERROR"

    # -- files ------------------------------------------------------------------
    FILE_LOADED = "FILE_LOADED"
    FILE_PARSE_FAILED = "FILE_PARSE_FAILED"
    FILE_SAVED = "FILE_SAVED"

    @property
    def category(self) -> EventCategory:
        """Return the :class:`EventCategory` this event belongs to."""
        prefix = self.value.split("_", 1)[0]
        return {
            "COMM": EventCategory.COMMUNICATION,
            "DIAG": EventCategory.DIAGNOSTIC,
            "TEST": EventCategory.TEST,
            "LOG": EventCategory.LOG,
            "UI": EventCategory.UI,
            "SYSTEM": EventCategory.SYSTEM,
            "FILE": EventCategory.FILE,
        }[prefix]


@dataclass(slots=True)
class Event:
    """An immutable notification published on the bus.

    Attributes:
        type: The event type.
        data: Payload mapping; the keys depend on the event type.
        source: Free-form identifier of the publisher.
        timestamp: Unix timestamp of publication.
        sequence: Monotonic counter, useful for ordering in the UI.
    """

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0

    @property
    def category(self) -> EventCategory:
        """Return the category of :attr:`type`."""
        return self.type.category

    def get(self, key: str, default: Any = None) -> Any:
        """Return ``data[key]`` with a *default* fallback."""
        return self.data.get(key, default)

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"<Event {self.type.value} from {self.source or '?'} {self.data}>"


@dataclass(slots=True)
class _Subscription:
    """Internal bookkeeping record for one handler registration."""

    token: int
    handler: EventHandler | weakref.ReferenceType
    is_weak: bool
    once: bool
    predicate: Callable[[Event], bool] | None

    def resolve(self) -> EventHandler | None:
        """Return the live handler, or ``None`` if a weak target has died."""
        if not self.is_weak:
            return self.handler  # type: ignore[return-value]
        return self.handler()  # type: ignore[operator]


class EventBus:
    """A thread-safe publish/subscribe hub.

    Handlers may be registered for a specific :class:`EventType`, for a whole
    :class:`EventCategory`, or globally. Publication is synchronous by default;
    :meth:`publish_async` awaits coroutine handlers.

    The bus never lets a misbehaving handler break the publisher: exceptions
    raised by handlers are caught, logged and reported through
    :attr:`error_handler`.
    """

    def __init__(self, name: str = "main") -> None:
        """Create an empty bus.

        Args:
            name: Identifier used in log messages.
        """
        self.name = name
        self._lock = threading.RLock()
        self._by_type: dict[EventType, list[_Subscription]] = {}
        self._by_category: dict[EventCategory, list[_Subscription]] = {}
        self._global: list[_Subscription] = []
        self._counter = itertools.count(1)
        self._sequence = itertools.count(1)
        self._history: list[Event] = []
        self._history_limit = 500
        self._enabled = True
        self.error_handler: Callable[[Exception, Event], None] | None = None

    # -- subscription management ------------------------------------------
    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
        *,
        weak: bool = False,
        once: bool = False,
        predicate: Callable[[Event], bool] | None = None,
    ) -> int:
        """Register *handler* for a single *event_type*.

        Args:
            event_type: The event to listen for.
            handler: Callable invoked with the :class:`Event`.
            weak: Hold only a weak reference so the handler's owner can be
                garbage collected (recommended for Qt widgets).
            once: Remove the subscription after the first delivery.
            predicate: Optional filter; the handler runs only when it returns
                ``True`` for the event.

        Returns:
            A token that can be passed to :meth:`unsubscribe`.
        """
        sub = self._make_subscription(handler, weak, once, predicate)
        with self._lock:
            self._by_type.setdefault(event_type, []).append(sub)
        return sub.token

    def subscribe_category(
        self,
        category: EventCategory,
        handler: EventHandler,
        *,
        weak: bool = False,
        once: bool = False,
        predicate: Callable[[Event], bool] | None = None,
    ) -> int:
        """Register *handler* for every event of *category*."""
        sub = self._make_subscription(handler, weak, once, predicate)
        with self._lock:
            self._by_category.setdefault(category, []).append(sub)
        return sub.token

    def subscribe_all(self, handler: EventHandler, *, weak: bool = False) -> int:
        """Register *handler* for every event published on the bus."""
        sub = self._make_subscription(handler, weak, False, None)
        with self._lock:
            self._global.append(sub)
        return sub.token

    def subscribe_many(self, event_types: Iterable[EventType], handler: EventHandler) -> list[int]:
        """Register *handler* for each type in *event_types*."""
        return [self.subscribe(t, handler) for t in event_types]

    def unsubscribe(self, token: int) -> bool:
        """Remove the subscription identified by *token*.

        Returns:
            ``True`` when a subscription was removed.
        """
        with self._lock:
            for bucket in (*self._by_type.values(), *self._by_category.values(), self._global):
                for sub in list(bucket):
                    if sub.token == token:
                        bucket.remove(sub)
                        return True
        return False

    def clear(self) -> None:
        """Remove every subscription and the event history."""
        with self._lock:
            self._by_type.clear()
            self._by_category.clear()
            self._global.clear()
            self._history.clear()

    # -- publication ---------------------------------------------------------
    def publish(
        self,
        event_type: EventType,
        data: dict[str, Any] | None = None,
        source: str = "",
    ) -> Event:
        """Publish an event synchronously and return it.

        Every matching handler is invoked on the calling thread. Exceptions are
        swallowed and logged so that one faulty subscriber cannot break others.
        """
        event = Event(
            type=event_type,
            data=data or {},
            source=source,
            sequence=next(self._sequence),
        )
        self.publish_event(event)
        return event

    def publish_event(self, event: Event) -> None:
        """Publish a pre-built :class:`Event`."""
        if not self._enabled:
            return
        self._remember(event)
        for sub in self._matching(event):
            handler = sub.resolve()
            if handler is None:
                self._drop(sub)
                continue
            if sub.predicate is not None and not sub.predicate(event):
                continue
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    # Fire and forget: schedule on the running loop if any.
                    try:
                        asyncio.get_running_loop().create_task(result)
                    except RuntimeError:
                        asyncio.run(result)
            except Exception as exc:  # noqa: BLE001 - handlers must not break the bus
                _logger.exception("event handler failed for %s", event.type.value)
                if self.error_handler is not None:
                    try:
                        self.error_handler(exc, event)
                    except Exception:  # noqa: BLE001
                        _logger.exception("event bus error_handler failed")
            finally:
                if sub.once:
                    self._drop(sub)

    async def publish_async(
        self,
        event_type: EventType,
        data: dict[str, Any] | None = None,
        source: str = "",
    ) -> Event:
        """Publish an event and await any coroutine handlers."""
        event = Event(
            type=event_type,
            data=data or {},
            source=source,
            sequence=next(self._sequence),
        )
        self._remember(event)
        for sub in self._matching(event):
            handler = sub.resolve()
            if handler is None:
                self._drop(sub)
                continue
            if sub.predicate is not None and not sub.predicate(event):
                continue
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:  # noqa: BLE001
                _logger.exception("async event handler failed for %s", event.type.value)
                if self.error_handler is not None:
                    self.error_handler(exc, event)
            finally:
                if sub.once:
                    self._drop(sub)
        return event

    # -- introspection ----------------------------------------------------------
    @property
    def enabled(self) -> bool:
        """Return ``False`` when publication is temporarily suppressed."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Enable or suppress publication (used during shutdown)."""
        self._enabled = enabled

    def subscriber_count(self, event_type: EventType | None = None) -> int:
        """Return the number of registered handlers, optionally for one type."""
        with self._lock:
            if event_type is None:
                total = sum(len(v) for v in self._by_type.values())
                total += sum(len(v) for v in self._by_category.values())
                return total + len(self._global)
            direct = len(self._by_type.get(event_type, ()))
            category = len(self._by_category.get(event_type.category, ()))
            return direct + category + len(self._global)

    def history(self, limit: int | None = None) -> list[Event]:
        """Return the most recent events, newest last."""
        with self._lock:
            return list(self._history[-limit:] if limit else self._history)

    def set_history_limit(self, limit: int) -> None:
        """Set how many events are retained for :meth:`history`."""
        self._history_limit = max(0, limit)

    # -- internals -----------------------------------------------------------------
    def _make_subscription(
        self,
        handler: EventHandler,
        weak: bool,
        once: bool,
        predicate: Callable[[Event], bool] | None,
    ) -> _Subscription:
        """Build a :class:`_Subscription` record for *handler*."""
        ref: EventHandler | weakref.ReferenceType
        is_weak = weak
        if weak:
            try:
                ref = weakref.WeakMethod(handler)  # type: ignore[arg-type]
            except TypeError:
                try:
                    ref = weakref.ref(handler)
                except TypeError:
                    ref, is_weak = handler, False
        else:
            ref = handler
        return _Subscription(next(self._counter), ref, is_weak, once, predicate)

    def _matching(self, event: Event) -> list[_Subscription]:
        """Return a snapshot of the subscriptions interested in *event*."""
        with self._lock:
            return [
                *self._by_type.get(event.type, ()),
                *self._by_category.get(event.category, ()),
                *self._global,
            ]

    def _drop(self, sub: _Subscription) -> None:
        """Remove *sub* from every bucket it may live in."""
        with self._lock:
            for bucket in (*self._by_type.values(), *self._by_category.values(), self._global):
                if sub in bucket:
                    bucket.remove(sub)

    def _remember(self, event: Event) -> None:
        """Append *event* to the bounded history buffer."""
        if self._history_limit <= 0:
            return
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_limit:
                del self._history[: len(self._history) - self._history_limit]

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<EventBus {self.name!r} subscribers={self.subscriber_count()}>"


_GLOBAL_BUS: EventBus | None = None
_GLOBAL_LOCK = threading.Lock()


def get_event_bus() -> EventBus:
    """Return the process wide default :class:`EventBus` (created on demand)."""
    global _GLOBAL_BUS
    if _GLOBAL_BUS is None:
        with _GLOBAL_LOCK:
            if _GLOBAL_BUS is None:
                _GLOBAL_BUS = EventBus("global")
    return _GLOBAL_BUS


def reset_event_bus() -> None:
    """Drop the global bus; primarily used to isolate unit tests."""
    global _GLOBAL_BUS
    with _GLOBAL_LOCK:
        _GLOBAL_BUS = None


__all__ = [
    "EventCategory",
    "EventType",
    "Event",
    "EventBus",
    "EventHandler",
    "get_event_bus",
    "reset_event_bus",
]
