"""UDS client (ISO 14229-1).

The client owns the request/response cycle: it builds requests, applies the
suppress-positive-response bit, waits through ``0x78`` pending responses,
retries on ``0x21`` busyRepeatRequest, validates the echoed service identifier
and produces a :class:`DiagnosticResponse` for every exchange.

Higher level services (``src.diagnostics.services.*``) delegate the actual
transmission to this class.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable

from ..communication.transport_layer import TransportLayer
from ..core.enums.nrc_enums import NegativeResponseCode
from ..core.enums.session_enums import SecurityState, SessionType
from ..core.enums.sid_enums import (
    NEGATIVE_RESPONSE_SID,
    POSITIVE_RESPONSE_OFFSET,
    ServiceID,
)
from ..core.event_bus import EventBus, EventType, get_event_bus
from ..core.exceptions import (
    InvalidResponseError,
    NegativeResponseError,
    NotConnectedError,
    RequestValidationError,
)
from ..core.models.response_data_model import DiagnosticResponse
from ..core.models.session_model import SessionState, SessionTiming
from ..utils.timer_utils import Stopwatch
from ..utils.validation_utils import validate_uds_request
from .nrc_handler import NRCHandler
from .pending_response_handler import PendingResponseHandler
from .suppress_positive_handler import apply_suppression, is_suppressed

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UDSClientConfig:
    """Behavioural configuration of the client.

    Attributes:
        p2_client_ms: Timeout for the first response.
        p2_star_client_ms: Timeout after each pending response.
        max_pending_responses: Maximum consecutive ``0x78`` responses accepted.
        retry_on_busy: Retry automatically on ``0x21`` busyRepeatRequest.
        max_retries: Maximum number of automatic retries.
        retry_delay_ms: Pause before an automatic retry.
        suppress_positive_response: Set the suppression bit by default.
        validate_session: Refuse services the active session forbids.
        raise_on_negative: Raise :class:`NegativeResponseError` instead of
            returning a negative :class:`DiagnosticResponse`.
    """

    p2_client_ms: float = 150.0
    p2_star_client_ms: float = 5000.0
    max_pending_responses: int = 20
    retry_on_busy: bool = True
    max_retries: int = 3
    retry_delay_ms: float = 100.0
    suppress_positive_response: bool = False
    validate_session: bool = False
    raise_on_negative: bool = False


@dataclass(slots=True)
class UDSStatistics:
    """Counters describing the client activity."""

    requests: int = 0
    positive: int = 0
    negative: int = 0
    timeouts: int = 0
    retries: int = 0
    pending: int = 0


class UDSClient:
    """A thread-safe UDS client bound to one :class:`TransportLayer`.

    Args:
        transport: The transport used to exchange payloads.
        config: Client behaviour configuration.
        event_bus: Bus used to publish diagnostic events.

    Example:
        >>> from src.communication import ConnectionManager, ConnectionProfile
        >>> manager = ConnectionManager()
        >>> transport = manager.connect(ConnectionProfile())
        >>> client = UDSClient(transport)
        >>> client.change_session(0x03).is_positive()
        True
        >>> client.read_data_by_identifier(0xF190).data.hex()[4:]
        '5742415a5a5a30474d31323334353637'
        >>> manager.disconnect()
    """

    def __init__(
        self,
        transport: TransportLayer,
        config: UDSClientConfig | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Create the client and its helper handlers."""
        self.transport = transport
        self.config = config or UDSClientConfig()
        self.bus = event_bus or get_event_bus()
        self.state = SessionState()
        self.statistics = UDSStatistics()
        self.nrc_handler = NRCHandler(self.config.max_retries)
        self.pending_handler = PendingResponseHandler(
            self.config.p2_star_client_ms, self.config.max_pending_responses
        )
        self.last_response: DiagnosticResponse | None = None
        self._lock = threading.RLock()
        self._listeners: list[Callable[[DiagnosticResponse], None]] = []

    # -- core exchange ------------------------------------------------------
    def send_request(
        self,
        payload: bytes,
        timeout: float | None = None,
        functional: bool = False,
        suppress_response: bool | None = None,
    ) -> DiagnosticResponse:
        """Send a raw UDS *payload* and return the parsed response.

        Args:
            payload: Complete request starting with the service identifier.
            timeout: Override for the P2 client timeout, in seconds.
            functional: Use functional (broadcast) addressing.
            suppress_response: Force or forbid the suppression bit.

        Returns:
            A :class:`DiagnosticResponse`; check :meth:`DiagnosticResponse.is_positive`.

        Raises:
            RequestValidationError: The payload is malformed.
            NotConnectedError: The transport is not connected.
            NegativeResponseError: Only when ``raise_on_negative`` is set.
        """
        validate_uds_request(payload)
        if not self.transport.is_connected:
            raise NotConnectedError("cannot send a UDS request without a connection")

        suppress = (
            self.config.suppress_positive_response
            if suppress_response is None
            else suppress_response
        )
        request = apply_suppression(payload, True) if suppress else payload
        suppressed = is_suppressed(request)
        window = timeout if timeout is not None else self.config.p2_client_ms / 1000.0

        with self._lock:
            response = self._exchange(request, window, functional, suppressed)
            self.last_response = response
            self.state.touch()

        self._notify(response)
        if response.is_negative:
            self.statistics.negative += 1
            nrc = response.raw[2]
            self.nrc_handler.record(nrc)
            self.bus.publish(
                EventType.DIAG_NRC_RECEIVED,
                {
                    "service": request[0],
                    "nrc": nrc,
                    "info": self.nrc_handler.describe(nrc).summary,
                },
                "UDSClient",
            )
            if self.config.raise_on_negative:
                raise NegativeResponseError(
                    request[0], nrc, {"request": request.hex(" ").upper()}
                )
        elif response.timed_out:
            self.statistics.timeouts += 1
        else:
            self.statistics.positive += 1
        return response

    def _exchange(
        self,
        request: bytes,
        window: float,
        functional: bool,
        suppressed: bool,
    ) -> DiagnosticResponse:
        """Perform the transmission, retries and pending handling."""
        attempt = 0
        watch = Stopwatch().start()
        pending_total = 0
        while True:
            attempt += 1
            self.statistics.requests += 1
            raw = self.transport.request(request, window, functional=functional)
            raw, pending = self.pending_handler.resolve(
                raw, lambda t: self.transport.receive(t)
            )
            pending_total += pending
            self.statistics.pending += pending

            if raw is None:
                if suppressed:
                    return DiagnosticResponse(
                        request=request,
                        raw=b"",
                        elapsed_ms=watch.stop(),
                        suppressed=True,
                        pending_count=pending_total,
                    )
                return DiagnosticResponse(
                    request=request,
                    raw=b"",
                    elapsed_ms=watch.stop(),
                    timed_out=True,
                    pending_count=pending_total,
                )

            response = DiagnosticResponse(
                request=request,
                raw=raw,
                elapsed_ms=watch.elapsed_ms,
                pending_count=pending_total,
                metadata={"attempt": attempt, "functional": functional},
            )
            if (
                response.is_negative
                and self.config.retry_on_busy
                and self.nrc_handler.should_retry(raw[2], attempt)
                and raw[2] == int(NegativeResponseCode.BUSY_REPEAT_REQUEST)
            ):
                self.statistics.retries += 1
                import time

                time.sleep(self.config.retry_delay_ms / 1000.0)
                continue
            response.elapsed_ms = watch.stop()
            self._validate_echo(request, response)
            return response

    def _validate_echo(self, request: bytes, response: DiagnosticResponse) -> None:
        """Verify the response echoes the requested service identifier.

        Raises:
            InvalidResponseError: The first byte is neither the positive echo
                nor a well formed negative response.
        """
        if not response.raw:
            return
        first = response.raw[0]
        if first == NEGATIVE_RESPONSE_SID:
            if len(response.raw) < 3:
                raise InvalidResponseError(
                    "truncated negative response", {"raw": response.raw.hex(" ").upper()}
                )
            return
        expected = (request[0] + POSITIVE_RESPONSE_OFFSET) & 0xFF
        if first != expected:
            raise InvalidResponseError(
                "the ECU echoed an unexpected service identifier",
                {
                    "expected": f"0x{expected:02X}",
                    "received": f"0x{first:02X}",
                    "raw": response.raw.hex(" ").upper(),
                },
            )

    # -- convenience wrappers ------------------------------------------------
    def send(self, *bytes_or_ints: int | bytes) -> DiagnosticResponse:
        """Build a request from ints/bytes and send it.

        Example:
            >>> # client.send(0x22, 0xF1, 0x90)
            >>> None
        """
        payload = bytearray()
        for item in bytes_or_ints:
            if isinstance(item, int):
                payload.append(item & 0xFF)
            else:
                payload.extend(item)
        return self.send_request(bytes(payload))

    def change_session(self, session: int = int(SessionType.EXTENDED_DIAGNOSTIC)) -> DiagnosticResponse:
        """Send DiagnosticSessionControl (0x10) and update the session state."""
        response = self.send_request(bytes([ServiceID.DIAGNOSTIC_SESSION_CONTROL, session & 0xFF]))
        if response.is_positive():
            timing = SessionTiming.from_response(response.raw[2:]) if len(response.raw) > 2 else None
            self.state.apply_session(session, timing)
            if timing is not None:
                self.config.p2_client_ms = max(self.config.p2_client_ms, timing.p2_server_ms)
                self.config.p2_star_client_ms = max(
                    self.config.p2_star_client_ms, timing.p2_star_server_ms
                )
                self.pending_handler.p2_star_ms = self.config.p2_star_client_ms
            self.bus.publish(
                EventType.DIAG_SESSION_CHANGED,
                {"session": session, "label": self.state.session_label},
                "UDSClient",
            )
        return response

    def ecu_reset(self, reset_type: int = 0x01) -> DiagnosticResponse:
        """Send ECUReset (0x11)."""
        response = self.send_request(bytes([ServiceID.ECU_RESET, reset_type & 0xFF]))
        if response.is_positive():
            self.state.reset()
            self.bus.publish(EventType.DIAG_ECU_RESET, {"type": reset_type}, "UDSClient")
        return response

    def read_data_by_identifier(self, *dids: int) -> DiagnosticResponse:
        """Send ReadDataByIdentifier (0x22) for one or more identifiers.

        Raises:
            RequestValidationError: No identifier was supplied.
        """
        if not dids:
            raise RequestValidationError("at least one data identifier is required")
        payload = bytearray([ServiceID.READ_DATA_BY_IDENTIFIER])
        for did in dids:
            payload.extend((did & 0xFFFF).to_bytes(2, "big"))
        return self.send_request(bytes(payload))

    def write_data_by_identifier(self, did: int, data: bytes) -> DiagnosticResponse:
        """Send WriteDataByIdentifier (0x2E)."""
        payload = bytes([ServiceID.WRITE_DATA_BY_IDENTIFIER]) + (did & 0xFFFF).to_bytes(2, "big") + data
        return self.send_request(payload)

    def read_dtc_information(self, sub_function: int, *extra: int) -> DiagnosticResponse:
        """Send ReadDTCInformation (0x19) with an arbitrary sub-function."""
        payload = bytes([ServiceID.READ_DTC_INFORMATION, sub_function & 0xFF, *[b & 0xFF for b in extra]])
        return self.send_request(payload, timeout=max(1.0, self.config.p2_client_ms / 1000.0))

    def clear_diagnostic_information(self, group: int = 0xFFFFFF) -> DiagnosticResponse:
        """Send ClearDiagnosticInformation (0x14)."""
        payload = bytes([ServiceID.CLEAR_DIAGNOSTIC_INFORMATION]) + (group & 0xFFFFFF).to_bytes(3, "big")
        response = self.send_request(payload, timeout=5.0)
        if response.is_positive():
            self.bus.publish(EventType.DIAG_DTC_CLEARED, {"group": group}, "UDSClient")
        return response

    def security_access(self, level: int, key: bytes = b"") -> DiagnosticResponse:
        """Send SecurityAccess (0x27) as a seed request or a key submission."""
        payload = bytes([ServiceID.SECURITY_ACCESS, level & 0xFF]) + key
        response = self.send_request(payload)
        if response.is_positive() and key:
            self.state.apply_unlock(level)
            self.bus.publish(EventType.DIAG_SECURITY_UNLOCKED, {"level": level}, "UDSClient")
        elif response.is_negative and key:
            self.state.security_state = SecurityState.LOCKED
            self.bus.publish(
                EventType.DIAG_SECURITY_FAILED,
                {"level": level, "nrc": response.raw[2]},
                "UDSClient",
            )
        return response

    def routine_control(self, sub_function: int, routine_id: int, data: bytes = b"") -> DiagnosticResponse:
        """Send RoutineControl (0x31)."""
        payload = (
            bytes([ServiceID.ROUTINE_CONTROL, sub_function & 0xFF])
            + (routine_id & 0xFFFF).to_bytes(2, "big")
            + data
        )
        return self.send_request(payload, timeout=5.0)

    def io_control(self, did: int, control_parameter: int, state: bytes = b"") -> DiagnosticResponse:
        """Send InputOutputControlByIdentifier (0x2F)."""
        payload = (
            bytes([ServiceID.INPUT_OUTPUT_CONTROL_BY_IDENTIFIER])
            + (did & 0xFFFF).to_bytes(2, "big")
            + bytes([control_parameter & 0xFF])
            + state
        )
        return self.send_request(payload)

    def tester_present(self, suppress: bool = True) -> DiagnosticResponse:
        """Send TesterPresent (0x3E)."""
        return self.send_request(
            bytes([ServiceID.TESTER_PRESENT, 0x00]), suppress_response=suppress
        )

    def control_dtc_setting(self, on: bool) -> DiagnosticResponse:
        """Send ControlDTCSetting (0x85)."""
        return self.send_request(bytes([ServiceID.CONTROL_DTC_SETTING, 0x01 if on else 0x02]))

    def communication_control(self, control_type: int, communication_type: int = 0x03) -> DiagnosticResponse:
        """Send CommunicationControl (0x28)."""
        return self.send_request(
            bytes([ServiceID.COMMUNICATION_CONTROL, control_type & 0xFF, communication_type & 0xFF])
        )

    # -- observation ------------------------------------------------------------
    def add_listener(self, callback: Callable[[DiagnosticResponse], None]) -> None:
        """Register *callback* to be notified about every response."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[DiagnosticResponse], None]) -> None:
        """Remove a previously registered listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, response: DiagnosticResponse) -> None:
        """Invoke every listener, ignoring their exceptions."""
        for listener in list(self._listeners):
            try:
                listener(response)
            except Exception:  # noqa: BLE001 - listeners must not break the client
                _logger.exception("UDS response listener failed")

    def get_info(self) -> dict[str, Any]:
        """Return a mapping describing the client state for the UI."""
        from dataclasses import asdict

        return {
            "session": self.state.session_label,
            "session_id": self.state.active_session,
            "security": self.state.security_state.value,
            "unlocked_level": self.state.unlocked_level,
            "statistics": asdict(self.statistics),
            "config": asdict(self.config),
        }

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<UDSClient session={self.state.session_label} {self.statistics.requests} requests>"


__all__ = ["UDSClient", "UDSClientConfig", "UDSStatistics"]
