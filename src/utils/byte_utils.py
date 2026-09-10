"""Byte and bit manipulation helpers.

All helpers are pure functions operating on :class:`bytes`/:class:`bytearray`
and are safe to use from any thread.
"""
from __future__ import annotations

from typing import Iterable, Iterator, Sequence

_HEX_DIGITS = set("0123456789abcdefABCDEF")


def clean_hex(text: str) -> str:
    """Return *text* with every non-hex character removed.

    Example:
        >>> clean_hex("0x22 F1:90")
        '22F190'
    """
    stripped = text.replace("0x", "").replace("0X", "")
    return "".join(ch for ch in stripped if ch in _HEX_DIGITS)


def hex_to_bytes(text: str) -> bytes:
    """Parse a loosely formatted hex string into bytes.

    Accepts separators (space, colon, dash, comma), ``0x`` prefixes and mixed
    case. An odd number of digits is left-padded with a zero.

    Args:
        text: The hex text to parse.

    Returns:
        The decoded bytes (empty for empty input).

    Raises:
        ValueError: The cleaned text is not valid hexadecimal.

    Example:
        >>> hex_to_bytes("22 F1 90")
        b'"\\xf1\\x90'
    """
    cleaned = clean_hex(text)
    if not cleaned:
        return b""
    if len(cleaned) % 2:
        cleaned = "0" + cleaned
    return bytes.fromhex(cleaned)


def bytes_to_hex(data: bytes | Iterable[int], separator: str = " ", upper: bool = True) -> str:
    """Format *data* as a hex string.

    Args:
        data: Bytes (or any iterable of ints) to format.
        separator: Text inserted between byte pairs.
        upper: Emit uppercase digits.

    Example:
        >>> bytes_to_hex(b"\\x22\\xf1\\x90")
        '22 F1 90'
    """
    fmt = "{:02X}" if upper else "{:02x}"
    return separator.join(fmt.format(b) for b in bytes(data))


def bytes_to_ascii(data: bytes, placeholder: str = ".") -> str:
    """Return the printable ASCII rendering of *data*.

    Non printable bytes are replaced by *placeholder*.
    """
    return "".join(chr(b) if 32 <= b < 127 else placeholder for b in data)


def bytes_to_binary(data: bytes, separator: str = " ") -> str:
    """Return the binary rendering of *data*, e.g. ``'01000001 01000010'``."""
    return separator.join(f"{b:08b}" for b in data)


def get_bit(data: bytes, bit_index: int, msb_first: bool = True) -> int:
    """Return the value (0/1) of a single bit of *data*.

    Args:
        data: The byte string to read from.
        bit_index: Absolute bit index across the whole byte string.
        msb_first: Count bits from the most significant bit of each byte.

    Raises:
        IndexError: The index lies outside *data*.
    """
    byte_index, offset = divmod(bit_index, 8)
    if byte_index >= len(data):
        raise IndexError(f"bit {bit_index} outside {len(data)} byte buffer")
    shift = (7 - offset) if msb_first else offset
    return (data[byte_index] >> shift) & 0x01


def set_bit(data: bytes, bit_index: int, value: bool, msb_first: bool = True) -> bytes:
    """Return a copy of *data* with the bit at *bit_index* set to *value*."""
    byte_index, offset = divmod(bit_index, 8)
    if byte_index >= len(data):
        raise IndexError(f"bit {bit_index} outside {len(data)} byte buffer")
    shift = (7 - offset) if msb_first else offset
    buf = bytearray(data)
    if value:
        buf[byte_index] |= 1 << shift
    else:
        buf[byte_index] &= ~(1 << shift) & 0xFF
    return bytes(buf)


def extract_bits(data: bytes, start_bit: int, bit_length: int, msb_first: bool = True) -> int:
    """Extract *bit_length* bits starting at *start_bit* as an integer.

    Args:
        data: Source bytes.
        start_bit: Absolute index of the first bit to extract.
        bit_length: Number of bits to extract (must be positive).
        msb_first: Bit numbering convention within each byte.

    Returns:
        The extracted bits, first bit becoming the most significant one.

    Raises:
        ValueError: *bit_length* is not positive.
        IndexError: The requested range exceeds *data*.

    Example:
        >>> extract_bits(b"\\xF0", 0, 4)
        15
    """
    if bit_length <= 0:
        raise ValueError("bit_length must be positive")
    if (start_bit + bit_length) > len(data) * 8:
        raise IndexError("bit range exceeds the buffer length")
    value = 0
    for offset in range(bit_length):
        value = (value << 1) | get_bit(data, start_bit + offset, msb_first)
    return value


def int_to_bytes(value: int, length: int, big_endian: bool = True, signed: bool = False) -> bytes:
    """Encode *value* into exactly *length* bytes."""
    return value.to_bytes(length, "big" if big_endian else "little", signed=signed)


def bytes_to_int(data: bytes, big_endian: bool = True, signed: bool = False) -> int:
    """Decode *data* into an integer."""
    if not data:
        return 0
    return int.from_bytes(data, "big" if big_endian else "little", signed=signed)


def swap_endianness(data: bytes, word_size: int = 2) -> bytes:
    """Reverse the byte order inside each *word_size* group.

    Example:
        >>> swap_endianness(b"\\x01\\x02\\x03\\x04").hex()
        '02010403'
    """
    if word_size <= 1:
        return data
    out = bytearray()
    for index in range(0, len(data), word_size):
        chunk = data[index : index + word_size]
        out.extend(chunk[::-1])
    return bytes(out)


def chunk_bytes(data: bytes, size: int) -> Iterator[bytes]:
    """Yield successive *size* byte chunks of *data*.

    Raises:
        ValueError: *size* is not positive.
    """
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for index in range(0, len(data), size):
        yield data[index : index + size]


def pad_bytes(data: bytes, length: int, pad_byte: int = 0x00, left: bool = False) -> bytes:
    """Pad *data* to *length* bytes with *pad_byte*."""
    if len(data) >= length:
        return data
    padding = bytes([pad_byte & 0xFF]) * (length - len(data))
    return padding + data if left else data + padding


def xor_bytes(first: bytes, second: bytes) -> bytes:
    """Return the byte-wise XOR of two equally long buffers.

    Raises:
        ValueError: The buffers differ in length.
    """
    if len(first) != len(second):
        raise ValueError("xor_bytes requires equal length buffers")
    return bytes(a ^ b for a, b in zip(first, second))


def hex_dump(data: bytes, width: int = 16, offset_base: int = 0) -> str:
    """Return a classic ``offset  hex  ascii`` dump of *data*."""
    lines: list[str] = []
    for index in range(0, len(data), width):
        chunk = data[index : index + width]
        hex_part = bytes_to_hex(chunk).ljust(width * 3 - 1)
        lines.append(f"{offset_base + index:08X}  {hex_part}  {bytes_to_ascii(chunk)}")
    return "\n".join(lines)


def compare_bytes(first: bytes, second: bytes) -> list[int]:
    """Return the indices at which two buffers differ."""
    longest = max(len(first), len(second))
    return [
        index
        for index in range(longest)
        if (first[index] if index < len(first) else None)
        != (second[index] if index < len(second) else None)
    ]


def is_valid_hex(text: str, expected_bytes: int | None = None) -> bool:
    """Return ``True`` when *text* parses as hex of the expected length."""
    try:
        parsed = hex_to_bytes(text)
    except ValueError:
        return False
    if expected_bytes is not None and len(parsed) != expected_bytes:
        return False
    return bool(parsed) or not clean_hex(text)


def split_did(did: int) -> tuple[int, int]:
    """Split a 16-bit data identifier into its high and low bytes."""
    return (did >> 8) & 0xFF, did & 0xFF


def join_bytes(values: Sequence[int]) -> bytes:
    """Build a byte string from a sequence of integers, masking to 8 bits."""
    return bytes(v & 0xFF for v in values)


__all__ = [
    "clean_hex",
    "hex_to_bytes",
    "bytes_to_hex",
    "bytes_to_ascii",
    "bytes_to_binary",
    "get_bit",
    "set_bit",
    "extract_bits",
    "int_to_bytes",
    "bytes_to_int",
    "swap_endianness",
    "chunk_bytes",
    "pad_bytes",
    "xor_bytes",
    "hex_dump",
    "compare_bytes",
    "is_valid_hex",
    "split_did",
    "join_bytes",
]
