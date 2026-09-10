"""Log entry data model."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any


class LogLevel(IntEnum):
    """Severity levels ordered from most to least verbose."""

    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    @classmethod
    def parse(cls, value: "str | int | LogLevel") -> "LogLevel":
        """Coerce *value* (name, number or member) into a :class:`LogLevel`."""
        if isinstance(value, LogLevel):
            return value
        if isinstance(value, int):
            return cls(value)
        return cls[str(value).strip().upper()]


class LogCategory(str, Enum):
    """Functional area a log entry belongs to."""

    COMM = "COMM"
    DIAG = "DIAG"
    UI = "UI"
    SYSTEM = "SYSTEM"
    TEST = "TEST"
    FILE = "FILE"


@dataclass(slots=True)
class LogEntry:
    """A single record written by the logging subsystem.

    Attributes:
        message: Human readable log text.
        level: Severity of the entry.
        category: Functional area of the entry.
        timestamp: Unix timestamp with sub-microsecond resolution.
        direction: ``"TX"``/``"RX"`` for communication entries.
        protocol: Protocol name for communication entries.
        channel: Hardware channel name.
        can_id: Formatted identifier for communication entries.
        data: Raw payload for communication entries.
        decoded_service: Decoded UDS service name, if any.
        decoded_detail: Extra decoding information.
        delta_us: Microseconds since the previous entry.
        session_id: Identifier grouping entries of one application run.
        extra: Free-form structured context.
    """

    message: str = ""
    level: LogLevel = LogLevel.INFO
    category: LogCategory = LogCategory.SYSTEM
    timestamp: float = field(default_factory=time.time)
    direction: str = ""
    protocol: str = ""
    channel: str = ""
    can_id: str = ""
    data: bytes = b""
    decoded_service: str = ""
    decoded_detail: str = ""
    delta_us: int = 0
    session_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def timestamp_us(self) -> int:
        """Return the timestamp as integer microseconds since the epoch."""
        return int(self.timestamp * 1_000_000)

    @property
    def hex_data(self) -> str:
        """Return the payload as space separated uppercase hex."""
        return " ".join(f"{b:02X}" for b in self.data)

    def formatted_time(self, absolute: bool = True) -> str:
        """Return the timestamp as ``HH:MM:SS.ffffff`` (or ISO 8601)."""
        dt = datetime.fromtimestamp(self.timestamp, tz=timezone.utc).astimezone()
        return dt.isoformat() if absolute else dt.strftime("%H:%M:%S.%f")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON/CSV friendly mapping of the entry."""
        return {
            "timestamp": self.formatted_time(),
            "timestamp_us": self.timestamp_us,
            "level": self.level.name,
            "category": self.category.value,
            "direction": self.direction,
            "protocol": self.protocol,
            "channel": self.channel,
            "can_id": self.can_id,
            "data_hex": self.hex_data,
            "data_length": len(self.data),
            "decoded_service": self.decoded_service,
            "decoded_detail": self.decoded_detail,
            "delta_us": self.delta_us,
            "session_id": self.session_id,
            "message": self.message,
        }

    def __str__(self) -> str:  # noqa: D105 - trivial
        head = f"{self.formatted_time(False)} [{self.level.name:<8}] [{self.category.value:<6}]"
        if self.data:
            return f"{head} {self.direction:<2} {self.protocol} {self.can_id} {self.hex_data}"
        return f"{head} {self.message}"


__all__ = ["LogLevel", "LogCategory", "LogEntry"]
