"""SAE J1939 Suspect Parameter Number definitions and decoding."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(slots=True)
class SPNDefinition:
    """Scaling information for one suspect parameter number.

    Attributes:
        spn: Suspect parameter number.
        name: Human readable signal name.
        start_bit: Bit offset inside the PGN payload.
        bit_length: Signal width in bits.
        factor: Scaling factor applied to the raw value.
        offset: Offset added after scaling.
        unit: Engineering unit.
    """

    spn: int
    name: str
    start_bit: int = 0
    bit_length: int = 8
    factor: float = 1.0
    offset: float = 0.0
    unit: str = ""

    def decode(self, data: bytes) -> float:
        """Extract and scale the signal from a PGN payload.

        Example:
            >>> SPNDefinition(190, "Engine speed", 24, 16, 0.125).decode(
            ...     bytes.fromhex("0000001027000000"))
            1250.0
        """
        from ....utils.byte_utils import extract_bits

        byte_index, bit_offset = divmod(self.start_bit, 8)
        if self.bit_length in (8, 16, 32) and bit_offset == 0:
            chunk = data[byte_index : byte_index + self.bit_length // 8]
            raw = int.from_bytes(chunk, "little") if chunk else 0
        else:
            raw = extract_bits(data, self.start_bit, self.bit_length)
        return raw * self.factor + self.offset


#: A small catalogue of frequently used SPNs.
COMMON_SPNS: Final[dict[int, SPNDefinition]] = {
    84: SPNDefinition(84, "Wheel based vehicle speed", 8, 16, 1 / 256, 0.0, "km/h"),
    91: SPNDefinition(91, "Accelerator pedal position", 8, 8, 0.4, 0.0, "%"),
    92: SPNDefinition(92, "Engine percent load", 16, 8, 1.0, 0.0, "%"),
    102: SPNDefinition(102, "Boost pressure", 8, 8, 2.0, 0.0, "kPa"),
    110: SPNDefinition(110, "Engine coolant temperature", 0, 8, 1.0, -40.0, "degC"),
    174: SPNDefinition(174, "Fuel temperature", 8, 8, 1.0, -40.0, "degC"),
    190: SPNDefinition(190, "Engine speed", 24, 16, 0.125, 0.0, "rpm"),
    247: SPNDefinition(247, "Engine total hours of operation", 0, 32, 0.05, 0.0, "h"),
    513: SPNDefinition(513, "Actual engine percent torque", 16, 8, 1.0, -125.0, "%"),
}


def decode_dtc(payload: bytes) -> tuple[int, int, int, int]:
    """Decode a four byte J1939 DTC into ``(spn, fmi, oc, cm)``.

    Args:
        payload: The four DTC bytes from a DM1/DM2 message.

    Returns:
        Tuple of suspect parameter number, failure mode identifier,
        occurrence count and conversion method.

    Raises:
        ValueError: Fewer than four bytes were supplied.

    Example:
        >>> decode_dtc(bytes.fromhex("EE0004 01".replace(" ", "")))
        (238, 4, 1, 0)
    """
    if len(payload) < 4:
        raise ValueError("a J1939 DTC needs four bytes")
    spn = payload[0] | (payload[1] << 8) | ((payload[2] & 0xE0) << 11)
    fmi = payload[2] & 0x1F
    occurrence = payload[3] & 0x7F
    conversion = (payload[3] >> 7) & 0x01
    return spn, fmi, occurrence, conversion


#: Failure mode identifier descriptions.
FMI_TEXT: Final[dict[int, str]] = {
    0: "data valid but above normal operating range (most severe)",
    1: "data valid but below normal operating range (most severe)",
    2: "data erratic, intermittent or incorrect",
    3: "voltage above normal or shorted high",
    4: "voltage below normal or shorted low",
    5: "current below normal or open circuit",
    6: "current above normal or grounded circuit",
    7: "mechanical system not responding properly",
    8: "abnormal frequency, pulse width or period",
    9: "abnormal update rate",
    10: "abnormal rate of change",
    11: "root cause not known",
    12: "bad intelligent device or component",
    13: "out of calibration",
    14: "special instructions",
    15: "data valid but above normal operating range (least severe)",
    31: "condition exists",
}


def describe_fmi(fmi: int) -> str:
    """Return a readable description of a failure mode identifier."""
    return FMI_TEXT.get(fmi, f"FMI {fmi}")


__all__ = ["SPNDefinition", "COMMON_SPNS", "decode_dtc", "describe_fmi", "FMI_TEXT"]
