"""Abstract firmware file parser interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..models.file_transfer_model import MemorySegment


class IFileParser(ABC):
    """Contract implemented by every firmware/flash file parser."""

    #: Filename suffixes handled by the parser, e.g. ``(".hex", ".ihex")``.
    suffixes: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, path: str | Path, **options: Any) -> list[MemorySegment]:
        """Parse *path* and return its memory segments sorted by address.

        Raises:
            ParseError: The file is malformed.
            ChecksumMismatchError: A record checksum failed.
        """

    @abstractmethod
    def validate(self, path: str | Path) -> bool:
        """Return ``True`` when *path* looks like a file this parser handles."""

    @abstractmethod
    def get_metadata(self, path: str | Path) -> dict[str, Any]:
        """Return descriptive metadata (record count, entry point, size...)."""

    def get_memory_segments(self, path: str | Path, **options: Any) -> list[MemorySegment]:
        """Alias of :meth:`parse` kept for API symmetry."""
        return self.parse(path, **options)

    def supports(self, path: str | Path) -> bool:
        """Return ``True`` when the suffix of *path* is handled by the parser."""
        return Path(path).suffix.lower() in self.suffixes


__all__ = ["IFileParser"]
