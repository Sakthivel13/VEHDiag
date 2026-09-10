"""Protocol layer exception hierarchy."""
from __future__ import annotations

from .communication_exceptions import VDPError


class ProtocolError(VDPError):
    """Base class for protocol level failures."""


class FramingError(ProtocolError):
    """Raised when a frame violates the protocol framing rules."""


class ChecksumError(ProtocolError):
    """Raised when a received frame fails its checksum/CRC check."""


class TimingError(ProtocolError):
    """Raised when protocol timing constraints (P1..P4, STmin) are violated."""


class IsoTpError(ProtocolError):
    """Base class for ISO 15765-2 specific errors."""


class FlowControlError(IsoTpError):
    """Raised on missing, malformed or overflow flow control frames."""


class SequenceNumberError(IsoTpError):
    """Raised when consecutive frames arrive out of order."""


class UnsupportedProtocolError(ProtocolError):
    """Raised when a protocol is requested that the platform cannot provide."""


__all__ = [
    "ProtocolError",
    "FramingError",
    "ChecksumError",
    "TimingError",
    "IsoTpError",
    "FlowControlError",
    "SequenceNumberError",
    "UnsupportedProtocolError",
]
