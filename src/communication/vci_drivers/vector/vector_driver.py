"""Vector Informatik hardware driver (XL Driver Library via python-can)."""
from __future__ import annotations

from typing import Any

from ....core.enums.vci_enums import VCICapability, VCIType
from ....core.event_bus import EventBus
from ....core.models.vci_model import VCIChannelConfig, VCIDeviceInfo
from ..pcan.pcan_driver import PythonCanDriver


class VectorDriver(PythonCanDriver):
    """Driver for Vector CAN/CAN FD channels.

    The python-can ``vector`` backend wraps ``vxlapi``; the application name
    below must be registered in the Vector Hardware Configuration tool.
    """

    vci_type = VCIType.VECTOR
    capabilities = frozenset(
        {
            VCICapability.CAN,
            VCICapability.CAN_FD,
            VCICapability.LIN,
            VCICapability.FLEXRAY,
            VCICapability.HARDWARE_TIMESTAMPS,
            VCICapability.BUS_STATISTICS,
            VCICapability.ERROR_FRAMES,
        }
    )

    #: Application name the channels must be assigned to.
    DEFAULT_APP_NAME = "VehicleDiagnosticsPlatform"

    def __init__(
        self,
        config: VCIChannelConfig | None = None,
        event_bus: EventBus | None = None,
        app_name: str | None = None,
        **bus_kwargs: Any,
    ) -> None:
        """Select the ``vector`` backend and the application name."""
        self.app_name = app_name or self.DEFAULT_APP_NAME
        super().__init__("vector", config, event_bus, VCIType.VECTOR, **bus_kwargs)

    def _do_connect(self) -> None:
        """Open the Vector channel with the registered application name."""
        self.bus_kwargs.setdefault("app_name", self.app_name)
        self.bus_kwargs.setdefault("rx_queue_size", 16384)
        super()._do_connect()

    def _build_device_info(self) -> VCIDeviceInfo:
        """Return Vector specific device information."""
        info = super()._build_device_info()
        info.name = "Vector XL channel"
        info.vci_type = VCIType.VECTOR
        info.extra["app_name"] = self.app_name
        return info


__all__ = ["VectorDriver"]
