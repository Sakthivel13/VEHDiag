"""Negative Response Code (NRC) enumerations and helpers (ISO 14229-1)."""
from __future__ import annotations

from enum import IntEnum
from typing import Final


class NegativeResponseCode(IntEnum):
    """Standardised UDS negative response codes."""

    POSITIVE_RESPONSE = 0x00
    GENERAL_REJECT = 0x10
    SERVICE_NOT_SUPPORTED = 0x11
    SUB_FUNCTION_NOT_SUPPORTED = 0x12
    INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT = 0x13
    RESPONSE_TOO_LONG = 0x14
    BUSY_REPEAT_REQUEST = 0x21
    CONDITIONS_NOT_CORRECT = 0x22
    REQUEST_SEQUENCE_ERROR = 0x24
    NO_RESPONSE_FROM_SUBNET_COMPONENT = 0x25
    FAILURE_PREVENTS_EXECUTION_OF_REQUESTED_ACTION = 0x26
    REQUEST_OUT_OF_RANGE = 0x31
    SECURITY_ACCESS_DENIED = 0x33
    AUTHENTICATION_REQUIRED = 0x34
    INVALID_KEY = 0x35
    EXCEEDED_NUMBER_OF_ATTEMPTS = 0x36
    REQUIRED_TIME_DELAY_NOT_EXPIRED = 0x37
    SECURE_DATA_TRANSMISSION_REQUIRED = 0x38
    SECURE_DATA_TRANSMISSION_NOT_ALLOWED = 0x39
    SECURE_DATA_VERIFICATION_FAILED = 0x3A
    UPLOAD_DOWNLOAD_NOT_ACCEPTED = 0x70
    TRANSFER_DATA_SUSPENDED = 0x71
    GENERAL_PROGRAMMING_FAILURE = 0x72
    WRONG_BLOCK_SEQUENCE_COUNTER = 0x73
    REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING = 0x78
    SUB_FUNCTION_NOT_SUPPORTED_IN_ACTIVE_SESSION = 0x7E
    SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION = 0x7F
    RPM_TOO_HIGH = 0x81
    RPM_TOO_LOW = 0x82
    ENGINE_IS_RUNNING = 0x83
    ENGINE_IS_NOT_RUNNING = 0x84
    ENGINE_RUN_TIME_TOO_LOW = 0x85
    TEMPERATURE_TOO_HIGH = 0x86
    TEMPERATURE_TOO_LOW = 0x87
    VEHICLE_SPEED_TOO_HIGH = 0x88
    VEHICLE_SPEED_TOO_LOW = 0x89
    THROTTLE_PEDAL_TOO_HIGH = 0x8A
    THROTTLE_PEDAL_TOO_LOW = 0x8B
    TRANSMISSION_RANGE_NOT_IN_NEUTRAL = 0x8C
    TRANSMISSION_RANGE_NOT_IN_GEAR = 0x8D
    BRAKE_SWITCHES_NOT_CLOSED = 0x8F
    SHIFTER_LEVER_NOT_IN_PARK = 0x90
    TORQUE_CONVERTER_CLUTCH_LOCKED = 0x91
    VOLTAGE_TOO_HIGH = 0x92
    VOLTAGE_TOO_LOW = 0x93

    @property
    def pretty_name(self) -> str:
        """Return the ISO style lowerCamelCase name."""
        words = self.name.split("_")
        return words[0].lower() + "".join(w.capitalize() for w in words[1:])

    @property
    def description(self) -> str:
        """Return a user friendly explanation of the code."""
        return NRC_DESCRIPTIONS.get(int(self), "Manufacturer or reserved specific code.")

    @property
    def recovery_hint(self) -> str:
        """Return a suggested corrective action for the operator."""
        return NRC_RECOVERY_HINTS.get(int(self), "Check the request and the ECU state, then retry.")

    @classmethod
    def from_byte(cls, value: int) -> "NegativeResponseCode | None":
        """Return the code for *value*, or ``None`` when not standardised."""
        try:
            return cls(value)
        except ValueError:
            return None


NRC_DESCRIPTIONS: Final[dict[int, str]] = {
    0x10: "General reject - the ECU refused the request without a more specific reason.",
    0x11: "The requested service is not supported by this ECU.",
    0x12: "The sub-function of the requested service is not supported.",
    0x13: "The request message length is wrong or the format is invalid.",
    0x14: "The response would be longer than the transport protocol allows.",
    0x21: "The ECU is busy; repeat the request later.",
    0x22: "The ECU conditions do not allow the requested action right now.",
    0x24: "The request arrived out of the required sequence.",
    0x25: "A sub-network component did not respond.",
    0x26: "A failure in the ECU prevents execution of the requested action.",
    0x31: "A parameter of the request is out of range or unknown (e.g. unsupported DID).",
    0x33: "Security access is required before this service may be used.",
    0x34: "Authentication (SID 0x29) is required before this service may be used.",
    0x35: "The key sent during security access was invalid.",
    0x36: "Too many invalid key attempts; the ECU locked the security level.",
    0x37: "The mandatory delay after failed security attempts has not expired.",
    0x38: "The request must be sent via secured data transmission.",
    0x39: "Secured data transmission is not allowed in the current state.",
    0x3A: "Verification of the secured data failed.",
    0x70: "The ECU refused the upload/download request.",
    0x71: "Data transfer was suspended by the ECU.",
    0x72: "A general error occurred while programming the memory.",
    0x73: "The block sequence counter of TransferData was wrong.",
    0x78: "Request received correctly; the response is still pending.",
    0x7E: "Sub-function is not supported in the currently active session.",
    0x7F: "Service is not supported in the currently active session.",
    0x81: "Engine RPM is above the allowed range for this action.",
    0x82: "Engine RPM is below the allowed range for this action.",
    0x83: "The engine is running; stop the engine to continue.",
    0x84: "The engine is not running; start the engine to continue.",
    0x92: "Supply voltage is too high for the requested action.",
    0x93: "Supply voltage is too low for the requested action.",
}

NRC_RECOVERY_HINTS: Final[dict[int, str]] = {
    0x11: "Verify the ECU supports this service, or check the addressing (TX/RX IDs).",
    0x12: "Check the sub-function byte against the ECU specification.",
    0x13: "Verify the payload length and byte order of the request.",
    0x21: "Automatic retry is applied; increase the retry delay if it persists.",
    0x22: "Check preconditions: ignition on, vehicle stationary, engine off, etc.",
    0x24: "Send the prerequisite requests first (e.g. RequestDownload before TransferData).",
    0x31: "Check the DID / routine ID / memory address is supported by the ECU.",
    0x33: "Run SecurityAccess (SID 0x27) for the required level first.",
    0x35: "Verify the seed-key algorithm, the key length and the security level.",
    0x36: "Power-cycle the ECU or wait for the lockout to clear.",
    0x37: "Wait for the delay timer to expire before requesting a new seed.",
    0x73: "Restart the transfer; the block sequence counter is out of sync.",
    0x78: "No action needed - the client waits automatically up to P2*.",
    0x7E: "Switch to an extended or programming session first.",
    0x7F: "Switch to an extended or programming session first.",
}

#: NRCs for which an automatic retry is sensible.
RETRYABLE_NRCS: Final[frozenset[int]] = frozenset(
    {
        NegativeResponseCode.BUSY_REPEAT_REQUEST,
        NegativeResponseCode.REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING,
    }
)


def describe_nrc(value: int) -> str:
    """Return ``"0x33 securityAccessDenied - ..."`` style text for *value*."""
    code = NegativeResponseCode.from_byte(value)
    if code is None:
        return f"0x{value:02X} unknownNegativeResponseCode - manufacturer specific or reserved."
    return f"0x{value:02X} {code.pretty_name} - {code.description}"


__all__ = [
    "NegativeResponseCode",
    "NRC_DESCRIPTIONS",
    "NRC_RECOVERY_HINTS",
    "RETRYABLE_NRCS",
    "describe_nrc",
]
