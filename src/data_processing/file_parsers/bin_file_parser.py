"""Raw binary firmware file parser."""
from __future__ import annotations

import logging
import mmap
from pathlib import Path
from typing import Any, Iterator

from ...core.exceptions import EmptyFileError, ParseError
from ...core.models.file_transfer_model import MemorySegment
from .base_file_parser import BaseFileParser

_logger = logging.getLogger(__name__)

#: Files larger than this are read through a memory map instead of into RAM.
MMAP_THRESHOLD = 4 * 1024 * 1024


class BinFileParser(BaseFileParser):
    """Read a raw binary image placed at a configurable base address.

    Example:
        >>> import tempfile, pathlib
        >>> path = pathlib.Path(tempfile.mkstemp(suffix=".bin")[1])
        >>> _ = path.write_bytes(bytes(range(8)))
        >>> segment = BinFileParser().parse(path, base_address=0x8000)[0]
        >>> hex(segment.address), segment.size
        ('0x8000', 8)
    """

    format_name = "Raw binary"
    suffixes = (".bin", ".raw", ".img", ".dat")

    def parse(self, path: str | Path, **options: Any) -> list[MemorySegment]:
        """Read the file into one (or several) memory segments.

        Args:
            path: File to read.
            **options: ``base_address`` (default 0), ``block_size`` to split
                the image, ``skip`` bytes at the start and ``length`` to read.

        Raises:
            ParseError: The file cannot be read.
            EmptyFileError: The file is empty.
        """
        file_path = Path(path).expanduser()
        try:
            size = file_path.stat().st_size
        except OSError as exc:
            raise ParseError(f"could not stat {file_path}", {"cause": str(exc)}) from exc
        if size == 0:
            raise EmptyFileError(f"{file_path} is empty")

        base = int(options.get("base_address") or 0)
        skip = int(options.get("skip", 0))
        length = int(options.get("length", 0)) or (size - skip)
        block_size = int(options.get("block_size", 0))

        data = self._read(file_path, skip, length)
        if block_size <= 0:
            return [MemorySegment(base, data)]
        return [
            MemorySegment(base + offset, data[offset : offset + block_size])
            for offset in range(0, len(data), block_size)
        ]

    def _read(self, path: Path, skip: int, length: int) -> bytes:
        """Read *length* bytes from *path*, memory mapping large files."""
        with path.open("rb") as handle:
            if path.stat().st_size >= MMAP_THRESHOLD:
                with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
                    return bytes(mapped[skip : skip + length])
            handle.seek(skip)
            return handle.read(length)

    def validate(self, path: str | Path) -> bool:
        """Any readable non-empty file is a valid raw binary."""
        file_path = Path(path).expanduser()
        return file_path.is_file() and file_path.stat().st_size > 0

    def iter_blocks(self, path: str | Path, block_size: int = 4096) -> Iterator[bytes]:
        """Stream the file in *block_size* chunks without loading it fully."""
        with Path(path).expanduser().open("rb") as handle:
            while True:
                chunk = handle.read(block_size)
                if not chunk:
                    return
                yield chunk

    def get_metadata(self, path: str | Path) -> dict[str, Any]:
        """Return the file size plus a checksum of the content."""
        from ...utils.checksum_calculator import crc32

        file_path = Path(path).expanduser()
        data = file_path.read_bytes()
        return {
            "path": str(file_path),
            "name": file_path.name,
            "format": self.format_name,
            "file_size": len(data),
            "segments": 1,
            "data_size": len(data),
            "crc32": f"0x{crc32(data):08X}",
        }

    def write(self, path: str | Path, segments: list[MemorySegment], fill: int = 0xFF) -> Path:
        """Write *segments* into a flat binary image."""
        from .memory_map import MemoryMap

        memory = MemoryMap(list(segments))
        _start, data = memory.to_flat(fill)
        target = Path(path).expanduser()
        target.write_bytes(data)
        return target


__all__ = ["BinFileParser", "MMAP_THRESHOLD"]
