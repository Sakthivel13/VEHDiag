"""Live flashing screen.

Shown once the operator presses *Start flash*. It mirrors the layout of the
reference tester: a row of stage bars across the top, the ECU identification
card, the block level transfer progress and a running log.

Example:
    >>> from ui.panels.diagnostic_panel.transfer_panel.flash_progress_view import (
    ...     STAGES, stage_of, format_bytes)
    >>> STAGES
    ('Connect', 'Identify', 'Prepare', 'Transfer', 'Finalise')
    >>> from src.diagnostics.flash_sequence import FlashStepKind
    >>> stage_of(FlashStepKind.READ_VIN)
    'Identify'
    >>> stage_of(FlashStepKind.TRANSFER_DATA)
    'Transfer'
    >>> format_bytes(2048)
    '2.0 KB'
"""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.enums.transfer_enums import TransferState
from src.core.models.file_transfer_model import TransferProgress
from src.diagnostics.flash_sequence import FlashStep, FlashStepKind, StepOutcome, StepStatus
from src.utils.file_utils import human_size

from ....dpi_scaler import DPIScaler
from ....styles.layout_helpers import tune_form
from ....styles.semantic_colors import semantic
from ....widgets.led_indicator import LedIndicator
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel, MonoLabel

__all__ = ["STAGES", "FlashProgressView", "format_bytes", "stage_of"]

#: The coarse stages shown as bars across the top, as in the reference tester.
STAGES: tuple[str, ...] = ("Connect", "Identify", "Prepare", "Transfer", "Finalise")

#: Which stage each step belongs to.
_STEP_STAGE: dict[FlashStepKind, str] = {
    FlashStepKind.CAN_INIT: "Connect",
    FlashStepKind.CAN_CONFIG: "Connect",
    FlashStepKind.ECU_COMM: "Connect",
    FlashStepKind.READ_BATTERY_VOLTAGE: "Connect",
    FlashStepKind.READ_VIN: "Identify",
    FlashStepKind.READ_HARDWARE: "Identify",
    FlashStepKind.READ_SOFTWARE: "Identify",
    FlashStepKind.READ_DID: "Identify",
    FlashStepKind.ENTER_EXTENDED: "Prepare",
    FlashStepKind.ENTER_PROGRAMMING: "Prepare",
    FlashStepKind.SECURITY_ACCESS: "Prepare",
    FlashStepKind.DISABLE_DTC: "Prepare",
    FlashStepKind.DISABLE_COMMUNICATION: "Prepare",
    FlashStepKind.CHECK_PROGRAMMING_DEPENDENCIES: "Prepare",
    FlashStepKind.ERASE_MEMORY: "Prepare",
    FlashStepKind.FILE_UPLOAD: "Prepare",
    FlashStepKind.REQUEST_DOWNLOAD: "Transfer",
    FlashStepKind.TRANSFER_DATA: "Transfer",
    FlashStepKind.TRANSFER_EXIT: "Transfer",
    FlashStepKind.CHECK_MEMORY: "Finalise",
    FlashStepKind.VERIFY_CHECKSUM: "Finalise",
    FlashStepKind.ENABLE_DTC: "Finalise",
    FlashStepKind.ENABLE_COMMUNICATION: "Finalise",
    FlashStepKind.CLEAR_DTC: "Finalise",
    FlashStepKind.ENTER_DEFAULT: "Finalise",
    FlashStepKind.ECU_RESET: "Finalise",
}


def stage_of(kind: FlashStepKind) -> str:
    """Return the stage the step *kind* belongs to.

    Example:
        >>> stage_of(FlashStepKind.ECU_RESET)
        'Finalise'
        >>> stage_of(FlashStepKind.DELAY)
        'Prepare'
    """
    return _STEP_STAGE.get(kind, "Prepare")


def format_bytes(count: int) -> str:
    """Return a human readable byte count.

    Example:
        >>> format_bytes(0)
        '0 B'
    """
    return human_size(count)


class FlashProgressView(ResponsiveWidget):
    """The screen shown while a flash sequence runs.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        stage_bars: One progress bar per entry of :data:`STAGES`.
        log: The running log of every step and block.
    """

    #: Emitted when the operator aborts the run.
    cancel_requested = Signal()
    #: Emitted when the operator leaves the screen after a finished run.
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the stage bars, the ECU card, the transfer block and the log."""
        super().__init__(parent, scaler)
        self._stage_totals: dict[str, int] = {}
        self._stage_done: dict[str, int] = {}
        self._started = 0.0

        # -- stage bars --------------------------------------------------------
        self.stage_bars: dict[str, QProgressBar] = {}
        self.stage_labels: dict[str, QLabel] = {}
        stage_grid = QGridLayout()
        stage_grid.setHorizontalSpacing(self.spacing(10))
        for column, stage in enumerate(STAGES):
            caption = QLabel(stage, self)
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            caption.setProperty("role", "caption")
            bar = QProgressBar(self)
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(self.px(8))
            self.stage_labels[stage] = caption
            self.stage_bars[stage] = bar
            stage_grid.addWidget(caption, 0, column)
            stage_grid.addWidget(bar, 1, column)

        # -- ECU identification card -------------------------------------------
        self.fields: dict[str, QLabel] = {}
        info_box = QGroupBox("ECU", self)
        info_form = QFormLayout(info_box)
        tune_form(info_form, self.scaler)
        for caption in ("VIN", "Hardware", "Software", "Battery voltage", "Flash file"):
            label = MonoLabel("-", self, self.scaler)
            # A ScalableLabel elides to its current width; in a form that width
            # starts at zero, which rendered every value as a single letter.
            label.setMinimumWidth(self.px(320))
            label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            self.fields[caption] = label
            info_form.addRow(f"{caption}:", label)

        # -- current step and transfer -----------------------------------------
        self.led = LedIndicator("idle", 14, self, self.scaler)
        self.step_label = QLabel("Ready", self)
        self.step_label.setProperty("role", "heading")
        self.elapsed_label = QLabel("0.0 s", self)
        self.elapsed_label.setProperty("role", "secondary")
        self.activity_label = QLabel("", self)
        self.activity_label.setProperty("role", "secondary")
        self.activity_label.setWordWrap(True)

        self.transfer_bar = QProgressBar(self)
        self.transfer_bar.setRange(0, 100)
        self.transfer_bar.setFormat("%p%")
        self.blocks_label = QLabel("-", self)
        self.bytes_label = QLabel("-", self)
        self.speed_label = QLabel("-", self)
        self.eta_label = QLabel("-", self)
        for label in (self.blocks_label, self.bytes_label, self.speed_label, self.eta_label):
            label.setProperty("role", "secondary")

        transfer_box = QGroupBox("Data transfer", self)
        transfer_layout = QVBoxLayout(transfer_box)
        transfer_layout.setSpacing(self.spacing(6))
        transfer_layout.addWidget(self.transfer_bar)
        stats = QGridLayout()
        stats.setHorizontalSpacing(self.spacing(14))
        for column, (caption, widget) in enumerate(
            (
                ("Blocks", self.blocks_label),
                ("Bytes", self.bytes_label),
                ("Speed", self.speed_label),
                ("ETA", self.eta_label),
            )
        ):
            title = QLabel(caption, self)
            title.setProperty("role", "caption")
            stats.addWidget(title, 0, column)
            stats.addWidget(widget, 1, column)
        transfer_layout.addLayout(stats)

        # -- log ---------------------------------------------------------------
        from ....widgets.table_widget_enhanced import EnhancedTableWidget

        self.log = EnhancedTableWidget(["Time", "Step", "Status", "Detail"], self, self.scaler)
        # A flash log is a transcript: it must stay in the order events happened.
        self.log.setSortingEnabled(False)
        log_box = QGroupBox("Logs", self)
        log_layout = QVBoxLayout(log_box)
        log_layout.addWidget(self.log)

        # -- footer ------------------------------------------------------------
        self.summary_label = QLabel("", self)
        self.summary_label.setWordWrap(True)
        self.cancel_button = ScalableButton("Cancel", "cancel", self, self.scaler, danger=True)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.close_button = ScalableButton("Back to sequence", "chevron_right", self, self.scaler)
        self.close_button.clicked.connect(self.close_requested.emit)
        self.close_button.setEnabled(False)

        footer = QHBoxLayout()
        footer.setSpacing(self.spacing(8))
        footer.addWidget(self.summary_label, 1)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.close_button)

        header = QHBoxLayout()
        header.setSpacing(self.spacing(8))
        header.addWidget(self.led)
        header.addWidget(self.step_label, 1)
        header.addWidget(self.elapsed_label)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(8))
        layout.addWidget(HeadingLabel("ECU flashing", 2, self, self.scaler))
        layout.addLayout(stage_grid)
        layout.addWidget(info_box)
        layout.addLayout(header)
        layout.addWidget(self.activity_label)
        layout.addWidget(transfer_box)
        layout.addWidget(log_box, 1)
        layout.addLayout(footer)

    # -- run lifecycle -------------------------------------------------------
    def begin(self, sequence: Any) -> None:
        """Reset the screen for a new run of *sequence*."""
        self._started = time.perf_counter()
        self._stage_totals = {stage: 0 for stage in STAGES}
        self._stage_done = {stage: 0 for stage in STAGES}
        for step in sequence.enabled_steps:
            self._stage_totals[stage_of(step.kind)] += 1
        for stage, bar in self.stage_bars.items():
            bar.setValue(0)
            bar.setEnabled(self._stage_totals.get(stage, 0) > 0)
        self.log.clear_rows()
        self.transfer_bar.setValue(0)
        for label in (self.blocks_label, self.bytes_label, self.speed_label, self.eta_label):
            label.setText("-")
        for label in self.fields.values():
            label.setText("-")
        if sequence.flash_file:
            self.fields["Flash file"].setText(str(sequence.flash_file.name))
        self.led.set_state("running")
        self.step_label.setText("Starting...")
        self.activity_label.setText("")
        self.summary_label.setText("")
        self.cancel_button.setEnabled(True)
        self.close_button.setEnabled(False)

    def step_started(self, step: FlashStep) -> None:
        """Show *step* as the one currently running."""
        self.led.set_state("running")
        self.step_label.setText(step.label)
        self._refresh_elapsed()

    def step_finished(self, outcome: StepOutcome) -> None:
        """Record the result of a finished step."""
        stage = stage_of(outcome.step.kind)
        if outcome.status is not StepStatus.SKIPPED:
            self._stage_done[stage] = self._stage_done.get(stage, 0) + 1
        total = max(1, self._stage_totals.get(stage, 1))
        self.stage_bars[stage].setValue(
            int(100 * min(self._stage_done.get(stage, 0), total) / total)
        )
        self.log.append_row(
            {
                "Time": f"{outcome.duration_ms:.0f} ms",
                "Step": outcome.step.label,
                "Status": outcome.status.value,
                "Detail": outcome.message,
                "_c": _status_colour(outcome.status),
            }
        )
        self.log.scrollToBottom()
        self._absorb_info(outcome)
        self._refresh_elapsed()

    def update_progress(self, progress: TransferProgress) -> None:
        """Refresh the block level transfer statistics."""
        self.transfer_bar.setValue(int(progress.percent))
        self.blocks_label.setText(
            f"{progress.blocks_done}/{progress.blocks_total}" if progress.blocks_total else "-"
        )
        self.bytes_label.setText(
            f"{format_bytes(progress.bytes_done)} / {format_bytes(progress.bytes_total)}"
        )
        self.speed_label.setText(
            f"{format_bytes(int(progress.speed_bps))}/s" if progress.speed_bps > 0 else "-"
        )
        self.eta_label.setText(f"{progress.eta_s:.1f} s" if progress.eta_s > 0 else "-")
        self._refresh_elapsed()

    def finish(self, report: Any) -> None:
        """Show the final outcome of the run."""
        self.led.set_state("pass" if report.completed else "error")
        self.step_label.setText("Finished" if report.completed else "Failed")
        self.summary_label.setText(report.summary())
        self.summary_label.setProperty("state", "success" if report.completed else "error")
        style = self.summary_label.style()
        if style is not None:
            style.unpolish(self.summary_label)
            style.polish(self.summary_label)
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
        if report.completed:
            for bar in self.stage_bars.values():
                if bar.isEnabled():
                    bar.setValue(100)
        self._refresh_elapsed()

    def set_activity(self, message: str) -> None:
        """Show the runner's latest trace line under the current step.

        Free-form trace lines are shown here rather than appended to the log
        table: the table is the structured per-step transcript, and mixing the
        two made the real results hard to read.
        """
        self.activity_label.setText(message.strip())

    def log_line(self, message: str) -> None:
        """Append a free-form line to the log."""
        self.log.append_row(
            {"Time": "", "Step": "", "Status": "", "Detail": message, "_c": _status_colour(None)}
        )
        self.log.scrollToBottom()

    # -- internals ------------------------------------------------------------
    def _absorb_info(self, outcome: StepOutcome) -> None:
        """Copy identification values from *outcome* into the ECU card."""
        data = outcome.data
        if "vin" in data:
            self.fields["VIN"].setText(str(data["vin"]))
        if "hardware" in data:
            self.fields["Hardware"].setText(" / ".join(data["hardware"]))
        if "software" in data:
            self.fields["Software"].setText(" / ".join(data["software"]))
        if "battery_v" in data and data["battery_v"]:
            self.fields["Battery voltage"].setText(f"{float(data['battery_v']):.4f} V")
        if "file" in data:
            self.fields["Flash file"].setText(str(data["file"]))

    def _refresh_elapsed(self) -> None:
        """Update the elapsed time label."""
        if self._started:
            self.elapsed_label.setText(f"{time.perf_counter() - self._started:.1f} s")


def _status_colour(status: StepStatus | None) -> str:
    """Return the semantic colour for a step status."""
    if status is StepStatus.PASSED:
        return semantic("success")
    if status is StepStatus.FAILED:
        return semantic("error")
    if status is StepStatus.SKIPPED:
        return semantic("muted")
    if status is StepStatus.RUNNING:
        return semantic("running")
    return semantic("text")
