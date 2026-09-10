"""LIN frame structures."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ....core.exceptions import ChecksumError, FramingError
from .lin_checksum import classic_checksum, enhanced_checksum, protected_id

#: Master request frame identifier used for diagnostics.
MASTER_REQUEST_ID = 0x3C
#: Slave response frame identifier used for diagnostics.
SLAVE_RESPONSE_ID = 0x3D


class LINFrameType(IntEnum):
    """LIN frame categories."""

    UNCONDITIONAL = 0
    EVENT_TRIGGERED = 1
    SPORADIC = 2
    DIAGNOSTIC = 3
    RESERVED = 4


class PCIType(IntEnum):
    """Transport layer PCI types of LIN diagnostic frames."""

    SINGLE_FRAME = 0x0
    FIRST_FRAME = 0x1
    CONSECUTIVE_FRAME = 0x2


@dataclass(slots=True)
class LINFrame:
    """A single LIN frame.

    Attributes:
        frame_id: 6-bit frame identifier.
        data: Up to eight data bytes.
        enhanced: Use the LIN 2.x enhanced checksum.
        frame_type: Category of the frame.
    """

    frame_id: int
    data: bytes = b""
    enhanced: bool = True
    frame_type: LINFrameType = LINFrameType.UNCONDITIONAL

    @property
    def pid(self) -> int:
        """Return the protected identifier of the frame."""
        return protected_id(self.frame_id)

    @property
    def checksum(self) -> int:
        """Return the checksum matching :attr:`enhanced`."""
        if self.enhanced and self.frame_id not in (MASTER_REQUEST_ID, SLAVE_RESPONSE_ID):
            return enhanced_checksum(self.pid, self.data)
        return classic_checksum(self.data)

    def to_bytes(self) -> bytes:
        """Serialise the frame as ``PID + data + checksum``."""
        return bytes([self.pid]) + self.data + bytes([self.checksum])

    @classmethod
    def from_bytes(cls, raw: bytes, enhanced: bool = True) -> "LINFrame":
        """Parse ``PID + data + checksum``.

        Raises:
            FramingError: The buffer is too short.
            ChecksumError: The trailing checksum does not match.
        """
        if len(raw) < 2:
            raise FramingError(f"LIN frame too short ({len(raw)} bytes)")
        pid, data, checksum = raw[0], bytes(raw[1:-1]), raw[-1]
        frame = cls(frame_id=pid & 0x3F, data=data, enhanced=enhanced)
        if frame.checksum != checksum:
            raise ChecksumError(
                "LIN checksum mismatch",
                {"expected": f"0x{frame.checksum:02X}", "received": f"0x{checksum:02X}"},
            )
        return frame

    def __str__(self) -> str:  # noqa: D105 - trivial
        hex_data = " ".join(f"{b:02X}" for b in self.data)
        return f"LIN id=0x{self.frame_id:02X} pid=0x{self.pid:02X} [{len(self.data)}] {hex_data}"


def build_master_request(nad: int, payload: bytes) -> LINFrame:
    """Build a diagnostic master request single frame.

    Args:
        nad: Node address of the addressed slave.
        payload: Up to five payload bytes for a single frame.

    Returns:
        The eight byte master request frame.

    Raises:
        ValueError: The payload does not fit into a single frame.

    Example:
        >>> build_master_request(0x01, bytes.fromhex("22F190")).data.hex().upper()
        '010322F190FFFFFF'
    """
    if len(payload) > 5:
        raise ValueError("LIN single frame payloads are limited to five bytes")
    body = bytes([nad & 0xFF, (PCIType.SINGLE_FRAME << 4) | len(payload)]) + payload
    body = body.ljust(8, b"\xff")
    return LINFrame(MASTER_REQUEST_ID, body, enhanced=False, frame_type=LINFrameType.DIAGNOSTIC)


def parse_slave_response(frame: LINFrame) -> tuple[int, bytes]:
    """Return ``(nad, payload)`` extracted from a slave response frame.

    Raises:
        FramingError: The frame is not a valid diagnostic response.
    """
    if len(frame.data) < 2:
        raise FramingError("LIN slave response too short")
    nad = frame.data[0]
    pci = frame.data[1]
    if (pci >> 4) != PCIType.SINGLE_FRAME:
        raise FramingError("only single frame LIN responses are supported here")
    length = pci & 0x0F
    return nad, bytes(frame.data[2 : 2 + length])


__all__ = [
    "LINFrame",
    "LINFrameType",
    "PCIType",
    "MASTER_REQUEST_ID",
    "SLAVE_RESPONSE_ID",
    "build_master_request",
    "parse_slave_response",
]
