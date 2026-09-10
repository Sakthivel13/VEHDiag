"""Unit tests for the byte manipulation helpers."""
from __future__ import annotations

import pytest

from src.utils.byte_utils import (
    bytes_to_ascii,
    bytes_to_binary,
    bytes_to_hex,
    bytes_to_int,
    chunk_bytes,
    clean_hex,
    compare_bytes,
    extract_bits,
    get_bit,
    hex_dump,
    hex_to_bytes,
    int_to_bytes,
    is_valid_hex,
    pad_bytes,
    set_bit,
    split_did,
    swap_endianness,
    xor_bytes,
)


class TestHexConversion:
    """Hexadecimal parsing and formatting."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("22F190", b"\x22\xf1\x90"),
            ("22 F1 90", b"\x22\xf1\x90"),
            ("0x22:F1-90", b"\x22\xf1\x90"),
            ("22f190", b"\x22\xf1\x90"),
            ("", b""),
            ("F", b"\x0f"),
        ],
    )
    def test_hex_to_bytes(self, text: str, expected: bytes) -> None:
        """Loosely formatted hex text parses into the expected bytes."""
        assert hex_to_bytes(text) == expected

    def test_bytes_to_hex_separators(self) -> None:
        """The separator and the case are configurable."""
        assert bytes_to_hex(b"\x41\x42") == "41 42"
        assert bytes_to_hex(b"\x41\x42", "") == "4142"
        assert bytes_to_hex(b"\x41\x42", ":", upper=False) == "41:42"

    def test_clean_hex_strips_noise(self) -> None:
        """Non-hex characters are removed."""
        assert clean_hex("0x1A:2B-3C ") == "1A2B3C"

    def test_round_trip(self) -> None:
        """Formatting and parsing are inverse operations."""
        data = bytes(range(256))
        assert hex_to_bytes(bytes_to_hex(data)) == data

    def test_is_valid_hex(self) -> None:
        """Length validation works as documented."""
        assert is_valid_hex("22F190", 3)
        assert not is_valid_hex("22F190", 2)


class TestBitOperations:
    """Bit level access."""

    def test_get_bit_msb_first(self) -> None:
        """Bit 0 is the most significant bit by default."""
        assert get_bit(b"\x80", 0) == 1
        assert get_bit(b"\x80", 7) == 0
        assert get_bit(b"\x01", 7) == 1

    def test_get_bit_lsb_first(self) -> None:
        """LSB-first numbering reverses the order."""
        assert get_bit(b"\x01", 0, msb_first=False) == 1

    def test_set_bit(self) -> None:
        """Setting and clearing a bit produces the expected byte."""
        assert set_bit(b"\x00", 0, True) == b"\x80"
        assert set_bit(b"\xff", 0, False) == b"\x7f"

    @pytest.mark.parametrize(
        ("data", "start", "length", "expected"),
        [
            (b"\xf0", 0, 4, 0x0F),
            (b"\x0f", 4, 4, 0x0F),
            (b"\xab\xcd", 0, 16, 0xABCD),
            (b"\xff", 0, 1, 1),
        ],
    )
    def test_extract_bits(self, data: bytes, start: int, length: int, expected: int) -> None:
        """Bit ranges are extracted MSB first."""
        assert extract_bits(data, start, length) == expected

    def test_extract_bits_out_of_range(self) -> None:
        """Requesting bits beyond the buffer raises."""
        with pytest.raises(IndexError):
            extract_bits(b"\x00", 0, 16)

    def test_extract_bits_invalid_length(self) -> None:
        """A non-positive length raises."""
        with pytest.raises(ValueError):
            extract_bits(b"\x00", 0, 0)


class TestIntegerConversion:
    """Integer encoding and decoding."""

    def test_big_and_little_endian(self) -> None:
        """Both byte orders round trip."""
        assert bytes_to_int(b"\x01\x00") == 256
        assert bytes_to_int(b"\x01\x00", big_endian=False) == 1
        assert int_to_bytes(256, 2) == b"\x01\x00"
        assert int_to_bytes(256, 2, big_endian=False) == b"\x00\x01"

    def test_signed(self) -> None:
        """Two's complement decoding works."""
        assert bytes_to_int(b"\xff\xff", signed=True) == -1

    def test_empty(self) -> None:
        """An empty buffer decodes to zero."""
        assert bytes_to_int(b"") == 0


class TestBufferHelpers:
    """Chunking, padding and comparison."""

    def test_chunk_bytes(self) -> None:
        """Data is split into equal chunks with a shorter tail."""
        assert list(chunk_bytes(b"12345", 2)) == [b"12", b"34", b"5"]

    def test_chunk_invalid_size(self) -> None:
        """A non-positive chunk size raises."""
        with pytest.raises(ValueError):
            list(chunk_bytes(b"12", 0))

    def test_pad_bytes(self) -> None:
        """Padding is appended or prepended as requested."""
        assert pad_bytes(b"\x01", 3) == b"\x01\x00\x00"
        assert pad_bytes(b"\x01", 3, 0xFF, left=True) == b"\xff\xff\x01"
        assert pad_bytes(b"\x01\x02\x03", 2) == b"\x01\x02\x03"

    def test_swap_endianness(self) -> None:
        """Byte order is reversed inside each word."""
        assert swap_endianness(b"\x01\x02\x03\x04") == b"\x02\x01\x04\x03"
        assert swap_endianness(b"\x01\x02\x03\x04", 4) == b"\x04\x03\x02\x01"

    def test_xor_bytes(self) -> None:
        """XOR requires equal lengths."""
        assert xor_bytes(b"\xff\x00", b"\x0f\xf0") == b"\xf0\xf0"
        with pytest.raises(ValueError):
            xor_bytes(b"\x00", b"\x00\x00")

    def test_compare_bytes(self) -> None:
        """Differing indices are reported."""
        assert compare_bytes(b"\x01\x02", b"\x01\x03") == [1]
        assert compare_bytes(b"\x01", b"\x01\x02") == [1]

    def test_hex_dump_layout(self) -> None:
        """The dump has an offset, hex and ASCII column."""
        dump = hex_dump(b"AB")
        assert dump.startswith("00000000  41 42")
        assert dump.endswith("AB")

    def test_split_did(self) -> None:
        """A DID splits into its high and low byte."""
        assert split_did(0xF190) == (0xF1, 0x90)

    def test_bytes_to_ascii_and_binary(self) -> None:
        """Unprintable bytes become dots; binary is zero padded."""
        assert bytes_to_ascii(b"A\x00B") == "A.B"
        assert bytes_to_binary(b"\x41") == "01000001"
