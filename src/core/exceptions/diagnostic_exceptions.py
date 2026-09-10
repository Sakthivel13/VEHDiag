"""Diagnostic (UDS) exception hierarchy."""
from __future__ import annotations

from typing import Any

from ..enums.nrc_enums import NegativeResponseCode, describe_nrc
from .communication_exceptions import VDPError


class DiagnosticError(VDPError):
    """Base class for diagnostic level failures."""


class NegativeResponseError(DiagnosticError):
    """Raised when the ECU answers with ``0x7F <SID> <NRC>``.

    Args:
        service_id: The request SID that was rejected.
        nrc: The negative response code byte.
        details: Optional extra context (raw response, request payload...).
    """

    def __init__(self, service_id: int, nrc: int, details: dict[str, Any] | None = None) -> None:
        self.service_id = service_id
        self.nrc = nrc
        self.code = NegativeResponseCode.from_byte(nrc)
        message = f"Service 0x{service_id:02X} rejected: {describe_nrc(nrc)}"
        super().__init__(message, details)

    @property
    def recovery_hint(self) -> str:
        """Return a suggested corrective action for the operator."""
        if self.code is None:
            return "Consult the OEM documentation for this manufacturer specific NRC."
        return self.code.recovery_hint


class ServiceNotSupportedError(DiagnosticError):
    """Raised when a service is not implemented by the platform or the ECU."""


class SecurityAccessDeniedError(DiagnosticError):
    """Raised when a service requires an unlocked security level."""


class InvalidResponseError(DiagnosticError):
    """Raised when a response is malformed, too short or echoes the wrong SID."""


class RequestValidationError(DiagnosticError):
    """Raised when a request fails client side validation before transmission."""


class SessionNotSupportedError(DiagnosticError):
    """Raised when the active session does not permit the requested service."""


class TransferError(DiagnosticError):
    """Raised when an upload/download sequence fails."""


__all__ = [
    "DiagnosticError",
    "NegativeResponseError",
    "ServiceNotSupportedError",
    "SecurityAccessDeniedError",
    "InvalidResponseError",
    "RequestValidationError",
    "SessionNotSupportedError",
    "TransferError",
]
