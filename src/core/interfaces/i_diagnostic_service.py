"""Abstract diagnostic (UDS) service interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models.response_data_model import DiagnosticResponse


class IDiagnosticService(ABC):
    """Contract implemented by every UDS service handler.

    A service builds a request payload, hands it to the UDS client and parses
    the response into a domain object.
    """

    #: The UDS service identifier implemented by the subclass.
    service_id: int = 0x00

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Build, send and parse the service in one call.

        Returns:
            A service specific result object (``DiagnosticResponse``,
            ``DTCReport``, list of ``DIDValue``...).
        """

    @abstractmethod
    def build_request(self, *args: Any, **kwargs: Any) -> bytes:
        """Return the raw request payload for the given arguments."""

    @abstractmethod
    def parse_response(self, response: DiagnosticResponse) -> Any:
        """Convert a raw *response* into a service specific result object.

        Raises:
            InvalidResponseError: The payload does not match the expectation.
        """

    @abstractmethod
    def validate_request(self, payload: bytes) -> None:
        """Validate a request payload before transmission.

        Raises:
            RequestValidationError: The payload is malformed.
        """

    def get_service_info(self) -> dict[str, Any]:
        """Return metadata describing the service for the UI."""
        return {
            "sid": self.service_id,
            "sid_hex": f"0x{self.service_id:02X}",
            "class": type(self).__name__,
            "doc": (self.__doc__ or "").strip().splitlines()[0] if self.__doc__ else "",
        }


__all__ = ["IDiagnosticService"]
