"""LIN protocol family."""
from __future__ import annotations

from .lin_checksum import classic_checksum, enhanced_checksum, protected_id
from .lin_frame import LINFrame, LINFrameType, build_master_request, parse_slave_response
from .lin_protocol import LINProtocol
from .lin_scheduler import LINScheduler, ScheduleEntry, ScheduleTable

__all__ = [
    "LINFrame",
    "LINFrameType",
    "LINProtocol",
    "LINScheduler",
    "ScheduleEntry",
    "ScheduleTable",
    "build_master_request",
    "classic_checksum",
    "enhanced_checksum",
    "parse_slave_response",
    "protected_id",
]
