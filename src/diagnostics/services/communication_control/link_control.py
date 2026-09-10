"""LinkControl - SID 0x87."""
from __future__ import annotations

import logging
from enum import IntEnum

from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


class LinkControlType(IntEnum):
    """Sub-functions of LinkControl."""

    VERIFY_MODE_TRANSITION_WITH_FIXED_PARAMETER = 0x01
    VERIFY_MODE_TRANSITION_WITH_SPECIFIC_PARAMETER = 0x02
    TRANSITION_MODE = 0x03


class LinkControlMode(IntEnum):
    """Standardised fixed baud rate identifiers."""

    PC9600 = 0x01
    PC19200 = 0x02
    PC38400 = 0x03
    PC57600 = 0x04
    PC115200 = 0x05
    CAN125000 = 0x10
    CAN250000 = 0x11
    CAN500000 = 0x12
    CAN1000000 = 0x13


class LinkControl(BaseService):
    """Switch the diagnostic link to a different baud rate.

    The transition is a two step protocol: first the mode is verified, then it
    is applied with the transitionMode sub-function.
    """

    service_id = int(ServiceID.LINK_CONTROL)
    min_request_length = 2
    has_sub_function = True

    def build_request(
        self,
        control_type: int,
        baudrate_identifier: int | None = None,
        specific_baudrate: int | None = None,
    ) -> bytes:
        """Return the LinkControl request payload.

        Raises:
            RequestValidationError: A verify request has no baud rate.
        """
        payload = bytearray([self.service_id, control_type & 0xFF])
        if control_type == int(LinkControlType.VERIFY_MODE_TRANSITION_WITH_FIXED_PARAMETER):
            if baudrate_identifier is None:
                raise RequestValidationError("a fixed baud rate identifier is required")
            payload.append(baudrate_identifier & 0xFF)
        elif control_type == int(LinkControlType.VERIFY_MODE_TRANSITION_WITH_SPECIFIC_PARAMETER):
            if specific_baudrate is None:
                raise RequestValidationError("a specific baud rate value is required")
            payload.extend((specific_baudrate & 0xFFFFFF).to_bytes(3, "big"))
        return bytes(payload)

    def parse_response(self, response: DiagnosticResponse) -> bool:
        """Return ``True`` when the ECU accepted the step."""
        return response.is_positive()

    def verify_fixed(self, baudrate_identifier: int) -> bool:
        """Verify a transition to a standardised baud rate."""
        payload = self.build_request(
            int(LinkControlType.VERIFY_MODE_TRANSITION_WITH_FIXED_PARAMETER),
            baudrate_identifier=baudrate_identifier,
        )
        return self.parse_response(self.send(payload))

    def verify_specific(self, baudrate: int) -> bool:
        """Verify a transition to an arbitrary baud rate."""
        payload = self.build_request(
            int(LinkControlType.VERIFY_MODE_TRANSITION_WITH_SPECIFIC_PARAMETER),
            specific_baudrate=baudrate,
        )
        return self.parse_response(self.send(payload))

    def transition(self) -> bool:
        """Apply the previously verified baud rate."""
        payload = self.build_request(int(LinkControlType.TRANSITION_MODE))
        return self.parse_response(self.send(payload))

    def execute(self, baudrate: int) -> bool:
        """Verify and then apply *baudrate* in bit/s."""
        fixed = {
            125_000: LinkControlMode.CAN125000,
            250_000: LinkControlMode.CAN250000,
            500_000: LinkControlMode.CAN500000,
            1_000_000: LinkControlMode.CAN1000000,
        }.get(baudrate)
        verified = (
            self.verify_fixed(int(fixed)) if fixed is not None else self.verify_specific(baudrate)
        )
        if not verified:
            return False
        return self.transition()


__all__ = ["LinkControl", "LinkControlType", "LinkControlMode"]
