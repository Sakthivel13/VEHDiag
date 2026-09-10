"""Vector FlexRay specific driver."""
from __future__ import annotations

from typing import Any

from ....core.enums.protocol_enums import ProtocolType
from ....core.enums.vci_enums import VCICapability
from ....core.exceptions import UnsupportedCapabilityError
from ....core.models.vci_model import VCIChannelConfig
from .vector_driver import VectorDriver


class VectorFlexRayDriver(VectorDriver):
    """Vector driver for FlexRay channels.

    FlexRay requires a cluster configuration (FIBEX) that is applied by the
    FlexRay protocol handler before the channel can start communicating.
    """

    capabilities = frozenset({VCICapability.FLEXRAY, VCICapability.HARDWARE_TIMESTAMPS})

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create the driver in FlexRay mode."""
        super().__init__(*args, **kwargs)
        self.config.protocol = ProtocolType.FLEXRAY
        self.cluster_config: dict[str, Any] = {}

    def configure(self, config: VCIChannelConfig) -> None:
        """Force the protocol to FlexRay before storing the config."""
        config.protocol = ProtocolType.FLEXRAY
        super().configure(config)

    def apply_cluster_config(self, cluster: dict[str, Any]) -> None:
        """Store the FlexRay cluster parameters used when starting the channel.

        Raises:
            UnsupportedCapabilityError: The cluster description is incomplete.
        """
        required = {"baudrate", "macro_per_cycle", "static_slots"}
        missing = required - set(cluster)
        if missing:
            raise UnsupportedCapabilityError(
                "incomplete FlexRay cluster configuration", {"missing": sorted(missing)}
            )
        self.cluster_config = dict(cluster)


__all__ = ["VectorFlexRayDriver"]
