"""Suppress positive response bit handling (bit 7 of the sub-function)."""
from __future__ import annotations

from ..core.enums.sid_enums import SUPPRESS_POS_RSP_BIT, ServiceID

#: Services whose second byte is a sub-function and therefore support the bit.
SUB_FUNCTION_SERVICES: frozenset[int] = frozenset(
    {
        ServiceID.DIAGNOSTIC_SESSION_CONTROL,
        ServiceID.ECU_RESET,
        ServiceID.READ_DTC_INFORMATION,
        ServiceID.SECURITY_ACCESS,
        ServiceID.COMMUNICATION_CONTROL,
        ServiceID.AUTHENTICATION,
        ServiceID.READ_DATA_BY_PERIODIC_IDENTIFIER,
        ServiceID.DYNAMICALLY_DEFINE_DATA_IDENTIFIER,
        ServiceID.ROUTINE_CONTROL,
        ServiceID.TESTER_PRESENT,
        ServiceID.ACCESS_TIMING_PARAMETER,
        ServiceID.CONTROL_DTC_SETTING,
        ServiceID.RESPONSE_ON_EVENT,
        ServiceID.LINK_CONTROL,
    }
)


def supports_suppression(service_id: int) -> bool:
    """Return ``True`` when *service_id* carries a sub-function byte.

    Example:
        >>> supports_suppression(0x3E)
        True
        >>> supports_suppression(0x22)
        False
    """
    return service_id in SUB_FUNCTION_SERVICES


def apply_suppression(payload: bytes, suppress: bool = True) -> bytes:
    """Return *payload* with the suppress positive response bit set or cleared.

    Args:
        payload: Complete request starting with the SID.
        suppress: Set the bit when ``True``, clear it when ``False``.

    Returns:
        The modified payload, unchanged when the service has no sub-function.

    Example:
        >>> apply_suppression(bytes.fromhex("3E00")).hex().upper()
        '3E80'
        >>> apply_suppression(bytes.fromhex("3E80"), False).hex().upper()
        '3E00'
    """
    if len(payload) < 2 or not supports_suppression(payload[0]):
        return payload
    sub = payload[1]
    sub = (sub | SUPPRESS_POS_RSP_BIT) if suppress else (sub & ~SUPPRESS_POS_RSP_BIT)
    return bytes([payload[0], sub & 0xFF]) + payload[2:]


def is_suppressed(payload: bytes) -> bool:
    """Return ``True`` when the request asks the ECU not to answer.

    Example:
        >>> is_suppressed(bytes.fromhex("3E80"))
        True
    """
    if len(payload) < 2 or not supports_suppression(payload[0]):
        return False
    return bool(payload[1] & SUPPRESS_POS_RSP_BIT)


def strip_suppression_bit(sub_function: int) -> int:
    """Return *sub_function* with the suppression bit removed."""
    return sub_function & ~SUPPRESS_POS_RSP_BIT & 0xFF


__all__ = [
    "SUB_FUNCTION_SERVICES",
    "supports_suppression",
    "apply_suppression",
    "is_suppressed",
    "strip_suppression_bit",
]
