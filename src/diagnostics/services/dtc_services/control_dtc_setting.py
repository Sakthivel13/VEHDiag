"""ControlDTCSetting - SID 0x85."""
from __future__ import annotations

import logging

from ....core.enums.session_enums import DTCSettingType
from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


class ControlDTCSetting(BaseService):
    """Enable or disable the storage of diagnostic trouble codes.

    Disabling DTC setting is a mandatory step of most flash sequences so that
    the communication interruption does not create spurious fault entries.
    """

    service_id = int(ServiceID.CONTROL_DTC_SETTING)
    min_request_length = 2
    has_sub_function = True

    def build_request(self, setting: int = int(DTCSettingType.ON), data: bytes = b"") -> bytes:
        """Return ``85 <setting> [data]``.

        Raises:
            RequestValidationError: The sub-function is not 0x01 or 0x02.
        """
        if setting not in (int(DTCSettingType.ON), int(DTCSettingType.OFF)):
            raise RequestValidationError(
                "ControlDTCSetting accepts only 0x01 (on) or 0x02 (off)",
                {"value": f"0x{setting:02X}"},
            )
        return bytes([self.service_id, setting & 0xFF]) + data

    def parse_response(self, response: DiagnosticResponse) -> bool:
        """Return ``True`` when the ECU accepted the request."""
        return response.is_positive()

    def execute(self, on: bool = True) -> bool:
        """Turn DTC setting on or off."""
        setting = int(DTCSettingType.ON if on else DTCSettingType.OFF)
        response = self.send(self.build_request(setting))
        accepted = self.parse_response(response)
        _logger.info("DTC setting %s: %s", "on" if on else "off", "accepted" if accepted else "rejected")
        return accepted

    def enable(self) -> bool:
        """Re-enable DTC storage."""
        return self.execute(True)

    def disable(self) -> bool:
        """Suspend DTC storage (used during flashing)."""
        return self.execute(False)


__all__ = ["ControlDTCSetting"]
