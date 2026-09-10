"""VCI hardware and driver exception hierarchy."""
from __future__ import annotations

from .communication_exceptions import VDPError


class VCIError(VDPError):
    """Base class for VCI hardware/driver failures."""


class DriverNotFoundError(VCIError):
    """Raised when the vendor shared library could not be located or loaded."""


class ConnectionFailedError(VCIError):
    """Raised when the driver failed to open a channel."""


class HardwareNotDetectedError(VCIError):
    """Raised when no matching hardware is present on the system."""


class ChannelNotAvailableError(VCIError):
    """Raised when the requested channel index is invalid or already in use."""


class UnsupportedCapabilityError(VCIError):
    """Raised when the hardware lacks a feature required by the configuration."""


__all__ = [
    "VCIError",
    "DriverNotFoundError",
    "ConnectionFailedError",
    "HardwareNotDetectedError",
    "ChannelNotAvailableError",
    "UnsupportedCapabilityError",
]
