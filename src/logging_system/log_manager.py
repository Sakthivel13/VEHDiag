"""Central log manager.

The manager is the single sink every part of the application writes to. It
fans each entry out to the console, a rotating file, the SQLite database, the
in-memory ring buffer consumed by the log viewer and any custom listener.
"""
from __future__ import annotations

import logging
import logging.handlers
import threading
from collections import deque
from pathlib import Path
from typing import Callable, Iterable

from ..core.configuration_manager import ConfigurationManager, get_config
from ..core.event_bus import EventBus, EventType, get_event_bus
from ..core.interfaces.i_logger import ILogger
from ..core.models.log_entry_model import LogCategory, LogEntry, LogLevel
from ..utils.file_utils import ensure_dir
from ..utils.platform_utils import log_dir
from .communication_logger import CommunicationLogger
from .diagnostic_logger import DiagnosticLogger
from .log_database import LogDatabase
from .log_filter import LogFilter
from .log_formatter import FormatOptions, LogFormatter
from .timestamped_logger import TimestampedLogger

_logger = logging.getLogger(__name__)

#: Mapping of the platform levels to the standard library levels.
STDLIB_LEVELS: dict[LogLevel, int] = {
    LogLevel.TRACE: 5,
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
    LogLevel.CRITICAL: logging.CRITICAL,
}

#: Signature of a live log listener (used by the log viewer).
LogListener = Callable[[LogEntry], None]


class LogManager(ILogger):
    """Fan out log entries to every configured sink.

    Args:
        config: Application configuration; the ``logging`` section is used.
        event_bus: Bus used to publish ``LOG_ENTRY_ADDED`` notifications.
        buffer_size: Number of entries kept in memory for the log viewer.

    Example:
        >>> manager = LogManager(buffer_size=10, use_database=False, use_file=False)
        >>> manager.info("hello", category=LogCategory.SYSTEM)
        >>> len(manager.entries())
        1
        >>> manager.close()
    """

    def __init__(
        self,
        config: ConfigurationManager | None = None,
        event_bus: EventBus | None = None,
        buffer_size: int = 100_000,
        use_database: bool | None = None,
        use_file: bool | None = None,
    ) -> None:
        """Create the manager and open the configured sinks."""
        self.config = config or get_config()
        self.bus = event_bus or get_event_bus()
        self.level = LogLevel.parse(self.config.get("logging.level", "INFO"))
        self.formatter = LogFormatter(FormatOptions())
        self.stamper = TimestampedLogger()
        self.filter = LogFilter()
        self._buffer: deque[LogEntry] = deque(maxlen=buffer_size)
        self._listeners: list[LogListener] = []
        self._lock = threading.RLock()
        self._paused = False
        self.dropped = 0

        self.database: LogDatabase | None = None
        if use_database if use_database is not None else self.config.get("logging.log_to_database", True):
            self.database = LogDatabase(
                self._database_path(),
                buffer_size=int(self.config.get("logging.buffer_size", 500)),
                flush_interval_s=float(self.config.get("logging.flush_interval_ms", 100)) / 1000.0,
            )

        self._file_handler: logging.Handler | None = None
        if use_file if use_file is not None else self.config.get("logging.log_to_file", True):
            self._file_handler = self._create_file_handler()

        self.communication = CommunicationLogger(self.log, self.bus)
        self.diagnostics = DiagnosticLogger(self.log, self.bus)

    # -- ILogger ------------------------------------------------------------
    def log(self, entry: LogEntry) -> None:
        """Write *entry* to every sink."""
        if self._paused or entry.level < self.level:
            return
        self.stamper.stamp(entry)
        with self._lock:
            if len(self._buffer) == self._buffer.maxlen:
                self.dropped += 1
            self._buffer.append(entry)
            listeners = list(self._listeners)
        if self.database is not None:
            self.database.insert(entry)
        if self._file_handler is not None:
            record = logging.LogRecord(
                name=f"vdp.{entry.category.value.lower()}",
                level=STDLIB_LEVELS.get(entry.level, logging.INFO),
                pathname=__file__,
                lineno=0,
                msg=self.formatter.to_text(entry),
                args=(),
                exc_info=None,
            )
            self._file_handler.handle(record)
        for listener in listeners:
            try:
                listener(entry)
            except Exception:  # noqa: BLE001 - a bad listener must not stop logging
                _logger.exception("log listener failed")
        self.bus.publish(EventType.LOG_ENTRY_ADDED, {"entry": entry}, "LogManager")

    def flush(self) -> None:
        """Flush the database buffer and the file handler."""
        if self.database is not None:
            self.database.flush()
        if self._file_handler is not None:
            self._file_handler.flush()

    def close(self) -> None:
        """Flush everything and release the sinks."""
        self.flush()
        self.communication.unsubscribe()
        self.diagnostics.unsubscribe()
        if self.database is not None:
            self.database.close()
            self.database = None
        if self._file_handler is not None:
            self._file_handler.close()
            self._file_handler = None

    # -- buffer access ---------------------------------------------------------
    def entries(self, apply_filter: bool = False, limit: int | None = None) -> list[LogEntry]:
        """Return the buffered entries, optionally filtered and limited."""
        with self._lock:
            items = list(self._buffer)
        if apply_filter and self.filter.is_active():
            items = self.filter.apply(items)
        return items[-limit:] if limit else items

    def entry_at(self, index: int) -> LogEntry | None:
        """Return the buffered entry at *index*, or ``None``."""
        with self._lock:
            if 0 <= index < len(self._buffer):
                return self._buffer[index]
        return None

    def count(self, apply_filter: bool = False) -> int:
        """Return the number of buffered entries."""
        return len(self.entries(apply_filter))

    def clear(self) -> None:
        """Empty the in-memory buffer and reset the delta chain."""
        with self._lock:
            self._buffer.clear()
        self.stamper.reset()
        self.bus.publish(EventType.LOG_CLEARED, {}, "LogManager")

    def search(self, text: str, limit: int = 500) -> list[LogEntry]:
        """Search the buffered entries, falling back to the database."""
        needle = text.lower()
        matches = [
            entry
            for entry in self.entries()
            if needle in self.formatter.to_text(entry).lower()
        ]
        if matches or self.database is None:
            return matches[:limit]
        return self.database.search(text, limit)

    # -- control ----------------------------------------------------------------
    def pause(self) -> None:
        """Stop accepting new entries (the *Pause* button of the log panel)."""
        self._paused = True

    def resume(self) -> None:
        """Resume accepting entries."""
        self._paused = False

    @property
    def paused(self) -> bool:
        """Return ``True`` while logging is paused."""
        return self._paused

    def set_level(self, level: LogLevel | str | int) -> None:
        """Change the minimum severity that is recorded."""
        self.level = LogLevel.parse(level)

    def add_listener(self, listener: LogListener) -> None:
        """Register a live listener (used by the log viewer widget)."""
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(self, listener: LogListener) -> None:
        """Remove a previously registered listener."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    # -- convenience helpers -------------------------------------------------------
    def trace(self, message: str, **kw: object) -> None:
        """Log at TRACE level."""
        self._emit(LogLevel.TRACE, message, **kw)

    def debug(self, message: str, **kw: object) -> None:
        """Log at DEBUG level."""
        self._emit(LogLevel.DEBUG, message, **kw)

    def info(self, message: str, **kw: object) -> None:
        """Log at INFO level."""
        self._emit(LogLevel.INFO, message, **kw)

    def warning(self, message: str, **kw: object) -> None:
        """Log at WARNING level."""
        self._emit(LogLevel.WARNING, message, **kw)

    def error(self, message: str, **kw: object) -> None:
        """Log at ERROR level."""
        self._emit(LogLevel.ERROR, message, **kw)

    def critical(self, message: str, **kw: object) -> None:
        """Log at CRITICAL level."""
        self._emit(LogLevel.CRITICAL, message, **kw)

    def _emit(self, level: LogLevel, message: str, **kw: object) -> None:
        """Build an entry from keyword arguments and log it."""
        category = kw.pop("category", LogCategory.SYSTEM)
        if isinstance(category, str):
            category = LogCategory(category)
        self.log(LogEntry(message=message, level=level, category=category, extra=dict(kw)))

    # -- export / maintenance --------------------------------------------------------
    def export(self, path: str | Path, export_format: str = "CSV", filtered: bool = True) -> Path:
        """Export the buffered entries to *path*."""
        from .log_exporter import ExportFormat, LogExporter

        target = LogExporter(self.formatter).export(
            self.entries(apply_filter=filtered), path, ExportFormat(export_format)
        )
        self.bus.publish(
            EventType.LOG_EXPORTED, {"path": str(target), "format": export_format}, "LogManager"
        )
        return target

    def prune_database(self) -> int:
        """Apply the retention policy to the database."""
        if self.database is None:
            return 0
        return self.database.prune(int(self.config.get("logging.retention_days", 30)))

    def statistics(self) -> dict[str, object]:
        """Return counters describing the logging subsystem."""
        from dataclasses import asdict

        return {
            "buffered": self.count(),
            "dropped": self.dropped,
            "paused": self._paused,
            "level": self.level.name,
            "database": self.database.count() if self.database is not None else 0,
            "communication": asdict(self.communication.statistics),
        }

    # -- internals ---------------------------------------------------------------------
    def _database_path(self) -> Path:
        """Return the configured database path."""
        configured = str(self.config.get("logging.database_path", "") or "")
        if configured:
            return Path(configured).expanduser()
        return log_dir() / "vdp_logs.sqlite3"

    def _create_file_handler(self) -> logging.Handler:
        """Create the rotating file handler for the text log."""
        directory = str(self.config.get("logging.directory", "") or "")
        target_dir = Path(directory).expanduser() if directory else log_dir()
        ensure_dir(target_dir)
        handler = logging.handlers.RotatingFileHandler(
            target_dir / "vdp.log",
            maxBytes=int(self.config.get("logging.max_file_size_mb", 50)) * 1024 * 1024,
            backupCount=int(self.config.get("logging.backup_count", 10)),
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        return handler

    def __enter__(self) -> "LogManager":
        """Return the manager for use in a ``with`` block."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the manager when leaving a ``with`` block."""
        self.close()


_INSTANCE: LogManager | None = None
_INSTANCE_LOCK = threading.Lock()


def get_log_manager() -> LogManager:
    """Return the process wide :class:`LogManager`."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = LogManager()
    return _INSTANCE


def set_log_manager(manager: LogManager | None) -> None:
    """Override (or clear) the global log manager, used in tests."""
    global _INSTANCE
    with _INSTANCE_LOCK:
        _INSTANCE = manager


__all__ = ["LogManager", "LogListener", "get_log_manager", "set_log_manager", "STDLIB_LEVELS"]
