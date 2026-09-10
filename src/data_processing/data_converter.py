"""Master data converter producing every representation at once.

The :class:`DataConverter` is what the *Data Converter* panel binds to: give it
bytes (or text in any format) and it returns a mapping with the hexadecimal,
ASCII, decimal, binary, BCD and floating point interpretations plus an optional
physical value.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..core.enums.data_format_enums import ByteOrder, DataFormat, HexSeparator
from ..core.interfaces.i_data_converter import IDataConverter
from .converters.ascii_converter import ASCIIConverter
from .converters.bcd_converter import BCDConverter
from .converters.binary_converter import BinaryConverter
from .converters.custom_formula_converter import CustomFormulaConverter
from .converters.decimal_converter import DecimalConverter
from .converters.hex_converter import HexConverter
from .converters.ieee754_converter import IEEE754Converter
from .converters.intel_converter import IntelConverter
from .converters.motorola_converter import MotorolaConverter
from .converters.physical_value_converter import PhysicalValueConverter, ScalingRule

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConversionResult:
    """Every representation of one byte string.

    Attributes:
        raw: The source bytes.
        values: Mapping of representation name to formatted value.
        physical: Optional physical value produced by a scaling rule.
        unit: Unit of the physical value.
    """

    raw: bytes
    values: dict[str, Any] = field(default_factory=dict)
    physical: float | None = None
    unit: str = ""

    def get(self, name: str, default: Any = None) -> Any:
        """Return one representation by name."""
        return self.values.get(name, default)

    def as_rows(self) -> list[tuple[str, str]]:
        """Return ``(label, value)`` pairs for the converter table."""
        rows = [(name, str(value)) for name, value in self.values.items()]
        if self.physical is not None:
            rows.append(("Physical", f"{self.physical:.3f} {self.unit}".strip()))
        return rows

    def __getitem__(self, name: str) -> Any:  # noqa: D105 - trivial
        return self.values[name]


class DataConverter(IDataConverter):
    """Convert bytes into every supported representation.

    Example:
        >>> converter = DataConverter()
        >>> result = converter.convert_all(b"AB")
        >>> result["HEX"], result["ASCII"], result["DEC_UNSIGNED_BE"]
        ('41 42', 'AB', 16706)
        >>> converter.parse("41 42", DataFormat.HEX)
        b'AB'
    """

    def __init__(self) -> None:
        """Create the sub-converters."""
        self.hex = HexConverter()
        self.ascii = ASCIIConverter()
        self.decimal = DecimalConverter()
        self.binary = BinaryConverter()
        self.motorola = MotorolaConverter()
        self.intel = IntelConverter()
        self.bcd = BCDConverter()
        self.float = IEEE754Converter()
        self.physical = PhysicalValueConverter()

    # -- IDataConverter -----------------------------------------------------
    def convert(self, data: bytes, **options: Any) -> Any:
        """Convert *data* into the single format given by ``target``."""
        target = options.get("target", DataFormat.HEX)
        fmt = DataFormat(target) if not isinstance(target, DataFormat) else target
        order = options.get("byte_order", ByteOrder.BIG_ENDIAN)
        if fmt is DataFormat.HEX:
            return self.hex.convert(data, **options)
        if fmt is DataFormat.ASCII:
            return self.ascii.convert(data, **options)
        if fmt is DataFormat.DEC_UNSIGNED:
            return self.decimal.convert(data, byte_order=order, signed=False)
        if fmt is DataFormat.DEC_SIGNED:
            return self.decimal.convert(data, byte_order=order, signed=True)
        if fmt is DataFormat.BIN:
            return self.binary.convert(data, **options)
        if fmt is DataFormat.BCD:
            return self.bcd.convert(data)
        if fmt in (DataFormat.FLOAT32, DataFormat.FLOAT64):
            return self.float.convert(data, byte_order=order)
        if fmt is DataFormat.MOT:
            return self.motorola.convert(data)
        if fmt is DataFormat.INTEL:
            return self.intel.convert(data)
        if fmt is DataFormat.PHYSICAL:
            return self.physical.convert(data, **options)
        raise ValueError(f"unsupported target format {fmt}")

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Parse *value* from the format given by ``source``."""
        source = options.get("source", DataFormat.HEX)
        return self.parse(value, source, **options)

    def get_supported_formats(self) -> list[DataFormat]:
        """Return every format the converter can produce."""
        return list(DataFormat)

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Ensure the input is a byte string."""
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("the data converter expects a byte string")

    # -- high level API --------------------------------------------------------
    def parse(self, value: Any, source: DataFormat | str = DataFormat.HEX, **options: Any) -> bytes:
        """Parse text in *source* format into bytes.

        Raises:
            ValueError: The text cannot be parsed in that format.
        """
        fmt = DataFormat(source) if not isinstance(source, DataFormat) else source
        if fmt is DataFormat.HEX:
            return self.hex.to_bytes(value)
        if fmt is DataFormat.ASCII:
            return self.ascii.to_bytes(value, **options)
        if fmt in (DataFormat.DEC_UNSIGNED, DataFormat.DEC_SIGNED):
            return self.decimal.to_bytes(int(str(value).strip()), **options)
        if fmt is DataFormat.BIN:
            return self.binary.to_bytes(value)
        if fmt is DataFormat.BCD:
            return self.bcd.to_bytes(value)
        if fmt in (DataFormat.FLOAT32, DataFormat.FLOAT64):
            width = 4 if fmt is DataFormat.FLOAT32 else 8
            return self.float.to_bytes(float(value), width=width, **options)
        if fmt is DataFormat.MOT:
            return self.motorola.to_bytes(int(str(value), 0), **options)
        if fmt is DataFormat.INTEL:
            return self.intel.to_bytes(int(str(value), 0), **options)
        raise ValueError(f"cannot parse input in {fmt} format")

    def convert_all(
        self,
        data: bytes,
        scaling: ScalingRule | None = None,
        formula: str = "",
    ) -> ConversionResult:
        """Return every representation of *data* in one pass.

        Args:
            data: Bytes to interpret.
            scaling: Optional linear scaling producing a physical value.
            formula: Optional custom formula overriding *scaling*.
        """
        result = ConversionResult(raw=bytes(data))
        if not data:
            return result
        values: dict[str, Any] = {
            "HEX": self.hex.convert(data, separator=HexSeparator.SPACE),
            "HEX_0x": self.hex.convert(data, separator=HexSeparator.NONE, prefix=True),
            "ASCII": self.ascii.convert(data),
            "BIN": self.binary.convert(data),
            "DEC_BYTES": self.decimal.per_byte(data),
        }
        if len(data) <= 8:
            values["DEC_UNSIGNED_BE"] = self.decimal.convert(data, byte_order=ByteOrder.BIG_ENDIAN)
            values["DEC_UNSIGNED_LE"] = self.decimal.convert(
                data, byte_order=ByteOrder.LITTLE_ENDIAN
            )
            values["DEC_SIGNED_BE"] = self.decimal.convert(
                data, byte_order=ByteOrder.BIG_ENDIAN, signed=True
            )
            values["DEC_SIGNED_LE"] = self.decimal.convert(
                data, byte_order=ByteOrder.LITTLE_ENDIAN, signed=True
            )
        if len(data) >= 2:
            values["UINT16_BE"] = self.decimal.per_word(data, 2, ByteOrder.BIG_ENDIAN)
            values["UINT16_LE"] = self.decimal.per_word(data, 2, ByteOrder.LITTLE_ENDIAN)
        if len(data) >= 4:
            values["UINT32_BE"] = self.decimal.per_word(data, 4, ByteOrder.BIG_ENDIAN)
            values["UINT32_LE"] = self.decimal.per_word(data, 4, ByteOrder.LITTLE_ENDIAN)
        float_be = self.float.try_convert(data, ByteOrder.BIG_ENDIAN)
        if float_be is not None:
            values["FLOAT_BE"] = float_be
            values["FLOAT_LE"] = self.float.try_convert(data, ByteOrder.LITTLE_ENDIAN)
        try:
            values["BCD"] = self.bcd.to_digits(data)
        except Exception:  # noqa: BLE001 - BCD is optional
            values["BCD"] = ""
        result.values = values

        if formula:
            try:
                converter = CustomFormulaConverter(formula)
                result.physical = converter.convert(data)
            except ValueError as exc:
                _logger.debug("formula evaluation failed: %s", exc)
        elif scaling is not None:
            result.physical = self.physical.convert(data, rule=scaling)
            result.unit = scaling.unit
        return result

    def convert_text(
        self,
        text: str,
        source: DataFormat | str = DataFormat.HEX,
        scaling: ScalingRule | None = None,
    ) -> ConversionResult:
        """Parse *text* and return every representation of the parsed bytes."""
        return self.convert_all(self.parse(text, source), scaling)

    @staticmethod
    def detect_format(text: str) -> DataFormat:
        """Guess the format of *text*.

        Example:
            >>> DataConverter.detect_format("01000001")
            <DataFormat.BIN: 'BIN'>
            >>> DataConverter.detect_format("0x41 0x42")
            <DataFormat.HEX: 'HEX'>
        """
        candidate = text.strip()
        if not candidate:
            return DataFormat.HEX
        compact = candidate.replace(" ", "")
        if compact.lower().startswith("0x"):
            return DataFormat.HEX
        if set(compact) <= set("01") and len(compact) % 8 == 0:
            return DataFormat.BIN
        if compact.isdigit():
            return DataFormat.DEC_UNSIGNED
        if all(ch in "0123456789abcdefABCDEF" for ch in compact):
            return DataFormat.HEX
        return DataFormat.ASCII


__all__ = ["DataConverter", "ConversionResult", "ScalingRule"]
