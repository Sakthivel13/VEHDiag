"""Vector CAN specific driver."""
from __future__ import annotations

from ....core.enums.protocol_enums import ProtocolType
from ....core.models.vci_model import VCIChannelConfig
from .vector_driver import VectorDriver


class VectorCANDriver(VectorDriver):
    """Vector driver restricted to classic CAN channels."""

    def configure(self, config: VCIChannelConfig) -> None:
        """Force the protocol to classic CAN before storing the config."""
        config.protocol = ProtocolType.CAN
        super().configure(config)


__all__ = ["VectorCANDriver"]
