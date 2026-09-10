"""Intrepid Control Systems configuration helpers."""
from __future__ import annotations

from dataclasses import dataclass

from ....core.enums.protocol_enums import ProtocolType
from ....core.models.vci_model import VCIChannelConfig

#: Typical network indices of the neoVI family.
NETWORK_IDS: dict[str, int] = {"HSCAN": 1, "MSCAN": 2, "SWCAN": 3, "LSFTCAN": 4, "LIN": 5}


@dataclass(slots=True)
class IntrepidCSConfig:
    """Configuration of one neoVI network.

    Attributes:
        network: Logical network name, see :data:`NETWORK_IDS`.
        serial: Device serial number, empty for the first device found.
        bitrate: Arbitration bitrate in bit/s.
        data_bitrate: FD data phase bitrate in bit/s.
        fd_mode: Open the network in CAN FD mode.
    """

    network: str = "HSCAN"
    serial: str = ""
    bitrate: int = 500_000
    data_bitrate: int = 2_000_000
    fd_mode: bool = False

    @property
    def network_id(self) -> int:
        """Return the numeric network identifier of :attr:`network`."""
        return NETWORK_IDS.get(self.network.upper(), 1)

    def to_channel_config(self) -> VCIChannelConfig:
        """Convert into the generic :class:`VCIChannelConfig`."""
        return VCIChannelConfig(
            channel=self.network_id,
            protocol=ProtocolType.CAN_FD if self.fd_mode else ProtocolType.CAN,
            bitrate=self.bitrate,
            data_bitrate=self.data_bitrate,
            extra={"serial": self.serial, "network": self.network},
        )


__all__ = ["IntrepidCSConfig", "NETWORK_IDS"]
