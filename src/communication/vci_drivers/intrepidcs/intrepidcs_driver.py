"""Intrepid Control Systems (neoVI / ValueCAN) driver."""
from __future__ import annotations

from typing import Any

from ....core.enums.vci_enums import VCICapability, VCIType
from ....core.event_bus import EventBus
from ....core.models.vci_model import VCIChannelConfig, VCIDeviceInfo
from ..pcan.pcan_driver import PythonCanDriver


class IntrepidCSDriver(PythonCanDriver):
    """Driver for Intrepid neoVI and ValueCAN interfaces.

    Uses the python-can ``neovi`` backend, which requires the ``python-ics``
    package and the vendor driver package to be installed.
    """

    vci_type = VCIType.INTREPIDCS
    capabilities = frozenset(
        {
            VCICapability.CAN,
            VCICapability.CAN_FD,
            VCICapability.LIN,
            VCICapability.ETHERNET,
            VCICapability.HARDWARE_TIMESTAMPS,
            VCICapability.BUS_STATISTICS,
        }
    )

    def __init__(
        self,
        config: VCIChannelConfig | None = None,
        event_bus: EventBus | None = None,
        serial: str = "",
        **bus_kwargs: Any,
    ) -> None:
        """Select the ``neovi`` backend, optionally binding to *serial*."""
        self.serial = serial
        super().__init__("neovi", config, event_bus, VCIType.INTREPIDCS, **bus_kwargs)

    def _do_connect(self) -> None:
        """Open the neoVI channel, binding to a serial number when given."""
        if self.serial:
            self.bus_kwargs.setdefault("serial", self.serial)
        self.bus_kwargs.setdefault("use_system_timestamp", True)
        super()._do_connect()

    def _build_device_info(self) -> VCIDeviceInfo:
        """Return Intrepid specific device information."""
        info = super()._build_device_info()
        info.name = "Intrepid neoVI"
        info.vci_type = VCIType.INTREPIDCS
        info.serial_number = self.serial
        return info


__all__ = ["IntrepidCSDriver"]
