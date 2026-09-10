"""Abstract Vehicle Communication Interface driver."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.message_model import BusMessage
from ..models.vci_model import VCIChannelConfig, VCIDeviceInfo, VCIStatus


class IVCIDriver(ABC):
    """Contract implemented by every VCI hardware driver.

    Implementations wrap a vendor library (PCANBasic, Vector XL, Kvaser
    CANlib, ...) or a software bus and expose a uniform frame oriented API.
    All methods must be safe to call from a background worker thread.
    """

    @abstractmethod
    def configure(self, config: VCIChannelConfig) -> None:
        """Apply *config* to the driver before connecting.

        Args:
            config: Channel, protocol and bitrate parameters.

        Raises:
            UnsupportedCapabilityError: The hardware cannot honour *config*.
        """

    @abstractmethod
    def connect(self) -> None:
        """Open the configured channel.

        Raises:
            ConnectionFailedError: The channel could not be opened.
            DriverNotFoundError: The vendor library is unavailable.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the channel and release all hardware resources."""

    @abstractmethod
    def send(self, message: BusMessage) -> None:
        """Transmit a single frame.

        Args:
            message: The frame to transmit.

        Raises:
            NotConnectedError: The channel is not open.
            SendError: The hardware rejected the frame.
        """

    @abstractmethod
    def receive(self, timeout: float = 1.0) -> BusMessage | None:
        """Return the next received frame, or ``None`` on timeout.

        Args:
            timeout: Maximum time to block, in seconds.
        """

    @abstractmethod
    def get_status(self) -> VCIStatus:
        """Return the live status of the channel."""

    @abstractmethod
    def get_device_info(self) -> VCIDeviceInfo:
        """Return static information about the hardware."""

    # -- optional hooks with sensible defaults ---------------------------
    def flush(self) -> None:
        """Discard any buffered frames. Drivers may override."""

    def reset(self) -> None:
        """Reset the controller (e.g. recover from bus-off). May be overridden."""

    @property
    def is_connected(self) -> bool:
        """Return ``True`` when the channel is open."""
        return self.get_status().is_connected

    def __enter__(self) -> "IVCIDriver":
        """Open the channel for use in a ``with`` block."""
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close the channel when leaving a ``with`` block."""
        self.disconnect()


__all__ = ["IVCIDriver"]
