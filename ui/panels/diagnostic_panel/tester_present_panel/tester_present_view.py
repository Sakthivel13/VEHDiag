"""TesterPresent (SID 0x3E) panel."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ....dpi_scaler import DPIScaler
from ....widgets.led_indicator import LedIndicator
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel


class TesterPresentView(ResponsiveWidget):
    """UI for the manual and automatic TesterPresent keep-alive.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted when the operator sends a single TesterPresent.
    send_requested = Signal(bool)
    #: Emitted with ``(enabled, interval_ms, suppress)`` for the scheduler.
    scheduler_toggled = Signal(bool, int, bool)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the manual and automatic sections."""
        super().__init__(parent, scaler)

        self.suppress_box = QCheckBox("Suppress positive response (0x3E 0x80)", self)
        self.suppress_box.setChecked(True)
        self.send_button = ScalableButton("Send tester present", "play", self, self.scaler)
        self.send_button.clicked.connect(
            lambda: self.send_requested.emit(self.suppress_box.isChecked())
        )

        self.auto_box = QCheckBox("Send automatically", self)
        self.interval_box = QSpinBox(self)
        self.interval_box.setRange(200, 60000)
        self.interval_box.setSingleStep(100)
        self.interval_box.setValue(2000)
        self.interval_box.setSuffix(" ms")
        self.auto_box.toggled.connect(self._on_auto_toggled)
        self.interval_box.valueChanged.connect(self._on_interval_changed)

        self.state_led = LedIndicator("idle", 14, self, self.scaler)
        self.state_label = QLabel("Inactive", self)
        self.counter_label = QLabel("Sent: 0 | Failed: 0", self)
        self.last_label = QLabel("Last: never", self)

        manual_box = QGroupBox("Manual", self)
        manual_layout = QGridLayout(manual_box)
        manual_layout.setSpacing(self.spacing(8))
        manual_layout.addWidget(self.suppress_box, 0, 0, 1, 2)
        manual_layout.addWidget(self.send_button, 1, 0, Qt.AlignmentFlag.AlignLeft)

        auto_box = QGroupBox("Automatic keep-alive", self)
        auto_layout = QGridLayout(auto_box)
        auto_layout.setSpacing(self.spacing(8))
        auto_layout.addWidget(self.auto_box, 0, 0)
        auto_layout.addWidget(QLabel("Interval:", self), 0, 1)
        auto_layout.addWidget(self.interval_box, 0, 2)
        auto_layout.addWidget(self.state_led, 1, 0)
        auto_layout.addWidget(self.state_label, 1, 1)
        auto_layout.addWidget(self.counter_label, 1, 2)
        auto_layout.addWidget(self.last_label, 2, 1, 1, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Tester present", 3, self, self.scaler))
        layout.addWidget(manual_box)
        layout.addWidget(auto_box)
        layout.addStretch(1)

    # -- API -----------------------------------------------------------------
    def set_active(self, active: bool) -> None:
        """Update the keep-alive state indicator."""
        self.state_led.set_state("running" if active else "idle")
        self.state_label.setText("Active" if active else "Inactive")
        if self.auto_box.isChecked() != active:
            self.auto_box.blockSignals(True)
            self.auto_box.setChecked(active)
            self.auto_box.blockSignals(False)

    def update_statistics(self, sent: int, failed: int, last_sent_at: float = 0.0) -> None:
        """Refresh the counters shown below the state indicator."""
        import time

        self.counter_label.setText(f"Sent: {sent} | Failed: {failed}")
        if last_sent_at:
            self.last_label.setText(f"Last: {time.strftime('%H:%M:%S', time.localtime(last_sent_at))}")

    def interval_ms(self) -> int:
        """Return the configured keep-alive interval."""
        return self.interval_box.value()

    # -- events ----------------------------------------------------------------
    def _on_auto_toggled(self, checked: bool) -> None:
        """Emit the scheduler toggle."""
        self.scheduler_toggled.emit(
            checked, self.interval_box.value(), self.suppress_box.isChecked()
        )
        self.set_active(checked)

    def _on_interval_changed(self, value: int) -> None:
        """Restart the scheduler with the new interval."""
        if self.auto_box.isChecked():
            self.scheduler_toggled.emit(True, value, self.suppress_box.isChecked())


__all__ = ["TesterPresentView"]
