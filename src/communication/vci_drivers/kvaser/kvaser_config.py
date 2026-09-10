"""Kvaser configuration helpers."""
from __future__ import annotations

from dataclasses import dataclass

from ....core.enums.protocol_enums import ProtocolType
from ....core.models.vci_model import VCIChannelConfig
from .kvaser_canlib_wrapper import bitrate_constant


@dataclass(slots=True)
class KvaserConfig:
    """Configuration of one Kvaser channel.

    Attributes:
        channel_index: Zero based CANlib channel number.
        bitrate: Arbitration bitrate in bit/s.
        data_bitrate: FD data phase bitrate in bit/s.
        fd_mode: Open the channel in CAN FD mode.
        exclusive: Request exclusive access to the channel.
        accept_virtual: Allow CANlib virtual channels to be opened.
        silent: Open in listen-only mode.
    """

    channel_index: int = 0
    bitrate: int = 500_000
    data_bitrate: int = 2_000_000
    fd_mode: bool = False
    exclusive: bool = True
    accept_virtual: bool = False
    silent: bool = False

    @property
    def bitrate_code(self) -> int:
        """Return the ``canBITRATE_*`` constant for :attr:`bitrate`."""
        return bitrate_constant(self.bitrate)

    def to_channel_config(self) -> VCIChannelConfig:
        """Convert into the generic :class:`VCIChannelConfig`."""
        return VCIChannelConfig(
            channel=self.channel_index,
            protocol=ProtocolType.CAN_FD if self.fd_mode else ProtocolType.CAN,
            bitrate=self.bitrate,
            data_bitrate=self.data_bitrate,
            listen_only=self.silent,
            extra={"accept_virtual": self.accept_virtual, "exclusive": self.exclusive},
        )


__all__ = ["KvaserConfig"]
