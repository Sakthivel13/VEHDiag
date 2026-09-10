"""Abstract logger interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models.log_entry_model import LogCategory, LogEntry, LogLevel


class ILogger(ABC):
    """Contract implemented by every log sink of the platform."""

    @abstractmethod
    def log(self, entry: LogEntry) -> None:
        """Write a fully constructed *entry* to the sink."""

    @abstractmethod
    def flush(self) -> None:
        """Persist any buffered entries."""

    @abstractmethod
    def close(self) -> None:
        """Flush and release the underlying resource."""

    # -- convenience helpers ---------------------------------------------
    def _emit(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        **extra: Any,
    ) -> None:
        """Build a :class:`LogEntry` and hand it to :meth:`log`."""
        self.log(LogEntry(message=message, level=level, category=category, extra=extra))

    def trace(self, message: str, **kw: Any) -> None:
        """Log at TRACE level."""
        self._emit(LogLevel.TRACE, message, **kw)

    def debug(self, message: str, **kw: Any) -> None:
        """Log at DEBUG level."""
        self._emit(LogLevel.DEBUG, message, **kw)

    def info(self, message: str, **kw: Any) -> None:
        """Log at INFO level."""
        self._emit(LogLevel.INFO, message, **kw)

    def warning(self, message: str, **kw: Any) -> None:
        """Log at WARNING level."""
        self._emit(LogLevel.WARNING, message, **kw)

    def error(self, message: str, **kw: Any) -> None:
        """Log at ERROR level."""
        self._emit(LogLevel.ERROR, message, **kw)

    def critical(self, message: str, **kw: Any) -> None:
        """Log at CRITICAL level."""
        self._emit(LogLevel.CRITICAL, message, **kw)


__all__ = ["ILogger"]
