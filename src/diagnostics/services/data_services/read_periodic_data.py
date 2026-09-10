"""ReadDataByPeriodicIdentifier - SID 0x2A."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable

from ....core.enums.sid_enums import ServiceID
from ....core.exceptions import RequestValidationError
from ....core.models.response_data_model import DiagnosticResponse
from ..base_service import BaseService

_logger = logging.getLogger(__name__)


class TransmissionMode(IntEnum):
    """Periodic transmission modes."""

    STOP_SENDING = 0x04
    SEND_AT_SLOW_RATE = 0x01
    SEND_AT_MEDIUM_RATE = 0x02
    SEND_AT_FAST_RATE = 0x03


@dataclass(slots=True)
class PeriodicReading:
    """One sample received from a periodic identifier."""

    identifier: int
    data: bytes
    timestamp: float


@dataclass(slots=True)
class PeriodicSubscription:
    """State of the periodic identifiers currently scheduled."""

    identifiers: list[int] = field(default_factory=list)
    mode: TransmissionMode = TransmissionMode.SEND_AT_MEDIUM_RATE
    active: bool = False


class ReadDataByPeriodicIdentifier(BaseService):
    """Schedule the ECU to send data records periodically."""

    service_id = int(ServiceID.READ_DATA_BY_PERIODIC_IDENTIFIER)
    min_request_length = 3
    has_sub_function = True

    def __init__(self, client) -> None:  # noqa: ANN001
        """Store the client and prepare the subscription state."""
        super().__init__(client)
        self.subscription = PeriodicSubscription()
        self._collector: threading.Thread | None = None
        self._stop = threading.Event()

    def build_request(
        self,
        mode: int = int(TransmissionMode.SEND_AT_MEDIUM_RATE),
        *identifiers: int,
    ) -> bytes:
        """Return ``2A <mode> <periodic identifiers...>``.

        Raises:
            RequestValidationError: No identifier was supplied for a start
                request, or an identifier exceeds one byte.
        """
        if mode != int(TransmissionMode.STOP_SENDING) and not identifiers:
            raise RequestValidationError("at least one periodic identifier is required")
        for identifier in identifiers:
            if not 0 <= identifier <= 0xFF:
                raise RequestValidationError(
                    "a periodic identifier is the low byte of the DID", {"value": hex(identifier)}
                )
        return bytes([self.service_id, mode & 0xFF, *[i & 0xFF for i in identifiers]])

    def parse_response(self, response: DiagnosticResponse) -> bool:
        """Return ``True`` when the schedule was accepted."""
        return response.is_positive()

    def start(
        self,
        identifiers: list[int],
        mode: TransmissionMode = TransmissionMode.SEND_AT_MEDIUM_RATE,
    ) -> bool:
        """Start periodic transmission of *identifiers*."""
        payload = self.build_request(int(mode), *identifiers)
        accepted = self.parse_response(self.send(payload))
        if accepted:
            self.subscription = PeriodicSubscription(list(identifiers), mode, True)
        return accepted

    def stop(self, identifiers: list[int] | None = None) -> bool:
        """Stop periodic transmission of *identifiers* (or of everything)."""
        targets = identifiers if identifiers is not None else self.subscription.identifiers
        payload = self.build_request(int(TransmissionMode.STOP_SENDING), *targets)
        accepted = self.parse_response(self.send(payload))
        if accepted:
            self.subscription.active = False
        self._stop.set()
        return accepted

    def collect(self, on_sample: Callable[[PeriodicReading], None], duration_s: float = 5.0) -> None:
        """Collect periodic responses for *duration_s* seconds.

        The callback is invoked on a background thread for every received
        sample; use Qt signals to forward the values to the UI.
        """
        import time

        def worker() -> None:
            deadline = time.perf_counter() + duration_s
            while not self._stop.is_set() and time.perf_counter() < deadline:
                payload = self.client.transport.receive(0.2)
                if not payload or len(payload) < 2:
                    continue
                on_sample(PeriodicReading(payload[0], bytes(payload[1:]), time.time()))

        self._stop.clear()
        self._collector = threading.Thread(target=worker, name="periodic-did", daemon=True)
        self._collector.start()

    def execute(self, identifiers: list[int], mode: TransmissionMode = TransmissionMode.SEND_AT_MEDIUM_RATE) -> bool:
        """Alias of :meth:`start` satisfying the service interface."""
        return self.start(identifiers, mode)


__all__ = [
    "ReadDataByPeriodicIdentifier",
    "TransmissionMode",
    "PeriodicReading",
    "PeriodicSubscription",
]
