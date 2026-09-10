"""FlexRay cluster configuration."""
from __future__ import annotations

from dataclasses import dataclass, field

from .flexray_frame import FlexRayChannel
from .flexray_timing import FlexRayTiming


@dataclass(slots=True)
class FlexRayNode:
    """One controller in the FlexRay cluster."""

    name: str
    key_slot: int = 0
    channels: FlexRayChannel = FlexRayChannel.AB
    is_sync_node: bool = False
    is_startup_node: bool = False


@dataclass(slots=True)
class FlexRayCluster:
    """Description of a FlexRay cluster.

    Attributes:
        name: Cluster name from the FIBEX description.
        timing: Global timing parameters.
        channels: Channels used by the cluster.
        nodes: Controllers participating in the cluster.
        cold_start_attempts: Number of coldstart attempts allowed.
        wakeup_channel: Channel used to transmit the wake-up pattern.
    """

    name: str = "cluster"
    timing: FlexRayTiming = field(default_factory=FlexRayTiming)
    channels: FlexRayChannel = FlexRayChannel.AB
    nodes: list[FlexRayNode] = field(default_factory=list)
    cold_start_attempts: int = 8
    wakeup_channel: FlexRayChannel = FlexRayChannel.A

    @property
    def sync_nodes(self) -> list[FlexRayNode]:
        """Return the nodes that transmit sync frames."""
        return [node for node in self.nodes if node.is_sync_node]

    @property
    def startup_nodes(self) -> list[FlexRayNode]:
        """Return the nodes capable of starting the cluster."""
        return [node for node in self.nodes if node.is_startup_node]

    def validate(self) -> list[str]:
        """Return a list of configuration problems (empty when valid)."""
        problems: list[str] = []
        if not self.timing.validate():
            problems.append("the segments do not fit into the communication cycle")
        if len(self.sync_nodes) < 2:
            problems.append("a FlexRay cluster needs at least two sync nodes")
        if not self.startup_nodes:
            problems.append("no coldstart capable node configured")
        slots = [node.key_slot for node in self.nodes if node.key_slot]
        if len(slots) != len(set(slots)):
            problems.append("duplicate key slots detected")
        return problems

    def to_dict(self) -> dict[str, object]:
        """Return the mapping consumed by the driver configuration."""
        return {
            "name": self.name,
            "channels": self.channels.value,
            "macro_per_cycle": self.timing.macro_per_cycle,
            "static_slots": self.timing.static_slots,
            "baudrate": self.timing.bitrate,
            "cold_start_attempts": self.cold_start_attempts,
            "nodes": [node.name for node in self.nodes],
        }


__all__ = ["FlexRayCluster", "FlexRayNode"]
