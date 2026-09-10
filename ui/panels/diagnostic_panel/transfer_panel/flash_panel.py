"""Two page ECU flashing panel.

Page one is the :class:`~ui.panels.diagnostic_panel.transfer_panel.
flash_sequence_editor.FlashSequenceEditor` where the operator arranges the
steps and picks the files. Pressing *Start flash* switches to page two, the
:class:`~ui.panels.diagnostic_panel.transfer_panel.flash_progress_view.
FlashProgressView`, which shows the live transfer.

The sequence runs on a :class:`QThread` so the interface stays responsive and
the cancel button keeps working while blocks are in flight.

Example:
    >>> from ui.panels.diagnostic_panel.transfer_panel.flash_panel import PAGE_EDITOR
    >>> PAGE_EDITOR
    0
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from src.core.models.file_transfer_model import TransferProgress
from src.diagnostics.flash_runner import FlashReport, FlashRunner
from src.diagnostics.flash_sequence import FlashSequence, FlashStep, StepOutcome

from ....dpi_scaler import DPIScaler
from ....widgets.responsive_widget import ResponsiveWidget
from .flash_progress_view import FlashProgressView
from .flash_sequence_editor import FlashSequenceEditor

__all__ = ["PAGE_EDITOR", "PAGE_PROGRESS", "FlashPanel", "FlashWorker"]

#: Index of the sequence editor page.
PAGE_EDITOR = 0

#: Index of the live progress page.
PAGE_PROGRESS = 1


class FlashWorker(QObject):
    """Runs a :class:`FlashRunner` on a worker thread.

    Args:
        runner: The configured runner.
        sequence: The sequence to execute.
    """

    #: Emitted with the step that just started.
    step_started = Signal(object)
    #: Emitted with the outcome of a finished step.
    step_finished = Signal(object)
    #: Emitted with a transfer progress update.
    progress = Signal(object)
    #: Emitted with every log line.
    log = Signal(str)
    #: Emitted with the report when the run ends.
    finished = Signal(object)

    def __init__(self, runner: FlashRunner, sequence: FlashSequence) -> None:
        """Store the runner and connect its callbacks to the signals."""
        super().__init__()
        self.runner = runner
        self.sequence = sequence
        runner.on_step = self.step_started.emit
        runner.on_step_done = self.step_finished.emit
        runner.on_progress = self.progress.emit
        runner.on_log = self.log.emit

    def run(self) -> None:
        """Execute the sequence and publish the report."""
        try:
            report = self.runner.run(self.sequence)
        except Exception as exc:  # noqa: BLE001 - never kill the thread silently
            report = FlashReport()
            self.log.emit(f"runner crashed: {type(exc).__name__}: {exc}")
        self.finished.emit(report)


class FlashPanel(ResponsiveWidget):
    """The complete flashing workflow.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        client: UDS client used by the runner.
        connection: Optional connection manager for the CAN steps.

    Attributes:
        editor: The sequence editor page.
        progress_view: The live progress page.
    """

    #: Emitted with the report when a run finishes.
    flash_finished = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        client: Any = None,
        connection: Any = None,
    ) -> None:
        """Build the two pages and the stack that switches between them."""
        super().__init__(parent, scaler)
        self.client = client
        self.connection = connection
        self._thread: QThread | None = None
        self._worker: FlashWorker | None = None
        self._runner: FlashRunner | None = None

        self.editor = FlashSequenceEditor(self, self.scaler)
        self.editor.start_requested.connect(self.start_flash)
        self.progress_view = FlashProgressView(self, self.scaler)
        self.progress_view.cancel_requested.connect(self.cancel)
        self.progress_view.close_requested.connect(self.show_editor)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.editor)
        self.stack.addWidget(self.progress_view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

    # -- API -----------------------------------------------------------------
    def set_client(self, client: Any, connection: Any = None) -> None:
        """Attach the UDS client the runner will drive."""
        self.client = client
        if connection is not None:
            self.connection = connection

    def show_editor(self) -> None:
        """Switch back to the sequence editor."""
        self.stack.setCurrentIndex(PAGE_EDITOR)

    def is_running(self) -> bool:
        """Return ``True`` while a flash is in flight."""
        return self._thread is not None and self._thread.isRunning()

    def start_flash(self, sequence: FlashSequence | None = None) -> bool:
        """Start the run and switch to the progress page.

        Args:
            sequence: Sequence to run; the editor's when omitted.

        Returns:
            ``True`` when the run was started.
        """
        if self.is_running():
            return False
        target = sequence or self.editor.sequence
        problems = target.validate()
        if problems:
            self.progress_view.log_line("cannot start: " + "; ".join(problems))
            return False
        if self.client is None:
            self.stack.setCurrentIndex(PAGE_PROGRESS)
            self.progress_view.begin(target)
            self.progress_view.log_line("no UDS client: connect to a VCI first")
            self.progress_view.finish(FlashReport())
            return False

        self.progress_view.begin(target)
        self.stack.setCurrentIndex(PAGE_PROGRESS)

        self._runner = FlashRunner(self.client, self.connection)
        self._worker = FlashWorker(self._runner, target)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.step_started.connect(self._on_step_started)
        self._worker.step_finished.connect(self._on_step_finished)
        self._worker.progress.connect(self.progress_view.update_progress)
        self._worker.log.connect(self.progress_view.set_activity)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()
        return True

    def cancel(self) -> None:
        """Ask the running sequence to stop."""
        if self._runner is not None:
            self._runner.cancel()
            self.progress_view.log_line("cancelling...")

    def wait(self, timeout_ms: int = 30_000) -> bool:
        """Block until the run finishes; used by the tests.

        Args:
            timeout_ms: Maximum time to wait.

        Returns:
            ``True`` when the thread finished in time.
        """
        if self._thread is None:
            return True
        return self._thread.wait(timeout_ms)

    # -- internals ------------------------------------------------------------
    def _on_step_started(self, step: FlashStep) -> None:
        """Forward the started step to both pages."""
        self.progress_view.step_started(step)
        self.editor.reload()

    def _on_step_finished(self, outcome: StepOutcome) -> None:
        """Forward the finished step to both pages."""
        self.progress_view.step_finished(outcome)
        self.editor.reload()

    def _on_finished(self, report: FlashReport) -> None:
        """Tear the thread down and publish the report."""
        self.progress_view.finish(report)
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self.flash_finished.emit(report)
