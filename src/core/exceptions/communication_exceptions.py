"""Communication layer exception hierarchy."""
from __future__ import annotations

from typing import Any


class VDPError(Exception):
    """Root exception for every error raised by the platform.

    Args:
        message: Human readable description shown to the operator.
        details: Optional structured context attached to the error, e.g. the
            offending payload or the driver status code.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def __str__(self) -> str:  # noqa: D105 - trivial
        if not self.details:
            return self.message
        rendered = ", ".join(f"{k}={v!r}" for k, v in self.details.items())
        return f"{self.message} ({rendered})"


class CommunicationError(VDPError):
    """Base class for all transport/bus level failures."""


class TimeoutError_(CommunicationError):
    """Raised when an expected message does not arrive within the timeout.

    Named with a trailing underscore to avoid shadowing the builtin; it is
    exported as ``CommunicationTimeoutError``.
    """


CommunicationTimeoutError = TimeoutError_


class BusError(CommunicationError):
    """Raised on bus level faults such as bus-off or error passive states."""


class BufferOverflowError(CommunicationError):
    """Raised when an RX/TX queue overflows and messages were dropped."""


class NotConnectedError(CommunicationError):
    """Raised when an operation requires an active connection."""


class SendError(CommunicationError):
    """Raised when a frame could not be handed to the hardware."""


__all__ = [
    "VDPError",
    "CommunicationError",
    "CommunicationTimeoutError",
    "BusError",
    "BufferOverflowError",
    "NotConnectedError",
    "SendError",
]
