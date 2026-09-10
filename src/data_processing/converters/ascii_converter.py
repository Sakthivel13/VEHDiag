"""ASCII and text conversion."""
from __future__ import annotations

from typing import Any

from ...core.enums.data_format_enums import DataFormat, TextEncoding
from ...core.interfaces.i_data_converter import IDataConverter


class ASCIIConverter(IDataConverter):
    """Convert between raw bytes and printable text.

    Example:
        >>> ASCIIConverter().convert(b"AB\\x00C")
        'AB.C'
        >>> ASCIIConverter().to_bytes("ABC").hex()
        '414243'
    """

    def convert(self, data: bytes, **options: Any) -> str:
        """Return the textual rendering of *data*.

        Args:
            data: Bytes to decode.
            **options: ``encoding`` (:class:`TextEncoding` or string),
                ``placeholder`` for unprintable bytes and ``strict`` to decode
                without substituting characters.
        """
        encoding = options.get("encoding", TextEncoding.ASCII)
        name = encoding.value if isinstance(encoding, TextEncoding) else str(encoding)
        if options.get("strict"):
            return data.decode(name)
        placeholder = str(options.get("placeholder", "."))
        if name in ("ascii", "latin-1"):
            return "".join(chr(b) if 32 <= b < 127 else placeholder for b in data)
        return data.decode(name, errors="replace")

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Encode text into bytes."""
        encoding = options.get("encoding", TextEncoding.ASCII)
        name = encoding.value if isinstance(encoding, TextEncoding) else str(encoding)
        return str(value).encode(name, errors="replace")

    def get_supported_formats(self) -> list[DataFormat]:
        """Return ``[DataFormat.ASCII]``."""
        return [DataFormat.ASCII]

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Ensure the input is a byte string."""
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("the ASCII converter expects a byte string")

    def mixed_view(self, data: bytes, width: int = 16) -> str:
        """Return a combined hex and ASCII dump of *data*."""
        from ...utils.byte_utils import hex_dump

        return hex_dump(data, width)


__all__ = ["ASCIIConverter"]
