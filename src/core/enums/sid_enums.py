"""UDS Service Identifier (SID) enumerations (ISO 14229-1).

The :class:`ServiceID` enumeration carries the numeric request SID. Helper
functions provide the positive response SID, human readable names and the
session requirements for each service.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Final

#: Offset added to a request SID to obtain the positive response SID.
POSITIVE_RESPONSE_OFFSET: Final[int] = 0x40
#: First byte of every negative response.
NEGATIVE_RESPONSE_SID: Final[int] = 0x7F
#: Bit 7 of the sub-function byte suppresses the positive response.
SUPPRESS_POS_RSP_BIT: Final[int] = 0x80


class ServiceID(IntEnum):
    """All standardised UDS service identifiers."""

    # -- diagnostic and communication management -------------------------
    DIAGNOSTIC_SESSION_CONTROL = 0x10
    ECU_RESET = 0x11
    CLEAR_DIAGNOSTIC_INFORMATION = 0x14
    READ_DTC_INFORMATION = 0x19
    READ_DATA_BY_IDENTIFIER = 0x22
    READ_MEMORY_BY_ADDRESS = 0x23
    READ_SCALING_DATA_BY_IDENTIFIER = 0x24
    SECURITY_ACCESS = 0x27
    COMMUNICATION_CONTROL = 0x28
    AUTHENTICATION = 0x29
    READ_DATA_BY_PERIODIC_IDENTIFIER = 0x2A
    DYNAMICALLY_DEFINE_DATA_IDENTIFIER = 0x2C
    WRITE_DATA_BY_IDENTIFIER = 0x2E
    INPUT_OUTPUT_CONTROL_BY_IDENTIFIER = 0x2F
    ROUTINE_CONTROL = 0x31
    REQUEST_DOWNLOAD = 0x34
    REQUEST_UPLOAD = 0x35
    TRANSFER_DATA = 0x36
    REQUEST_TRANSFER_EXIT = 0x37
    REQUEST_FILE_TRANSFER = 0x38
    WRITE_MEMORY_BY_ADDRESS = 0x3D
    TESTER_PRESENT = 0x3E
    ACCESS_TIMING_PARAMETER = 0x83
    SECURED_DATA_TRANSMISSION = 0x84
    CONTROL_DTC_SETTING = 0x85
    RESPONSE_ON_EVENT = 0x86
    LINK_CONTROL = 0x87

    @property
    def response_id(self) -> int:
        """Return the positive response SID for this service."""
        return int(self) + POSITIVE_RESPONSE_OFFSET

    @property
    def pretty_name(self) -> str:
        """Return the CamelCase ISO name, e.g. ``ReadDataByIdentifier``."""
        return "".join(part.capitalize() for part in self.name.split("_"))

    @property
    def description(self) -> str:
        """Return a short human readable description."""
        return SID_DESCRIPTIONS.get(int(self), self.pretty_name)

    @classmethod
    def from_byte(cls, value: int) -> "ServiceID | None":
        """Return the :class:`ServiceID` for *value* or ``None`` if unknown."""
        try:
            return cls(value)
        except ValueError:
            return None


SID_DESCRIPTIONS: Final[dict[int, str]] = {
    0x10: "Switch the ECU into a different diagnostic session.",
    0x11: "Request an ECU reset (hard, key off/on or soft).",
    0x14: "Clear diagnostic information (DTCs) from ECU memory.",
    0x19: "Read diagnostic trouble code information.",
    0x22: "Read one or more data records by data identifier.",
    0x23: "Read ECU memory by physical address.",
    0x24: "Read scaling information for a data identifier.",
    0x27: "Request seed and send key to unlock a security level.",
    0x28: "Enable or disable transmission/reception of messages.",
    0x29: "Perform certificate/PKI based authentication.",
    0x2A: "Schedule periodic transmission of data records.",
    0x2C: "Dynamically define a data identifier.",
    0x2E: "Write a data record identified by a data identifier.",
    0x2F: "Substitute a value for an input/output signal.",
    0x31: "Start, stop or request results of a routine.",
    0x34: "Initiate a download of data to the ECU.",
    0x35: "Initiate an upload of data from the ECU.",
    0x36: "Transfer one data block during upload/download.",
    0x37: "Terminate a data transfer.",
    0x38: "Request a file system operation on the ECU.",
    0x3D: "Write ECU memory by physical address.",
    0x3E: "Keep a non-default diagnostic session alive.",
    0x83: "Read or change the P2/P2* communication timing.",
    0x84: "Transmit data protected by a security layer.",
    0x85: "Enable or disable the setting of DTCs.",
    0x86: "Configure event driven responses from the ECU.",
    0x87: "Change the baud rate of the diagnostic link.",
}


#: Services that are typically rejected in the default session.
NON_DEFAULT_SESSION_SERVICES: Final[frozenset[int]] = frozenset(
    {
        ServiceID.SECURITY_ACCESS,
        ServiceID.WRITE_DATA_BY_IDENTIFIER,
        ServiceID.WRITE_MEMORY_BY_ADDRESS,
        ServiceID.INPUT_OUTPUT_CONTROL_BY_IDENTIFIER,
        ServiceID.ROUTINE_CONTROL,
        ServiceID.REQUEST_DOWNLOAD,
        ServiceID.REQUEST_UPLOAD,
        ServiceID.TRANSFER_DATA,
        ServiceID.REQUEST_TRANSFER_EXIT,
        ServiceID.REQUEST_FILE_TRANSFER,
        ServiceID.CONTROL_DTC_SETTING,
        ServiceID.LINK_CONTROL,
    }
)

#: Services that require a preceding successful SecurityAccess.
SECURITY_REQUIRED_SERVICES: Final[frozenset[int]] = frozenset(
    {
        ServiceID.REQUEST_DOWNLOAD,
        ServiceID.REQUEST_UPLOAD,
        ServiceID.TRANSFER_DATA,
        ServiceID.REQUEST_TRANSFER_EXIT,
        ServiceID.WRITE_MEMORY_BY_ADDRESS,
    }
)


def is_positive_response(sid: int, response_first_byte: int) -> bool:
    """Return ``True`` when *response_first_byte* is the positive echo of *sid*."""
    return response_first_byte == (sid + POSITIVE_RESPONSE_OFFSET) & 0xFF


def request_sid_from_response(response_first_byte: int) -> int:
    """Return the request SID that produced a positive *response_first_byte*."""
    return (response_first_byte - POSITIVE_RESPONSE_OFFSET) & 0xFF


__all__ = [
    "POSITIVE_RESPONSE_OFFSET",
    "NEGATIVE_RESPONSE_SID",
    "SUPPRESS_POS_RSP_BIT",
    "ServiceID",
    "SID_DESCRIPTIONS",
    "NON_DEFAULT_SESSION_SERVICES",
    "SECURITY_REQUIRED_SERVICES",
    "is_positive_response",
    "request_sid_from_response",
]
