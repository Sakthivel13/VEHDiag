"""AccessTimingParameter - SID 0x83."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum

from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


class TimingAccessType(IntEnum):
    """Sub-functions of AccessTimingParameter."""

    READ_EXTENDED_TIMING_PARAMETER_SET = 0x01
    SET_TIMING_PARAMETERS_TO_DEFAULT = 0x02
    READ_CURRENTLY_ACTIVE_TIMING_PARAMETERS = 0x03
    SET_TIMING_PARAMETERS_TO_GIVEN_VALUES = 0x04


@dataclass(slots=True)
class TimingParameters:
    """P2 and P2* values reported or requested by the service."""

    p2_ms: float = 50.0
    p2_star_ms: float = 5000.0

    def to_bytes(self) -> bytes:
        """Encode the values as ``P2(2) P2*(2)`` with 10 ms P2* resolution."""
        return int(round(self.p2_ms)).to_bytes(2, "big") + int(
            round(self.p2_star_ms / 10)
        ).to_bytes(2, "big")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "TimingParameters":
        """Decode four timing bytes."""
        if len(raw) < 4:
            return cls()
        return cls(
            p2_ms=float(int.from_bytes(raw[0:2], "big")),
            p2_star_ms=float(int.from_bytes(raw[2:4], "big") * 10),
        )


class AccessTimingParameter(BaseService):
    """Read or change the P2/P2* communication timing of the ECU."""

    service_id = int(ServiceID.ACCESS_TIMING_PARAMETER)
    min_request_length = 2
    has_sub_function = True

    def build_request(self, access_type: int, parameters: TimingParameters | None = None) -> bytes:
        """Return ``83 <access type> [timing]``.

        Raises:
            RequestValidationError: A set request has no timing parameters.
        """
        payload = bytearray([self.service_id, access_type & 0xFF])
        if access_type == int(TimingAccessType.SET_TIMING_PARAMETERS_TO_GIVEN_VALUES):
            if parameters is None:
                raise RequestValidationError("setting timing parameters requires values")
            payload.extend(parameters.to_bytes())
        return bytes(payload)

    def parse_response(self, response: DiagnosticResponse) -> TimingParameters:
        """Parse the timing parameters carried by the response."""
        raw = self.require_positive(response, min_length=2)
        return TimingParameters.from_bytes(raw[2:])

    def read_active(self) -> TimingParameters:
        """Read the currently active timing parameters."""
        payload = self.build_request(int(TimingAccessType.READ_CURRENTLY_ACTIVE_TIMING_PARAMETERS))
        return self.parse_response(self.send(payload))

    def read_extended(self) -> TimingParameters:
        """Read the extended (maximum supported) timing parameters."""
        payload = self.build_request(int(TimingAccessType.READ_EXTENDED_TIMING_PARAMETER_SET))
        return self.parse_response(self.send(payload))

    def set_default(self) -> bool:
        """Restore the default timing parameters."""
        payload = self.build_request(int(TimingAccessType.SET_TIMING_PARAMETERS_TO_DEFAULT))
        return self.send(payload).is_positive()

    def set_values(self, parameters: TimingParameters) -> bool:
        """Apply *parameters* and mirror them in the client configuration."""
        payload = self.build_request(
            int(TimingAccessType.SET_TIMING_PARAMETERS_TO_GIVEN_VALUES), parameters
        )
        accepted = self.send(payload).is_positive()
        if accepted:
            self.client.config.p2_client_ms = parameters.p2_ms * 1.5
            self.client.config.p2_star_client_ms = parameters.p2_star_ms * 1.5
        return accepted

    def execute(self, access_type: int = int(TimingAccessType.READ_CURRENTLY_ACTIVE_TIMING_PARAMETERS)) -> TimingParameters:
        """Send one AccessTimingParameter request."""
        return self.parse_response(self.send(self.build_request(access_type)))


__all__ = ["AccessTimingParameter", "TimingAccessType", "TimingParameters"]
