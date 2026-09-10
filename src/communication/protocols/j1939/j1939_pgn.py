"""SAE J1939 Parameter Group Number handling."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Global (broadcast) destination address.
GLOBAL_ADDRESS: Final[int] = 0xFF
#: Null address used before a successful address claim.
NULL_ADDRESS: Final[int] = 0xFE

#: Well known parameter group numbers.
KNOWN_PGNS: Final[dict[int, str]] = {
    0x00E800: "Acknowledgement",
    0x00EA00: "Request",
    0x00EB00: "TP.DT - transport protocol data transfer",
    0x00EC00: "TP.CM - transport protocol connection management",
    0x00EE00: "Address claimed",
    0x00EF00: "Proprietary A",
    0x00FECA: "DM1 - active diagnostic trouble codes",
    0x00FECB: "DM2 - previously active diagnostic trouble codes",
    0x00FECC: "DM3 - diagnostic data clear",
    0x00FED3: "DM11 - clear active DTCs",
    0x00FEE5: "Engine hours",
    0x00FEEE: "Engine temperature",
    0x00FEF1: "Cruise control / vehicle speed",
    0x00FEF2: "Fuel economy",
    0x00F004: "Electronic engine controller 1",
}


@dataclass(slots=True)
class J1939Id:
    """Decomposed 29-bit J1939 CAN identifier.

    Attributes:
        priority: Three bit message priority (0 = highest).
        pgn: Parameter group number.
        source_address: Address of the transmitting node.
        destination_address: Destination for PDU1 messages.
    """

    priority: int = 6
    pgn: int = 0
    source_address: int = 0
    destination_address: int = GLOBAL_ADDRESS

    @property
    def is_pdu1(self) -> bool:
        """Return ``True`` for destination specific (PDU1) messages."""
        return ((self.pgn >> 8) & 0xFF) < 240

    def to_can_id(self) -> int:
        """Encode the fields into a 29-bit CAN identifier.

        Example:
            >>> hex(J1939Id(priority=6, pgn=0x00FECA, source_address=0x00).to_can_id())
            '0x18feca00'
        """
        pgn = self.pgn
        if self.is_pdu1:
            pgn = (pgn & 0x3FF00) | (self.destination_address & 0xFF)
        return ((self.priority & 0x07) << 26) | ((pgn & 0x3FFFF) << 8) | (self.source_address & 0xFF)

    @classmethod
    def from_can_id(cls, can_id: int) -> "J1939Id":
        """Decode a 29-bit CAN identifier.

        Example:
            >>> J1939Id.from_can_id(0x18FECA00).pgn == 0xFECA
            True
        """
        priority = (can_id >> 26) & 0x07
        source = can_id & 0xFF
        pdu_format = (can_id >> 16) & 0xFF
        pdu_specific = (can_id >> 8) & 0xFF
        data_page = (can_id >> 24) & 0x03
        if pdu_format < 240:  # PDU1: destination specific
            pgn = (data_page << 16) | (pdu_format << 8)
            destination = pdu_specific
        else:  # PDU2: broadcast
            pgn = (data_page << 16) | (pdu_format << 8) | pdu_specific
            destination = GLOBAL_ADDRESS
        return cls(priority=priority, pgn=pgn, source_address=source, destination_address=destination)

    @property
    def name(self) -> str:
        """Return the well known name of the PGN, if any."""
        return KNOWN_PGNS.get(self.pgn, f"PGN 0x{self.pgn:05X}")

    def __str__(self) -> str:  # noqa: D105 - trivial
        return (
            f"J1939 p{self.priority} {self.name} SA=0x{self.source_address:02X} "
            f"DA=0x{self.destination_address:02X}"
        )


def pgn_to_bytes(pgn: int) -> bytes:
    """Return the three little-endian bytes used inside J1939 payloads."""
    return bytes([pgn & 0xFF, (pgn >> 8) & 0xFF, (pgn >> 16) & 0xFF])


def bytes_to_pgn(data: bytes) -> int:
    """Decode three little-endian PGN bytes."""
    if len(data) < 3:
        raise ValueError("a PGN needs three bytes")
    return data[0] | (data[1] << 8) | (data[2] << 16)


__all__ = [
    "GLOBAL_ADDRESS",
    "NULL_ADDRESS",
    "KNOWN_PGNS",
    "J1939Id",
    "pgn_to_bytes",
    "bytes_to_pgn",
]
