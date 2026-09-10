"""Threading helpers shared by the communication and test layers."""
from __future__ import annotations

import functools
import queue
import threading
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class StoppableThread(threading.Thread):
    """A daemon thread exposing a cooperative stop flag.

    Subclasses implement :meth:`run_loop`, which is called repeatedly until
    :meth:`stop` is invoked.
    """

    def __init__(self, name: str = "worker", interval_s: float = 0.0) -> None:
        """Create the thread.

        Args:
            name: Thread name used in logs.
            interval_s: Optional pause between two loop iterations.
        """
        super().__init__(name=name, daemon=True)
        self._stop_event = threading.Event()
        self.interval_s = interval_s

    @property
    def stopped(self) -> bool:
        """Return ``True`` once a stop was requested."""
        return self._stop_event.is_set()

    def stop(self, timeout: float | None = 2.0) -> None:
        """Request a stop and optionally join the thread."""
        self._stop_event.set()
        if timeout and self.is_alive():
            self.join(timeout)

    def run(self) -> None:
        """Drive :meth:`run_loop` until stopped."""
        while not self._stop_event.is_set():
            try:
                self.run_loop()
            except Exception:  # noqa: BLE001 - keep the worker alive
                self.on_error()
            if self.interval_s:
                self._stop_event.wait(self.interval_s)

    def run_loop(self) -> None:
        """One iteration of the worker loop; override in subclasses."""
        raise NotImplementedError

    def on_error(self) -> None:
        """Hook invoked when :meth:`run_loop` raised; default is to ignore."""


class ThreadSafeCounter:
    """An integer counter guarded by a lock."""

    def __init__(self, initial: int = 0) -> None:
        """Initialise the counter with *initial*."""
        self._value = initial
        self._lock = threading.Lock()

    def increment(self, amount: int = 1) -> int:
        """Add *amount* and return the new value."""
        with self._lock:
            self._value += amount
            return self._value

    def reset(self, value: int = 0) -> None:
        """Set the counter to *value*."""
        with self._lock:
            self._value = value

    @property
    def value(self) -> int:
        """Return the current value."""
        with self._lock:
            return self._value


class Result(Generic[T]):
    """A one-shot value slot used to hand results between threads."""

    def __init__(self) -> None:
        """Create an unset result."""
        self._event = threading.Event()
        self._value: T | None = None
        self._error: BaseException | None = None

    def set(self, value: T) -> None:
        """Publish *value* and wake every waiter."""
        self._value = value
        self._event.set()

    def set_error(self, error: BaseException) -> None:
        """Publish an *error* to be re-raised in :meth:`wait`."""
        self._error = error
        self._event.set()

    def wait(self, timeout: float | None = None) -> T | None:
        """Block until a value is available.

        Raises:
            BaseException: Whatever was passed to :meth:`set_error`.
        """
        if not self._event.wait(timeout):
            return None
        if self._error is not None:
            raise self._error
        return self._value

    @property
    def ready(self) -> bool:
        """Return ``True`` when a value or error has been set."""
        return self._event.is_set()


def synchronized(lock_attr: str = "_lock") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a method so it runs while holding ``self.<lock_attr>``."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            lock = getattr(self, lock_attr)
            with lock:
                return func(self, *args, **kwargs)

        return wrapper

    return decorator


def run_in_thread(name: str = "task") -> Callable[[Callable[..., Any]], Callable[..., threading.Thread]]:
    """Decorate a function so calling it spawns a daemon thread."""

    def decorator(func: Callable[..., Any]) -> Callable[..., threading.Thread]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> threading.Thread:
            thread = threading.Thread(
                target=func, args=args, kwargs=kwargs, name=name, daemon=True
            )
            thread.start()
            return thread

        return wrapper

    return decorator


def drain_queue(source: "queue.Queue[Any]", limit: int | None = None) -> list[Any]:
    """Remove and return up to *limit* items from *source* without blocking."""
    items: list[Any] = []
    while limit is None or len(items) < limit:
        try:
            items.append(source.get_nowait())
        except queue.Empty:
            break
    return items


__all__ = [
    "StoppableThread",
    "ThreadSafeCounter",
    "Result",
    "synchronized",
    "run_in_thread",
    "drain_queue",
]
