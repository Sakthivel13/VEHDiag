"""TesterPresent - SID 0x3E."""
from __future__ import annotations

import logging

from ....core.enums.sid_enums import ServiceID
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)

#: The only standardised sub-function of TesterPresent.
ZERO_SUB_FUNCTION = 0x00


class TesterPresent(BaseService):
    """Keep a non-default diagnostic session alive."""

    service_id = int(ServiceID.TESTER_PRESENT)
    min_request_length = 2
    has_sub_function = True

    def build_request(self, suppress: bool = True) -> bytes:
        """Return ``3E 80`` (suppressed) or ``3E 00``."""
        return bytes([self.service_id, 0x80 if suppress else ZERO_SUB_FUNCTION])

    def parse_response(self, response: DiagnosticResponse) -> bool:
        """Return ``True`` when the ECU is alive (or suppressed the answer)."""
        return response.is_positive()

    def execute(self, suppress: bool = True) -> bool:
        """Send one TesterPresent request."""
        response = self.client.send_request(
            self.build_request(suppress), suppress_response=suppress, timeout=1.0
        )
        return self.parse_response(response)

    def ping(self) -> bool:
        """Send a non-suppressed TesterPresent to verify the ECU answers."""
        return self.execute(suppress=False)


__all__ = ["TesterPresent", "ZERO_SUB_FUNCTION"]
