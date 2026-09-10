"""Vector LIN specific driver."""
from __future__ import annotations

from typing import Any

from ....core.enums.protocol_enums import ProtocolType
from ....core.enums.vci_enums import VCICapability
from ....core.models.vci_model import VCIChannelConfig
from .vector_driver import VectorDriver


class VectorLINDriver(VectorDriver):
    """Vector driver for LIN channels.

    LIN uses the ``vector`` python-can backend in LIN mode; master/slave role
    and the schedule table are handled by the LIN protocol handler.
    """

    capabilities = frozenset({VCICapability.LIN, VCICapability.HARDWARE_TIMESTAMPS})

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create the driver in LIN mode."""
        super().__init__(*args, **kwargs)
        self.config.protocol = ProtocolType.LIN

    def configure(self, config: VCIChannelConfig) -> None:
        """Force the protocol to LIN before storing the config."""
        config.protocol = ProtocolType.LIN
        super().configure(config)


__all__ = ["VectorLINDriver"]
