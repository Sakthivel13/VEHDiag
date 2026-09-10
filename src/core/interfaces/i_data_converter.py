"""Abstract data converter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..enums.data_format_enums import DataFormat


class IDataConverter(ABC):
    """Contract implemented by every raw-bytes to representation converter."""

    @abstractmethod
    def convert(self, data: bytes, **options: Any) -> Any:
        """Convert *data* into the target representation.

        Args:
            data: Raw bytes to interpret.
            **options: Converter specific options such as ``byte_order``.
        """

    @abstractmethod
    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Convert a representation back into raw bytes.

        Raises:
            ValueError: *value* cannot be represented as bytes.
        """

    @abstractmethod
    def get_supported_formats(self) -> list[DataFormat]:
        """Return the formats this converter can produce."""

    @abstractmethod
    def validate_input(self, data: bytes, **options: Any) -> None:
        """Validate that *data* can be converted.

        Raises:
            ValueError: The input is unsuitable (wrong length, bad chars...).
        """


__all__ = ["IDataConverter"]
