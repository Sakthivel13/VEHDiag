"""ECUReset - SID 0x11."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from ....core.enums.session_enums import ResetType
from ....core.enums.sid_enums import ServiceID
from ....core.event_bus import EventType
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)

#: Default time to wait for the ECU to boot after a reset, in seconds.
DEFAULT_WAIT_S = 2.0


@dataclass(slots=True)
class ResetResult:
    """Outcome of an ECU reset request."""

    reset_type: int
    accepted: bool
    power_down_time_s: int | None = None
    reachable_after_s: float | None = None
    response: DiagnosticResponse | None = None

    @property
    def type_name(self) -> str:
        """Return the ISO name of the reset type."""
        try:
            return ResetType(self.reset_type).pretty_name
        except ValueError:
            return f"reset 0x{self.reset_type:02X}"

    def __str__(self) -> str:  # noqa: D105 - trivial
        state = "accepted" if self.accepted else "rejected"
        suffix = "" if self.reachable_after_s is None else f", back after {self.reachable_after_s:.1f} s"
        return f"{self.type_name} {state}{suffix}"


class ECUReset(BaseService):
    """Reset the ECU and optionally wait until it answers again."""

    service_id = int(ServiceID.ECU_RESET)
    min_request_length = 2
    has_sub_function = True

    def build_request(self, reset_type: int = int(ResetType.HARD_RESET)) -> bytes:
        """Return ``11 <reset type>``.

        Raises:
            RequestValidationError: The sub-function is outside 0x01..0x7F.
        """
        if not 0x01 <= reset_type <= 0x7F:
            raise RequestValidationError(
                "the reset type must be in 0x01..0x7F", {"value": f"0x{reset_type:02X}"}
            )
        return bytes([self.service_id, reset_type & 0xFF])

    def parse_response(self, response: DiagnosticResponse) -> ResetResult:
        """Parse the echoed reset type and the optional power down time."""
        if response.is_negative or response.timed_out:
            return ResetResult(reset_type=0, accepted=False, response=response)
        raw = self.require_positive(response, min_length=2)
        power_down = raw[2] if len(raw) > 2 else None
        return ResetResult(
            reset_type=raw[1],
            accepted=True,
            power_down_time_s=power_down,
            response=response,
        )

    def execute(
        self,
        reset_type: int = int(ResetType.HARD_RESET),
        wait_s: float = DEFAULT_WAIT_S,
        verify: bool = True,
    ) -> ResetResult:
        """Reset the ECU and optionally wait for it to come back.

        Args:
            reset_type: The reset sub-function.
            wait_s: How long to wait before probing the ECU again.
            verify: Send TesterPresent afterwards to confirm the ECU is back.
        """
        result = self.parse_response(self.send(self.build_request(reset_type), timeout=5.0))
        if not result.accepted:
            return result
        self.client.state.reset()
        self.client.bus.publish(
            EventType.DIAG_ECU_RESET,
            {"type": reset_type, "name": result.type_name},
            "ECUReset",
        )
        if wait_s > 0:
            time.sleep(wait_s)
        if verify:
            result.reachable_after_s = self._wait_until_reachable(wait_s)
        _logger.info("%s", result)
        return result

    def hard_reset(self, wait_s: float = DEFAULT_WAIT_S) -> ResetResult:
        """Perform a hard reset (0x01)."""
        return self.execute(int(ResetType.HARD_RESET), wait_s)

    def soft_reset(self, wait_s: float = 1.0) -> ResetResult:
        """Perform a soft reset (0x03)."""
        return self.execute(int(ResetType.SOFT_RESET), wait_s)

    def key_off_on_reset(self, wait_s: float = DEFAULT_WAIT_S) -> ResetResult:
        """Perform a key off/on reset (0x02)."""
        return self.execute(int(ResetType.KEY_OFF_ON_RESET), wait_s)

    def _wait_until_reachable(self, timeout_s: float = 5.0) -> float | None:
        """Poll TesterPresent until the ECU answers, returning the delay."""
        from ..misc_services.tester_present import TesterPresent

        tester = TesterPresent(self.client)
        started = time.perf_counter()
        deadline = started + max(1.0, timeout_s * 3)
        while time.perf_counter() < deadline:
            try:
                if tester.ping():
                    return time.perf_counter() - started
            except Exception:  # noqa: BLE001 - the ECU is expected to be silent
                pass
            time.sleep(0.2)
        return None


__all__ = ["ECUReset", "ResetResult", "DEFAULT_WAIT_S"]
