"""InputOutputControlByIdentifier - SID 0x2F."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ....core.enums.session_enums import IOControlParameter
from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)

#: Readable names of the control parameters.
PARAMETER_NAMES: dict[int, str] = {
    0x00: "returnControlToECU",
    0x01: "resetToDefault",
    0x02: "freezeCurrentState",
    0x03: "shortTermAdjustment",
}


@dataclass(slots=True)
class IOControlResult:
    """Outcome of an input/output control request."""

    did: int
    parameter: int
    accepted: bool
    status_record: bytes = b""
    response: DiagnosticResponse | None = None

    @property
    def parameter_name(self) -> str:
        """Return the readable control parameter name."""
        return PARAMETER_NAMES.get(self.parameter, f"0x{self.parameter:02X}")

    def __str__(self) -> str:  # noqa: D105 - trivial
        state = "accepted" if self.accepted else "rejected"
        return f"IO control 0x{self.did:04X} {self.parameter_name} {state}"


class InputOutputControlByIdentifier(BaseService):
    """Override an ECU input or output signal for actuator tests."""

    service_id = int(ServiceID.INPUT_OUTPUT_CONTROL_BY_IDENTIFIER)
    min_request_length = 4
    has_sub_function = False

    def build_request(
        self,
        did: int,
        parameter: int = int(IOControlParameter.SHORT_TERM_ADJUSTMENT),
        control_state: bytes = b"",
        control_mask: bytes = b"",
    ) -> bytes:
        """Return ``2F <did> <parameter> [state] [mask]``.

        Raises:
            RequestValidationError: The DID is out of range or a short term
                adjustment is requested without a control state.
        """
        if not 0 <= did <= 0xFFFF:
            raise RequestValidationError("the data identifier must fit into two bytes")
        if parameter == int(IOControlParameter.SHORT_TERM_ADJUSTMENT) and not control_state:
            raise RequestValidationError("shortTermAdjustment requires a control state")
        return (
            bytes([self.service_id])
            + did.to_bytes(2, "big")
            + bytes([parameter & 0xFF])
            + control_state
            + control_mask
        )

    def parse_response(self, response: DiagnosticResponse) -> IOControlResult:
        """Parse the echoed identifier and the returned status record."""
        if response.is_negative or response.timed_out:
            return IOControlResult(did=0, parameter=0, accepted=False, response=response)
        raw = self.require_positive(response, min_length=4)
        return IOControlResult(
            did=int.from_bytes(raw[1:3], "big"),
            parameter=raw[3],
            accepted=True,
            status_record=bytes(raw[4:]),
            response=response,
        )

    def execute(
        self,
        did: int,
        parameter: int = int(IOControlParameter.SHORT_TERM_ADJUSTMENT),
        control_state: bytes = b"",
        control_mask: bytes = b"",
    ) -> IOControlResult:
        """Send one input/output control request."""
        payload = self.build_request(did, parameter, control_state, control_mask)
        result = self.parse_response(self.send(payload, timeout=3.0))
        _logger.info("%s", result)
        return result

    def return_control(self, did: int) -> IOControlResult:
        """Hand the signal back to the ECU."""
        return self.execute(did, int(IOControlParameter.RETURN_CONTROL_TO_ECU))

    def reset_to_default(self, did: int) -> IOControlResult:
        """Reset the signal to its default value."""
        return self.execute(did, int(IOControlParameter.RESET_TO_DEFAULT))

    def freeze(self, did: int) -> IOControlResult:
        """Freeze the current value of the signal."""
        return self.execute(did, int(IOControlParameter.FREEZE_CURRENT_STATE))

    def adjust(self, did: int, value: bytes, mask: bytes = b"") -> IOControlResult:
        """Apply a short term adjustment with *value*."""
        return self.execute(did, int(IOControlParameter.SHORT_TERM_ADJUSTMENT), value, mask)


__all__ = ["InputOutputControlByIdentifier", "IOControlResult", "PARAMETER_NAMES"]
