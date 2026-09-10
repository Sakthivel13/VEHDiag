"""Firmware and calibration file parsers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ...core.enums.transfer_enums import FirmwareFileType
from ...core.exceptions import FormatNotSupportedError
from ...core.models.file_transfer_model import MemorySegment
from .a2l_file_parser import A2LDatabase, A2LFileParser
from .base_file_parser import BaseFileParser
from .bin_file_parser import BinFileParser
from .elf_file_parser import ElfFileParser
from .file_merger import FileMerger, MergeReport, OverlapPolicy
from .file_validator import FileValidator, ValidationResult
from .hex_file_parser import HexFileParser
from .memory_map import MemoryGap, MemoryMap
from .srec_mot_file_parser import SRecordParser

#: Parser instances keyed by firmware file type.
PARSERS: dict[FirmwareFileType, BaseFileParser] = {
    FirmwareFileType.INTEL_HEX: HexFileParser(),
    FirmwareFileType.SREC: SRecordParser(),
    FirmwareFileType.BINARY: BinFileParser(),
    FirmwareFileType.ELF: ElfFileParser(),
}


def get_parser(path: str | Path) -> BaseFileParser:
    """Return the parser matching the suffix of *path*.

    Raises:
        FormatNotSupportedError: No parser handles the suffix.
    """
    file_type = FirmwareFileType.from_suffix(Path(path).suffix)
    parser = PARSERS.get(file_type)
    if parser is None:
        raise FormatNotSupportedError(
            f"no parser for {Path(path).suffix!r}",
            {"supported": sorted(s for p in PARSERS.values() for s in p.suffixes)},
        )
    return parser


def parse_firmware_file(path: str | Path, **options: Any) -> list[MemorySegment]:
    """Parse any supported firmware file into memory segments.

    Args:
        path: File to parse.
        **options: Forwarded to the parser; raw binaries accept
            ``base_address``.

    Raises:
        FormatNotSupportedError: The file type is unknown.
    """
    cleaned = {k: v for k, v in options.items() if v is not None}
    return get_parser(path).parse(path, **cleaned)


def describe_firmware_file(path: str | Path) -> dict[str, Any]:
    """Return metadata about any supported firmware file."""
    return get_parser(path).get_metadata(path)


__all__ = [
    "A2LDatabase",
    "A2LFileParser",
    "BaseFileParser",
    "BinFileParser",
    "ElfFileParser",
    "FileMerger",
    "FileValidator",
    "HexFileParser",
    "MemoryGap",
    "MemoryMap",
    "MergeReport",
    "OverlapPolicy",
    "PARSERS",
    "SRecordParser",
    "ValidationResult",
    "describe_firmware_file",
    "get_parser",
    "parse_firmware_file",
]
