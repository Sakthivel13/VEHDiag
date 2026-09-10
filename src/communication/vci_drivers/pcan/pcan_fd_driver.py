"""PCAN FD driver specialisation."""
from __future__ import annotations

from typing import Any

from ....core.enums.protocol_enums import ProtocolType
from ....core.enums.vci_enums import VCIType
from ....core.event_bus import EventBus
from ....core.models.vci_model import VCIChannelConfig, VCIDeviceInfo
from .pcan_driver import PCANDriver


class PCANFDDriver(PCANDriver):
    """PEAK PCAN-USB FD driver.

    The only difference from :class:`PCANDriver` is that the channel is opened
    in FD mode with a separate data phase bitrate.
    """

    vci_type = VCIType.PCAN_FD

    def __init__(
        self,
        config: VCIChannelConfig | None = None,
        event_bus: EventBus | None = None,
        **bus_kwargs: Any,
    ) -> None:
        """Force the protocol of the configuration to CAN FD."""
        super().__init__(config, event_bus, **bus_kwargs)
        self.config.protocol = ProtocolType.CAN_FD

    def _build_device_info(self) -> VCIDeviceInfo:
        """Return PCAN FD specific device information."""
        info = super()._build_device_info()
        info.name = "PEAK PCAN-USB FD"
        info.vci_type = VCIType.PCAN_FD
        return info


__all__ = ["PCANFDDriver"]
