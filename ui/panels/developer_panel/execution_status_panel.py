"""Live execution status shown while a sequence runs."""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QPlainTextEdit, QProgressBar, QWidget

from src.core.models.test_sequence_model import TestResult, TestStep

from ...dpi_scaler import DPIScaler
from ...widgets.led_indicator import LedIndicator
from ...widgets.responsive_widget import ResponsiveWidget


class ExecutionStatusPanel(ResponsiveWidget):
    """Shows the running step, the progress and a live TX/RX stream.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the status grid and the stream view."""
        super().__init__(parent, scaler)
        self.total = 0
        self.completed = 0
        self._started_at = 0.0
        self._step_started_at = 0.0

        self.led = LedIndicator("idle", 14, self, self.scaler)
        self.current_label = QLabel("Idle", self)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.count_label = QLabel("0 / 0", self)
        self.elapsed_label = QLabel("0.0 s", self)
        self.step_elapsed_label = QLabel("0.0 s", self)
        self.stream = QPlainTextEdit(self)
        self.stream.setReadOnly(True)
        self.stream.setProperty("role", "mono")
        self.stream.setMaximumHeight(self.px(140))

        box = QGroupBox("Execution status", self)
        grid = QGridLayout(box)
        grid.setSpacing(self.spacing(8))
        grid.addWidget(self.led, 0, 0)
        grid.addWidget(self.current_label, 0, 1, 1, 3)
        grid.addWidget(self.progress, 1, 0, 1, 4)
        grid.addWidget(QLabel("Step:", self), 2, 0)
        grid.addWidget(self.count_label, 2, 1)
        grid.addWidget(QLabel("Elapsed:", self), 2, 2)
        grid.addWidget(self.elapsed_label, 2, 3)
        grid.addWidget(QLabel("Current step:", self), 3, 0)
        grid.addWidget(self.step_elapsed_label, 3, 1)
        grid.addWidget(self.stream, 4, 0, 1, 4)

        from PySide6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(box)

        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._tick)

    # -- API -----------------------------------------------------------------
    def start(self, total_steps: int) -> None:
        """Begin a new run with *total_steps* steps."""
        self.total = total_steps
        self.completed = 0
        self._started_at = time.perf_counter()
        self.progress.setValue(0)
        self.count_label.setText(f"0 / {total_steps}")
        self.led.set_state("running")
        self.stream.clear()
        self._timer.start()

    def step_started(self, step: TestStep) -> None:
        """Show the step that just started."""
        self._step_started_at = time.perf_counter()
        self.current_label.setText(f"Running: {step.name} (0x{step.service_id:02X})")
        self.log(f"> {step.name}: {step.payload_hex or step.script_path}")

    def step_completed(self, result: TestResult) -> None:
        """Record a completed step and advance the progress bar."""
        self.completed += 1
        if self.total:
            self.progress.setValue(int(self.completed / self.total * 100))
        self.count_label.setText(f"{self.completed} / {self.total}")
        self.log(f"< {result.status.value}: {result.message} ({result.duration_ms:.1f} ms)")

    def finish(self, summary: str = "") -> None:
        """Stop the timers and show the final summary."""
        self._timer.stop()
        self.led.set_state("pass" if "Failed 0" in summary else "idle")
        self.current_label.setText(summary or "Finished")
        self.progress.setValue(100 if self.total else 0)

    def cancelled(self) -> None:
        """Show that the run was cancelled."""
        self._timer.stop()
        self.led.set_state("cancelled")
        self.current_label.setText("Cancelled by the operator")

    def log(self, message: str) -> None:
        """Append one line to the live stream."""
        self.stream.appendPlainText(message)

    def reset(self) -> None:
        """Clear every field."""
        self._timer.stop()
        self.total = self.completed = 0
        self.progress.setValue(0)
        self.count_label.setText("0 / 0")
        self.elapsed_label.setText("0.0 s")
        self.step_elapsed_label.setText("0.0 s")
        self.current_label.setText("Idle")
        self.led.set_state("idle")
        self.stream.clear()

    def _tick(self) -> None:
        """Refresh the elapsed time labels."""
        self.elapsed_label.setText(f"{time.perf_counter() - self._started_at:.1f} s")
        if self._step_started_at:
            self.step_elapsed_label.setText(f"{time.perf_counter() - self._step_started_at:.1f} s")


__all__ = ["ExecutionStatusPanel"]
