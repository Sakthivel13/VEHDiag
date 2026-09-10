"""The API exposed to user written test scripts.

A script never talks to the transport layer directly; it receives a
:class:`DiagnosticAPI` instance which offers a small, safe and well documented
surface plus assertion helpers that turn failures into readable messages.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from ...core.enums.session_enums import SessionType
from ...core.exceptions import DiagnosticError
from ...core.models.response_data_model import DiagnosticResponse
from ...diagnostics.uds_client import UDSClient

_logger = logging.getLogger(__name__)


class AssertionFailure(DiagnosticError):
    """Raised when a script assertion fails."""


@dataclass(slots=True)
class ScriptContext:
    """Mutable state shared between the steps of one script run.

    Attributes:
        variables: Free-form variables the script can store and read back.
        logs: Messages produced with :meth:`DiagnosticAPI.log`.
        cancelled: Set by the runner to request a graceful abort.
    """

    variables: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    cancelled: bool = False


class DiagnosticAPI:
    """Everything a test script is allowed to do.

    Args:
        client: The UDS client the script drives.
        context: Shared script context.

    Example:
        >>> # api.send_request(bytes.fromhex("22F190"))
        >>> # api.assert_positive_response()
        >>> None
    """

    def __init__(self, client: UDSClient, context: ScriptContext | None = None) -> None:
        """Store the client and the shared context."""
        self.client = client
        self.context = context or ScriptContext()
        self.last_response: DiagnosticResponse | None = None

    # -- raw exchanges ------------------------------------------------------
    def send_request(self, data: bytes, timeout: float | None = None) -> DiagnosticResponse:
        """Send a raw UDS request and return the response.

        Raises:
            AssertionFailure: The run was cancelled before the request.
        """
        self._check_cancelled()
        self.last_response = self.client.send_request(bytes(data), timeout=timeout)
        return self.last_response

    def send_hex(self, text: str, timeout: float | None = None) -> DiagnosticResponse:
        """Send a request written as hexadecimal text."""
        from ...utils.byte_utils import hex_to_bytes

        return self.send_request(hex_to_bytes(text), timeout)

    def send_raw(self, data: bytes, timeout: float | None = None) -> bytes:
        """Send a request and return the raw response bytes."""
        return self.send_request(data, timeout).raw

    def get_last_response(self) -> DiagnosticResponse | None:
        """Return the response of the previous request."""
        return self.last_response

    # -- convenience services --------------------------------------------------
    def change_session(self, session: int = int(SessionType.EXTENDED_DIAGNOSTIC)) -> bool:
        """Switch the diagnostic session and return whether it was accepted."""
        self._check_cancelled()
        self.last_response = self.client.change_session(session)
        return self.last_response.is_positive()

    def read_did(self, did: int) -> bytes:
        """Read one data identifier and return its payload bytes.

        Raises:
            AssertionFailure: The ECU rejected the request.
        """
        self._check_cancelled()
        self.last_response = self.client.read_data_by_identifier(did)
        if not self.last_response.is_positive():
            raise AssertionFailure(
                f"reading DID 0x{did:04X} failed: {self.last_response.summary()}"
            )
        return self.last_response.raw[3:]

    def write_did(self, did: int, data: bytes) -> bool:
        """Write a data identifier and return whether it was accepted."""
        self._check_cancelled()
        self.last_response = self.client.write_data_by_identifier(did, bytes(data))
        return self.last_response.is_positive()

    def read_dtcs(self, status_mask: int = 0xFF) -> list[dict[str, Any]]:
        """Read the DTCs matching *status_mask* as plain dictionaries."""
        from ...diagnostics.services.dtc_services.read_dtc_information import ReadDTCInformation

        self._check_cancelled()
        report = ReadDTCInformation(self.client).read_by_status_mask(status_mask)
        return [dtc.as_row() for dtc in report]

    def clear_dtcs(self, group: int = 0xFFFFFF) -> bool:
        """Clear DTCs and return whether the ECU accepted the request."""
        self._check_cancelled()
        self.last_response = self.client.clear_diagnostic_information(group)
        return self.last_response.is_positive()

    def security_unlock(self, level: int = 0x01, algorithm: str = "xor_complement") -> bool:
        """Unlock a security level using a built-in algorithm."""
        from ...diagnostics.services.security.security_access import SecurityAccess

        self._check_cancelled()
        return SecurityAccess(self.client, algorithm).execute(level).unlocked

    def routine(self, routine_id: int, sub_function: int = 0x01, data: bytes = b"") -> bool:
        """Run a routine and return whether the ECU accepted it."""
        self._check_cancelled()
        self.last_response = self.client.routine_control(sub_function, routine_id, bytes(data))
        return self.last_response.is_positive()

    def ecu_reset(self, reset_type: int = 0x01) -> bool:
        """Reset the ECU and return whether it accepted the request."""
        self._check_cancelled()
        self.last_response = self.client.ecu_reset(reset_type)
        return self.last_response.is_positive()

    def tester_present(self) -> bool:
        """Send a TesterPresent keep-alive."""
        self.last_response = self.client.tester_present()
        return self.last_response.is_positive()

    # -- assertions -----------------------------------------------------------------
    def assert_positive_response(self, message: str = "") -> None:
        """Assert the last response was positive.

        Raises:
            AssertionFailure: The response was missing or negative.
        """
        if self.last_response is None:
            raise AssertionFailure(message or "no request has been sent yet")
        if not self.last_response.is_positive():
            raise AssertionFailure(
                message or f"expected a positive response, got: {self.last_response.summary()}"
            )

    def assert_nrc(self, expected_nrc: int, message: str = "") -> None:
        """Assert the last response carried a specific NRC.

        Raises:
            AssertionFailure: The NRC differs or the response was positive.
        """
        if self.last_response is None or not self.last_response.is_negative:
            raise AssertionFailure(message or f"expected NRC 0x{expected_nrc:02X}, got a positive response")
        actual = self.last_response.nrc
        if actual != expected_nrc:
            raise AssertionFailure(
                message or f"expected NRC 0x{expected_nrc:02X}, got 0x{actual:02X}"
            )

    def assert_equal(self, actual: Any, expected: Any, message: str = "") -> None:
        """Assert two values are equal.

        Raises:
            AssertionFailure: The values differ.
        """
        if actual != expected:
            raise AssertionFailure(message or f"expected {expected!r}, got {actual!r}")

    def assert_data(self, expected: bytes, offset: int = 0, message: str = "") -> None:
        """Assert the response payload contains *expected* at *offset*.

        Raises:
            AssertionFailure: The bytes differ.
        """
        if self.last_response is None:
            raise AssertionFailure(message or "no response available")
        actual = self.last_response.raw[offset : offset + len(expected)]
        if actual != expected:
            raise AssertionFailure(
                message
                or f"expected {expected.hex(' ').upper()} at offset {offset}, got {actual.hex(' ').upper()}"
            )

    def assert_true(self, condition: bool, message: str = "") -> None:
        """Assert *condition* is true.

        Raises:
            AssertionFailure: The condition is false.
        """
        if not condition:
            raise AssertionFailure(message or "assertion failed")

    # -- utilities -------------------------------------------------------------------
    def wait(self, milliseconds: float) -> None:
        """Sleep for *milliseconds*, honouring cancellation.

        Raises:
            AssertionFailure: The run was cancelled while waiting.
        """
        deadline = time.perf_counter() + milliseconds / 1000.0
        while time.perf_counter() < deadline:
            self._check_cancelled()
            time.sleep(min(0.05, max(0.0, deadline - time.perf_counter())))

    def log(self, message: str) -> None:
        """Record a message in the script log."""
        self.context.logs.append(message)
        _logger.info("[script] %s", message)

    def set_variable(self, name: str, value: Any) -> None:
        """Store a value for later steps of the sequence."""
        self.context.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Return a previously stored value."""
        return self.context.variables.get(name, default)

    @property
    def session(self) -> int:
        """Return the currently active diagnostic session."""
        return self.client.state.active_session

    @property
    def is_unlocked(self) -> bool:
        """Return ``True`` when a security level is unlocked."""
        return self.client.state.unlocked_level is not None

    def _check_cancelled(self) -> None:
        """Abort the script when the runner requested cancellation.

        Raises:
            AssertionFailure: The run was cancelled.
        """
        if self.context.cancelled:
            raise AssertionFailure("execution cancelled by the operator")


__all__ = ["DiagnosticAPI", "ScriptContext", "AssertionFailure"]
