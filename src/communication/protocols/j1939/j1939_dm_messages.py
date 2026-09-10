"""J1939 diagnostic messages DM1, DM2, DM3 and DM11."""
from __future__ import annotations

from dataclasses import dataclass, field

from .j1939_pgn import GLOBAL_ADDRESS, J1939Id
from .j1939_spn import decode_dtc, describe_fmi

#: PGNs of the supported diagnostic messages.
DM1_PGN = 0x00FECA
DM2_PGN = 0x00FECB
DM3_PGN = 0x00FECC
DM11_PGN = 0x00FED3

#: Lamp status names decoded from the first two payload bytes.
LAMP_NAMES = ("protect", "amber warning", "red stop", "malfunction indicator")


@dataclass(slots=True)
class J1939DTC:
    """A decoded J1939 diagnostic trouble code."""

    spn: int
    fmi: int
    occurrence_count: int = 0
    conversion_method: int = 0

    @property
    def description(self) -> str:
        """Return a readable description of the failure mode."""
        return describe_fmi(self.fmi)

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"SPN {self.spn} FMI {self.fmi} ({self.description}) x{self.occurrence_count}"


@dataclass(slots=True)
class LampStatus:
    """Decoded lamp status of a DM1/DM2 message."""

    protect: int = 0
    amber_warning: int = 0
    red_stop: int = 0
    malfunction_indicator: int = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> "LampStatus":
        """Decode the two lamp status bytes."""
        if len(data) < 1:
            return cls()
        first = data[0]
        return cls(
            protect=(first >> 6) & 0x03,
            amber_warning=(first >> 4) & 0x03,
            red_stop=(first >> 2) & 0x03,
            malfunction_indicator=first & 0x03,
        )

    def active_lamps(self) -> list[str]:
        """Return the names of the lamps that are currently on."""
        values = (
            self.protect,
            self.amber_warning,
            self.red_stop,
            self.malfunction_indicator,
        )
        return [name for name, value in zip(LAMP_NAMES, values) if value == 1]


@dataclass(slots=True)
class DiagnosticMessage:
    """A parsed DM1 or DM2 message."""

    pgn: int
    lamps: LampStatus = field(default_factory=LampStatus)
    dtcs: list[J1939DTC] = field(default_factory=list)
    source_address: int = 0

    @property
    def is_active(self) -> bool:
        """Return ``True`` for DM1 (currently active codes)."""
        return self.pgn == DM1_PGN

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.dtcs)


def parse_dm(payload: bytes, pgn: int = DM1_PGN, source_address: int = 0) -> DiagnosticMessage:
    """Parse a DM1/DM2 payload into lamp status and DTC list.

    Example:
        >>> msg = parse_dm(bytes.fromhex("00FF" + "EE000401"))
        >>> msg.dtcs[0].spn
        238
    """
    message = DiagnosticMessage(pgn=pgn, source_address=source_address)
    if len(payload) < 2:
        return message
    message.lamps = LampStatus.from_bytes(payload[:2])
    body = payload[2:]
    for index in range(0, len(body) - 3, 4):
        chunk = body[index : index + 4]
        if chunk in (b"\x00\x00\x00\x00", b"\xff\xff\xff\xff"):
            continue
        spn, fmi, occurrence, conversion = decode_dtc(chunk)
        message.dtcs.append(J1939DTC(spn, fmi, occurrence, conversion))
    return message


def build_dm3_request(source: int, destination: int = GLOBAL_ADDRESS) -> tuple[int, bytes]:
    """Build a DM3 (clear previously active DTCs) request."""
    can_id = J1939Id(
        priority=6, pgn=DM3_PGN, source_address=source, destination_address=destination
    ).to_can_id()
    return can_id, b"\xff" * 8


def build_dm11_request(source: int, destination: int = GLOBAL_ADDRESS) -> tuple[int, bytes]:
    """Build a DM11 (clear active DTCs) request."""
    can_id = J1939Id(
        priority=6, pgn=DM11_PGN, source_address=source, destination_address=destination
    ).to_can_id()
    return can_id, b"\xff" * 8


__all__ = [
    "DM1_PGN",
    "DM2_PGN",
    "DM3_PGN",
    "DM11_PGN",
    "J1939DTC",
    "LampStatus",
    "DiagnosticMessage",
    "parse_dm",
    "build_dm3_request",
    "build_dm11_request",
]
