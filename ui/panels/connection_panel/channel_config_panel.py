"""Channel configuration helpers."""
from __future__ import annotations

from typing import Any

from src.core.enums.protocol_enums import ProtocolType
from src.core.models.vci_model import VCIChannelConfig


def build_channel_config(
   channel: int | str,
   protocol: ProtocolType,
   bitrate: int = 500_000,
   data_bitrate: int = 2_000_000,
   **extra: Any,
) -> VCIChannelConfig:
   """Return a :class:`VCIChannelConfig` for the panel inputs.

   Example:
       >>> config = build_channel_config(0, ProtocolType.CAN)
       >>> config.bitrate
       500000
   """
   return VCIChannelConfig(
       channel=channel,
       protocol=protocol,
       bitrate=bitrate,
       data_bitrate=data_bitrate,
       extra=dict(extra),
   )


def channel_labels(count: int = 8) -> list[str]:
   """Return the channel labels shown in the drop-down."""
   return [str(index) for index in range(count)]
