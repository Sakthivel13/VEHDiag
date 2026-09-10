"""Authentication - SID 0x29 (ISO 14229-1:2020)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum

from ....core.enums.sid_enums import ServiceID
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


class AuthenticationTask(IntEnum):
    """Sub-functions of the Authentication service."""

    DE_AUTHENTICATE = 0x00
    VERIFY_CERTIFICATE_UNIDIRECTIONAL = 0x01
    VERIFY_CERTIFICATE_BIDIRECTIONAL = 0x02
    PROOF_OF_OWNERSHIP = 0x03
    TRANSMIT_CERTIFICATE = 0x04
    REQUEST_CHALLENGE_FOR_AUTHENTICATION = 0x05
    VERIFY_PROOF_OF_OWNERSHIP_UNIDIRECTIONAL = 0x06
    VERIFY_PROOF_OF_OWNERSHIP_BIDIRECTIONAL = 0x07
    AUTHENTICATION_CONFIGURATION = 0x08


class ReturnValue(IntEnum):
    """Authentication return values."""

    REQUEST_ACCEPTED = 0x00
    GENERAL_REJECT = 0x01
    AUTHENTICATION_CONFIGURATION_APCE = 0x02
    AUTHENTICATION_CONFIGURATION_ACR_WITH_ASYMMETRIC = 0x03
    AUTHENTICATION_CONFIGURATION_ACR_WITH_SYMMETRIC = 0x04
    DE_AUTHENTICATION_SUCCESSFUL = 0x10
    CERTIFICATE_VERIFIED_OWNERSHIP_VERIFICATION_NECESSARY = 0x11
    OWNERSHIP_VERIFIED_AUTHENTICATION_COMPLETE = 0x12
    CERTIFICATE_VERIFIED = 0x13


@dataclass(slots=True)
class AuthenticationResult:
    """Outcome of an authentication step."""

    task: int
    return_value: int
    payload: bytes = b""
    response: DiagnosticResponse | None = None

    @property
    def accepted(self) -> bool:
        """Return ``True`` when the ECU accepted the step."""
        try:
            value = ReturnValue(self.return_value)
        except ValueError:
            return False
        return value not in (ReturnValue.GENERAL_REJECT,)

    @property
    def complete(self) -> bool:
        """Return ``True`` when authentication finished successfully."""
        return self.return_value == int(ReturnValue.OWNERSHIP_VERIFIED_AUTHENTICATION_COMPLETE)


class Authentication(BaseService):
    """Certificate based authentication (PKI) replacing SecurityAccess."""

    service_id = int(ServiceID.AUTHENTICATION)
    min_request_length = 2
    has_sub_function = True

    def build_request(self, task: int, payload: bytes = b"") -> bytes:
        """Return ``29 <task> [payload]``."""
        return bytes([self.service_id, task & 0xFF]) + payload

    def parse_response(self, response: DiagnosticResponse) -> AuthenticationResult:
        """Parse the sub-function echo and the return value byte."""
        raw = self.require_positive(response, min_length=3)
        return AuthenticationResult(
            task=raw[1], return_value=raw[2], payload=bytes(raw[3:]), response=response
        )

    def execute(self, task: int, payload: bytes = b"") -> AuthenticationResult:
        """Send one authentication step."""
        return self.parse_response(self.send(self.build_request(task, payload), timeout=5.0))

    def de_authenticate(self) -> AuthenticationResult:
        """Terminate an active authentication."""
        return self.execute(int(AuthenticationTask.DE_AUTHENTICATE))

    def request_challenge(self, configuration: int = 0x00, algorithm: bytes = b"") -> AuthenticationResult:
        """Request a challenge for a challenge-response authentication."""
        return self.execute(
            int(AuthenticationTask.REQUEST_CHALLENGE_FOR_AUTHENTICATION),
            bytes([configuration]) + algorithm,
        )

    def verify_certificate(self, certificate: bytes, challenge: bytes = b"") -> AuthenticationResult:
        """Send the client certificate for unidirectional verification."""
        payload = (
            bytes([0x00])
            + len(certificate).to_bytes(2, "big")
            + certificate
            + len(challenge).to_bytes(2, "big")
            + challenge
        )
        return self.execute(int(AuthenticationTask.VERIFY_CERTIFICATE_UNIDIRECTIONAL), payload)

    def proof_of_ownership(self, proof: bytes, ephemeral: bytes = b"") -> AuthenticationResult:
        """Send the proof of ownership completing the authentication."""
        payload = (
            len(proof).to_bytes(2, "big")
            + proof
            + len(ephemeral).to_bytes(2, "big")
            + ephemeral
        )
        return self.execute(int(AuthenticationTask.PROOF_OF_OWNERSHIP), payload)


__all__ = ["Authentication", "AuthenticationTask", "AuthenticationResult", "ReturnValue"]
