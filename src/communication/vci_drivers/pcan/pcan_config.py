"""PCAN specific configuration helpers."""
from __future__ import annotations

from dataclasses import dataclass

from ....core.models.vci_model import VCIChannelConfig
from .pcan_basic_wrapper import PCAN_BAUD_CODES, PCAN_USBBUS


@dataclass(slots=True)
class PCANConfig:
    """Configuration of one PCAN channel.

    Attributes:
        channel_index: 1-based USB channel index.
        bitrate: Arbitration bitrate in bit/s.
        data_bitrate: FD data phase bitrate in bit/s.
        fd_mode: Open the channel in CAN FD mode.
        listen_only: Do not acknowledge frames.
        message_filter_open: Accept every identifier.
    """

    channel_index: int = 1
    bitrate: int = 500_000
    data_bitrate: int = 2_000_000
    fd_mode: bool = False
    listen_only: bool = False
    message_filter_open: bool = True

    @property
    def handle(self) -> int:
        """Return the numeric PCAN channel handle."""
        return PCAN_USBBUS.get(self.channel_index, PCAN_USBBUS[1])

    @property
    def handle_name(self) -> str:
        """Return the symbolic handle name, e.g. ``"PCAN_USBBUS1"``."""
        return f"PCAN_USBBUS{self.channel_index}"

    @property
    def baud_code(self) -> int:
        """Return the SJA1000 style bit timing code for :attr:`bitrate`."""
        return PCAN_BAUD_CODES.get(self.bitrate, PCAN_BAUD_CODES[500_000])

    def fd_bitrate_string(self) -> str:
        """Return the PCAN FD bit rate string expected by the driver."""
        return (
            "f_clock_mhz=80, nom_brp=2, nom_tseg1=63, nom_tseg2=16, nom_sjw=16, "
            "data_brp=2, data_tseg1=15, data_tseg2=4, data_sjw=4"
        )

    def to_channel_config(self) -> VCIChannelConfig:
        """Convert into the generic :class:`VCIChannelConfig`."""
        from ....core.enums.protocol_enums import ProtocolType

        return VCIChannelConfig(
            channel=self.handle_name,
            protocol=ProtocolType.CAN_FD if self.fd_mode else ProtocolType.CAN,
            bitrate=self.bitrate,
            data_bitrate=self.data_bitrate,
            listen_only=self.listen_only,
        )


__all__ = ["PCANConfig"]
