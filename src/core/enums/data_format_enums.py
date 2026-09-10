"""Data representation and conversion enumerations."""
from __future__ import annotations

from enum import Enum


class DataFormat(str, Enum):
    """Supported textual/numeric representations of raw byte data."""

    HEX = "HEX"
    ASCII = "ASCII"
    DEC_UNSIGNED = "DEC_UNSIGNED"
    DEC_SIGNED = "DEC_SIGNED"
    BIN = "BIN"
    BCD = "BCD"
    FLOAT32 = "FLOAT32"
    FLOAT64 = "FLOAT64"
    MOT = "MOT"
    INTEL = "INTEL"
    PHYSICAL = "PHYSICAL"

    @property
    def display_name(self) -> str:
        """Return the label used in conversion drop-downs."""
        return {
            DataFormat.HEX: "Hexadecimal",
            DataFormat.ASCII: "ASCII text",
            DataFormat.DEC_UNSIGNED: "Decimal (unsigned)",
            DataFormat.DEC_SIGNED: "Decimal (signed)",
            DataFormat.BIN: "Binary",
            DataFormat.BCD: "BCD",
            DataFormat.FLOAT32: "Float 32 (IEEE-754)",
            DataFormat.FLOAT64: "Float 64 (IEEE-754)",
            DataFormat.MOT: "Motorola (big endian)",
            DataFormat.INTEL: "Intel (little endian)",
            DataFormat.PHYSICAL: "Physical value",
        }[self]


class ByteOrder(str, Enum):
    """Byte ordering used when interpreting multi-byte values."""

    BIG_ENDIAN = "BIG_ENDIAN"
    LITTLE_ENDIAN = "LITTLE_ENDIAN"

    @property
    def struct_prefix(self) -> str:
        """Return the :mod:`struct` format prefix (``>`` or ``<``)."""
        return ">" if self is ByteOrder.BIG_ENDIAN else "<"

    @property
    def int_byteorder(self) -> str:
        """Return the literal expected by :meth:`int.from_bytes`."""
        return "big" if self is ByteOrder.BIG_ENDIAN else "little"


class HexSeparator(str, Enum):
    """Separator inserted between hexadecimal byte pairs."""

    NONE = ""
    SPACE = " "
    COLON = ":"
    DASH = "-"
    COMMA = ","


class TextEncoding(str, Enum):
    """Text encodings offered by the ASCII converter."""

    ASCII = "ascii"
    UTF8 = "utf-8"
    LATIN1 = "latin-1"


class BitOrder(str, Enum):
    """Bit numbering convention used for bit level slicing."""

    MSB_FIRST = "MSB_FIRST"
    LSB_FIRST = "LSB_FIRST"


__all__ = ["DataFormat", "ByteOrder", "HexSeparator", "TextEncoding", "BitOrder"]
