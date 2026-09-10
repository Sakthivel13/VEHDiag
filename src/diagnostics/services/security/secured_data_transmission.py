"""SecuredDataTransmission - SID 0x84."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)

#: Administrative parameter bit indicating a request message.
APAR_REQUEST = 0x0001
#: Administrative parameter bit requesting a signed response.
APAR_SIGNED_RESPONSE = 0x0002
#: Administrative parameter bit indicating the payload is encrypted.
APAR_ENCRYPTED = 0x0008


@dataclass(slots=True)
class SecuredMessage:
    """A message wrapped for secured transmission.

    Attributes:
        administrative_parameter: Bit field describing the protection applied.
        signature_encryption_calculation: Algorithm identifier byte.
        anti_replay_counter: Monotonic counter protecting against replays.
        internal_service_id: The SID of the protected request.
        payload: The protected request payload without its SID.
        signature: Message authentication code or signature.
    """

    administrative_parameter: int = APAR_REQUEST
    signature_encryption_calculation: int = 0x00
    anti_replay_counter: int = 0
    internal_service_id: int = 0x22
    payload: bytes = b""
    signature: bytes = b""

    def to_bytes(self) -> bytes:
        """Serialise the secured message body (without the 0x84 SID)."""
        return (
            self.administrative_parameter.to_bytes(2, "big")
            + bytes([self.signature_encryption_calculation & 0xFF])
            + self.anti_replay_counter.to_bytes(2, "big")
            + bytes([self.internal_service_id & 0xFF])
            + len(self.signature).to_bytes(2, "big")
            + self.payload
            + self.signature
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "SecuredMessage":
        """Parse a secured message body.

        Raises:
            RequestValidationError: The body is shorter than the header.
        """
        if len(raw) < 8:
            raise RequestValidationError("secured message shorter than its header")
        signature_length = int.from_bytes(raw[6:8], "big")
        body = raw[8:]
        payload = body[: len(body) - signature_length] if signature_length else body
        signature = body[len(body) - signature_length :] if signature_length else b""
        return cls(
            administrative_parameter=int.from_bytes(raw[0:2], "big"),
            signature_encryption_calculation=raw[2],
            anti_replay_counter=int.from_bytes(raw[3:5], "big"),
            internal_service_id=raw[5],
            payload=bytes(payload),
            signature=bytes(signature),
        )


class SecuredDataTransmission(BaseService):
    """Transmit a diagnostic request protected by a security layer."""

    service_id = int(ServiceID.SECURED_DATA_TRANSMISSION)
    min_request_length = 2
    has_sub_function = False

    def __init__(self, client) -> None:  # noqa: ANN001
        """Store the client and initialise the anti-replay counter."""
        super().__init__(client)
        self.counter = 0

    def build_request(self, inner_request: bytes, signature: bytes = b"", encrypted: bool = False) -> bytes:
        """Wrap *inner_request* into a secured data transmission request.

        Raises:
            RequestValidationError: The inner request is empty.
        """
        if not inner_request:
            raise RequestValidationError("SecuredDataTransmission needs an inner request")
        self.counter = (self.counter + 1) & 0xFFFF
        apar = APAR_REQUEST | (APAR_ENCRYPTED if encrypted else 0)
        message = SecuredMessage(
            administrative_parameter=apar,
            anti_replay_counter=self.counter,
            internal_service_id=inner_request[0],
            payload=bytes(inner_request[1:]),
            signature=signature,
        )
        return bytes([self.service_id]) + message.to_bytes()

    def parse_response(self, response: DiagnosticResponse) -> SecuredMessage:
        """Parse the secured response body."""
        raw = self.require_positive(response, min_length=9)
        return SecuredMessage.from_bytes(raw[1:])

    def execute(self, inner_request: bytes, signature: bytes = b"") -> SecuredMessage:
        """Send *inner_request* protected and return the secured answer."""
        payload = self.build_request(inner_request, signature)
        return self.parse_response(self.send(payload, timeout=5.0))


__all__ = [
    "SecuredDataTransmission",
    "SecuredMessage",
    "APAR_REQUEST",
    "APAR_SIGNED_RESPONSE",
    "APAR_ENCRYPTED",
]
