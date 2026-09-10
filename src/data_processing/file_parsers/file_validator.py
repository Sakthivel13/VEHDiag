"""Firmware file integrity validation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...core.exceptions import ChecksumMismatchError
from ...core.models.file_transfer_model import MemorySegment
from ...utils.checksum_calculator import ALGORITHMS, calculate, crc32, md5, sha256

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ValidationResult:
    """Outcome of a file or segment validation."""

    valid: bool = True
    checksums: dict[str, Any] = field(default_factory=dict)
    size: int = 0
    problems: list[str] = field(default_factory=list)

    def add_problem(self, message: str) -> None:
        """Record a problem and mark the result invalid."""
        self.problems.append(message)
        self.valid = False

    def summary(self) -> str:
        """Return a one line summary for the log panel."""
        if self.valid:
            return f"validation passed ({self.size} bytes)"
        return "validation failed: " + "; ".join(self.problems)


class FileValidator:
    """Compute and verify checksums of firmware files and segments.

    Example:
        >>> validator = FileValidator()
        >>> result = validator.validate_bytes(b"12345", expected={"CRC32": 0xCBF53A1C})
        >>> result.valid
        True
    """

    def compute(self, data: bytes, algorithms: tuple[str, ...] = ("CRC32", "MD5", "SHA256")) -> dict[str, Any]:
        """Return the requested checksums of *data*."""
        return {name: calculate(name, data) for name in algorithms if name.upper() in ALGORITHMS}

    def validate_bytes(
        self,
        data: bytes,
        expected: dict[str, Any] | None = None,
        expected_size: int | None = None,
    ) -> ValidationResult:
        """Validate raw *data* against expected checksums and size."""
        result = ValidationResult(size=len(data))
        result.checksums = self.compute(data)
        if expected_size is not None and len(data) != expected_size:
            result.add_problem(f"size mismatch: expected {expected_size}, got {len(data)}")
        for name, value in (expected or {}).items():
            actual = calculate(name, data)
            if isinstance(actual, str) and isinstance(value, str):
                matches = actual.lower() == value.lower().strip()
            else:
                reference = int(value, 16) if isinstance(value, str) else int(value)
                matches = actual == reference
            if not matches:
                result.add_problem(f"{name} mismatch: expected {value}, got {actual}")
        return result

    def validate_file(
        self,
        path: str | Path,
        expected: dict[str, Any] | None = None,
        expected_size: int | None = None,
    ) -> ValidationResult:
        """Validate the raw content of a file on disk."""
        file_path = Path(path).expanduser()
        if not file_path.is_file():
            result = ValidationResult(valid=False)
            result.add_problem(f"file not found: {file_path}")
            return result
        return self.validate_bytes(file_path.read_bytes(), expected, expected_size)

    def validate_segments(self, segments: list[MemorySegment]) -> ValidationResult:
        """Check a segment list for overlaps and empty entries."""
        from .memory_map import MemoryMap

        memory = MemoryMap(list(segments))
        result = ValidationResult(size=memory.total_size)
        for segment in segments:
            if segment.size == 0:
                result.add_problem(f"empty segment at 0x{segment.address:08X}")
        for first, second in memory.overlaps():
            result.add_problem(
                f"segments overlap at 0x{first.address:08X} and 0x{second.address:08X}"
            )
        _start, flat = memory.to_flat()
        result.checksums = self.compute(flat)
        return result

    def verify_or_raise(self, data: bytes, algorithm: str, expected: int | str) -> None:
        """Verify one checksum, raising when it does not match.

        Raises:
            ChecksumMismatchError: The computed digest differs from *expected*.
        """
        actual = calculate(algorithm, data)
        reference = expected
        if isinstance(actual, int) and isinstance(expected, str):
            reference = int(expected, 16)
        if actual != reference:
            raise ChecksumMismatchError(
                f"{algorithm} checksum mismatch",
                {"expected": str(expected), "actual": str(actual)},
            )

    @staticmethod
    def quick_crc(data: bytes) -> str:
        """Return the CRC-32 of *data* formatted as ``0xXXXXXXXX``."""
        return f"0x{crc32(data):08X}"


__all__ = ["FileValidator", "ValidationResult"]
