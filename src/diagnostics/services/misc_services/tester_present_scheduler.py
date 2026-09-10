"""Automatic TesterPresent transmission."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from ....core.event_bus import EventType
from ....utils.timer_utils import PeriodicTimer
from .tester_present import TesterPresent

_logger = logging.getLogger(__name__)

#: Default keep-alive interval, comfortably below the usual 5 s S3 timer.
DEFAULT_INTERVAL_MS = 2000.0


@dataclass(slots=True)
class SchedulerStatistics:
    """Counters describing the keep-alive activity."""

    sent: int = 0
    failed: int = 0
    last_sent_at: float = 0.0


class TesterPresentScheduler:
    """Sends TesterPresent periodically while a session is active.

    Args:
        client: UDS client used for transmission.
        interval_ms: Delay between two keep-alive messages.
        suppress_response: Set the suppress positive response bit.
        only_when_idle: Skip the keep-alive when another request was sent
            recently, avoiding unnecessary bus load.
    """

    def __init__(
        self,
        client,  # noqa: ANN001
        interval_ms: float = DEFAULT_INTERVAL_MS,
        suppress_response: bool = True,
        only_when_idle: bool = True,
    ) -> None:
        """Create the scheduler in the stopped state."""
        self.client = client
        self.interval_ms = interval_ms
        self.suppress_response = suppress_response
        self.only_when_idle = only_when_idle
        self.statistics = SchedulerStatistics()
        self.service = TesterPresent(client)
        self._timer: PeriodicTimer | None = None
        self._lock = threading.RLock()

    @property
    def is_running(self) -> bool:
        """Return ``True`` while the keep-alive thread is active."""
        return self._timer is not None and self._timer.is_running

    def start(self, interval_ms: float | None = None) -> None:
        """Start sending TesterPresent periodically."""
        with self._lock:
            if self.is_running:
                return
            if interval_ms is not None:
                self.interval_ms = interval_ms
            self._timer = PeriodicTimer(self.interval_ms / 1000.0, self._tick, "tester-present")
            self._timer.start()
            _logger.info("tester present started (%.0f ms)", self.interval_ms)

    def stop(self) -> None:
        """Stop sending TesterPresent."""
        with self._lock:
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
                _logger.info("tester present stopped")

    def sync_with_session(self) -> None:
        """Start or stop the keep-alive to match the active session."""
        if self.client.state.requires_tester_present:
            self.start()
        else:
            self.stop()

    def _tick(self) -> None:
        """Send one keep-alive message, skipping it when the bus is busy."""
        if self.only_when_idle:
            idle_ms = self.client.state.seconds_since_activity * 1000.0
            if idle_ms < self.interval_ms * 0.5:
                return
        try:
            ok = self.service.execute(self.suppress_response)
        except Exception as exc:  # noqa: BLE001 - a keep-alive must not crash
            self.statistics.failed += 1
            _logger.debug("tester present failed: %s", exc)
            return
        if ok:
            self.statistics.sent += 1
            self.statistics.last_sent_at = time.time()
        else:
            self.statistics.failed += 1
            self.client.bus.publish(
                EventType.COMM_ERROR,
                {"error": "tester present was not acknowledged"},
                "TesterPresentScheduler",
            )

    def __enter__(self) -> "TesterPresentScheduler":
        """Start the keep-alive for use in a ``with`` block."""
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        """Stop the keep-alive when leaving a ``with`` block."""
        self.stop()


__all__ = ["TesterPresentScheduler", "SchedulerStatistics", "DEFAULT_INTERVAL_MS"]
