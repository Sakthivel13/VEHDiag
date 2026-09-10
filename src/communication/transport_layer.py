"""Unified transport layer abstraction.

The transport layer is the single door between the diagnostic layer and the
protocol handlers. It owns the request/response serialisation, the connection
state machine, priority queuing and the timing budget (P2, P2*, S3).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from ..core.enums.protocol_enums import ConnectionState, ProtocolType
from ..core.event_bus import EventBus, EventType, get_event_bus
from ..core.exceptions import CommunicationTimeoutError, NotConnectedError
from ..core.interfaces.i_protocol_handler import IProtocolHandler
from ..utils.timer_utils import Stopwatch
from .message_queue import Priority, PriorityMessageQueue
from .rate_limiter import RateLimiter

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TransportTiming:
    """Client side timing budget used for every request.

    Attributes:
        p2_client_ms: Time to wait for the first response.
        p2_star_client_ms: Time to wait after each ``0x78`` pending response.
        s3_client_ms: Inactivity limit before a non-default session expires.
        inter_request_gap_ms: Minimum pause between two consecutive requests.
    """

    p2_client_ms: float = 150.0
    p2_star_client_ms: float = 5000.0
    s3_client_ms: float = 4000.0
    inter_request_gap_ms: float = 0.0


@dataclass(slots=True)
class TransportStatistics:
    """Counters displayed in the status bar and the trace viewer."""

    requests: int = 0
    responses: int = 0
    timeouts: int = 0
    errors: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_round_trip_ms: float = 0.0

    def average_note(self) -> str:
        """Return a short human readable summary of the counters."""
        return (
            f"{self.requests} requests, {self.responses} responses, "
            f"{self.timeouts} timeouts, last {self.last_round_trip_ms:.1f} ms"
        )


class TransportLayer:
    """Serialises diagnostic exchanges over one protocol handler.

    Args:
        protocol: The active protocol handler.
        timing: Client timing budget.
        event_bus: Bus used to publish transport events.
        rate_limit: Optional cap on requests per second.

    Example:
        >>> from src.communication.vci_drivers.virtual import VirtualVCIDriver
        >>> from src.communication.protocols.can import CANProtocol
        >>> driver = VirtualVCIDriver(); driver.connect()
        >>> transport = TransportLayer(CANProtocol(driver))
        >>> transport.connect()
        >>> transport.request(bytes.fromhex("1003"), timeout=2.0).hex()
        '5003003201f4'
        >>> transport.disconnect(); driver.disconnect()
    """

    def __init__(
        self,
        protocol: IProtocolHandler,
        timing: TransportTiming | None = None,
        event_bus: EventBus | None = None,
        rate_limit: float = 0.0,
    ) -> None:
        """Store the protocol handler and prepare the queues."""
        self.protocol = protocol
        self.timing = timing or TransportTiming()
        self.bus = event_bus or get_event_bus()
        self.statistics = TransportStatistics()
        self.queue: PriorityMessageQueue[bytes] = PriorityMessageQueue(maxsize=1024)
        self.rate_limiter = RateLimiter(rate_limit) if rate_limit else None
        self._state = ConnectionState.DISCONNECTED
        self._lock = threading.RLock()
        self._last_request_at = 0.0

    # -- lifecycle ----------------------------------------------------------
    @property
    def state(self) -> ConnectionState:
        """Return the transport connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Return ``True`` when requests may be sent."""
        return self._state is ConnectionState.CONNECTED

    @property
    def protocol_type(self) -> ProtocolType:
        """Return the protocol carried by this transport."""
        return self.protocol.protocol_type

    def connect(self) -> None:
        """Initialise the protocol handler and enter the connected state."""
        with self._lock:
            self._state = ConnectionState.CONNECTING
            try:
                self.protocol.initialize()
            except Exception:
                self._state = ConnectionState.ERROR
                raise
            self._state = ConnectionState.CONNECTED

    def disconnect(self) -> None:
        """Shut the protocol handler down and clear the queues."""
        with self._lock:
            self._state = ConnectionState.DISCONNECTING
            try:
                self.protocol.shutdown()
            finally:
                self.queue.clear()
                self._state = ConnectionState.DISCONNECTED

    # -- exchanges ------------------------------------------------------------
    def send(self, payload: bytes, functional: bool = False) -> None:
        """Send *payload* without waiting for a response.

        Raises:
            NotConnectedError: The transport is not connected.
        """
        self._require_connection()
        self._respect_gap()
        if self.rate_limiter is not None:
            self.rate_limiter.acquire()
        self.protocol.send_message(payload, functional=functional)
        self.statistics.requests += 1
        self.statistics.bytes_sent += len(payload)
        self._last_request_at = time.perf_counter()
        self.bus.publish(
            EventType.DIAG_REQUEST_SENT,
            {"payload": payload, "functional": functional},
            "TransportLayer",
        )

    def receive(self, timeout: float | None = None) -> bytes | None:
        """Receive the next payload without sending anything first."""
        self._require_connection()
        window = timeout if timeout is not None else self.timing.p2_client_ms / 1000.0
        payload = self.protocol.receive_message(window)
        if payload:
            self.statistics.responses += 1
            self.statistics.bytes_received += len(payload)
        return payload

    def request(
        self,
        payload: bytes,
        timeout: float | None = None,
        functional: bool = False,
        priority: Priority = Priority.NORMAL,
    ) -> bytes | None:
        """Send *payload* and wait for one response payload.

        Args:
            payload: Complete UDS request.
            timeout: Response timeout in seconds; defaults to P2 client.
            functional: Use functional addressing.
            priority: Reserved for the queued execution mode.

        Returns:
            The response payload, or ``None`` when nothing arrived in time.

        Raises:
            NotConnectedError: The transport is not connected.
        """
        self._require_connection()
        window = timeout if timeout is not None else self.timing.p2_client_ms / 1000.0
        watch = Stopwatch().start()
        with self._lock:
            self.send(payload, functional=functional)
            response = self.protocol.receive_message(window)
        self.statistics.last_round_trip_ms = watch.stop()
        if response is None:
            self.statistics.timeouts += 1
            return None
        self.statistics.responses += 1
        self.statistics.bytes_received += len(response)
        self.bus.publish(
            EventType.DIAG_RESPONSE_RECEIVED,
            {
                "request": payload,
                "response": response,
                "elapsed_ms": self.statistics.last_round_trip_ms,
            },
            "TransportLayer",
        )
        return response

    def request_or_raise(self, payload: bytes, timeout: float | None = None) -> bytes:
        """Like :meth:`request` but raise instead of returning ``None``.

        Raises:
            CommunicationTimeoutError: No response arrived in time.
        """
        response = self.request(payload, timeout)
        if response is None:
            raise CommunicationTimeoutError(
                "no response received from the ECU",
                {"request": payload.hex(" ").upper(), "timeout_s": timeout},
            )
        return response

    def flush(self) -> None:
        """Discard any buffered frames in the protocol handler."""
        flusher = getattr(self.protocol, "flush", None)
        if callable(flusher):
            flusher()

    # -- helpers ---------------------------------------------------------------
    def set_timing(self, **values: float) -> None:
        """Update the client timing budget and forward it to the protocol."""
        for key, value in values.items():
            if hasattr(self.timing, key):
                setattr(self.timing, key, float(value))
        self.protocol.set_timing(**values)

    def get_info(self) -> dict[str, Any]:
        """Return a mapping describing the transport for the UI."""
        return {
            "state": self._state.value,
            "protocol": self.protocol_type.value,
            "timing": asdict(self.timing),
            "statistics": asdict(self.statistics),
            "protocol_info": self.protocol.get_protocol_info(),
        }

    def _require_connection(self) -> None:
        """Raise when the transport is not connected.

        Raises:
            NotConnectedError: The transport has not been connected.
        """
        if not self.is_connected:
            raise NotConnectedError(
                "the transport layer is not connected", {"state": self._state.value}
            )

    def _respect_gap(self) -> None:
        """Sleep so consecutive requests honour the inter-request gap."""
        gap = self.timing.inter_request_gap_ms / 1000.0
        if gap <= 0 or not self._last_request_at:
            return
        elapsed = time.perf_counter() - self._last_request_at
        if elapsed < gap:
            time.sleep(gap - elapsed)

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<TransportLayer {self.protocol_type.value} {self._state.value}>"


__all__ = ["TransportLayer", "TransportTiming", "TransportStatistics"]
