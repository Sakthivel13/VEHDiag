"""A recording mock VCI driver used to assert on the raw traffic."""
from __future__ import annotations

from typing import Any

from src.core.enums.vci_enums import VCIType
from src.core.models.message_model import BusMessage
from src.core.models.vci_model import VCIDeviceInfo
from src.communication.vci_drivers.virtual.virtual_vci_driver import VirtualVCIDriver


class MockVCIDriver(VirtualVCIDriver):
    """A virtual driver that records every frame it sends and receives.

    Example:
        >>> driver = MockVCIDriver()
        >>> driver.connect()
        >>> driver.sent
        []
        >>> driver.disconnect()
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create the driver with empty recordings."""
        super().__init__(*args, **kwargs)
        self.sent: list[BusMessage] = []
        self.received: list[BusMessage] = []

    def _do_send(self, message: BusMessage) -> None:
        """Record and forward the frame."""
        self.sent.append(message)
        super()._do_send(message)

    def _do_receive(self, timeout: float) -> BusMessage | None:
        """Record and return the received frame."""
        message = super()._do_receive(timeout)
        if message is not None:
            self.received.append(message)
        return message

    def _build_device_info(self) -> VCIDeviceInfo:
        """Return the mock device description."""
        info = super()._build_device_info()
        info.name = "Mock VCI"
        info.vci_type = VCIType.VIRTUAL
        return info

    def clear_recordings(self) -> None:
        """Forget everything that was recorded."""
        self.sent.clear()
        self.received.clear()

    @property
    def sent_hex(self) -> list[str]:
        """Return the transmitted frames as hexadecimal strings."""
        return [message.hex_data for message in self.sent]

    @property
    def received_hex(self) -> list[str]:
        """Return the received frames as hexadecimal strings."""
        return [message.hex_data for message in self.received]


__all__ = ["MockVCIDriver"]
