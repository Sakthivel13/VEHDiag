"""Slice diagnostic response data by byte or by bit.

The slicer backs the *Response Slicer* panel: the operator defines named
slices over a response, chooses a conversion for each and saves the whole set
as a reusable profile.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.enums.data_format_enums import ByteOrder, DataFormat
from ..utils.byte_utils import extract_bits
from ..utils.file_utils import load_yaml, save_yaml
from .data_converter import DataConverter
from .converters.physical_value_converter import ScalingRule

_logger = logging.getLogger(__name__)

#: Colour palette used to distinguish slices in the visual byte map.
SLICE_COLORS: tuple[str, ...] = (
    "#7C3AED",
    "#06B6D4",
    "#22C55E",
    "#F59E0B",
    "#EF4444",
    "#EC4899",
    "#8B5CF6",
    "#14B8A6",
)


@dataclass(slots=True)
class SliceDefinition:
    """One named slice of a response.

    Attributes:
        name: Label shown next to the value.
        start: Start byte index, or start bit index in bit mode.
        length: Number of bytes, or number of bits in bit mode.
        bit_mode: Interpret *start* and *length* as bit positions.
        data_format: Conversion applied to the extracted bytes.
        byte_order: Byte order used for numeric conversions.
        signed: Interpret numeric values as two's complement.
        factor: Physical scaling factor.
        offset: Physical scaling offset.
        unit: Engineering unit appended to physical values.
        color: Highlight colour used by the visual byte map.
    """

    name: str = "slice"
    start: int = 0
    length: int = 1
    bit_mode: bool = False
    data_format: DataFormat = DataFormat.HEX
    byte_order: ByteOrder = ByteOrder.BIG_ENDIAN
    signed: bool = False
    factor: float = 1.0
    offset: float = 0.0
    unit: str = ""
    color: str = SLICE_COLORS[0]

    @property
    def end(self) -> int:
        """Return the exclusive end index of the slice."""
        return self.start + self.length

    @property
    def scaling(self) -> ScalingRule:
        """Return the scaling rule described by the factor/offset/unit."""
        return ScalingRule(factor=self.factor, offset=self.offset, unit=self.unit)

    def to_dict(self) -> dict[str, Any]:
        """Return the YAML serialisable representation."""
        return {
            "name": self.name,
            "start": self.start,
            "length": self.length,
            "bit_mode": self.bit_mode,
            "format": self.data_format.value,
            "byte_order": self.byte_order.value,
            "signed": self.signed,
            "factor": self.factor,
            "offset": self.offset,
            "unit": self.unit,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SliceDefinition":
        """Build a definition from its YAML representation."""
        return cls(
            name=str(data.get("name", "slice")),
            start=int(data.get("start", 0)),
            length=int(data.get("length", 1)),
            bit_mode=bool(data.get("bit_mode", False)),
            data_format=DataFormat(str(data.get("format", "HEX"))),
            byte_order=ByteOrder(str(data.get("byte_order", "BIG_ENDIAN"))),
            signed=bool(data.get("signed", False)),
            factor=float(data.get("factor", 1.0)),
            offset=float(data.get("offset", 0.0)),
            unit=str(data.get("unit", "")),
            color=str(data.get("color", SLICE_COLORS[0])),
        )


@dataclass(slots=True)
class SliceResult:
    """The value extracted by one slice."""

    definition: SliceDefinition
    raw: bytes = b""
    value: Any = None
    error: str = ""

    @property
    def name(self) -> str:
        """Return the slice name."""
        return self.definition.name

    @property
    def hex_value(self) -> str:
        """Return the extracted bytes as hex."""
        return " ".join(f"{b:02X}" for b in self.raw)

    @property
    def display(self) -> str:
        """Return the value formatted for the results table."""
        if self.error:
            return f"error: {self.error}"
        if self.definition.unit and isinstance(self.value, (int, float)):
            return f"{self.value} {self.definition.unit}"
        return str(self.value)


@dataclass(slots=True)
class SliceProfile:
    """A named, reusable collection of slice definitions."""

    name: str = "profile"
    description: str = ""
    slices: list[SliceDefinition] = field(default_factory=list)

    def add(self, definition: SliceDefinition) -> SliceDefinition:
        """Append *definition*, assigning it the next palette colour."""
        definition.color = SLICE_COLORS[len(self.slices) % len(SLICE_COLORS)]
        self.slices.append(definition)
        return definition

    def remove(self, index: int) -> None:
        """Remove the slice at *index* if it exists."""
        if 0 <= index < len(self.slices):
            del self.slices[index]

    def to_dict(self) -> dict[str, Any]:
        """Return the YAML serialisable representation."""
        return {
            "name": self.name,
            "description": self.description,
            "slices": [s.to_dict() for s in self.slices],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SliceProfile":
        """Build a profile from its YAML representation."""
        return cls(
            name=str(data.get("name", "profile")),
            description=str(data.get("description", "")),
            slices=[SliceDefinition.from_dict(item) for item in data.get("slices", [])],
        )

    def save(self, path: str | Path) -> Path:
        """Write the profile to a YAML file."""
        return save_yaml(path, self.to_dict())

    @classmethod
    def load(cls, path: str | Path) -> "SliceProfile":
        """Read a profile from a YAML file."""
        return cls.from_dict(load_yaml(path, default={}) or {})

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.slices)


class ResponseSlicer:
    """Extracts and converts named parts of a response.

    Example:
        >>> slicer = ResponseSlicer()
        >>> data = bytes.fromhex("62F190" + "5742415A")
        >>> slicer.slice_bytes(data, 1, 2).hex().upper()
        'F190'
        >>> slicer.slice_bits(bytes([0b10110000]), 0, 4)
        11
        >>> profile = SliceProfile("VIN read")
        >>> _ = profile.add(SliceDefinition("SID", 0, 1))
        >>> _ = profile.add(SliceDefinition("DID", 1, 2))
        >>> _ = profile.add(SliceDefinition("Data", 3, 4, data_format=DataFormat.ASCII))
        >>> [r.display for r in slicer.apply(data, profile)]
        ['62', 'F1 90', 'WBAZ']
    """

    def __init__(self, converter: DataConverter | None = None) -> None:
        """Create the slicer with an optional shared converter."""
        self.converter = converter or DataConverter()

    # -- primitive operations ------------------------------------------------
    @staticmethod
    def slice_bytes(data: bytes, start: int, length: int) -> bytes:
        """Return *length* bytes starting at *start*.

        Out of range requests return the available bytes instead of raising, so
        the UI can show a partial result while the operator types.
        """
        if start < 0:
            start = max(0, len(data) + start)
        return bytes(data[start : start + max(0, length)])

    @staticmethod
    def slice_bits(data: bytes, start_bit: int, bit_length: int, msb_first: bool = True) -> int:
        """Return *bit_length* bits starting at *start_bit* as an integer.

        Raises:
            IndexError: The bit range exceeds the data.
            ValueError: *bit_length* is not positive.
        """
        return extract_bits(data, start_bit, bit_length, msb_first)

    # -- profile application ----------------------------------------------------
    def apply_slice(self, data: bytes, definition: SliceDefinition) -> SliceResult:
        """Apply one *definition* to *data* and convert the extracted value."""
        result = SliceResult(definition=definition)
        try:
            if definition.bit_mode:
                value = self.slice_bits(data, definition.start, definition.length)
                byte_width = max(1, (definition.length + 7) // 8)
                result.raw = value.to_bytes(byte_width, "big")
            else:
                result.raw = self.slice_bytes(data, definition.start, definition.length)
                if not result.raw:
                    result.error = "no data at this position"
                    return result
            result.value = self._convert(result.raw, definition)
        except (IndexError, ValueError) as exc:
            result.error = str(exc)
        return result

    def apply(self, data: bytes, profile: SliceProfile) -> list[SliceResult]:
        """Apply every slice of *profile* to *data*."""
        return [self.apply_slice(data, definition) for definition in profile.slices]

    def apply_dict(self, data: bytes, profile: SliceProfile) -> dict[str, Any]:
        """Return ``{slice name: value}`` for *profile* applied to *data*."""
        return {result.name: result.value for result in self.apply(data, profile)}

    def _convert(self, raw: bytes, definition: SliceDefinition) -> Any:
        """Convert *raw* according to the definition."""
        fmt = definition.data_format
        if fmt is DataFormat.PHYSICAL:
            return round(
                self.converter.physical.convert(
                    raw, rule=definition.scaling, byte_order=definition.byte_order,
                    signed=definition.signed,
                ),
                6,
            )
        if fmt in (DataFormat.DEC_UNSIGNED, DataFormat.DEC_SIGNED):
            return self.converter.decimal.convert(
                raw,
                byte_order=definition.byte_order,
                signed=definition.signed or fmt is DataFormat.DEC_SIGNED,
            )
        return self.converter.convert(
            raw, target=fmt, byte_order=definition.byte_order, signed=definition.signed
        )

    # -- helpers -------------------------------------------------------------------
    @staticmethod
    def auto_profile(data: bytes, name: str = "auto") -> SliceProfile:
        """Build a naive profile splitting a UDS response into SID/DID/data.

        Example:
            >>> profile = ResponseSlicer.auto_profile(bytes.fromhex("62F1904142"))
            >>> [s.name for s in profile.slices]
            ['Service echo', 'Data identifier', 'Data']
        """
        profile = SliceProfile(name=name)
        if not data:
            return profile
        profile.add(SliceDefinition("Service echo", 0, 1))
        if len(data) >= 3 and data[0] in (0x62, 0x6E, 0x64):
            profile.add(SliceDefinition("Data identifier", 1, 2))
            if len(data) > 3:
                profile.add(
                    SliceDefinition("Data", 3, len(data) - 3, data_format=DataFormat.ASCII)
                )
        elif len(data) > 1:
            profile.add(SliceDefinition("Data", 1, len(data) - 1))
        return profile

    @staticmethod
    def byte_map(data: bytes, profile: SliceProfile | None = None) -> list[dict[str, Any]]:
        """Return per-byte metadata used to render the visual byte map."""
        assignments: dict[int, SliceDefinition] = {}
        for definition in (profile.slices if profile else []):
            if definition.bit_mode:
                continue
            for index in range(definition.start, definition.end):
                assignments.setdefault(index, definition)
        return [
            {
                "index": index,
                "value": byte,
                "hex": f"{byte:02X}",
                "ascii": chr(byte) if 32 <= byte < 127 else ".",
                "slice": assignments[index].name if index in assignments else "",
                "color": assignments[index].color if index in assignments else "",
            }
            for index, byte in enumerate(data)
        ]


__all__ = [
    "ResponseSlicer",
    "SliceDefinition",
    "SliceProfile",
    "SliceResult",
    "SLICE_COLORS",
]
