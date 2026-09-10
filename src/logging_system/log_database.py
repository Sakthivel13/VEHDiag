"""SQLite storage for log entries."""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterator

from ..core.models.log_entry_model import LogCategory, LogEntry, LogLevel
from ..utils.file_utils import ensure_dir

_logger = logging.getLogger(__name__)

#: Schema of the communication log table.
SCHEMA = """
CREATE TABLE IF NOT EXISTS communication_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    timestamp_us INTEGER NOT NULL,
    direction TEXT DEFAULT '',
    protocol TEXT DEFAULT '',
    channel TEXT DEFAULT '',
    can_id TEXT DEFAULT '',
    data_hex TEXT DEFAULT '',
    data_length INTEGER DEFAULT 0,
    decoded_service TEXT DEFAULT '',
    decoded_detail TEXT DEFAULT '',
    level TEXT DEFAULT 'INFO',
    category TEXT DEFAULT 'COMM',
    session_id TEXT DEFAULT '',
    delta_us INTEGER DEFAULT 0,
    message TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_timestamp ON communication_log(timestamp_us);
CREATE INDEX IF NOT EXISTS idx_level ON communication_log(level);
CREATE INDEX IF NOT EXISTS idx_category ON communication_log(category);
CREATE INDEX IF NOT EXISTS idx_session ON communication_log(session_id);
CREATE VIRTUAL TABLE IF NOT EXISTS log_search USING fts5(
    data_hex, decoded_service, message, content='communication_log', content_rowid='id'
);
"""


class LogDatabase:
    """Persist log entries in SQLite with buffered writes.

    Args:
        path: Database file; ``":memory:"`` keeps everything in RAM.
        buffer_size: Number of entries buffered before a flush.
        flush_interval_s: Maximum age of buffered entries.

    Example:
        >>> database = LogDatabase(":memory:")
        >>> database.insert(LogEntry(message="hello"))
        >>> _ = database.flush()
        >>> database.count()
        1
        >>> database.close()
    """

    def __init__(
        self,
        path: str | Path = ":memory:",
        buffer_size: int = 500,
        flush_interval_s: float = 0.1,
    ) -> None:
        """Open the database and create the schema."""
        self.path = str(path)
        self.buffer_size = buffer_size
        self.flush_interval_s = flush_interval_s
        if self.path != ":memory:":
            ensure_dir(Path(self.path).parent)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.commit()
        self._buffer: list[LogEntry] = []
        self._lock = threading.RLock()
        self._last_flush = time.perf_counter()
        self.session_id = time.strftime("%Y%m%d-%H%M%S")

    # -- writing ------------------------------------------------------------
    def insert(self, entry: LogEntry) -> None:
        """Buffer *entry*, flushing when the buffer is full or stale."""
        with self._lock:
            if not entry.session_id:
                entry.session_id = self.session_id
            self._buffer.append(entry)
            stale = (time.perf_counter() - self._last_flush) >= self.flush_interval_s
            if len(self._buffer) >= self.buffer_size or stale:
                self._flush_locked()

    def insert_many(self, entries: list[LogEntry]) -> None:
        """Buffer several entries at once."""
        with self._lock:
            self._buffer.extend(entries)
            if len(self._buffer) >= self.buffer_size:
                self._flush_locked()

    def flush(self) -> int:
        """Write the buffered entries and return how many were stored."""
        with self._lock:
            return self._flush_locked()

    def _flush_locked(self) -> int:
        """Write the buffer; the caller must hold the lock."""
        if not self._buffer:
            return 0
        rows = [
            (
                entry.formatted_time(True),
                entry.timestamp_us,
                entry.direction,
                entry.protocol,
                entry.channel,
                entry.can_id,
                entry.hex_data,
                len(entry.data),
                entry.decoded_service,
                entry.decoded_detail,
                entry.level.name,
                entry.category.value,
                entry.session_id,
                entry.delta_us,
                entry.message,
            )
            for entry in self._buffer
        ]
        self._connection.executemany(
            """INSERT INTO communication_log
               (timestamp, timestamp_us, direction, protocol, channel, can_id, data_hex,
                data_length, decoded_service, decoded_detail, level, category, session_id,
                delta_us, message)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        self._connection.commit()
        written = len(self._buffer)
        self._buffer.clear()
        self._last_flush = time.perf_counter()
        return written

    # -- reading --------------------------------------------------------------
    def count(self, session_id: str | None = None) -> int:
        """Return the number of stored entries."""
        with self._lock:
            if session_id:
                cursor = self._connection.execute(
                    "SELECT COUNT(*) FROM communication_log WHERE session_id = ?", (session_id,)
                )
            else:
                cursor = self._connection.execute("SELECT COUNT(*) FROM communication_log")
            return int(cursor.fetchone()[0])

    def query(
        self,
        limit: int = 1000,
        offset: int = 0,
        level: str | None = None,
        category: str | None = None,
        session_id: str | None = None,
        since_us: int | None = None,
    ) -> list[LogEntry]:
        """Return stored entries matching the given criteria."""
        clauses: list[str] = []
        params: list[Any] = []
        if level:
            clauses.append("level = ?")
            params.append(level)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if since_us is not None:
            clauses.append("timestamp_us >= ?")
            params.append(since_us)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        with self._lock:
            cursor = self._connection.execute(
                f"SELECT * FROM communication_log {where} ORDER BY id LIMIT ? OFFSET ?", params
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def search(self, text: str, limit: int = 500) -> list[LogEntry]:
        """Search the payload, decoded service and message columns."""
        pattern = f"%{text}%"
        with self._lock:
            cursor = self._connection.execute(
                """SELECT * FROM communication_log
                   WHERE data_hex LIKE ? OR decoded_service LIKE ? OR message LIKE ?
                   ORDER BY id LIMIT ?""",
                (pattern, pattern, pattern, limit),
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def iter_all(self, chunk: int = 1000) -> Iterator[LogEntry]:
        """Stream every entry in insertion order."""
        offset = 0
        while True:
            batch = self.query(limit=chunk, offset=offset)
            if not batch:
                return
            yield from batch
            offset += chunk

    def statistics(self) -> dict[str, Any]:
        """Return counts per level and per category."""
        with self._lock:
            levels = dict(
                self._connection.execute(
                    "SELECT level, COUNT(*) FROM communication_log GROUP BY level"
                ).fetchall()
            )
            categories = dict(
                self._connection.execute(
                    "SELECT category, COUNT(*) FROM communication_log GROUP BY category"
                ).fetchall()
            )
        return {"total": self.count(), "levels": levels, "categories": categories}

    # -- maintenance -----------------------------------------------------------
    def clear(self) -> None:
        """Delete every stored entry."""
        with self._lock:
            self._buffer.clear()
            self._connection.execute("DELETE FROM communication_log")
            self._connection.commit()

    def prune(self, retention_days: int = 30, max_entries: int = 0) -> int:
        """Delete old entries and return how many rows were removed."""
        removed = 0
        cutoff_us = int((time.time() - retention_days * 86400) * 1_000_000)
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM communication_log WHERE timestamp_us < ?", (cutoff_us,)
            )
            removed += cursor.rowcount or 0
            if max_entries:
                cursor = self._connection.execute(
                    """DELETE FROM communication_log WHERE id NOT IN
                       (SELECT id FROM communication_log ORDER BY id DESC LIMIT ?)""",
                    (max_entries,),
                )
                removed += cursor.rowcount or 0
            self._connection.commit()
        return removed

    def vacuum(self) -> None:
        """Compact the database file."""
        with self._lock:
            self._connection.execute("VACUUM")
            self._connection.commit()

    def close(self) -> None:
        """Flush the buffer and close the connection."""
        with self._lock:
            self._flush_locked()
            self._connection.close()

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> LogEntry:
        """Convert a database row back into a :class:`LogEntry`."""
        data_hex = row["data_hex"] or ""
        data = bytes.fromhex(data_hex.replace(" ", "")) if data_hex else b""
        return LogEntry(
            message=row["message"] or "",
            level=LogLevel.parse(row["level"] or "INFO"),
            category=LogCategory(row["category"] or "SYSTEM"),
            timestamp=(row["timestamp_us"] or 0) / 1_000_000,
            direction=row["direction"] or "",
            protocol=row["protocol"] or "",
            channel=row["channel"] or "",
            can_id=row["can_id"] or "",
            data=data,
            decoded_service=row["decoded_service"] or "",
            decoded_detail=row["decoded_detail"] or "",
            delta_us=row["delta_us"] or 0,
            session_id=row["session_id"] or "",
        )

    def __enter__(self) -> "LogDatabase":
        """Open the database for use in a ``with`` block."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the database when leaving a ``with`` block."""
        self.close()


__all__ = ["LogDatabase", "SCHEMA"]
