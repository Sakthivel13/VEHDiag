"""Intel (little endian) byte and bit order handling."""
from __future__ import annotations

from typing import Any

from ...core.enums.data_format_enums import ByteOrder, DataFormat
from ...core.interfaces.i_data_converter import IDataConverter
from ...utils.byte_utils import extract_bits


class IntelConverter(IDataConverter):
    """Interpret data using Intel (little endian, LSB first) conventions.

    Example:
        >>> IntelConverter().convert(b"\\x01\\x00")
        1
        >>> IntelConverter().to_bytes(256, width=2).hex()
        '0001'
    """

    byte_order = ByteOrder.LITTLE_ENDIAN

    def convert(self, data: bytes, **options: Any) -> int:
        """Return *data* as a little-endian integer."""
        if not data:
            return 0
        return int.from_bytes(data, "little", signed=bool(options.get("signed", False)))

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Encode an integer as little-endian bytes."""
        number = int(value)
        width = int(options.get("width", 0)) or max(1, (number.bit_length() + 7) // 8)
        return number.to_bytes(width, "little", signed=bool(options.get("signed", number < 0)))

    def get_supported_formats(self) -> list[DataFormat]:
        """Return ``[DataFormat.INTEL]``."""
        return [DataFormat.INTEL]

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Reject inputs wider than eight bytes."""
        if len(data) > 8:
            raise ValueError("interpret at most eight bytes as a single integer")

    def extract_signal(self, data: bytes, start_bit: int, bit_length: int, signed: bool = False) -> int:
        """Extract a signal defined with Intel bit numbering.

        Example:
            >>> IntelConverter().extract_signal(b"\\x0F\\x00", 0, 4)
            15
        """
        value = 0
        for offset in range(bit_length):
            bit_index = start_bit + offset
            byte_index, bit_in_byte = divmod(bit_index, 8)
            if byte_index >= len(data):
                break
            bit = (data[byte_index] >> bit_in_byte) & 1
            value |= bit << offset
        if signed and value & (1 << (bit_length - 1)):
            value -= 1 << bit_length
        return value


__all__ = ["IntelConverter"]
