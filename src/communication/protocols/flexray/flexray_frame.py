"""FlexRay frame structure (ISO 17458 / FlexRay 3.0)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ....core.exceptions import FramingError

#: Maximum payload of a FlexRay frame in bytes.
MAX_PAYLOAD = 254


class FlexRayChannel(str, Enum):
    """FlexRay physical channels."""

    A = "A"
    B = "B"
    AB = "AB"


@dataclass(slots=True)
class FlexRayFrame:
    """A FlexRay frame.

    Attributes:
        slot_id: Frame identifier (slot number), 1..2047.
        cycle: Communication cycle counter, 0..63.
        payload: Frame payload (must have an even length).
        channel: Channel the frame was seen on.
        startup_frame: Startup frame indicator.
        sync_frame: Sync frame indicator.
        null_frame: Null frame indicator (payload is not valid).
        payload_preamble: Payload preamble indicator.
        header_crc: 11-bit header CRC.
    """

    slot_id: int
    cycle: int = 0
    payload: bytes = b""
    channel: FlexRayChannel = FlexRayChannel.A
    startup_frame: bool = False
    sync_frame: bool = False
    null_frame: bool = False
    payload_preamble: bool = False
    header_crc: int = 0

    @property
    def payload_length_words(self) -> int:
        """Return the payload length in 16-bit words."""
        return (len(self.payload) + 1) // 2

    def validate(self) -> None:
        """Check the frame against the FlexRay constraints.

        Raises:
            FramingError: The slot, cycle or payload is out of range.
        """
        if not 1 <= self.slot_id <= 2047:
            raise FramingError(f"FlexRay slot id {self.slot_id} is outside 1..2047")
        if not 0 <= self.cycle <= 63:
            raise FramingError(f"FlexRay cycle {self.cycle} is outside 0..63")
        if len(self.payload) > MAX_PAYLOAD:
            raise FramingError(
                f"FlexRay payload of {len(self.payload)} bytes exceeds {MAX_PAYLOAD}"
            )

    def header_bytes(self) -> bytes:
        """Return the five byte FlexRay header.

        Example:
            >>> FlexRayFrame(slot_id=1, payload=b"\\x01\\x02").header_bytes().hex()
            '0001010000'
        """
        self.validate()
        first = (int(self.payload_preamble) << 5) | (int(self.null_frame) << 4)
        first |= (int(self.sync_frame) << 3) | (int(self.startup_frame) << 2)
        first |= (self.slot_id >> 8) & 0x07
        return bytes(
            [
                first,
                self.slot_id & 0xFF,
                self.payload_length_words & 0x7F,
                (self.header_crc >> 4) & 0xFF,
                ((self.header_crc & 0x0F) << 4) | (self.cycle & 0x3F) >> 2,
            ]
        )

    def __str__(self) -> str:  # noqa: D105 - trivial
        hex_data = " ".join(f"{b:02X}" for b in self.payload[:16])
        return f"FlexRay slot={self.slot_id} cycle={self.cycle} ch={self.channel.value} {hex_data}"


def header_crc(slot_id: int, payload_length_words: int, sync: bool = False, startup: bool = False) -> int:
    """Compute the 11-bit FlexRay header CRC.

    The polynomial is ``x^11 + x^9 + x^8 + x^7 + x^2 + 1`` (0x385) with the
    initialisation vector 0x1A.

    Example:
        >>> header_crc(1, 1) >> 8 <= 0x07
        True
    """
    value = (int(sync) << 19) | (int(startup) << 18) | ((slot_id & 0x7FF) << 7)
    value |= payload_length_words & 0x7F
    crc = 0x1A
    for index in range(19, -1, -1):
        bit = (value >> index) & 1
        crc_msb = (crc >> 10) & 1
        crc = ((crc << 1) & 0x7FF)
        if bit ^ crc_msb:
            crc ^= 0x385
    return crc & 0x7FF


__all__ = ["FlexRayFrame", "FlexRayChannel", "header_crc", "MAX_PAYLOAD"]
