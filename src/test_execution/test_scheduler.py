"""Scheduled and repeated test execution."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ..core.models.test_sequence_model import TestResult, TestSequence
from .test_runner import TestRunner

_logger = logging.getLogger(__name__)


class ScheduleMode(str, Enum):
    """How a scheduled run repeats."""

    ONCE = "ONCE"
    INTERVAL = "INTERVAL"
    COUNT = "COUNT"
    CONTINUOUS = "CONTINUOUS"


@dataclass(slots=True)
class ScheduleConfig:
    """Configuration of a scheduled execution.

    Attributes:
        mode: Repetition mode.
        interval_s: Delay between two runs for interval based modes.
        repetitions: Number of runs for :attr:`ScheduleMode.COUNT`.
        start_delay_s: Delay before the first run.
        stop_on_failure: Stop repeating after a failed run.
    """

    mode: ScheduleMode = ScheduleMode.ONCE
    interval_s: float = 60.0
    repetitions: int = 1
    start_delay_s: float = 0.0
    stop_on_failure: bool = True


@dataclass(slots=True)
class ScheduleStatistics:
    """Counters describing the scheduled runs."""

    runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    last_run_at: float = 0.0
    next_run_at: float = 0.0


class TestScheduler:
    """Repeat a sequence on a timer (soak testing, EOL loops).

    Args:
        runner: The runner executing the sequence.
        config: Schedule configuration.
        on_run_complete: Callback invoked with the results of each run.
    """

    def __init__(
        self,
        runner: TestRunner,
        config: ScheduleConfig | None = None,
        on_run_complete: Callable[[list[TestResult]], None] | None = None,
    ) -> None:
        """Create the scheduler in the stopped state."""
        self.runner = runner
        self.config = config or ScheduleConfig()
        self.on_run_complete = on_run_complete
        self.statistics = ScheduleStatistics()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def is_running(self) -> bool:
        """Return ``True`` while the schedule thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def start(self, sequence: TestSequence | None = None) -> None:
        """Start the scheduled execution."""
        if self.is_running:
            return
        if sequence is not None:
            self.runner.load_sequence(sequence)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="test-scheduler", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the schedule and cancel a running sequence."""
        self._stop.set()
        self.runner.cancel()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def _run(self) -> None:
        """Thread body executing the sequence according to the schedule."""
        if self.config.start_delay_s and self._stop.wait(self.config.start_delay_s):
            return
        iteration = 0
        while not self._stop.is_set():
            iteration += 1
            self.statistics.runs += 1
            self.statistics.last_run_at = time.time()
            results = self.runner.execute_all()
            summary = self.runner.summary()
            if summary.successful:
                self.statistics.successful_runs += 1
            else:
                self.statistics.failed_runs += 1
            if self.on_run_complete is not None:
                try:
                    self.on_run_complete(results)
                except Exception:  # noqa: BLE001
                    _logger.exception("schedule completion callback failed")
            if self.config.stop_on_failure and not summary.successful:
                _logger.info("schedule stopped after a failed run")
                return
            if self.config.mode is ScheduleMode.ONCE:
                return
            if self.config.mode is ScheduleMode.COUNT and iteration >= self.config.repetitions:
                return
            self.statistics.next_run_at = time.time() + self.config.interval_s
            if self._stop.wait(self.config.interval_s):
                return


__all__ = ["TestScheduler", "ScheduleConfig", "ScheduleMode", "ScheduleStatistics"]
