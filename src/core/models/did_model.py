"""Data Identifier (DID) model and definition registry entries."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..enums.data_format_enums import ByteOrder, DataFormat


@dataclass(slots=True)
class DIDDefinition:
    """Static description of a data identifier.

    Attributes:
        did: The 16-bit data identifier.
        name: Short name, e.g. ``"VIN"``.
        description: Longer explanation shown in tooltips.
        length: Expected payload length in bytes (``None`` when variable).
        data_format: Default interpretation of the payload.
        byte_order: Byte order used for numeric interpretation.
        factor: Physical conversion factor.
        offset: Physical conversion offset.
        unit: Engineering unit appended to the physical value.
        writable: ``True`` when the DID may be written with SID 0x2E.
        session_required: Minimum session needed to read the DID.
    """

    did: int
    name: str = ""
    description: str = ""
    length: int | None = None
    data_format: DataFormat = DataFormat.HEX
    byte_order: ByteOrder = ByteOrder.BIG_ENDIAN
    factor: float = 1.0
    offset: float = 0.0
    unit: str = ""
    writable: bool = False
    session_required: int = 0x01

    @property
    def did_hex(self) -> str:
        """Return the identifier as ``"F190"``."""
        return f"{self.did:04X}"

    @property
    def label(self) -> str:
        """Return ``"F190 - VIN"`` for use in drop-downs."""
        return f"{self.did_hex} - {self.name}" if self.name else self.did_hex

    def to_bytes(self) -> bytes:
        """Return the identifier as two big-endian bytes."""
        return self.did.to_bytes(2, "big")


@dataclass(slots=True)
class DIDValue:
    """A single DID reading returned by ReadDataByIdentifier."""

    did: int
    raw: bytes = b""
    definition: DIDDefinition | None = None
    timestamp: float = 0.0
    parsed: Any = None

    @property
    def name(self) -> str:
        """Return the DID name from the definition, if any."""
        return self.definition.name if self.definition else ""

    @property
    def hex_value(self) -> str:
        """Return the payload as space separated uppercase hex."""
        return " ".join(f"{b:02X}" for b in self.raw)

    @property
    def ascii_value(self) -> str:
        """Return the payload decoded as ASCII with dots for control bytes."""
        return "".join(chr(b) if 32 <= b < 127 else "." for b in self.raw)

    @property
    def unit(self) -> str:
        """Return the engineering unit of the definition, if any."""
        return self.definition.unit if self.definition else ""

    def as_row(self) -> dict[str, Any]:
        """Return a flat mapping used by the DID results table."""
        return {
            "did": f"{self.did:04X}",
            "name": self.name,
            "hex": self.hex_value,
            "ascii": self.ascii_value,
            "parsed": self.parsed,
            "unit": self.unit,
            "length": len(self.raw),
        }


@dataclass(slots=True)
class DIDRegistry:
    """In-memory registry of known DID definitions."""

    definitions: dict[int, DIDDefinition] = field(default_factory=dict)

    def add(self, definition: DIDDefinition) -> None:
        """Register or replace *definition*."""
        self.definitions[definition.did] = definition

    def get(self, did: int) -> DIDDefinition | None:
        """Return the definition for *did* or ``None``."""
        return self.definitions.get(did)

    def search(self, text: str) -> list[DIDDefinition]:
        """Return definitions whose id or name contains *text* (case insensitive)."""
        needle = text.strip().lower()
        if not needle:
            return list(self.definitions.values())
        return [
            d
            for d in self.definitions.values()
            if needle in d.name.lower() or needle in d.did_hex.lower()
        ]

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.definitions)


__all__ = ["DIDDefinition", "DIDValue", "DIDRegistry"]
