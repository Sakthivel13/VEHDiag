"""Base class for firmware file parsers."""
from __future__ import annotations

import logging
from abc import abstractmethod
from pathlib import Path
from typing import Any

from ...core.exceptions import EmptyFileError, ParseError
from ...core.interfaces.i_file_parser import IFileParser
from ...core.models.file_transfer_model import MemorySegment
from .memory_map import MemoryMap

_logger = logging.getLogger(__name__)


class BaseFileParser(IFileParser):
    """Shared behaviour for all firmware parsers.

    Subclasses implement :meth:`parse` and usually override :meth:`validate`
    and :meth:`get_metadata`.
    """

    #: Human readable name of the format.
    format_name: str = "unknown"

    def validate(self, path: str | Path) -> bool:
        """Return ``True`` when the suffix matches and the file is readable."""
        file_path = Path(path).expanduser()
        return file_path.is_file() and self.supports(file_path)

    def get_metadata(self, path: str | Path) -> dict[str, Any]:
        """Return descriptive metadata about the file."""
        file_path = Path(path).expanduser()
        segments = self.parse(file_path)
        memory = MemoryMap(list(segments))
        return {
            "path": str(file_path),
            "name": file_path.name,
            "format": self.format_name,
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
            "segments": len(segments),
            "data_size": memory.total_size,
            "start_address": memory.start_address,
            "end_address": memory.end_address,
            "gaps": len(memory.gaps()),
        }

    def to_memory_map(self, path: str | Path, **options: Any) -> MemoryMap:
        """Parse *path* and return the result as a :class:`MemoryMap`."""
        return MemoryMap(list(self.parse(path, **options)))

    def _read_lines(self, path: str | Path) -> list[str]:
        """Read a text based firmware file line by line.

        Raises:
            ParseError: The file cannot be read as text.
            EmptyFileError: The file contains no records.
        """
        file_path = Path(path).expanduser()
        try:
            text = file_path.read_text(encoding="ascii", errors="ignore")
        except OSError as exc:
            raise ParseError(f"could not read {file_path}", {"cause": str(exc)}) from exc
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise EmptyFileError(f"{file_path} contains no records")
        return lines

    @staticmethod
    def _sorted(segments: list[MemorySegment]) -> list[MemorySegment]:
        """Return *segments* sorted by address."""
        return sorted(segments, key=lambda s: s.address)

    @abstractmethod
    def parse(self, path: str | Path, **options: Any) -> list[MemorySegment]:
        """Parse *path* and return its memory segments."""


__all__ = ["BaseFileParser"]
