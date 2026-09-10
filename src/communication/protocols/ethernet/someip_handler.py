"""Basic SOME/IP message support.

Only the header parsing and construction needed to observe SOME/IP traffic in
the trace viewer is implemented; full service discovery is out of scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Final

from ....core.exceptions import FramingError

#: Length of the SOME/IP header in bytes (including the length field).
HEADER_LENGTH: Final[int] = 16


class MessageType(IntEnum):
    """SOME/IP message types."""

    REQUEST = 0x00
    REQUEST_NO_RETURN = 0x01
    NOTIFICATION = 0x02
    RESPONSE = 0x80
    ERROR = 0x81


class ReturnCode(IntEnum):
    """SOME/IP return codes."""

    E_OK = 0x00
    E_NOT_OK = 0x01
    E_UNKNOWN_SERVICE = 0x02
    E_UNKNOWN_METHOD = 0x03
    E_NOT_READY = 0x04
    E_NOT_REACHABLE = 0x05
    E_TIMEOUT = 0x06
    E_WRONG_PROTOCOL_VERSION = 0x07
    E_WRONG_INTERFACE_VERSION = 0x08
    E_MALFORMED_MESSAGE = 0x09


@dataclass(slots=True)
class SomeIPMessage:
    """A SOME/IP message header plus payload."""

    service_id: int
    method_id: int
    client_id: int = 0
    session_id: int = 1
    protocol_version: int = 0x01
    interface_version: int = 0x01
    message_type: int = int(MessageType.REQUEST)
    return_code: int = int(ReturnCode.E_OK)
    payload: bytes = b""

    @property
    def message_id(self) -> int:
        """Return the combined 32-bit message identifier."""
        return (self.service_id << 16) | self.method_id

    @property
    def request_id(self) -> int:
        """Return the combined 32-bit request identifier."""
        return (self.client_id << 16) | self.session_id

    def to_bytes(self) -> bytes:
        """Serialise the message.

        Example:
            >>> SomeIPMessage(0x1234, 0x0001).to_bytes()[:4].hex()
            '12340001'
        """
        length = 8 + len(self.payload)
        return (
            self.message_id.to_bytes(4, "big")
            + length.to_bytes(4, "big")
            + self.request_id.to_bytes(4, "big")
            + bytes(
                [
                    self.protocol_version & 0xFF,
                    self.interface_version & 0xFF,
                    self.message_type & 0xFF,
                    self.return_code & 0xFF,
                ]
            )
            + self.payload
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "SomeIPMessage":
        """Parse a SOME/IP message.

        Raises:
            FramingError: The buffer is shorter than the header.
        """
        if len(raw) < HEADER_LENGTH:
            raise FramingError(f"SOME/IP message too short ({len(raw)} bytes)")
        message_id = int.from_bytes(raw[0:4], "big")
        length = int.from_bytes(raw[4:8], "big")
        request_id = int.from_bytes(raw[8:12], "big")
        return cls(
            service_id=message_id >> 16,
            method_id=message_id & 0xFFFF,
            client_id=request_id >> 16,
            session_id=request_id & 0xFFFF,
            protocol_version=raw[12],
            interface_version=raw[13],
            message_type=raw[14],
            return_code=raw[15],
            payload=bytes(raw[HEADER_LENGTH : 8 + length]),
        )

    def __str__(self) -> str:  # noqa: D105 - trivial
        try:
            kind = MessageType(self.message_type).name
        except ValueError:
            kind = f"0x{self.message_type:02X}"
        return f"SOME/IP {self.service_id:04X}.{self.method_id:04X} {kind} [{len(self.payload)}]"


__all__ = ["SomeIPMessage", "MessageType", "ReturnCode", "HEADER_LENGTH"]
