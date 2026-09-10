"""FlexRay timing and synchronisation parameters."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FlexRayTiming:
    """Global timing parameters of a FlexRay cluster.

    Attributes:
        macrotick_us: Duration of one macrotick in microseconds.
        macro_per_cycle: Number of macroticks in one communication cycle.
        static_slots: Number of slots in the static segment.
        static_slot_macroticks: Length of one static slot in macroticks.
        minislots: Number of minislots in the dynamic segment.
        minislot_macroticks: Length of one minislot in macroticks.
        network_idle_macroticks: Length of the network idle time.
        bitrate: Channel bitrate in bit/s.
    """

    macrotick_us: float = 1.0
    macro_per_cycle: int = 5000
    static_slots: int = 60
    static_slot_macroticks: int = 40
    minislots: int = 120
    minislot_macroticks: int = 10
    network_idle_macroticks: int = 100
    bitrate: int = 10_000_000

    @property
    def cycle_time_us(self) -> float:
        """Return the duration of one communication cycle in microseconds."""
        return self.macro_per_cycle * self.macrotick_us

    @property
    def static_segment_macroticks(self) -> int:
        """Return the length of the static segment in macroticks."""
        return self.static_slots * self.static_slot_macroticks

    @property
    def dynamic_segment_macroticks(self) -> int:
        """Return the length of the dynamic segment in macroticks."""
        return self.minislots * self.minislot_macroticks

    def validate(self) -> bool:
        """Return ``True`` when the segments fit into the cycle."""
        total = (
            self.static_segment_macroticks
            + self.dynamic_segment_macroticks
            + self.network_idle_macroticks
        )
        return total <= self.macro_per_cycle

    def slot_start_us(self, slot_id: int) -> float:
        """Return the start time of a static *slot_id* inside the cycle."""
        return (slot_id - 1) * self.static_slot_macroticks * self.macrotick_us


__all__ = ["FlexRayTiming"]
