"""RoutineControl - SID 0x31."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from ....core.enums.session_enums import RoutineControlType
from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService
from .routine_types import RoutineDescriptor, describe_routine, sub_function_label

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RoutineResult:
    """Outcome of a routine control request."""

    routine_id: int
    sub_function: int
    accepted: bool
    status_record: bytes = b""
    response: DiagnosticResponse | None = None

    @property
    def descriptor(self) -> RoutineDescriptor:
        """Return the description of the routine."""
        return describe_routine(self.routine_id)

    @property
    def status_byte(self) -> int | None:
        """Return the first status byte, conventionally the routine result."""
        return self.status_record[0] if self.status_record else None

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when accepted and the status byte is zero."""
        return self.accepted and (self.status_byte in (None, 0x00))

    def __str__(self) -> str:  # noqa: D105 - trivial
        state = "accepted" if self.accepted else "rejected"
        return (
            f"{sub_function_label(self.sub_function)} {self.descriptor.label} {state}"
            + (f" status=0x{self.status_byte:02X}" if self.status_byte is not None else "")
        )


class RoutineControl(BaseService):
    """Start, stop and query routines implemented by the ECU."""

    service_id = int(ServiceID.ROUTINE_CONTROL)
    min_request_length = 4
    has_sub_function = True

    def build_request(self, sub_function: int, routine_id: int, option_record: bytes = b"") -> bytes:
        """Return ``31 <sub> <routine hi> <routine lo> [options]``.

        Raises:
            RequestValidationError: The sub-function or routine id is invalid.
        """
        if sub_function not in (0x01, 0x02, 0x03):
            raise RequestValidationError(
                "RoutineControl accepts sub-functions 0x01, 0x02 and 0x03",
                {"value": f"0x{sub_function:02X}"},
            )
        if not 0 <= routine_id <= 0xFFFF:
            raise RequestValidationError("the routine identifier must fit into two bytes")
        return (
            bytes([self.service_id, sub_function & 0xFF])
            + routine_id.to_bytes(2, "big")
            + option_record
        )

    def parse_response(self, response: DiagnosticResponse) -> RoutineResult:
        """Parse the echoed sub-function, routine id and status record."""
        if response.is_negative or response.timed_out:
            return RoutineResult(
                routine_id=0,
                sub_function=0,
                accepted=False,
                response=response,
            )
        raw = self.require_positive(response, min_length=4)
        return RoutineResult(
            routine_id=int.from_bytes(raw[2:4], "big"),
            sub_function=raw[1],
            accepted=True,
            status_record=bytes(raw[4:]),
            response=response,
        )

    def execute(
        self,
        routine_id: int,
        sub_function: int = int(RoutineControlType.START_ROUTINE),
        option_record: bytes = b"",
        timeout: float = 10.0,
    ) -> RoutineResult:
        """Send one routine control request."""
        payload = self.build_request(sub_function, routine_id, option_record)
        result = self.parse_response(self.send(payload, timeout=timeout))
        _logger.info("%s", result)
        return result

    def start(self, routine_id: int, option_record: bytes = b"", timeout: float = 10.0) -> RoutineResult:
        """Start the routine identified by *routine_id*."""
        return self.execute(routine_id, int(RoutineControlType.START_ROUTINE), option_record, timeout)

    def stop(self, routine_id: int, option_record: bytes = b"") -> RoutineResult:
        """Stop a running routine."""
        return self.execute(routine_id, int(RoutineControlType.STOP_ROUTINE), option_record)

    def results(self, routine_id: int) -> RoutineResult:
        """Request the results of a routine."""
        return self.execute(routine_id, int(RoutineControlType.REQUEST_ROUTINE_RESULTS))

    def run_and_wait(
        self,
        routine_id: int,
        option_record: bytes = b"",
        poll_interval_s: float = 0.5,
        timeout_s: float = 60.0,
    ) -> RoutineResult:
        """Start a routine and poll its results until it finishes.

        Returns:
            The final :class:`RoutineResult`; when the routine never reports a
            terminal state the last polled result is returned.
        """
        start_result = self.start(routine_id, option_record)
        if not start_result.accepted:
            return start_result
        deadline = time.perf_counter() + timeout_s
        last = start_result
        while time.perf_counter() < deadline:
            time.sleep(poll_interval_s)
            last = self.results(routine_id)
            if not last.accepted:
                return last
            if last.status_byte is not None and last.status_byte != 0x01:
                return last
        return last

    def erase_memory(self, address: int, size: int, address_bytes: int = 4, length_bytes: int = 4) -> RoutineResult:
        """Run the standard eraseMemory routine (0xFF00)."""
        option = address.to_bytes(address_bytes, "big") + size.to_bytes(length_bytes, "big")
        return self.run_and_wait(0xFF00, option, timeout_s=120.0)

    def check_programming_dependencies(self) -> RoutineResult:
        """Run the standard checkProgrammingDependencies routine (0xFF01)."""
        return self.run_and_wait(0xFF01, timeout_s=60.0)


__all__ = ["RoutineControl", "RoutineResult"]
