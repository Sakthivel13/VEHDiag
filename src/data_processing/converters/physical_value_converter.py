"""Raw to physical value conversion."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...core.enums.data_format_enums import ByteOrder, DataFormat
from ...core.interfaces.i_data_converter import IDataConverter


@dataclass(slots=True)
class ScalingRule:
    """Linear scaling applied to a raw value.

    Attributes:
        factor: Multiplier applied to the raw value.
        offset: Value added after scaling.
        unit: Engineering unit appended to the formatted result.
        minimum: Optional lower clamp of the physical value.
        maximum: Optional upper clamp of the physical value.
        decimals: Number of decimals used when formatting.
    """

    factor: float = 1.0
    offset: float = 0.0
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None
    decimals: int = 3

    def apply(self, raw: float) -> float:
        """Return ``raw * factor + offset`` clamped to the configured range."""
        value = raw * self.factor + self.offset
        if self.minimum is not None:
            value = max(self.minimum, value)
        if self.maximum is not None:
            value = min(self.maximum, value)
        return value

    def invert(self, physical: float) -> float:
        """Return the raw value producing *physical*."""
        if self.factor == 0:
            return 0.0
        return (physical - self.offset) / self.factor

    def format(self, physical: float) -> str:
        """Return the physical value with its unit.

        Example:
            >>> ScalingRule(0.1, 0, "V").format(13.2)
            '13.200 V'
        """
        text = f"{physical:.{self.decimals}f}"
        return f"{text} {self.unit}".strip()


class PhysicalValueConverter(IDataConverter):
    """Convert raw bytes into engineering values.

    Example:
        >>> converter = PhysicalValueConverter(ScalingRule(0.001, 0.0, "V"))
        >>> round(converter.convert(bytes.fromhex("3390")), 3)
        13.2
        >>> converter.format(bytes.fromhex("3390"))
        '13.200 V'
    """

    def __init__(self, rule: ScalingRule | None = None) -> None:
        """Store the scaling rule used by default."""
        self.rule = rule or ScalingRule()

    def convert(self, data: bytes, **options: Any) -> float:
        """Return the physical value of *data*.

        Args:
            data: Raw bytes to interpret.
            **options: ``rule`` to override the stored scaling, ``byte_order``
                and ``signed``.
        """
        rule = options.get("rule", self.rule)
        order = options.get("byte_order", ByteOrder.BIG_ENDIAN)
        endianness = order.int_byteorder if isinstance(order, ByteOrder) else str(order)
        raw = int.from_bytes(data, endianness, signed=bool(options.get("signed", False))) if data else 0
        return rule.apply(float(raw))

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Encode a physical value back into raw bytes."""
        rule = options.get("rule", self.rule)
        width = int(options.get("width", 2))
        order = options.get("byte_order", ByteOrder.BIG_ENDIAN)
        endianness = order.int_byteorder if isinstance(order, ByteOrder) else str(order)
        raw = int(round(rule.invert(float(value))))
        return raw.to_bytes(width, endianness, signed=raw < 0)

    def get_supported_formats(self) -> list[DataFormat]:
        """Return ``[DataFormat.PHYSICAL]``."""
        return [DataFormat.PHYSICAL]

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Reject inputs wider than eight bytes."""
        if len(data) > 8:
            raise ValueError("physical conversion handles at most eight bytes")

    def format(self, data: bytes, **options: Any) -> str:
        """Return the formatted physical value including the unit."""
        rule = options.get("rule", self.rule)
        return rule.format(self.convert(data, **options))


__all__ = ["PhysicalValueConverter", "ScalingRule"]
