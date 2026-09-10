"""File transfer state model."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from ..enums.transfer_enums import FirmwareFileType, TransferDirection, TransferState


@dataclass(slots=True)
class MemorySegment:
    """A contiguous block of firmware data at a physical address."""

    address: int
    data: bytes

    @property
    def size(self) -> int:
        """Return the segment length in bytes."""
        return len(self.data)

    @property
    def end_address(self) -> int:
        """Return the exclusive end address of the segment."""
        return self.address + len(self.data)

    def overlaps(self, other: "MemorySegment") -> bool:
        """Return ``True`` when this segment overlaps *other*."""
        return self.address < other.end_address and other.address < self.end_address

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"0x{self.address:08X}..0x{self.end_address:08X} ({self.size} bytes)"


@dataclass(slots=True)
class TransferFile:
    """One firmware file queued for transfer."""

    path: Path
    file_type: FirmwareFileType = FirmwareFileType.UNKNOWN
    base_address: int | None = None
    segments: list[MemorySegment] = field(default_factory=list)
    enabled: bool = True

    @property
    def total_size(self) -> int:
        """Return the sum of all segment sizes."""
        return sum(seg.size for seg in self.segments)

    @property
    def start_address(self) -> int:
        """Return the lowest address covered by the file."""
        if self.base_address is not None:
            return self.base_address
        return min((seg.address for seg in self.segments), default=0)


@dataclass(slots=True)
class TransferProgress:
    """Live progress of an ongoing transfer."""

    state: TransferState = TransferState.IDLE
    direction: TransferDirection = TransferDirection.DOWNLOAD
    bytes_total: int = 0
    bytes_done: int = 0
    blocks_total: int = 0
    blocks_done: int = 0
    started_at: float = 0.0
    updated_at: float = 0.0
    current_file: str = ""
    message: str = ""

    @property
    def percent(self) -> float:
        """Return completion as a percentage in the range 0..100."""
        if self.bytes_total <= 0:
            return 0.0
        return min(100.0, self.bytes_done * 100.0 / self.bytes_total)

    @property
    def elapsed_s(self) -> float:
        """Return the elapsed transfer time in seconds."""
        if not self.started_at:
            return 0.0
        end = self.updated_at or time.time()
        return max(0.0, end - self.started_at)

    @property
    def speed_bps(self) -> float:
        """Return the average transfer speed in bytes per second."""
        elapsed = self.elapsed_s
        return self.bytes_done / elapsed if elapsed > 0 else 0.0

    @property
    def eta_s(self) -> float:
        """Return the estimated remaining time in seconds."""
        speed = self.speed_bps
        if speed <= 0:
            return 0.0
        return max(0.0, (self.bytes_total - self.bytes_done) / speed)

    def advance(self, block_size: int) -> None:
        """Record that one block of *block_size* bytes has been transferred."""
        self.bytes_done += block_size
        self.blocks_done += 1
        self.updated_at = time.time()


__all__ = ["MemorySegment", "TransferFile", "TransferProgress"]
