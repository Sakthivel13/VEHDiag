"""Hexadecimal conversion."""
from __future__ import annotations

from typing import Any

from ...core.enums.data_format_enums import DataFormat, HexSeparator
from ...core.interfaces.i_data_converter import IDataConverter
from ...utils.byte_utils import bytes_to_hex, hex_to_bytes


class HexConverter(IDataConverter):
    """Convert between raw bytes and hexadecimal text.

    Example:
        >>> HexConverter().convert(b"\\x22\\xf1\\x90")
        '22 F1 90'
        >>> HexConverter().to_bytes("0x22:F1-90").hex()
        '22f190'
    """

    def convert(self, data: bytes, **options: Any) -> str:
        """Return the hexadecimal rendering of *data*.

        Args:
            data: Bytes to format.
            **options: ``separator`` (:class:`HexSeparator` or string),
                ``upper`` (bool) and ``prefix`` (bool).
        """
        separator = options.get("separator", HexSeparator.SPACE)
        text = separator.value if isinstance(separator, HexSeparator) else str(separator)
        upper = bool(options.get("upper", True))
        rendered = bytes_to_hex(data, text, upper)
        if options.get("prefix"):
            return "0x" + rendered.replace(text, "") if text else "0x" + rendered
        return rendered

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Parse hexadecimal text into bytes.

        Raises:
            ValueError: The text contains non-hex characters.
        """
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        return hex_to_bytes(str(value))

    def get_supported_formats(self) -> list[DataFormat]:
        """Return ``[DataFormat.HEX]``."""
        return [DataFormat.HEX]

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Accept any byte string; nothing can fail here."""
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("the hex converter expects a byte string")


__all__ = ["HexConverter"]
