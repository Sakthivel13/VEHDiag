"""Kvaser Leaf v3 (USB CAN FD) specialisation."""
from __future__ import annotations

from typing import Any

from ....core.enums.vci_enums import VCIType
from ....core.models.vci_model import VCIDeviceInfo
from .kvaser_driver import KvaserDriver


class KvaserLeafV3Driver(KvaserDriver):
    """Driver for the USB connected Kvaser Leaf v3."""

    vci_type = VCIType.KVASER_LEAF_V3

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create the driver bound to the Leaf v3 identity."""
        super().__init__(*args, vci_type=VCIType.KVASER_LEAF_V3, **kwargs)

    def _build_device_info(self) -> VCIDeviceInfo:
        """Return Leaf v3 specific device information."""
        info = super()._build_device_info()
        info.name = "Kvaser Leaf v3"
        info.extra["connection"] = "usb"
        return info


__all__ = ["KvaserLeafV3Driver"]
