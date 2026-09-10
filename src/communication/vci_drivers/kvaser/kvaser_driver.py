"""Kvaser CANlib based driver."""
from __future__ import annotations

from typing import Any

from ....core.enums.vci_enums import VCICapability, VCIType
from ....core.event_bus import EventBus
from ....core.models.vci_model import VCIChannelConfig, VCIDeviceInfo, VCIStatus
from ..pcan.pcan_driver import PythonCanDriver


class KvaserDriver(PythonCanDriver):
    """Driver for Kvaser CAN/CAN FD interfaces.

    Uses the python-can ``kvaser`` backend, which binds Kvaser CANlib. The
    Blackbird and Leaf subclasses only refine the reported metadata and the
    default timing.
    """

    vci_type = VCIType.KVASER_LEAF_V3
    capabilities = frozenset(
        {
            VCICapability.CAN,
            VCICapability.CAN_FD,
            VCICapability.LISTEN_ONLY,
            VCICapability.HARDWARE_TIMESTAMPS,
            VCICapability.BUS_STATISTICS,
            VCICapability.ERROR_FRAMES,
        }
    )

    def __init__(
        self,
        config: VCIChannelConfig | None = None,
        event_bus: EventBus | None = None,
        vci_type: VCIType | None = None,
        **bus_kwargs: Any,
    ) -> None:
        """Select the ``kvaser`` python-can backend."""
        super().__init__("kvaser", config, event_bus, vci_type or self.vci_type, **bus_kwargs)

    def _do_connect(self) -> None:
        """Open the CANlib channel with sensible defaults."""
        self.bus_kwargs.setdefault("accept_virtual", False)
        self.bus_kwargs.setdefault("driver_mode", True)  # normal, not silent
        super()._do_connect()

    def get_status(self) -> VCIStatus:
        """Return the status enriched with the CANlib bus statistics."""
        status = super().get_status()
        bus = getattr(self, "_bus", None)
        stats = getattr(bus, "get_stats", None)
        if callable(stats):
            try:
                raw = stats()
                status.bus_load_percent = float(getattr(raw, "busLoad", 0)) / 100.0
                status.error_count = int(getattr(raw, "errFrame", 0))
            except Exception:  # noqa: BLE001 - statistics are best effort
                pass
        return status

    def _build_device_info(self) -> VCIDeviceInfo:
        """Return Kvaser specific device information."""
        info = super()._build_device_info()
        info.name = self.vci_type.display_name
        info.vci_type = self.vci_type
        return info


__all__ = ["KvaserDriver"]
