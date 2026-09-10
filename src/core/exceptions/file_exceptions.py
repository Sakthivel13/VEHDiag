"""File handling exception hierarchy."""
from __future__ import annotations

from .communication_exceptions import VDPError


class FileError(VDPError):
    """Base class for file parsing and validation failures."""


class ParseError(FileError):
    """Raised when a firmware or configuration file cannot be parsed."""


class ChecksumMismatchError(FileError):
    """Raised when a computed checksum does not match the expected value."""


class FormatNotSupportedError(FileError):
    """Raised when the file format cannot be handled by any parser."""


class EmptyFileError(FileError):
    """Raised when a file contains no usable data records."""


__all__ = [
    "FileError",
    "ParseError",
    "ChecksumMismatchError",
    "FormatNotSupportedError",
    "EmptyFileError",
]
