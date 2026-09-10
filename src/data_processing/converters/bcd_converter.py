"""Binary Coded Decimal conversion."""
from __future__ import annotations

from typing import Any

from ...core.enums.data_format_enums import DataFormat
from ...core.interfaces.i_data_converter import IDataConverter


class BCDConverter(IDataConverter):
    """Convert between packed/unpacked BCD and decimal values.

    Example:
        >>> BCDConverter().convert(b"\\x12\\x34")
        1234
        >>> BCDConverter().to_bytes(1234).hex()
        '1234'
    """

    def convert(self, data: bytes, **options: Any) -> int:
        """Return the decimal value of packed BCD *data*.

        Args:
            data: Packed BCD bytes.
            **options: ``packed`` (default ``True``); unpacked BCD uses one
                digit per byte in the low nibble.

        Raises:
            ValueError: A nibble holds a value above nine.
        """
        packed = bool(options.get("packed", True))
        digits: list[int] = []
        for byte in data:
            if packed:
                high, low = byte >> 4, byte & 0x0F
                if high > 9 or low > 9:
                    raise ValueError(f"invalid packed BCD byte 0x{byte:02X}")
                digits.extend((high, low))
            else:
                low = byte & 0x0F
                if low > 9:
                    raise ValueError(f"invalid unpacked BCD byte 0x{byte:02X}")
                digits.append(low)
        return int("".join(str(d) for d in digits) or "0")

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Encode a decimal value into packed BCD."""
        text = str(int(value))
        if len(text) % 2:
            text = "0" + text
        return bytes(int(text[i]) << 4 | int(text[i + 1]) for i in range(0, len(text), 2))

    def get_supported_formats(self) -> list[DataFormat]:
        """Return ``[DataFormat.BCD]``."""
        return [DataFormat.BCD]

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Verify every nibble holds a decimal digit.

        Raises:
            ValueError: The data is not valid BCD.
        """
        for byte in data:
            if (byte >> 4) > 9 or (byte & 0x0F) > 9:
                raise ValueError(f"0x{byte:02X} is not a valid BCD byte")

    def to_digits(self, data: bytes) -> str:
        """Return the BCD digits as text, keeping leading zeros.

        Example:
            >>> BCDConverter().to_digits(b"\\x20\\x24\\x01\\x15")
            '20240115'
        """
        return "".join(f"{b >> 4}{b & 0x0F}" for b in data)

    def to_date(self, data: bytes) -> str:
        """Format a four byte BCD manufacturing date as ``YYYY-MM-DD``.

        Example:
            >>> BCDConverter().to_date(b"\\x20\\x24\\x01\\x15")
            '2024-01-15'
        """
        digits = self.to_digits(data)
        if len(digits) < 8:
            return digits
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"


__all__ = ["BCDConverter"]
