"""Developer mode controller running test sequences off the UI thread."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal

from src.core.event_bus import EventBus, get_event_bus
from src.core.models.test_sequence_model import TestResult, TestSequence, TestStep
from src.diagnostics.uds_client import UDSClient
from src.test_execution.test_runner import RunnerOptions, TestRunner

_logger = logging.getLogger(__name__)


class _RunnerThread(QThread):
    """Executes a sequence or a single step on a background thread."""

    #: Emitted with the step that just started.
    step_started = Signal(object)
    #: Emitted with the result of a finished step.
    step_completed = Signal(object)
    #: Emitted with the list of results when the run finished.
    finished_run = Signal(object)
    #: Emitted with the exception when the run crashed.
    failed = Signal(object)

    def __init__(self, runner: TestRunner, single: TestStep | None = None) -> None:
        """Store the runner and the optional single step."""
        super().__init__()
        self.runner = runner
        self.single = single

    def run(self) -> None:
        """Execute the sequence or the single step."""
        try:
            if self.single is not None:
                self.finished_run.emit([self.runner.execute_step(self.single)])
            else:
                self.finished_run.emit(self.runner.execute_all())
        except Exception as exc:  # noqa: BLE001 - surfaced in the UI
            _logger.exception("test execution failed")
            self.failed.emit(exc)


class DeveloperModeController(QObject):
    """Connects the developer panel to the :class:`TestRunner`.

    Args:
        panel: The developer mode panel.
        window: The main window used for notifications.
        event_bus: Shared event bus.
    """

    #: Emitted with the summary text when a run completes.
    run_completed = Signal(str)
    #: Emitted with the step that started; mirrors the runner callback.
    step_started = Signal(object)
    #: Emitted with the result of a finished step.
    step_completed = Signal(object)
    #: Internal relays used to hop from the worker thread to the UI thread.
    _relay_started = Signal(object)
    _relay_completed = Signal(object)

    def __init__(self, panel: Any, window: Any = None, event_bus: EventBus | None = None) -> None:
        """Wire the panel signals to the runner."""
        super().__init__()
        self.panel = panel
        self.window = window
        self.bus = event_bus or get_event_bus()
        self.client: UDSClient | None = None
        self.runner: TestRunner | None = None
        self._thread: _RunnerThread | None = None

        self._relay_started.connect(
            self._apply_step_started, Qt.ConnectionType.QueuedConnection
        )
        self._relay_completed.connect(
            self._apply_step_completed, Qt.ConnectionType.QueuedConnection
        )

        panel.run_all_requested.connect(self.run_all)
        panel.run_step_requested.connect(self.run_step)
        panel.cancel_requested.connect(self.cancel)

    # -- lifecycle ----------------------------------------------------------
    def attach_client(self, client: UDSClient) -> None:
        """Create the runner for *client*."""
        self.client = client
        self.runner = TestRunner(
            client,
            RunnerOptions(stop_on_failure=self.panel.stop_on_failure_box.isChecked()),
            self.bus,
            on_step=self._on_step,
        )

    def detach(self) -> None:
        """Drop the runner when the connection closes."""
        self.cancel()
        self.client = None
        self.runner = None

    # -- execution ------------------------------------------------------------
    def run_all(self) -> None:
        """Run the whole sequence."""
        if not self._require_runner():
            return
        sequence: TestSequence = self.panel.sequence()
        self.runner.options.stop_on_failure = self.panel.stop_on_failure_box.isChecked()
        self.runner.load_sequence(sequence)
        self.panel.execution_started(len(sequence.enabled_steps))
        self._start(_RunnerThread(self.runner))

    def run_step(self, step: TestStep) -> None:
        """Run a single step."""
        if not self._require_runner():
            return
        self.runner.load_sequence(self.panel.sequence())
        self.panel.execution_started(1)
        self._start(_RunnerThread(self.runner, step))

    def cancel(self) -> None:
        """Cancel the running sequence."""
        if self.runner is not None:
            self.runner.cancel()
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait(2000)
        self.panel.execution_cancelled()

    # -- callbacks ------------------------------------------------------------
    def _on_step(self, step: TestStep, result: TestResult | None) -> None:
        """Relay a runner callback from the worker thread.

        The runner calls this on its own thread, so the panel must not be
        touched here. Re-emitting through a queued signal hands the update to
        the UI thread, which is where the spinner timers may be started.
        """
        if result is None:
            self._relay_started.emit(step)
        else:
            self._relay_completed.emit(result)

    def _apply_step_started(self, step: TestStep) -> None:
        """Show *step* as running; always called on the UI thread."""
        self.panel.step_started(step)
        self.step_started.emit(step)

    def _apply_step_completed(self, result: TestResult) -> None:
        """Show the result of a finished step on the UI thread."""
        self.panel.step_completed(result)
        self.step_completed.emit(result)

    def _on_finished(self, results: list[TestResult]) -> None:
        """Update the panel when a run completed."""
        summary = self.runner.summary().as_text() if self.runner else ""
        self.panel.execution_finished(summary)
        self.run_completed.emit(summary)
        self._notify(summary, "success" if "Failed 0" in summary else "warning")

    def _on_failed(self, error: Exception) -> None:
        """Report a crashed run."""
        self.panel.execution_finished(f"execution failed: {error}")
        self._notify(f"Test execution failed: {error}", "error")

    def _start(self, thread: _RunnerThread) -> None:
        """Start *thread* and connect its signals."""
        # Queue explicitly: the slots repaint widgets and start spinner
        # timers, which Qt forbids from the worker thread.
        thread.finished_run.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        thread.failed.connect(self._on_failed, Qt.ConnectionType.QueuedConnection)
        self._thread = thread
        thread.start()

    def _require_runner(self) -> bool:
        """Return ``True`` when a runner is available."""
        if self.runner is None:
            self._notify("Connect to a VCI before running tests", "warning")
            return False
        return True

    def _notify(self, message: str, level: str = "info") -> None:
        """Show a toast and a status bar message."""
        if self.window is None:
            _logger.info("%s", message)
            return
        toasts = getattr(self.window, "toasts", None)
        if toasts is not None:
            getattr(toasts, level, toasts.info)(message)
        status = getattr(self.window, "status", None)
        if status is not None:
            status.set_message(message)


__all__ = ["DeveloperModeController"]
