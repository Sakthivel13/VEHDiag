"""DiagnosticSessionControl - SID 0x10."""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

from ....core.enums.session_enums import SessionType
from ....core.enums.sid_enums import ServiceID
from ....core.event_bus import EventType
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ....core.models.session_model import SessionTiming
from ..base_service import BaseService
from .session_timing import TimingBudget
from .session_types import SessionDescriptor, describe_session

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionResult:
    """Outcome of a session change request."""

    session: int
    accepted: bool
    timing: SessionTiming
    descriptor: SessionDescriptor
    response: DiagnosticResponse

    @property
    def label(self) -> str:
        """Return the readable session name."""
        return self.descriptor.label

    @property
    def budget(self) -> TimingBudget:
        """Return the client timing budget derived from the ECU values."""
        return TimingBudget.from_session_timing(self.timing)

    def __str__(self) -> str:  # noqa: D105 - trivial
        state = "accepted" if self.accepted else "rejected"
        return f"{self.label} ({self.descriptor.hex_value}) {state}"


class DiagnosticSessionControl(BaseService):
    """Switch the ECU into another diagnostic session.

    Example:
        >>> # service = DiagnosticSessionControl(client)
        >>> # result = service.execute(0x03)
        >>> None
    """

    service_id = int(ServiceID.DIAGNOSTIC_SESSION_CONTROL)
    min_request_length = 2
    has_sub_function = True

    def build_request(self, session: int = int(SessionType.EXTENDED_DIAGNOSTIC)) -> bytes:
        """Return ``10 <session>``.

        Raises:
            RequestValidationError: The sub-function is outside 0x01..0x7E.
        """
        if not 0x01 <= session <= 0x7E:
            raise RequestValidationError(
                "session sub-function must be in 0x01..0x7E", {"value": f"0x{session:02X}"}
            )
        return bytes([self.service_id, session & 0xFF])

    def parse_response(self, response: DiagnosticResponse) -> SessionResult:
        """Extract the echoed session and the P2/P2* timing."""
        session = response.raw[1] if len(response.raw) > 1 else 0
        timing = SessionTiming.from_response(response.raw[2:]) if len(response.raw) > 2 else SessionTiming()
        return SessionResult(
            session=session,
            accepted=response.is_positive(),
            timing=timing,
            descriptor=describe_session(session),
            response=response,
        )

    def execute(self, session: int = int(SessionType.EXTENDED_DIAGNOSTIC)) -> SessionResult:
        """Request *session* and update the client session state."""
        payload = self.build_request(session)
        response = self.send(payload)
        result = self.parse_response(response)
        if result.accepted:
            self.client.state.apply_session(session, result.timing)
            budget = result.budget
            self.client.config.p2_client_ms = budget.p2_client_ms
            self.client.config.p2_star_client_ms = budget.p2_star_client_ms
            self.client.pending_handler.p2_star_ms = budget.p2_star_client_ms
            self.client.bus.publish(
                EventType.DIAG_SESSION_CHANGED,
                {"session": session, "label": result.label, "timing": asdict(result.timing)},
                "DiagnosticSessionControl",
            )
            _logger.info("session changed to %s", result.label)
        return result

    def enter_default(self) -> SessionResult:
        """Switch back to the default session."""
        return self.execute(int(SessionType.DEFAULT))

    def enter_extended(self) -> SessionResult:
        """Switch to the extended diagnostic session."""
        return self.execute(int(SessionType.EXTENDED_DIAGNOSTIC))

    def enter_programming(self) -> SessionResult:
        """Switch to the programming session."""
        return self.execute(int(SessionType.PROGRAMMING))


__all__ = ["DiagnosticSessionControl", "SessionResult"]
