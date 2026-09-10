"""Test execution controller for scheduled and parallel runs.

The developer panel uses :class:`DeveloperModeController` for interactive runs;
this controller adds the batch capabilities: repeating a sequence on a timer
(soak testing) and running several ECUs in parallel.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from src.core.models.test_sequence_model import TestResult, TestSequence
from src.diagnostics.uds_client import UDSClient
from src.test_execution.parallel_test_runner import ECUTarget, ParallelResult, ParallelTestRunner
from src.test_execution.test_result_collector import TestResultCollector
from src.test_execution.test_runner import RunnerOptions, TestRunner
from src.test_execution.test_scheduler import ScheduleConfig, ScheduleMode, TestScheduler

_logger = logging.getLogger(__name__)


class _ScheduleThread(QThread):
    """Runs the scheduler off the UI thread."""

    #: Emitted with the results of every completed run.
    run_completed = Signal(object)
    #: Emitted when the schedule stops.
    finished_schedule = Signal()

    def __init__(self, scheduler: TestScheduler, sequence: TestSequence) -> None:
        """Store the scheduler and the sequence."""
        super().__init__()
        self.scheduler = scheduler
        self.sequence = sequence

    def run(self) -> None:
        """Start the scheduler and wait for it to finish."""
        self.scheduler.on_run_complete = self.run_completed.emit
        self.scheduler.start(self.sequence)
        while self.scheduler.is_running:
            self.msleep(200)
        self.finished_schedule.emit()


class TestExecutionController(QObject):
    """Runs sequences repeatedly or against several ECUs at once.

    Args:
        window: The main window used for notifications.
        options: Runner options shared by every execution.
    """

    #: Emitted with the summary after each scheduled run.
    run_completed = Signal(str)
    #: Emitted with the per-target results after a parallel run.
    parallel_completed = Signal(object)

    def __init__(self, window: Any = None, options: RunnerOptions | None = None) -> None:
        """Create the controller without a client."""
        super().__init__()
        self.window = window
        self.options = options or RunnerOptions()
        self.client: UDSClient | None = None
        self.collector = TestResultCollector()
        self.scheduler: TestScheduler | None = None
        self.parallel = ParallelTestRunner(self.options)
        self._thread: _ScheduleThread | None = None

    # -- lifecycle ----------------------------------------------------------
    def attach_client(self, client: UDSClient) -> None:
        """Bind the controller to a diagnostic client."""
        self.client = client

    def detach(self) -> None:
        """Stop everything and release the client."""
        self.stop_schedule()
        self.parallel.cancel()
        self.client = None

    # -- scheduled execution ----------------------------------------------------
    def start_schedule(
        self,
        sequence: TestSequence,
        mode: ScheduleMode = ScheduleMode.COUNT,
        repetitions: int = 10,
        interval_s: float = 30.0,
        stop_on_failure: bool = True,
    ) -> bool:
        """Repeat *sequence* according to the schedule configuration."""
        if self.client is None:
            self._notify("Connect to a VCI before scheduling tests", "warning")
            return False
        runner = TestRunner(self.client, self.options)
        self.scheduler = TestScheduler(
            runner,
            ScheduleConfig(
                mode=mode,
                repetitions=repetitions,
                interval_s=interval_s,
                stop_on_failure=stop_on_failure,
            ),
        )
        self._thread = _ScheduleThread(self.scheduler, sequence)
        self._thread.run_completed.connect(self._on_run_completed)
        self._thread.finished_schedule.connect(
            lambda: self._notify("Scheduled execution finished", "info")
        )
        self._thread.start()
        self._notify(f"Scheduled execution started ({mode.value.lower()})", "info")
        return True

    def stop_schedule(self) -> None:
        """Stop a running schedule."""
        if self.scheduler is not None:
            self.scheduler.stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait(3000)
        self._thread = None

    @property
    def is_scheduled(self) -> bool:
        """Return ``True`` while a schedule is active."""
        return self.scheduler is not None and self.scheduler.is_running

    # -- parallel execution -------------------------------------------------------
    def run_parallel(self, targets: list[ECUTarget]) -> list[ParallelResult]:
        """Run every target's sequence concurrently and return the results."""
        results = self.parallel.run(targets)
        successful = sum(1 for result in results if result.successful)
        self.parallel_completed.emit(results)
        self._notify(
            f"Parallel run finished: {successful}/{len(results)} target(s) passed",
            "success" if successful == len(results) else "warning",
        )
        return results

    def cancel_parallel(self) -> None:
        """Cancel every running target."""
        self.parallel.cancel()

    # -- reporting -------------------------------------------------------------------
    def export_report(self, path: str | Path, kind: str = "html") -> Path:
        """Write the aggregated results of the last runs."""
        target = Path(path)
        if kind == "csv":
            return self.collector.to_csv(target)
        if kind == "json":
            return self.collector.to_json(target)
        return self.collector.to_html(target)

    def _on_run_completed(self, results: list[TestResult]) -> None:
        """Aggregate the results of one scheduled run."""
        for result in results:
            self.collector.add(result)
        summary = self.collector.summary().as_text()
        self.run_completed.emit(summary)
        _logger.info("scheduled run: %s", summary)

    def _notify(self, message: str, level: str = "info") -> None:
        """Show a toast and a status bar message."""
        if self.window is None:
            _logger.info("%s", message)
            return
        toasts = getattr(self.window, "toasts", None)
        if toasts is not None:
            getattr(toasts, level, toasts.info)(message)


__all__ = ["TestExecutionController"]
