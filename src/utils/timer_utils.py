"""High resolution timing helpers."""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator


def now_us() -> int:
    """Return the current wall clock time in microseconds since the epoch."""
    return time.time_ns() // 1_000


def monotonic_ms() -> float:
    """Return a monotonic millisecond counter unaffected by clock changes."""
    return time.perf_counter() * 1000.0


@dataclass(slots=True)
class Stopwatch:
    """Measure elapsed time with millisecond resolution.

    Example:
        >>> sw = Stopwatch()
        >>> _ = sw.start()
        >>> _ = sw.stop()
        >>> sw.elapsed_ms >= 0
        True
    """

    _start: float = 0.0
    _end: float = 0.0
    _running: bool = False

    def start(self) -> "Stopwatch":
        """Start (or restart) the stopwatch and return it."""
        self._start = time.perf_counter()
        self._end = 0.0
        self._running = True
        return self

    def stop(self) -> float:
        """Stop the stopwatch and return the elapsed milliseconds."""
        if self._running:
            self._end = time.perf_counter()
            self._running = False
        return self.elapsed_ms

    @property
    def elapsed_ms(self) -> float:
        """Return elapsed milliseconds (live while running)."""
        if not self._start:
            return 0.0
        end = time.perf_counter() if self._running else self._end
        return (end - self._start) * 1000.0

    @property
    def elapsed_s(self) -> float:
        """Return elapsed seconds."""
        return self.elapsed_ms / 1000.0


@contextmanager
def measure(callback: Callable[[float], None] | None = None) -> Iterator[Stopwatch]:
    """Context manager measuring the duration of a block.

    Example:
        >>> with measure() as sw:
        ...     pass
        >>> sw.elapsed_ms >= 0
        True
    """
    watch = Stopwatch().start()
    try:
        yield watch
    finally:
        watch.stop()
        if callback is not None:
            callback(watch.elapsed_ms)


@dataclass(slots=True)
class Deadline:
    """A monotonic deadline used for protocol timeouts."""

    timeout_s: float
    _start: float = field(default_factory=time.perf_counter)

    @property
    def remaining(self) -> float:
        """Return the remaining seconds (never negative)."""
        return max(0.0, self.timeout_s - (time.perf_counter() - self._start))

    @property
    def expired(self) -> bool:
        """Return ``True`` once the deadline has passed."""
        return self.remaining <= 0.0

    def reset(self, timeout_s: float | None = None) -> None:
        """Restart the deadline, optionally with a new timeout."""
        if timeout_s is not None:
            self.timeout_s = timeout_s
        self._start = time.perf_counter()


class PeriodicTimer:
    """Call a function periodically on a daemon thread.

    The timer is used for tester-present transmission, periodic DID reads and
    connection health checks.
    """

    def __init__(self, interval_s: float, callback: Callable[[], None], name: str = "timer") -> None:
        """Create the timer without starting it.

        Args:
            interval_s: Delay between two invocations.
            callback: Function invoked on each tick; exceptions are ignored.
            name: Thread name used in diagnostics.
        """
        self.interval_s = interval_s
        self.callback = callback
        self.name = name
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        """Return ``True`` while the worker thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start ticking; a second call while running is a no-op."""
        if self.is_running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        """Signal the thread to stop and wait up to *timeout* seconds."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def _run(self) -> None:
        """Thread body: invoke the callback every :attr:`interval_s`."""
        while not self._stop.wait(self.interval_s):
            try:
                self.callback()
            except Exception:  # noqa: BLE001 - a timer must never die
                pass

    def __enter__(self) -> "PeriodicTimer":
        """Start the timer for use in a ``with`` block."""
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        """Stop the timer when leaving a ``with`` block."""
        self.stop()


def sleep_ms(milliseconds: float) -> None:
    """Sleep for *milliseconds* using the most precise clock available."""
    if milliseconds <= 0:
        return
    time.sleep(milliseconds / 1000.0)


def busy_wait_us(microseconds: float) -> None:
    """Busy wait for *microseconds* (used for sub-millisecond STmin)."""
    if microseconds <= 0:
        return
    end = time.perf_counter() + microseconds / 1_000_000.0
    while time.perf_counter() < end:
        pass


__all__ = [
    "now_us",
    "monotonic_ms",
    "Stopwatch",
    "measure",
    "Deadline",
    "PeriodicTimer",
    "sleep_ms",
    "busy_wait_us",
]
