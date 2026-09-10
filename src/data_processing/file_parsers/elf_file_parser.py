"""ELF firmware file parser.

The parser prefers :mod:`elftools` (installed as a dependency of ``bincopy``)
and falls back to a minimal built-in reader for the program header table when
pyelftools is unavailable.
"""
from __future__ import annotations

import logging
import struct
from pathlib import Path
from typing import Any

from ...core.exceptions import ParseError
from ...core.models.file_transfer_model import MemorySegment
from .base_file_parser import BaseFileParser

_logger = logging.getLogger(__name__)

#: Magic bytes at the start of every ELF file.
ELF_MAGIC = b"\x7fELF"

#: Program header type for loadable segments.
PT_LOAD = 1


class ElfFileParser(BaseFileParser):
    """Extract the loadable segments of an ELF executable."""

    format_name = "ELF"
    suffixes = (".elf", ".axf", ".out", ".o")

    def parse(self, path: str | Path, **options: Any) -> list[MemorySegment]:
        """Return the ``PT_LOAD`` segments of the ELF file.

        Args:
            path: File to read.
            **options: ``use_physical`` (default ``True``) selects the physical
                rather than the virtual address of each segment.

        Raises:
            ParseError: The file is not a valid ELF image.
        """
        file_path = Path(path).expanduser()
        data = file_path.read_bytes()
        if not data.startswith(ELF_MAGIC):
            raise ParseError(f"{file_path} is not an ELF file")
        segments = self._parse_with_pyelftools(file_path, bool(options.get("use_physical", True)))
        if segments is not None:
            return self._sorted(segments)
        return self._sorted(self._parse_manually(data, bool(options.get("use_physical", True))))

    def _parse_with_pyelftools(self, path: Path, use_physical: bool) -> list[MemorySegment] | None:
        """Parse with :mod:`elftools`, returning ``None`` when unavailable."""
        try:
            from elftools.elf.elffile import ELFFile  # type: ignore[import-not-found]
        except ImportError:
            return None
        segments: list[MemorySegment] = []
        with path.open("rb") as handle:
            elf = ELFFile(handle)
            for segment in elf.iter_segments():
                header = segment.header
                if header["p_type"] != "PT_LOAD" or header["p_filesz"] == 0:
                    continue
                address = header["p_paddr"] if use_physical else header["p_vaddr"]
                segments.append(MemorySegment(int(address), bytes(segment.data())))
        return segments

    def _parse_manually(self, data: bytes, use_physical: bool) -> list[MemorySegment]:
        """Parse the program header table without external dependencies.

        Raises:
            ParseError: The header table is truncated or malformed.
        """
        if len(data) < 52:
            raise ParseError("ELF file shorter than its header")
        is_64bit = data[4] == 2
        little = data[5] == 1
        endian = "<" if little else ">"
        try:
            if is_64bit:
                ph_offset = struct.unpack_from(f"{endian}Q", data, 0x20)[0]
                ph_entry_size = struct.unpack_from(f"{endian}H", data, 0x36)[0]
                ph_count = struct.unpack_from(f"{endian}H", data, 0x38)[0]
            else:
                ph_offset = struct.unpack_from(f"{endian}I", data, 0x1C)[0]
                ph_entry_size = struct.unpack_from(f"{endian}H", data, 0x2A)[0]
                ph_count = struct.unpack_from(f"{endian}H", data, 0x2C)[0]
        except struct.error as exc:
            raise ParseError("truncated ELF header") from exc

        segments: list[MemorySegment] = []
        for index in range(ph_count):
            base = ph_offset + index * ph_entry_size
            if base + ph_entry_size > len(data):
                break
            if is_64bit:
                p_type = struct.unpack_from(f"{endian}I", data, base)[0]
                p_offset = struct.unpack_from(f"{endian}Q", data, base + 0x08)[0]
                p_vaddr = struct.unpack_from(f"{endian}Q", data, base + 0x10)[0]
                p_paddr = struct.unpack_from(f"{endian}Q", data, base + 0x18)[0]
                p_filesz = struct.unpack_from(f"{endian}Q", data, base + 0x20)[0]
            else:
                p_type = struct.unpack_from(f"{endian}I", data, base)[0]
                p_offset = struct.unpack_from(f"{endian}I", data, base + 0x04)[0]
                p_vaddr = struct.unpack_from(f"{endian}I", data, base + 0x08)[0]
                p_paddr = struct.unpack_from(f"{endian}I", data, base + 0x0C)[0]
                p_filesz = struct.unpack_from(f"{endian}I", data, base + 0x10)[0]
            if p_type != PT_LOAD or p_filesz == 0:
                continue
            address = p_paddr if use_physical else p_vaddr
            segments.append(MemorySegment(int(address), data[p_offset : p_offset + p_filesz]))
        return segments

    def validate(self, path: str | Path) -> bool:
        """Return ``True`` when the file starts with the ELF magic."""
        file_path = Path(path).expanduser()
        if not file_path.is_file():
            return False
        with file_path.open("rb") as handle:
            return handle.read(4) == ELF_MAGIC

    def get_metadata(self, path: str | Path) -> dict[str, Any]:
        """Return the base metadata plus the ELF class and machine."""
        metadata = super().get_metadata(path)
        data = Path(path).expanduser().read_bytes()[:20]
        metadata.update(
            {
                "elf_class": "64-bit" if len(data) > 4 and data[4] == 2 else "32-bit",
                "endianness": "little" if len(data) > 5 and data[5] == 1 else "big",
                "machine": struct.unpack_from("<H", data, 0x12)[0] if len(data) >= 20 else 0,
            }
        )
        return metadata


__all__ = ["ElfFileParser", "ELF_MAGIC", "PT_LOAD"]
