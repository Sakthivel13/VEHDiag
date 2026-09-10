"""Unit tests for the event bus."""
from __future__ import annotations

import threading

import pytest

from src.core.event_bus import Event, EventBus, EventCategory, EventType


class TestSubscription:
    """Subscribing and unsubscribing."""

    def test_publish_reaches_subscriber(self, event_bus: EventBus) -> None:
        """A handler registered for a type receives the event."""
        received: list[Event] = []
        event_bus.subscribe(EventType.COMM_CONNECTED, received.append)
        event_bus.publish(EventType.COMM_CONNECTED, {"vci": "VIRTUAL"})
        assert len(received) == 1
        assert received[0].get("vci") == "VIRTUAL"

    def test_unsubscribe(self, event_bus: EventBus) -> None:
        """After unsubscribing no more events arrive."""
        received: list[Event] = []
        token = event_bus.subscribe(EventType.COMM_CONNECTED, received.append)
        assert event_bus.unsubscribe(token)
        event_bus.publish(EventType.COMM_CONNECTED)
        assert not received

    def test_category_subscription(self, event_bus: EventBus) -> None:
        """A category handler receives every event of that category."""
        received: list[Event] = []
        event_bus.subscribe_category(EventCategory.DIAGNOSTIC, received.append)
        event_bus.publish(EventType.DIAG_SESSION_CHANGED)
        event_bus.publish(EventType.DIAG_DTC_READ)
        event_bus.publish(EventType.COMM_CONNECTED)
        assert len(received) == 2

    def test_global_subscription(self, event_bus: EventBus) -> None:
        """A global handler sees everything."""
        received: list[Event] = []
        event_bus.subscribe_all(received.append)
        event_bus.publish(EventType.COMM_CONNECTED)
        event_bus.publish(EventType.DIAG_DTC_READ)
        assert len(received) == 2

    def test_once(self, event_bus: EventBus) -> None:
        """A one-shot subscription fires exactly once."""
        received: list[Event] = []
        event_bus.subscribe(EventType.COMM_CONNECTED, received.append, once=True)
        event_bus.publish(EventType.COMM_CONNECTED)
        event_bus.publish(EventType.COMM_CONNECTED)
        assert len(received) == 1

    def test_predicate_filters(self, event_bus: EventBus) -> None:
        """A predicate suppresses non-matching events."""
        received: list[Event] = []
        event_bus.subscribe(
            EventType.COMM_MESSAGE_TX,
            received.append,
            predicate=lambda e: e.get("protocol") == "CAN",
        )
        event_bus.publish(EventType.COMM_MESSAGE_TX, {"protocol": "CAN"})
        event_bus.publish(EventType.COMM_MESSAGE_TX, {"protocol": "DOIP"})
        assert len(received) == 1

    def test_subscribe_many(self, event_bus: EventBus) -> None:
        """One handler can cover several types."""
        received: list[Event] = []
        event_bus.subscribe_many(
            [EventType.COMM_CONNECTED, EventType.COMM_DISCONNECTED], received.append
        )
        event_bus.publish(EventType.COMM_CONNECTED)
        event_bus.publish(EventType.COMM_DISCONNECTED)
        assert len(received) == 2


class TestRobustness:
    """The bus must survive misbehaving handlers."""

    def test_exception_is_isolated(self, event_bus: EventBus) -> None:
        """One failing handler does not stop the others."""
        received: list[Event] = []

        def broken(_event: Event) -> None:
            raise RuntimeError("boom")

        event_bus.subscribe(EventType.COMM_CONNECTED, broken)
        event_bus.subscribe(EventType.COMM_CONNECTED, received.append)
        event_bus.publish(EventType.COMM_CONNECTED)
        assert len(received) == 1

    def test_error_handler_is_called(self, event_bus: EventBus) -> None:
        """The error handler receives the exception."""
        errors: list[Exception] = []
        event_bus.error_handler = lambda exc, _event: errors.append(exc)
        event_bus.subscribe(
            EventType.COMM_CONNECTED, lambda _e: (_ for _ in ()).throw(ValueError("x"))
        )
        event_bus.publish(EventType.COMM_CONNECTED)
        assert isinstance(errors[0], ValueError)

    def test_thread_safety(self, event_bus: EventBus) -> None:
        """Concurrent publishing does not lose events."""
        received: list[Event] = []
        lock = threading.Lock()

        def handler(event: Event) -> None:
            with lock:
                received.append(event)

        event_bus.subscribe(EventType.COMM_MESSAGE_TX, handler)
        threads = [
            threading.Thread(
                target=lambda: [event_bus.publish(EventType.COMM_MESSAGE_TX) for _ in range(50)]
            )
            for _ in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(received) == 200


class TestIntrospection:
    """History, counters and the disable switch."""

    def test_history(self, event_bus: EventBus) -> None:
        """Published events are remembered."""
        event_bus.publish(EventType.COMM_CONNECTED)
        event_bus.publish(EventType.COMM_DISCONNECTED)
        assert len(event_bus.history()) == 2
        assert event_bus.history(1)[0].type is EventType.COMM_DISCONNECTED

    def test_subscriber_count(self, event_bus: EventBus) -> None:
        """The counter reflects the registrations."""
        event_bus.subscribe(EventType.COMM_CONNECTED, lambda _e: None)
        event_bus.subscribe_all(lambda _e: None)
        assert event_bus.subscriber_count() == 2

    def test_disable(self, event_bus: EventBus) -> None:
        """A disabled bus drops every event."""
        received: list[Event] = []
        event_bus.subscribe(EventType.COMM_CONNECTED, received.append)
        event_bus.set_enabled(False)
        event_bus.publish(EventType.COMM_CONNECTED)
        assert not received

    def test_event_category_mapping(self) -> None:
        """Every event maps to the right category."""
        assert EventType.COMM_CONNECTED.category is EventCategory.COMMUNICATION
        assert EventType.DIAG_DTC_READ.category is EventCategory.DIAGNOSTIC
        assert EventType.TEST_STARTED.category is EventCategory.TEST
        assert EventType.UI_THEME_CHANGED.category is EventCategory.UI

    def test_clear(self, event_bus: EventBus) -> None:
        """Clearing removes handlers and history."""
        event_bus.subscribe(EventType.COMM_CONNECTED, lambda _e: None)
        event_bus.publish(EventType.COMM_CONNECTED)
        event_bus.clear()
        assert event_bus.subscriber_count() == 0
        assert not event_bus.history()
