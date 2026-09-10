"""Memory map and segment operations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator

from ...core.models.file_transfer_model import MemorySegment


@dataclass(slots=True)
class MemoryGap:
    """An unmapped region between two segments."""

    start: int
    end: int

    @property
    def size(self) -> int:
        """Return the gap size in bytes."""
        return max(0, self.end - self.start)

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"gap 0x{self.start:08X}..0x{self.end:08X} ({self.size} bytes)"


@dataclass(slots=True)
class MemoryMap:
    """An ordered collection of :class:`MemorySegment` objects.

    Example:
        >>> memory = MemoryMap()
        >>> memory.add(MemorySegment(0x1000, b"\\x01\\x02"))
        >>> memory.add(MemorySegment(0x1002, b"\\x03"))
        >>> memory.merge_adjacent()
        >>> len(memory), memory.segments[0].size
        (1, 3)
    """

    segments: list[MemorySegment] = field(default_factory=list)

    # -- construction -------------------------------------------------------
    def add(self, segment: MemorySegment) -> None:
        """Insert *segment* keeping the list sorted by address."""
        self.segments.append(segment)
        self.segments.sort(key=lambda s: s.address)

    def extend(self, segments: Iterable[MemorySegment]) -> None:
        """Insert every segment of *segments*."""
        for segment in segments:
            self.add(segment)

    def clear(self) -> None:
        """Remove every segment."""
        self.segments.clear()

    # -- queries --------------------------------------------------------------
    @property
    def start_address(self) -> int:
        """Return the lowest mapped address."""
        return min((s.address for s in self.segments), default=0)

    @property
    def end_address(self) -> int:
        """Return the exclusive highest mapped address."""
        return max((s.end_address for s in self.segments), default=0)

    @property
    def total_size(self) -> int:
        """Return the number of mapped bytes."""
        return sum(s.size for s in self.segments)

    @property
    def span(self) -> int:
        """Return the distance between the first and the last address."""
        return max(0, self.end_address - self.start_address)

    def gaps(self) -> list[MemoryGap]:
        """Return the unmapped regions between the segments."""
        result: list[MemoryGap] = []
        for previous, current in zip(self.segments, self.segments[1:]):
            if current.address > previous.end_address:
                result.append(MemoryGap(previous.end_address, current.address))
        return result

    def overlaps(self) -> list[tuple[MemorySegment, MemorySegment]]:
        """Return every pair of overlapping segments."""
        return [
            (a, b)
            for a, b in zip(self.segments, self.segments[1:])
            if a.overlaps(b)
        ]

    def read(self, address: int, size: int, fill: int = 0xFF) -> bytes:
        """Return *size* bytes starting at *address*, filling gaps with *fill*."""
        out = bytearray([fill & 0xFF]) * size
        for segment in self.segments:
            start = max(address, segment.address)
            end = min(address + size, segment.end_address)
            if start >= end:
                continue
            out[start - address : end - address] = segment.data[
                start - segment.address : end - segment.address
            ]
        return bytes(out)

    # -- transformations ----------------------------------------------------------
    def merge_adjacent(self, max_gap: int = 0) -> None:
        """Merge segments separated by at most *max_gap* bytes."""
        if not self.segments:
            return
        self.segments.sort(key=lambda s: s.address)
        merged: list[MemorySegment] = [
            MemorySegment(self.segments[0].address, bytes(self.segments[0].data))
        ]
        for segment in self.segments[1:]:
            last = merged[-1]
            gap = segment.address - last.end_address
            if 0 <= gap <= max_gap:
                data = bytearray(last.data)
                if gap:
                    data.extend(b"\xff" * gap)
                data.extend(segment.data)
                merged[-1] = MemorySegment(last.address, bytes(data))
            elif gap < 0:  # overlapping: later data wins
                data = bytearray(last.data)
                offset = segment.address - last.address
                data[offset : offset + segment.size] = segment.data
                merged[-1] = MemorySegment(last.address, bytes(data))
            else:
                merged.append(MemorySegment(segment.address, bytes(segment.data)))
        self.segments = merged

    def fill_gaps(self, pattern: int = 0xFF, max_gap: int | None = None) -> None:
        """Fill the gaps between segments with *pattern*."""
        limit = max_gap if max_gap is not None else self.span
        self.merge_adjacent(max_gap=limit if limit > 0 else 0)
        if pattern != 0xFF:
            for index, segment in enumerate(self.segments):
                self.segments[index] = MemorySegment(
                    segment.address, segment.data.replace(b"\xff", bytes([pattern & 0xFF]))
                )

    def split(self, block_size: int) -> list[MemorySegment]:
        """Return the segments split into blocks of at most *block_size*."""
        blocks: list[MemorySegment] = []
        for segment in self.segments:
            for offset in range(0, segment.size, block_size):
                blocks.append(
                    MemorySegment(
                        segment.address + offset, segment.data[offset : offset + block_size]
                    )
                )
        return blocks

    def to_flat(self, fill: int = 0xFF) -> tuple[int, bytes]:
        """Return ``(start_address, contiguous_bytes)`` for the whole map."""
        if not self.segments:
            return 0, b""
        start = self.start_address
        return start, self.read(start, self.span, fill)

    # -- presentation ------------------------------------------------------------------
    def layout_rows(self) -> list[dict[str, object]]:
        """Return rows for the memory layout table in the transfer panel."""
        rows: list[dict[str, object]] = []
        for index, segment in enumerate(self.segments, start=1):
            rows.append(
                {
                    "index": index,
                    "start": f"0x{segment.address:08X}",
                    "end": f"0x{segment.end_address:08X}",
                    "size": segment.size,
                    "size_text": f"{segment.size / 1024:.1f} KB",
                }
            )
        return rows

    def __iter__(self) -> Iterator[MemorySegment]:  # noqa: D105 - trivial
        return iter(self.segments)

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.segments)

    def __str__(self) -> str:  # noqa: D105 - trivial
        return (
            f"MemoryMap {len(self.segments)} segments, {self.total_size} bytes, "
            f"0x{self.start_address:08X}..0x{self.end_address:08X}"
        )


__all__ = ["MemoryMap", "MemoryGap", "MemorySegment"]
