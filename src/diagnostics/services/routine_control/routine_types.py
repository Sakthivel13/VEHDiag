"""Routine control sub-functions and well known routine identifiers."""
from __future__ import annotations

from dataclasses import dataclass

from ....core.enums.session_enums import RoutineControlType

#: Routine identifiers standardised by ISO 14229-1.
STANDARD_ROUTINES: dict[int, str] = {
    0x0202: "Erase memory",
    0x0203: "Check programming dependencies",
    0xFF00: "Erase memory (OBD)",
    0xFF01: "Check programming dependencies (OBD)",
    0xFF02: "Erase mirror memory DTCs",
}


@dataclass(slots=True)
class RoutineDescriptor:
    """UI friendly description of a routine."""

    routine_id: int
    name: str = ""
    description: str = ""
    option_hint: str = ""

    @property
    def hex_id(self) -> str:
        """Return the routine identifier as ``"0202"``."""
        return f"{self.routine_id:04X}"

    @property
    def label(self) -> str:
        """Return ``"0202 - Erase memory"`` for the drop-down."""
        return f"{self.hex_id} - {self.name}" if self.name else self.hex_id


def describe_routine(routine_id: int) -> RoutineDescriptor:
    """Return a descriptor for *routine_id*."""
    return RoutineDescriptor(
        routine_id=routine_id,
        name=STANDARD_ROUTINES.get(routine_id, "Manufacturer specific routine"),
    )


def sub_function_label(sub_function: int) -> str:
    """Return the readable name of a routine control sub-function.

    Example:
        >>> sub_function_label(0x01)
        'startRoutine'
    """
    mapping = {
        int(RoutineControlType.START_ROUTINE): "startRoutine",
        int(RoutineControlType.STOP_ROUTINE): "stopRoutine",
        int(RoutineControlType.REQUEST_ROUTINE_RESULTS): "requestRoutineResults",
    }
    return mapping.get(sub_function, f"reserved (0x{sub_function:02X})")


__all__ = [
    "STANDARD_ROUTINES",
    "RoutineDescriptor",
    "describe_routine",
    "sub_function_label",
]
