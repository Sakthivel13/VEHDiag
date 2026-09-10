"""Diagnostic session and reset related enumerations."""
from __future__ import annotations

from enum import Enum, IntEnum


class SessionType(IntEnum):
    """Standardised diagnostic session types (SID 0x10 sub-functions)."""

    DEFAULT = 0x01
    PROGRAMMING = 0x02
    EXTENDED_DIAGNOSTIC = 0x03
    SAFETY_SYSTEM_DIAGNOSTIC = 0x04

    @property
    def pretty_name(self) -> str:
        """Return the ISO style session name."""
        return {
            SessionType.DEFAULT: "defaultSession",
            SessionType.PROGRAMMING: "programmingSession",
            SessionType.EXTENDED_DIAGNOSTIC: "extendedDiagnosticSession",
            SessionType.SAFETY_SYSTEM_DIAGNOSTIC: "safetySystemDiagnosticSession",
        }[self]

    @property
    def requires_tester_present(self) -> bool:
        """Return ``True`` when the session must be kept alive with SID 0x3E."""
        return self is not SessionType.DEFAULT


def session_name(sub_function: int) -> str:
    """Return a readable name for any session *sub_function* byte."""
    known = SessionType.__members__.values()
    for session in known:
        if int(session) == sub_function:
            return session.pretty_name
    if 0x40 <= sub_function <= 0x5F:
        return f"vehicleManufacturerSpecificSession (0x{sub_function:02X})"
    if 0x60 <= sub_function <= 0x7E:
        return f"systemSupplierSpecificSession (0x{sub_function:02X})"
    return f"reservedSession (0x{sub_function:02X})"


class ResetType(IntEnum):
    """ECUReset (SID 0x11) sub-functions."""

    HARD_RESET = 0x01
    KEY_OFF_ON_RESET = 0x02
    SOFT_RESET = 0x03
    ENABLE_RAPID_POWER_SHUTDOWN = 0x04
    DISABLE_RAPID_POWER_SHUTDOWN = 0x05

    @property
    def pretty_name(self) -> str:
        """Return the ISO style reset name."""
        words = self.name.split("_")
        return words[0].lower() + "".join(w.capitalize() for w in words[1:])


class SecurityState(str, Enum):
    """Security access state of the connected ECU."""

    LOCKED = "LOCKED"
    SEED_REQUESTED = "SEED_REQUESTED"
    UNLOCKED = "UNLOCKED"
    DELAY_ACTIVE = "DELAY_ACTIVE"


class RoutineControlType(IntEnum):
    """RoutineControl (SID 0x31) sub-functions."""

    START_ROUTINE = 0x01
    STOP_ROUTINE = 0x02
    REQUEST_ROUTINE_RESULTS = 0x03


class IOControlParameter(IntEnum):
    """InputOutputControlByIdentifier (SID 0x2F) control parameters."""

    RETURN_CONTROL_TO_ECU = 0x00
    RESET_TO_DEFAULT = 0x01
    FREEZE_CURRENT_STATE = 0x02
    SHORT_TERM_ADJUSTMENT = 0x03


class CommunicationControlType(IntEnum):
    """CommunicationControl (SID 0x28) sub-functions."""

    ENABLE_RX_AND_TX = 0x00
    ENABLE_RX_DISABLE_TX = 0x01
    DISABLE_RX_ENABLE_TX = 0x02
    DISABLE_RX_AND_TX = 0x03


class DTCSettingType(IntEnum):
    """ControlDTCSetting (SID 0x85) sub-functions."""

    ON = 0x01
    OFF = 0x02


__all__ = [
    "SessionType",
    "session_name",
    "ResetType",
    "SecurityState",
    "RoutineControlType",
    "IOControlParameter",
    "CommunicationControlType",
    "DTCSettingType",
]
