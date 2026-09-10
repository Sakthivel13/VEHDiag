"""Diagnostic session helpers."""
from __future__ import annotations

from dataclasses import dataclass

from ....core.enums.session_enums import SessionType, session_name


@dataclass(slots=True)
class SessionDescriptor:
    """UI friendly description of one selectable session."""

    value: int
    label: str
    description: str = ""
    requires_tester_present: bool = False

    @property
    def hex_value(self) -> str:
        """Return the sub-function as ``"0x03"``."""
        return f"0x{self.value:02X}"


#: Sessions offered in the session type drop-down.
STANDARD_SESSIONS: tuple[SessionDescriptor, ...] = (
    SessionDescriptor(
        int(SessionType.DEFAULT),
        "Default session",
        "Read-only diagnostics; no keep-alive required.",
        False,
    ),
    SessionDescriptor(
        int(SessionType.PROGRAMMING),
        "Programming session",
        "Bootloader session used for flashing.",
        True,
    ),
    SessionDescriptor(
        int(SessionType.EXTENDED_DIAGNOSTIC),
        "Extended diagnostic session",
        "Full diagnostic access including actuator tests.",
        True,
    ),
    SessionDescriptor(
        int(SessionType.SAFETY_SYSTEM_DIAGNOSTIC),
        "Safety system diagnostic session",
        "Access to safety relevant functions.",
        True,
    ),
)


def describe_session(sub_function: int) -> SessionDescriptor:
    """Return a descriptor for any session sub-function."""
    for descriptor in STANDARD_SESSIONS:
        if descriptor.value == sub_function:
            return descriptor
    return SessionDescriptor(
        sub_function,
        session_name(sub_function),
        "Manufacturer or supplier specific session.",
        True,
    )


def is_manufacturer_specific(sub_function: int) -> bool:
    """Return ``True`` for the 0x40..0x5F vehicle manufacturer range."""
    return 0x40 <= sub_function <= 0x5F


def is_supplier_specific(sub_function: int) -> bool:
    """Return ``True`` for the 0x60..0x7E system supplier range."""
    return 0x60 <= sub_function <= 0x7E


__all__ = [
    "SessionDescriptor",
    "STANDARD_SESSIONS",
    "describe_session",
    "is_manufacturer_specific",
    "is_supplier_specific",
]
