"""Kvaser BlackBird V2 (wireless) specialisation."""
from __future__ import annotations

from typing import Any

from ....core.enums.vci_enums import VCICapability, VCIType
from ....core.models.vci_model import VCIDeviceInfo
from .kvaser_driver import KvaserDriver


class KvaserBlackbirdV2Driver(KvaserDriver):
    """Driver for the wireless Kvaser BlackBird V2.

    Wireless latency is significantly higher than USB, so the class raises the
    default diagnostic timeouts advertised to the connection manager.
    """

    vci_type = VCIType.KVASER_BLACKBIRD_V2
    capabilities = frozenset(
        {
            VCICapability.CAN,
            VCICapability.LISTEN_ONLY,
            VCICapability.HARDWARE_TIMESTAMPS,
            VCICapability.BUS_STATISTICS,
        }
    )

    #: Suggested P2 client timing in milliseconds for wireless operation.
    RECOMMENDED_P2_MS = 500

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create the driver and remember the wireless recommendation."""
        super().__init__(*args, vci_type=VCIType.KVASER_BLACKBIRD_V2, **kwargs)

    def _build_device_info(self) -> VCIDeviceInfo:
        """Return BlackBird specific device information."""
        info = super()._build_device_info()
        info.name = "Kvaser BlackBird V2"
        info.extra["connection"] = "wireless"
        info.extra["recommended_p2_ms"] = self.RECOMMENDED_P2_MS
        return info


__all__ = ["KvaserBlackbirdV2Driver"]
