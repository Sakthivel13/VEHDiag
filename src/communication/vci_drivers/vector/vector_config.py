"""Vector channel configuration helpers."""
from __future__ import annotations

from dataclasses import dataclass, field

from ....core.enums.protocol_enums import ProtocolType
from ....core.models.vci_model import VCIChannelConfig
from .vector_xl_wrapper import channel_mask


@dataclass(slots=True)
class VectorConfig:
    """Configuration of one Vector channel.

    Attributes:
        app_name: Application name registered in Vector Hardware Config.
        channel_index: Zero based channel index inside the application.
        bitrate: Arbitration bitrate in bit/s.
        data_bitrate: FD data phase bitrate in bit/s.
        fd_mode: Open the channel in CAN FD mode.
        rx_queue_size: Size of the driver receive queue.
        sample_point: Desired sample point as a fraction.
        serial_number: Optional hardware serial to bind to a specific device.
    """

    app_name: str = "VehicleDiagnosticsPlatform"
    channel_index: int = 0
    bitrate: int = 500_000
    data_bitrate: int = 2_000_000
    fd_mode: bool = False
    rx_queue_size: int = 16384
    sample_point: float = 0.8
    serial_number: str = ""
    extra: dict[str, object] = field(default_factory=dict)

    @property
    def mask(self) -> int:
        """Return the XL channel mask for :attr:`channel_index`."""
        return channel_mask(self.channel_index)

    def to_channel_config(self) -> VCIChannelConfig:
        """Convert into the generic :class:`VCIChannelConfig`."""
        return VCIChannelConfig(
            channel=self.channel_index,
            protocol=ProtocolType.CAN_FD if self.fd_mode else ProtocolType.CAN,
            bitrate=self.bitrate,
            data_bitrate=self.data_bitrate,
            sample_point=self.sample_point,
            extra={
                "app_name": self.app_name,
                "rx_queue_size": self.rx_queue_size,
                "serial": self.serial_number,
                **self.extra,
            },
        )


__all__ = ["VectorConfig"]
