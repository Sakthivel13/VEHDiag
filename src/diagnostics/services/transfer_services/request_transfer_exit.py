"""RequestTransferExit - SID 0x37."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ....core.enums.sid_enums import ServiceID
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TransferExitResult:
    """Outcome of the transfer termination."""

    accepted: bool
    parameter_record: bytes = b""
    response: DiagnosticResponse | None = None

    @property
    def checksum(self) -> int | None:
        """Return the parameter record interpreted as a checksum, if present."""
        if not self.parameter_record:
            return None
        return int.from_bytes(self.parameter_record, "big")

    def __str__(self) -> str:  # noqa: D105 - trivial
        if not self.accepted:
            reason = self.response.nrc_text if self.response else "no response"
            return f"transfer exit rejected: {reason}"
        checksum = self.checksum
        suffix = f", checksum 0x{checksum:X}" if checksum is not None else ""
        return f"transfer exit accepted{suffix}"


class RequestTransferExit(BaseService):
    """Terminate an upload or download sequence."""

    service_id = int(ServiceID.REQUEST_TRANSFER_EXIT)
    min_request_length = 1
    has_sub_function = False

    def build_request(self, parameter_record: bytes = b"") -> bytes:
        """Return ``37 [parameter record]``."""
        return bytes([self.service_id]) + parameter_record

    def parse_response(self, response: DiagnosticResponse) -> TransferExitResult:
        """Parse the optional parameter record of the response."""
        if response.is_negative or response.timed_out:
            return TransferExitResult(accepted=False, response=response)
        raw = self.require_positive(response, min_length=1)
        return TransferExitResult(
            accepted=True, parameter_record=bytes(raw[1:]), response=response
        )

    def execute(self, parameter_record: bytes = b"") -> TransferExitResult:
        """Terminate the transfer and return the ECU verification data."""
        result = self.parse_response(
            self.send(self.build_request(parameter_record), timeout=30.0)
        )
        _logger.info("%s", result)
        return result


__all__ = ["RequestTransferExit", "TransferExitResult"]
