"""Motorola (big endian) byte and bit order handling."""
from __future__ import annotations

from typing import Any

from ...core.enums.data_format_enums import ByteOrder, DataFormat
from ...core.interfaces.i_data_converter import IDataConverter
from ...utils.byte_utils import extract_bits


class MotorolaConverter(IDataConverter):
    """Interpret data using Motorola (big endian, MSB first) conventions.

    Example:
        >>> MotorolaConverter().convert(b"\\x01\\x00")
        256
        >>> MotorolaConverter().to_bytes(256, width=2).hex()
        '0100'
    """

    byte_order = ByteOrder.BIG_ENDIAN

    def convert(self, data: bytes, **options: Any) -> int:
        """Return *data* as a big-endian integer."""
        if not data:
            return 0
        return int.from_bytes(data, "big", signed=bool(options.get("signed", False)))

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Encode an integer as big-endian bytes."""
        number = int(value)
        width = int(options.get("width", 0)) or max(1, (number.bit_length() + 7) // 8)
        return number.to_bytes(width, "big", signed=bool(options.get("signed", number < 0)))

    def get_supported_formats(self) -> list[DataFormat]:
        """Return ``[DataFormat.MOT]``."""
        return [DataFormat.MOT]

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Reject inputs wider than eight bytes."""
        if len(data) > 8:
            raise ValueError("interpret at most eight bytes as a single integer")

    @staticmethod
    def motorola_start_bit(start_bit: int) -> int:
        """Translate a Motorola (sawtooth) bit index into a linear MSB index.

        In Motorola notation bit 7 is the most significant bit of byte 0, so
        the linear index is ``byte * 8 + (7 - bit_in_byte)``.

        Example:
            >>> MotorolaConverter.motorola_start_bit(7)
            0
            >>> MotorolaConverter.motorola_start_bit(15)
            8
        """
        byte_index, bit_in_byte = divmod(start_bit, 8)
        return byte_index * 8 + (7 - bit_in_byte)

    def extract_signal(self, data: bytes, start_bit: int, bit_length: int, signed: bool = False) -> int:
        """Extract a signal defined with Motorola bit numbering.

        Example:
            >>> MotorolaConverter().extract_signal(b"\\xF0\\x00", 7, 4)
            15
        """
        linear = self.motorola_start_bit(start_bit)
        value = extract_bits(data, linear, bit_length, msb_first=True)
        if signed and value & (1 << (bit_length - 1)):
            value -= 1 << bit_length
        return value


__all__ = ["MotorolaConverter"]
