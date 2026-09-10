"""Microsecond precision timestamping helpers."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from ..core.models.log_entry_model import LogEntry


@dataclass(slots=True)
class TimeReference:
    """The reference used to compute relative timestamps."""

    absolute: float = 0.0
    label: str = "start"

    def relative(self, timestamp: float) -> float:
        """Return the seconds elapsed since the reference."""
        return max(0.0, timestamp - self.absolute)


class TimestampedLogger:
    """Assigns absolute, relative and delta timestamps to log entries.

    Example:
        >>> stamper = TimestampedLogger()
        >>> first = stamper.stamp(LogEntry(message="a"))
        >>> second = stamper.stamp(LogEntry(message="b"))
        >>> second.delta_us >= 0
        True
    """

    def __init__(self) -> None:
        """Create the stamper with the reference set to now."""
        self.reference = TimeReference(absolute=time.time())
        self._previous_us: int | None = None
        self._lock = threading.Lock()

    def stamp(self, entry: LogEntry) -> LogEntry:
        """Fill in the timestamp and delta fields of *entry*."""
        with self._lock:
            if not entry.timestamp:
                entry.timestamp = time.time()
            current = entry.timestamp_us
            entry.delta_us = 0 if self._previous_us is None else current - self._previous_us
            self._previous_us = current
            return entry

    def set_reference(self, timestamp: float | None = None, label: str = "manual") -> None:
        """Set the reference used for relative timestamps."""
        with self._lock:
            self.reference = TimeReference(timestamp or time.time(), label)

    def reset(self) -> None:
        """Reset both the reference and the delta chain."""
        with self._lock:
            self.reference = TimeReference(time.time())
            self._previous_us = None

    def relative_seconds(self, entry: LogEntry) -> float:
        """Return the entry timestamp relative to the reference."""
        return self.reference.relative(entry.timestamp)

    @staticmethod
    def format_absolute(timestamp: float, with_date: bool = False) -> str:
        """Format *timestamp* with microsecond precision."""
        moment = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone()
        pattern = "%Y-%m-%d %H:%M:%S.%f" if with_date else "%H:%M:%S.%f"
        return moment.strftime(pattern)

    @staticmethod
    def format_relative(seconds: float) -> str:
        """Format a relative time as ``mm:ss.ffffff``.

        Example:
            >>> TimestampedLogger.format_relative(65.5)
            '01:05.500000'
        """
        minutes, remainder = divmod(max(0.0, seconds), 60)
        return f"{int(minutes):02d}:{remainder:09.6f}"

    @staticmethod
    def format_delta(delta_us: int) -> str:
        """Format a delta in microseconds as a readable duration.

        Example:
            >>> TimestampedLogger.format_delta(1500)
            '+1.500 ms'
        """
        if abs(delta_us) < 1000:
            return f"+{delta_us} us"
        if abs(delta_us) < 1_000_000:
            return f"+{delta_us / 1000.0:.3f} ms"
        return f"+{delta_us / 1_000_000.0:.3f} s"


__all__ = ["TimestampedLogger", "TimeReference"]
