"""K-Line frame construction and parsing.

Two header families are supported:

* ISO 9141-2: ``[FMT] [TGT] [SRC] data... [CS]`` with ``FMT = 0x68``.
* ISO 14230 (KWP2000): a format byte whose lower six bits carry the length,
  optionally followed by target/source bytes and an extra length byte.
"""
from __future__ import annotations

from dataclasses import dataclass

from ....core.exceptions import ChecksumError, FramingError
from ....utils.checksum_calculator import sum8


@dataclass(slots=True)
class KLineFrame:
    """A decoded K-Line message."""

    data: bytes
    target: int = 0x33
    source: int = 0xF1
    format_byte: int = 0x00

    @property
    def length(self) -> int:
        """Return the payload length in bytes."""
        return len(self.data)

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"KLine {self.source:02X}->{self.target:02X} " + " ".join(
            f"{b:02X}" for b in self.data
        )


def build_iso14230_frame(
    data: bytes,
    target: int = 0x33,
    source: int = 0xF1,
    with_addresses: bool = True,
) -> bytes:
    """Build a KWP2000 frame with checksum.

    Args:
        data: Service payload.
        target: Target address byte.
        source: Source (tester) address byte.
        with_addresses: Include the target/source bytes in the header.

    Returns:
        The complete frame including the trailing checksum.

    Example:
        >>> build_iso14230_frame(bytes.fromhex("1003")).hex().upper()
        '8233F11003B9'
    """
    if not data:
        raise FramingError("cannot build an empty K-Line frame")
    length = len(data)
    header = bytearray()
    if with_addresses:
        format_byte = 0x80 | (length if length < 64 else 0)
        header.append(format_byte)
        header.append(target & 0xFF)
        header.append(source & 0xFF)
    else:
        header.append(length if length < 64 else 0)
    if length >= 64:
        header.append(length & 0xFF)
    frame = bytes(header) + data
    return frame + bytes([sum8(frame)])


def build_iso9141_frame(data: bytes, target: int = 0x33, source: int = 0xF1) -> bytes:
    """Build an ISO 9141-2 frame with the fixed ``0x68 0x6A`` style header.

    Example:
        >>> build_iso9141_frame(bytes.fromhex("0100")).hex().upper()
        '6833F101008D'
    """
    frame = bytes([0x68, target & 0xFF, source & 0xFF]) + data
    return frame + bytes([sum8(frame)])


def parse_frame(raw: bytes, verify_checksum: bool = True) -> KLineFrame:
    """Parse a received K-Line frame.

    Args:
        raw: The complete frame including the checksum byte.
        verify_checksum: Validate the trailing checksum.

    Returns:
        The decoded frame.

    Raises:
        FramingError: The frame is too short or malformed.
        ChecksumError: The checksum does not match.

    Example:
        >>> parse_frame(bytes.fromhex("86F1115003003201F402")).data.hex().upper()
        '5003003201F4'
    """
    if len(raw) < 4:
        raise FramingError(f"K-Line frame too short ({len(raw)} bytes)")
    if verify_checksum and sum8(raw[:-1]) != raw[-1]:
        raise ChecksumError(
            "K-Line checksum mismatch",
            {"expected": f"0x{sum8(raw[:-1]):02X}", "received": f"0x{raw[-1]:02X}"},
        )
    format_byte = raw[0]
    body = raw[:-1]
    if format_byte == 0x68:  # ISO 9141-2 fixed header
        return KLineFrame(data=bytes(body[3:]), target=body[1], source=body[2], format_byte=format_byte)
    length = format_byte & 0x3F
    if format_byte & 0x80:  # header with addresses
        offset = 3
        if length == 0:
            length = body[3]
            offset = 4
    else:
        offset = 1
        if length == 0:
            length = body[1]
            offset = 2
    payload = bytes(body[offset : offset + length]) if length else bytes(body[offset:])
    target = body[1] if format_byte & 0x80 else 0x00
    source = body[2] if format_byte & 0x80 else 0x00
    return KLineFrame(data=payload, target=target, source=source, format_byte=format_byte)


def strip_echo(sent: bytes, received: bytes) -> bytes:
    """Remove the local echo of *sent* from the beginning of *received*."""
    if received.startswith(sent):
        return received[len(sent) :]
    return received


__all__ = [
    "KLineFrame",
    "build_iso14230_frame",
    "build_iso9141_frame",
    "parse_frame",
    "strip_echo",
]
