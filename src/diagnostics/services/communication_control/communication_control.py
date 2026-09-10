"""CommunicationControl - SID 0x28."""
from __future__ import annotations

import logging
from enum import IntEnum

from ....core.enums.session_enums import CommunicationControlType
from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


class CommunicationType(IntEnum):
    """communicationType parameter values."""

    NORMAL = 0x01
    NETWORK_MANAGEMENT = 0x02
    NORMAL_AND_NETWORK_MANAGEMENT = 0x03


class CommunicationControl(BaseService):
    """Enable or disable transmission and reception of bus messages.

    Disabling normal communication is a standard step of flash sequences: it
    silences application messages so the programming session is not disturbed.
    """

    service_id = int(ServiceID.COMMUNICATION_CONTROL)
    min_request_length = 3
    has_sub_function = True

    def build_request(
        self,
        control_type: int = int(CommunicationControlType.DISABLE_RX_AND_TX),
        communication_type: int = int(CommunicationType.NORMAL_AND_NETWORK_MANAGEMENT),
        node_identification: int | None = None,
    ) -> bytes:
        """Return ``28 <control type> <communication type> [node id]``.

        Raises:
            RequestValidationError: The control type is not standardised.
        """
        if not 0x00 <= control_type <= 0x7F:
            raise RequestValidationError("the control type must be in 0x00..0x7F")
        payload = bytearray([self.service_id, control_type & 0xFF, communication_type & 0xFF])
        if node_identification is not None:
            payload.extend((node_identification & 0xFFFF).to_bytes(2, "big"))
        return bytes(payload)

    def parse_response(self, response: DiagnosticResponse) -> bool:
        """Return ``True`` when the ECU accepted the request."""
        return response.is_positive()

    def execute(
        self,
        control_type: int = int(CommunicationControlType.DISABLE_RX_AND_TX),
        communication_type: int = int(CommunicationType.NORMAL_AND_NETWORK_MANAGEMENT),
    ) -> bool:
        """Send one CommunicationControl request."""
        accepted = self.parse_response(
            self.send(self.build_request(control_type, communication_type))
        )
        _logger.info(
            "communication control 0x%02X: %s",
            control_type,
            "accepted" if accepted else "rejected",
        )
        return accepted

    def disable_normal_communication(self) -> bool:
        """Disable transmission and reception of normal messages."""
        return self.execute(
            int(CommunicationControlType.DISABLE_RX_AND_TX), int(CommunicationType.NORMAL)
        )

    def enable_all(self) -> bool:
        """Re-enable transmission and reception."""
        return self.execute(
            int(CommunicationControlType.ENABLE_RX_AND_TX),
            int(CommunicationType.NORMAL_AND_NETWORK_MANAGEMENT),
        )


__all__ = ["CommunicationControl", "CommunicationType"]
