"""Base class for all UDS diagnostic services."""
from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any

from ...core.enums.sid_enums import NON_DEFAULT_SESSION_SERVICES, SECURITY_REQUIRED_SERVICES, ServiceID
from ...core.enums.session_enums import SecurityState, SessionType
from ...core.exceptions import (
    InvalidResponseError,
    RequestValidationError,
    SecurityAccessDeniedError,
    SessionNotSupportedError,
)
from ...core.interfaces.i_diagnostic_service import IDiagnosticService
from ...core.models.response_data_model import DiagnosticResponse
from ..uds_client import UDSClient

_logger = logging.getLogger(__name__)


class BaseService(IDiagnosticService):
    """Common behaviour shared by every service implementation.

    Args:
        client: The UDS client used to transmit requests.

    Subclasses set :attr:`service_id`, implement :meth:`build_request` and
    :meth:`parse_response`, and usually override :meth:`execute`.
    """

    #: Minimum request length in bytes, used by :meth:`validate_request`.
    min_request_length: int = 1
    #: Whether the second request byte is a sub-function.
    has_sub_function: bool = False

    def __init__(self, client: UDSClient) -> None:
        """Store the UDS client."""
        self.client = client

    # -- helpers -----------------------------------------------------------
    @property
    def name(self) -> str:
        """Return the ISO name of the service."""
        service = ServiceID.from_byte(self.service_id)
        return service.pretty_name if service else f"Service 0x{self.service_id:02X}"

    def validate_request(self, payload: bytes) -> None:
        """Validate a request before transmission.

        Raises:
            RequestValidationError: The payload is empty, too short or does not
                start with the expected service identifier.
        """
        if not payload:
            raise RequestValidationError(f"{self.name}: empty request")
        if payload[0] != self.service_id:
            raise RequestValidationError(
                f"{self.name}: wrong service identifier",
                {"expected": f"0x{self.service_id:02X}", "received": f"0x{payload[0]:02X}"},
            )
        if len(payload) < self.min_request_length:
            raise RequestValidationError(
                f"{self.name}: request too short",
                {"expected_min": self.min_request_length, "received": len(payload)},
            )

    def check_preconditions(self) -> None:
        """Verify session and security prerequisites.

        Raises:
            SessionNotSupportedError: The active session forbids the service.
            SecurityAccessDeniedError: The service needs an unlocked ECU.
        """
        if not self.client.config.validate_session:
            return
        state = self.client.state
        if (
            self.service_id in NON_DEFAULT_SESSION_SERVICES
            and state.active_session == int(SessionType.DEFAULT)
        ):
            raise SessionNotSupportedError(
                f"{self.name} requires a non-default diagnostic session",
                {"active_session": state.session_label},
            )
        if (
            self.service_id in SECURITY_REQUIRED_SERVICES
            and state.security_state is not SecurityState.UNLOCKED
        ):
            raise SecurityAccessDeniedError(
                f"{self.name} requires an unlocked security level",
                {"security_state": state.security_state.value},
            )

    def send(self, payload: bytes, timeout: float | None = None, **kwargs: Any) -> DiagnosticResponse:
        """Validate, check preconditions and transmit *payload*."""
        self.validate_request(payload)
        self.check_preconditions()
        return self.client.send_request(payload, timeout=timeout, **kwargs)

    def require_positive(self, response: DiagnosticResponse, min_length: int = 1) -> bytes:
        """Return the raw response, raising when it is not usable.

        Raises:
            InvalidResponseError: The response timed out, is negative or is
                shorter than *min_length*.
        """
        if response.timed_out:
            raise InvalidResponseError(f"{self.name}: no response from the ECU")
        if response.is_negative:
            raise InvalidResponseError(f"{self.name}: {response.nrc_text}")
        if len(response.raw) < min_length:
            raise InvalidResponseError(
                f"{self.name}: response too short",
                {"expected_min": min_length, "received": len(response.raw)},
            )
        return response.raw

    # -- interface ---------------------------------------------------------------
    @abstractmethod
    def build_request(self, *args: Any, **kwargs: Any) -> bytes:
        """Return the raw request payload."""

    def parse_response(self, response: DiagnosticResponse) -> Any:
        """Default parsing simply returns the response object."""
        return response

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Build, send and parse the service in one call."""
        payload = self.build_request(*args, **kwargs)
        response = self.send(payload)
        return self.parse_response(response)

    def get_service_info(self) -> dict[str, Any]:
        """Return metadata about the service for the UI."""
        info = super().get_service_info()
        info.update(
            {
                "name": self.name,
                "has_sub_function": self.has_sub_function,
                "min_request_length": self.min_request_length,
                "requires_security": self.service_id in SECURITY_REQUIRED_SERVICES,
                "requires_session": self.service_id in NON_DEFAULT_SESSION_SERVICES,
            }
        )
        return info

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<{type(self).__name__} 0x{self.service_id:02X}>"


__all__ = ["BaseService"]
