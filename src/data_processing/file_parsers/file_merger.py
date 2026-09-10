"""Merge multiple firmware files into one memory map."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ...core.exceptions import ParseError
from ...core.models.file_transfer_model import MemorySegment, TransferFile
from ...core.enums.transfer_enums import FirmwareFileType
from .memory_map import MemoryMap

_logger = logging.getLogger(__name__)


class OverlapPolicy(str, Enum):
    """How to resolve overlapping segments."""

    LAST_WINS = "LAST_WINS"
    FIRST_WINS = "FIRST_WINS"
    REJECT = "REJECT"


@dataclass(slots=True)
class MergeReport:
    """Description of what a merge operation did."""

    files: list[str] = field(default_factory=list)
    segments_in: int = 0
    segments_out: int = 0
    overlaps: list[str] = field(default_factory=list)
    gaps_filled: int = 0
    total_bytes: int = 0

    def summary(self) -> str:
        """Return a one line summary for the log panel."""
        return (
            f"merged {len(self.files)} file(s): {self.segments_in} -> {self.segments_out} "
            f"segments, {self.total_bytes} bytes, {len(self.overlaps)} overlap(s)"
        )


class FileMerger:
    """Combine several firmware files into a single :class:`MemoryMap`.

    Example:
        >>> merger = FileMerger()
        >>> memory, report = merger.merge_segments([
        ...     MemorySegment(0x1000, b"\\x01\\x02"),
        ...     MemorySegment(0x1002, b"\\x03\\x04"),
        ... ])
        >>> len(memory), memory.total_size
        (1, 4)
    """

    def __init__(self, overlap_policy: OverlapPolicy = OverlapPolicy.LAST_WINS) -> None:
        """Create the merger with the given overlap policy."""
        self.overlap_policy = overlap_policy

    def merge_segments(
        self,
        segments: list[MemorySegment],
        fill_gaps: bool = False,
        fill_pattern: int = 0xFF,
        max_gap: int = 0,
    ) -> tuple[MemoryMap, MergeReport]:
        """Merge *segments* into one memory map.

        Raises:
            ParseError: Segments overlap and the policy is ``REJECT``.
        """
        report = MergeReport(segments_in=len(segments))
        memory = MemoryMap(sorted(segments, key=lambda s: s.address))
        for first, second in memory.overlaps():
            message = f"0x{first.address:08X}+{first.size} overlaps 0x{second.address:08X}"
            report.overlaps.append(message)
            if self.overlap_policy is OverlapPolicy.REJECT:
                raise ParseError("overlapping memory segments", {"overlap": message})
        if self.overlap_policy is OverlapPolicy.FIRST_WINS:
            memory.segments = self._keep_first(memory.segments)
        gaps_before = len(memory.gaps())
        memory.merge_adjacent(max_gap=max_gap)
        if fill_gaps:
            memory.fill_gaps(fill_pattern)
            report.gaps_filled = gaps_before
        report.segments_out = len(memory)
        report.total_bytes = memory.total_size
        _logger.info("%s", report.summary())
        return memory, report

    def merge_files(
        self,
        paths: list[str | Path],
        base_addresses: dict[str, int] | None = None,
        fill_gaps: bool = False,
        fill_pattern: int = 0xFF,
    ) -> tuple[MemoryMap, MergeReport]:
        """Parse and merge every file of *paths*.

        Args:
            paths: Firmware files to merge.
            base_addresses: Base address per file name, needed for raw binaries.
            fill_gaps: Fill the holes between segments with *fill_pattern*.
            fill_pattern: Byte used to fill gaps.
        """
        from . import parse_firmware_file

        segments: list[MemorySegment] = []
        names: list[str] = []
        for path in paths:
            file_path = Path(path).expanduser()
            base = (base_addresses or {}).get(file_path.name)
            segments.extend(parse_firmware_file(file_path, base_address=base))
            names.append(file_path.name)
        memory, report = self.merge_segments(segments, fill_gaps, fill_pattern)
        report.files = names
        return memory, report

    def merge_transfer_files(
        self,
        files: list[TransferFile],
        fill_gaps: bool = False,
    ) -> tuple[MemoryMap, MergeReport]:
        """Merge the segments of already parsed :class:`TransferFile` objects."""
        segments: list[MemorySegment] = []
        names: list[str] = []
        for entry in files:
            if not entry.enabled:
                continue
            segments.extend(entry.segments)
            names.append(entry.path.name)
        memory, report = self.merge_segments(segments, fill_gaps)
        report.files = names
        return memory, report

    @staticmethod
    def _keep_first(segments: list[MemorySegment]) -> list[MemorySegment]:
        """Trim later segments so earlier data is preserved on overlap."""
        result: list[MemorySegment] = []
        for segment in segments:
            if result and segment.address < result[-1].end_address:
                offset = result[-1].end_address - segment.address
                if offset >= segment.size:
                    continue
                segment = MemorySegment(result[-1].end_address, segment.data[offset:])
            result.append(segment)
        return result

    @staticmethod
    def describe_file(path: str | Path) -> dict[str, Any]:
        """Return a row for the file selector table of the transfer panel."""
        from . import parse_firmware_file

        file_path = Path(path).expanduser()
        file_type = FirmwareFileType.from_suffix(file_path.suffix)
        try:
            segments = parse_firmware_file(file_path)
            memory = MemoryMap(list(segments))
            address = f"0x{memory.start_address:08X}"
            size = memory.total_size
            error = ""
        except Exception as exc:  # noqa: BLE001 - shown in the table
            address, size, error = "-", 0, str(exc)
        return {
            "name": file_path.name,
            "path": str(file_path),
            "type": file_type.value,
            "address": address,
            "size": size,
            "error": error,
        }


__all__ = ["FileMerger", "MergeReport", "OverlapPolicy"]
