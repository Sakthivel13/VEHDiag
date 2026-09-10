"""Decimal (signed and unsigned) conversion."""
from __future__ import annotations

from typing import Any

from ...core.enums.data_format_enums import ByteOrder, DataFormat
from ...core.interfaces.i_data_converter import IDataConverter


class DecimalConverter(IDataConverter):
    """Interpret bytes as integers.

    Example:
        >>> DecimalConverter().convert(b"\\x01\\x00")
        256
        >>> DecimalConverter().convert(b"\\xff\\xff", signed=True)
        -1
        >>> DecimalConverter().to_bytes(256, width=2).hex()
        '0100'
    """

    def convert(self, data: bytes, **options: Any) -> int:
        """Return *data* interpreted as one integer.

        Args:
            data: Bytes to interpret.
            **options: ``byte_order`` (:class:`ByteOrder`) and ``signed``.
        """
        if not data:
            return 0
        order = options.get("byte_order", ByteOrder.BIG_ENDIAN)
        endianness = order.int_byteorder if isinstance(order, ByteOrder) else str(order)
        return int.from_bytes(data, endianness, signed=bool(options.get("signed", False)))

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Encode an integer into *width* bytes.

        Raises:
            ValueError: The value does not fit into the requested width.
        """
        number = int(value)
        width = int(options.get("width", 0)) or max(1, (number.bit_length() + 7) // 8)
        order = options.get("byte_order", ByteOrder.BIG_ENDIAN)
        endianness = order.int_byteorder if isinstance(order, ByteOrder) else str(order)
        return number.to_bytes(width, endianness, signed=bool(options.get("signed", number < 0)))

    def get_supported_formats(self) -> list[DataFormat]:
        """Return the signed and unsigned decimal formats."""
        return [DataFormat.DEC_UNSIGNED, DataFormat.DEC_SIGNED]

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Reject inputs wider than eight bytes for a single integer."""
        if len(data) > 8:
            raise ValueError("interpret at most eight bytes as a single integer")

    def per_byte(self, data: bytes, signed: bool = False) -> list[int]:
        """Return every byte as an individual integer.

        Example:
            >>> DecimalConverter().per_byte(b"\\x41\\x42")
            [65, 66]
        """
        return [int.from_bytes(bytes([b]), "big", signed=signed) for b in data]

    def per_word(self, data: bytes, width: int = 2, byte_order: ByteOrder = ByteOrder.BIG_ENDIAN,
                 signed: bool = False) -> list[int]:
        """Return the data split into *width* byte integers.

        Example:
            >>> DecimalConverter().per_word(b"\\x41\\x42\\x43\\x44")
            [16706, 17220]
        """
        endianness = byte_order.int_byteorder
        return [
            int.from_bytes(data[i : i + width], endianness, signed=signed)
            for i in range(0, len(data) - width + 1, width)
        ]


__all__ = ["DecimalConverter"]
