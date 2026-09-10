"""Binary string conversion."""
from __future__ import annotations

from typing import Any

from ...core.enums.data_format_enums import BitOrder, DataFormat
from ...core.interfaces.i_data_converter import IDataConverter


class BinaryConverter(IDataConverter):
    """Convert between raw bytes and binary text.

    Example:
        >>> BinaryConverter().convert(b"\\x41")
        '01000001'
        >>> BinaryConverter().to_bytes("01000001 01000010").hex()
        '4142'
    """

    def convert(self, data: bytes, **options: Any) -> str:
        """Return the binary rendering of *data*.

        Args:
            data: Bytes to format.
            **options: ``separator`` between bytes, ``group`` (4 or 8 bits) and
                ``bit_order`` (:class:`BitOrder`).
        """
        separator = str(options.get("separator", " "))
        group = int(options.get("group", 8))
        bit_order = options.get("bit_order", BitOrder.MSB_FIRST)
        chunks: list[str] = []
        for byte in data:
            bits = f"{byte:08b}"
            if bit_order is BitOrder.LSB_FIRST:
                bits = bits[::-1]
            if group == 4:
                chunks.append(f"{bits[:4]} {bits[4:]}")
            else:
                chunks.append(bits)
        return separator.join(chunks)

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Parse binary text into bytes.

        Raises:
            ValueError: The text contains characters other than 0 and 1.
        """
        text = "".join(ch for ch in str(value) if ch in "01")
        if not text:
            return b""
        if len(text) % 8:
            text = text.zfill(((len(text) // 8) + 1) * 8)
        return bytes(int(text[i : i + 8], 2) for i in range(0, len(text), 8))

    def get_supported_formats(self) -> list[DataFormat]:
        """Return ``[DataFormat.BIN]``."""
        return [DataFormat.BIN]

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Ensure the input is a byte string."""
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("the binary converter expects a byte string")

    def bit_table(self, data: bytes) -> list[tuple[int, int]]:
        """Return ``(bit_index, value)`` pairs for the bit level viewer.

        Example:
            >>> BinaryConverter().bit_table(b"\\x80")[0]
            (0, 1)
        """
        return [
            (index, (data[index // 8] >> (7 - index % 8)) & 1) for index in range(len(data) * 8)
        ]


__all__ = ["BinaryConverter"]
