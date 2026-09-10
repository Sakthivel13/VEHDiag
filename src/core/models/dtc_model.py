"""Diagnostic Trouble Code data model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

#: Bit position -> ISO 14229 status bit name.
DTC_STATUS_BITS: dict[int, str] = {
    0: "testFailed",
    1: "testFailedThisOperationCycle",
    2: "pendingDTC",
    3: "confirmedDTC",
    4: "testNotCompletedSinceLastClear",
    5: "testFailedSinceLastClear",
    6: "testNotCompletedThisOperationCycle",
    7: "warningIndicatorRequested",
}

#: First two bits of the high byte -> SAE fault category letter.
_CATEGORY_LETTERS = {0b00: "P", 0b01: "C", 0b10: "B", 0b11: "U"}


@dataclass(slots=True)
class DTCStatus:
    """Decoded DTC status byte."""

    value: int = 0

    def bit(self, index: int) -> bool:
        """Return the state of status bit *index* (0..7)."""
        return bool(self.value & (1 << index))

    @property
    def test_failed(self) -> bool:
        """Return the ``testFailed`` bit."""
        return self.bit(0)

    @property
    def pending(self) -> bool:
        """Return the ``pendingDTC`` bit."""
        return self.bit(2)

    @property
    def confirmed(self) -> bool:
        """Return the ``confirmedDTC`` bit."""
        return self.bit(3)

    @property
    def warning_indicator(self) -> bool:
        """Return the ``warningIndicatorRequested`` bit."""
        return self.bit(7)

    def as_dict(self) -> dict[str, bool]:
        """Return a mapping of every status bit name to its boolean state."""
        return {name: self.bit(index) for index, name in DTC_STATUS_BITS.items()}

    def active_bits(self) -> list[str]:
        """Return the names of all set status bits."""
        return [name for index, name in DTC_STATUS_BITS.items() if self.bit(index)]

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"0x{self.value:02X} [" + ", ".join(self.active_bits()) + "]"


@dataclass(slots=True)
class DTCSnapshotRecord:
    """A freeze-frame (snapshot) record attached to a DTC."""

    record_number: int
    data: bytes = b""
    parsed: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DTCExtendedRecord:
    """An extended data record attached to a DTC."""

    record_number: int
    data: bytes = b""
    parsed: dict[str, Any] = field(default_factory=dict)

    @property
    def occurrence_counter(self) -> int | None:
        """Return the first data byte, conventionally the occurrence counter."""
        return self.data[0] if self.data else None


@dataclass(slots=True)
class DTC:
    """A single diagnostic trouble code with its status and attachments.

    Attributes:
        code: The three byte DTC value, e.g. ``0xC07300``.
        status: Decoded status byte.
        name: Human readable fault description if known.
        severity: Optional severity byte from SID 0x19 sub-function 0x08/0x09.
        functional_unit: Optional functional unit byte.
        snapshots: Freeze frame records read for this DTC.
        extended_records: Extended data records read for this DTC.
    """

    code: int
    status: DTCStatus = field(default_factory=DTCStatus)
    name: str = ""
    severity: int | None = None
    functional_unit: int | None = None
    snapshots: list[DTCSnapshotRecord] = field(default_factory=list)
    extended_records: list[DTCExtendedRecord] = field(default_factory=list)

    @property
    def code_bytes(self) -> bytes:
        """Return the DTC as three big-endian bytes."""
        return self.code.to_bytes(3, "big")

    @property
    def code_hex(self) -> str:
        """Return the raw code as ``"C07300"``."""
        return f"{self.code:06X}"

    @property
    def sae_code(self) -> str:
        """Return the SAE J2012 style code, e.g. ``"C0730"``.

        The two most significant bits select the category letter, the next two
        bits and the remaining nibbles form the four digit code. The lowest
        byte (the failure type) is dropped from this representation.
        """
        high = (self.code >> 16) & 0xFF
        middle = (self.code >> 8) & 0xFF
        letter = _CATEGORY_LETTERS[(high >> 6) & 0b11]
        return f"{letter}{(high >> 4) & 0b11}{high & 0x0F:X}{middle >> 4:X}{middle & 0x0F:X}"

    @property
    def failure_type(self) -> int:
        """Return the failure type byte (lowest byte of the DTC)."""
        return self.code & 0xFF

    @property
    def display_code(self) -> str:
        """Return the code as most tools show it, e.g. ``0xC07300 -> "C0730"``.

        This is the plain hexadecimal rendering of the upper 20 bits and is the
        representation used in the DTC results table.
        """
        return f"{self.code >> 4:05X}"

    @classmethod
    def from_bytes(cls, raw: bytes, status: int = 0, name: str = "") -> "DTC":
        """Build a :class:`DTC` from three code bytes plus a status byte."""
        if len(raw) < 3:
            raise ValueError("A DTC requires at least three bytes")
        return cls(code=int.from_bytes(raw[:3], "big"), status=DTCStatus(status), name=name)

    def as_row(self) -> dict[str, Any]:
        """Return a flat mapping used by the DTC results table."""
        return {
            "code": self.display_code,
            "raw": self.code_hex,
            "name": self.name,
            "status": f"0x{self.status.value:02X}",
            "confirmed": self.status.confirmed,
            "pending": self.status.pending,
            "severity": self.severity,
            "occurrences": self.extended_records[0].occurrence_counter
            if self.extended_records
            else None,
        }

    def __str__(self) -> str:  # noqa: D105 - trivial
        label = f" {self.name}" if self.name else ""
        return f"{self.display_code} (0x{self.code:06X}){label} status={self.status}"


@dataclass(slots=True)
class DTCReport:
    """The full result of a ReadDTCInformation request."""

    sub_function: int
    dtcs: list[DTC] = field(default_factory=list)
    status_availability_mask: int = 0
    raw: bytes = b""

    def __iter__(self) -> Iterator[DTC]:  # noqa: D105 - trivial
        return iter(self.dtcs)

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.dtcs)

    @property
    def confirmed_count(self) -> int:
        """Return the number of confirmed DTCs in the report."""
        return sum(1 for dtc in self.dtcs if dtc.status.confirmed)

    @property
    def pending_count(self) -> int:
        """Return the number of pending DTCs in the report."""
        return sum(1 for dtc in self.dtcs if dtc.status.pending)


__all__ = [
    "DTC_STATUS_BITS",
    "DTCStatus",
    "DTCSnapshotRecord",
    "DTCExtendedRecord",
    "DTC",
    "DTCReport",
]
