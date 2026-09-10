"""Core Data Models."""
from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class CANFrame:
    timestamp: float
    can_id: int
    dlc: int
    data: bytes
    bus: int = 0

    def __repr__(self) -> str:
        return f"CANFrame(ts={self.timestamp:.6f}, id=0x{self.can_id:X}, dlc={self.dlc})"


class FrameBatch:
    """Batch container for frames."""

    __slots__ = ("frames",)

    def __init__(self, frames: List[CANFrame] | None = None):
        self.frames = frames or []

    def append(self, frame: CANFrame) -> None:
        self.frames.append(frame)

    def __len__(self) -> int:
        return len(self.frames)


@dataclass
class Signal:
    name: str
    start_bit: int
    length: int
    endianness: str = "little"
    scale: float = 1.0
    offset: float = 0.0


@dataclass
class SignalCandidate:
    start_bit: int
    length: int
    endianness: str
    score: float = 0.0
    entropy: float = 0.0
    variance: float = 0.0


@dataclass
class SignalCluster:
    members: List[int]
    score: float = 0.0


@dataclass
class DeviceState:
    name: str
    connected: bool = False
    last_seen: float | None = None


class SystemState:
    """Represents overall system state."""
    def __init__(self):
        self.devices = []
        self.pipeline_running = False