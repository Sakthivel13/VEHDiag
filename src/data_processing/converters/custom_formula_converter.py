"""User defined formula evaluation.

Formulas are evaluated in a restricted namespace: only arithmetic, a handful of
maths functions and the variables ``raw``/``x`` are available, so a formula
typed into the UI cannot access the file system or import modules.
"""
from __future__ import annotations

import math
from typing import Any

from ...core.enums.data_format_enums import ByteOrder, DataFormat
from ...core.interfaces.i_data_converter import IDataConverter

#: Names a formula may reference.
SAFE_NAMES: dict[str, Any] = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "pow": pow,
    "int": int,
    "float": float,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
}


class CustomFormulaConverter(IDataConverter):
    """Evaluate a user supplied formula on the raw value.

    Example:
        >>> converter = CustomFormulaConverter("raw * 0.1 - 40")
        >>> converter.convert(bytes([200]))
        -20.0
    """

    def __init__(self, formula: str = "raw", unit: str = "", decimals: int = 3) -> None:
        """Store the formula and the presentation options."""
        self.formula = formula
        self.unit = unit
        self.decimals = decimals

    def convert(self, data: bytes, **options: Any) -> float:
        """Evaluate the formula for *data*.

        Args:
            data: Raw bytes to interpret.
            **options: ``formula`` override, ``byte_order`` and ``signed``.

        Raises:
            ValueError: The formula is invalid or references unknown names.
        """
        order = options.get("byte_order", ByteOrder.BIG_ENDIAN)
        endianness = order.int_byteorder if isinstance(order, ByteOrder) else str(order)
        raw = int.from_bytes(data, endianness, signed=bool(options.get("signed", False))) if data else 0
        return self.evaluate(raw, str(options.get("formula", self.formula)))

    def evaluate(self, raw: float, formula: str | None = None) -> float:
        """Evaluate *formula* with ``raw`` bound to the given value.

        Raises:
            ValueError: The formula could not be evaluated safely.
        """
        expression = formula if formula is not None else self.formula
        namespace = dict(SAFE_NAMES)
        namespace.update({"raw": raw, "x": raw, "value": raw})
        try:
            result = eval(expression, {"__builtins__": {}}, namespace)  # noqa: S307
        except Exception as exc:  # noqa: BLE001 - user supplied expression
            raise ValueError(f"invalid formula {expression!r}: {exc}") from exc
        try:
            return float(result)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"the formula did not produce a number: {result!r}") from exc

    def to_bytes(self, value: Any, **options: Any) -> bytes:
        """Formulas are not generally invertible.

        Raises:
            ValueError: Always; use :class:`PhysicalValueConverter` instead.
        """
        raise ValueError("a custom formula cannot be inverted automatically")

    def get_supported_formats(self) -> list[DataFormat]:
        """Return ``[DataFormat.PHYSICAL]``."""
        return [DataFormat.PHYSICAL]

    def validate_input(self, data: bytes, **options: Any) -> None:
        """Verify the formula parses by evaluating it with a dummy value.

        Raises:
            ValueError: The formula is invalid.
        """
        self.evaluate(0.0, str(options.get("formula", self.formula)))

    def format(self, data: bytes, **options: Any) -> str:
        """Return the evaluated value with its unit."""
        value = self.convert(data, **options)
        return f"{value:.{self.decimals}f} {self.unit}".strip()


__all__ = ["CustomFormulaConverter", "SAFE_NAMES"]
