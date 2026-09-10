"""Minimal observer pattern used by models that predate the event bus."""
from __future__ import annotations

import threading
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")

Observer = Callable[[Any], None]


class Observable(Generic[T]):
    """A value container notifying observers whenever the value changes.

    Example:
        >>> state = Observable("DISCONNECTED")
        >>> seen = []
        >>> _ = state.subscribe(seen.append)
        >>> state.value = "CONNECTED"
        >>> seen
        ['CONNECTED']
    """

    def __init__(self, initial: T) -> None:
        """Store *initial* as the current value."""
        self._value = initial
        self._observers: list[Observer] = []
        self._lock = threading.RLock()

    @property
    def value(self) -> T:
        """Return the current value."""
        return self._value

    @value.setter
    def value(self, new_value: T) -> None:
        """Assign a new value and notify observers when it changed."""
        with self._lock:
            if new_value == self._value:
                return
            self._value = new_value
            observers = list(self._observers)
        for observer in observers:
            observer(new_value)

    def subscribe(self, observer: Observer, *, immediate: bool = False) -> Observer:
        """Register *observer*; return it so it can be used as a decorator."""
        with self._lock:
            self._observers.append(observer)
        if immediate:
            observer(self._value)
        return observer

    def unsubscribe(self, observer: Observer) -> None:
        """Remove *observer* if present."""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def clear(self) -> None:
        """Remove all observers."""
        with self._lock:
            self._observers.clear()

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<Observable {self._value!r} observers={len(self._observers)}>"


__all__ = ["Observable", "Observer"]
