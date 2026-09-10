"""DoIP (ISO 13400-2) message structures."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Final

from ....core.exceptions import FramingError

#: Length of the fixed DoIP header in bytes.
HEADER_LENGTH: Final[int] = 8

#: Protocol version used by ISO 13400-2:2012 and later.
PROTOCOL_VERSION: Final[int] = 0x02


class PayloadType(IntEnum):
    """DoIP payload types."""

    GENERIC_NEGATIVE_ACK = 0x0000
    VEHICLE_IDENTIFICATION_REQUEST = 0x0001
    VEHICLE_IDENTIFICATION_REQUEST_EID = 0x0002
    VEHICLE_IDENTIFICATION_REQUEST_VIN = 0x0003
    VEHICLE_ANNOUNCEMENT = 0x0004
    ROUTING_ACTIVATION_REQUEST = 0x0005
    ROUTING_ACTIVATION_RESPONSE = 0x0006
    ALIVE_CHECK_REQUEST = 0x0007
    ALIVE_CHECK_RESPONSE = 0x0008
    ENTITY_STATUS_REQUEST = 0x4001
    ENTITY_STATUS_RESPONSE = 0x4002
    POWER_MODE_REQUEST = 0x4003
    POWER_MODE_RESPONSE = 0x4004
    DIAGNOSTIC_MESSAGE = 0x8001
    DIAGNOSTIC_MESSAGE_ACK = 0x8002
    DIAGNOSTIC_MESSAGE_NACK = 0x8003

    @property
    def pretty_name(self) -> str:
        """Return the lowerCamelCase ISO name of the payload type."""
        words = self.name.split("_")
        return words[0].lower() + "".join(w.capitalize() for w in words[1:])


class RoutingActivationResponseCode(IntEnum):
    """Response codes of the routing activation response."""

    UNKNOWN_SOURCE_ADDRESS = 0x00
    ALL_SOCKETS_REGISTERED = 0x01
    SOURCE_ADDRESS_MISMATCH = 0x02
    SOURCE_ADDRESS_IN_USE = 0x03
    SOCKET_ALREADY_ACTIVATED = 0x04
    MISSING_AUTHENTICATION = 0x05
    REJECTED_CONFIRMATION = 0x06
    UNSUPPORTED_ACTIVATION_TYPE = 0x07
    SUCCESS = 0x10
    SUCCESS_PENDING_CONFIRMATION = 0x11

    @property
    def is_success(self) -> bool:
        """Return ``True`` for the two positive outcomes."""
        return self in (
            RoutingActivationResponseCode.SUCCESS,
            RoutingActivationResponseCode.SUCCESS_PENDING_CONFIRMATION,
        )


class NackCode(IntEnum):
    """Generic DoIP header negative acknowledge codes."""

    INCORRECT_PATTERN_FORMAT = 0x00
    UNKNOWN_PAYLOAD_TYPE = 0x01
    MESSAGE_TOO_LARGE = 0x02
    OUT_OF_MEMORY = 0x03
    INVALID_PAYLOAD_LENGTH = 0x04


@dataclass(slots=True)
class DoIPMessage:
    """A complete DoIP message.

    Attributes:
        payload_type: Type of the payload.
        payload: Payload bytes following the eight byte header.
        protocol_version: Protocol version byte.
    """

    payload_type: int
    payload: bytes = b""
    protocol_version: int = PROTOCOL_VERSION

    def to_bytes(self) -> bytes:
        """Serialise the message including its header.

        Example:
            >>> DoIPMessage(PayloadType.ALIVE_CHECK_REQUEST).to_bytes().hex()
            '02fd000700000000'
        """
        header = bytes(
            [
                self.protocol_version & 0xFF,
                (~self.protocol_version) & 0xFF,
                (self.payload_type >> 8) & 0xFF,
                self.payload_type & 0xFF,
            ]
        ) + len(self.payload).to_bytes(4, "big")
        return header + self.payload

    @classmethod
    def from_bytes(cls, raw: bytes) -> "DoIPMessage":
        """Parse a complete DoIP message.

        Raises:
            FramingError: The header is truncated, the inverse version byte is
                wrong or the declared length does not match the payload.
        """
        if len(raw) < HEADER_LENGTH:
            raise FramingError(f"DoIP message shorter than the header ({len(raw)} bytes)")
        version, inverse = raw[0], raw[1]
        if (version ^ 0xFF) != inverse:
            raise FramingError(
                "DoIP protocol version pattern mismatch",
                {"version": f"0x{version:02X}", "inverse": f"0x{inverse:02X}"},
            )
        payload_type = int.from_bytes(raw[2:4], "big")
        length = int.from_bytes(raw[4:8], "big")
        payload = raw[HEADER_LENGTH : HEADER_LENGTH + length]
        if len(payload) != length:
            raise FramingError(
                "DoIP payload length mismatch",
                {"declared": length, "received": len(payload)},
            )
        return cls(payload_type=payload_type, payload=bytes(payload), protocol_version=version)

    @property
    def type_name(self) -> str:
        """Return the readable payload type name."""
        try:
            return PayloadType(self.payload_type).pretty_name
        except ValueError:
            return f"unknown(0x{self.payload_type:04X})"

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"DoIP {self.type_name} [{len(self.payload)}]"


def build_diagnostic_message(source: int, target: int, uds_payload: bytes) -> DoIPMessage:
    """Wrap a UDS payload into a DoIP diagnostic message.

    Example:
        >>> msg = build_diagnostic_message(0x0E00, 0x1000, bytes.fromhex("1003"))
        >>> msg.payload.hex()
        '0e0010001003'
    """
    payload = source.to_bytes(2, "big") + target.to_bytes(2, "big") + uds_payload
    return DoIPMessage(PayloadType.DIAGNOSTIC_MESSAGE, payload)


def build_routing_activation(source: int, activation_type: int = 0x00, oem: bytes = b"") -> DoIPMessage:
    """Build a routing activation request.

    Example:
        >>> build_routing_activation(0x0E00).payload.hex()
        '0e000000000000'
    """
    payload = source.to_bytes(2, "big") + bytes([activation_type]) + b"\x00\x00\x00\x00" + oem
    return DoIPMessage(PayloadType.ROUTING_ACTIVATION_REQUEST, payload)


def parse_diagnostic_message(message: DoIPMessage) -> tuple[int, int, bytes]:
    """Split a diagnostic message into ``(source, target, uds_payload)``.

    Raises:
        FramingError: The payload is shorter than the two address fields.
    """
    if len(message.payload) < 4:
        raise FramingError("DoIP diagnostic message without address fields")
    source = int.from_bytes(message.payload[0:2], "big")
    target = int.from_bytes(message.payload[2:4], "big")
    return source, target, bytes(message.payload[4:])


__all__ = [
    "HEADER_LENGTH",
    "PROTOCOL_VERSION",
    "PayloadType",
    "RoutingActivationResponseCode",
    "NackCode",
    "DoIPMessage",
    "build_diagnostic_message",
    "build_routing_activation",
    "parse_diagnostic_message",
]
