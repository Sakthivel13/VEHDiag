"""IEEE-754 floating point conversion."""
from __future__ import annotations

import struct
from typing import Any

from ...core.enums.data_format_enums import ByteOrder, DataFormat
from ...core.interfaces.i_data_converter import IDataConverter


class IEEE754Converter(IDataConverter):
    """Convert between raw bytes and IEEE-754 floats.

    Example:
        >>> round(IEEE754Converter().convert(bytes.fromhex("40490FDB")), 5)
        3.14159
        >>> IEEE754Converter().to_bytes(3.14159265, width=4).hex().upper()
        '40490FDB'
    """

    def convert(self, data: bytes, **options: Any) -> float:
        """Return *data* interpreted as a float.

        Args:
            data: Four bytes for float32, eight bytes for float64.
            **options: ``byte_order`` (:class:`ByteOrder`).

        Raises:
            ValueError: The length is neither four nor eight bytes.
        """
        order = options.get("byte_order", ByteOrder.BIG_ENDIAN)
        prefix = order.struct_prefix if isinstance(order, ByteOrder) else ">"
        if len(data) == 4:
            return float(struct.unpack(f"{prefix}f", data)[0])
        if len(data) == 8:
            return float(struct.unpack(f"{prefix}d", data)[0])
        raise ValueError("IEEE-754 conversion requires exactly four or eight bytes")

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Encode a float into four or eight bytes."""
        order = options.get("byte_order", ByteOrder.BIG_ENDIAN)
        prefix = order.struct_prefix if isinstance(order, ByteOrder) else ">"
        width = int(options.get("width", 4))
        code = "f" if width == 4 else "d"
        return struct.pack(f"{prefix}{code}", float(value))

    def get_supported_formats(self) -> list[DataFormat]:
        """Return the 32 and 64 bit float formats."""
        return [DataFormat.FLOAT32, DataFormat.FLOAT64]

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Verify the length is four or eight bytes.

        Raises:
            ValueError: The length is unsupported.
        """
        if len(data) not in (4, 8):
            raise ValueError("IEEE-754 conversion requires four or eight bytes")

    def try_convert(self, data: bytes, byte_order: ByteOrder = ByteOrder.BIG_ENDIAN) -> float | None:
        """Return the float value, or ``None`` when the length is wrong."""
        try:
            return self.convert(data, byte_order=byte_order)
        except (ValueError, struct.error):
            return None


__all__ = ["IEEE754Converter"]
