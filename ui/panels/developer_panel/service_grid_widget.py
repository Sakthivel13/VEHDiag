"""Per-service test grid card used by the developer mode panel."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.enums.sid_enums import ServiceID
from src.core.models.test_sequence_model import ExecutionMode, TestResult, TestStatus, TestStep

from ...dpi_scaler import DPIScaler
from ...styles.style_constants import FontRole, state_color
from ...widgets.file_browser_widget import FileBrowserWidget
from ...widgets.hex_input_field import HexInputField
from ...widgets.led_indicator import LedIndicator
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton


class ServiceGridWidget(ResponsiveWidget):
    """One card of the developer mode sequence editor.

    The card carries the drag handle, the service name, the mapped test file,
    the payload field, the execution mode and the per-service run button.

    Args:
        step: The test step the card represents.
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the step when the operator presses the run button.
    run_requested = Signal(object)
    #: Emitted with the step whenever any field changes.
    step_changed = Signal(object)
    #: Emitted with the step when the operator removes the card.
    remove_requested = Signal(object)

    def __init__(
        self,
        step: TestStep,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
    ) -> None:
        """Build the card for *step*."""
        super().__init__(parent, scaler)
        self.step = step
        self.setObjectName("ServiceGrid")

        service = ServiceID.from_byte(step.service_id)
        title = step.name or (service.pretty_name if service else f"Service 0x{step.service_id:02X}")

        self.drag_handle = QLabel("\u22ee\u22ee", self)
        self.drag_handle.setToolTip("Drag to reorder")
        self.drag_handle.setCursor(Qt.CursorShape.OpenHandCursor)
        self.order_label = QLabel(str(step.order), self)
        self.order_label.setProperty("role", "secondary")
        self.title_label = QLabel(f"{title}  (0x{step.service_id:02X})", self)
        self.title_label.setProperty("role", "heading")
        self.enabled_box = QCheckBox("Enabled", self)
        self.enabled_box.setChecked(step.enabled)
        self.enabled_box.toggled.connect(self._on_enabled)
        self.collapse_button = QToolButton(self)
        self.collapse_button.setArrowType(Qt.ArrowType.DownArrow)
        self.collapse_button.setCheckable(True)
        self.collapse_button.setChecked(True)
        self.collapse_button.toggled.connect(self.set_expanded)
        self.remove_button = QToolButton(self)
        self.remove_button.setText("x")
        self.remove_button.setToolTip("Remove this service")
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.step))

        self.file_browser = FileBrowserWidget(
            self, self.scaler, "Select a test script", "Python files (*.py)"
        )
        if step.script_path:
            self.file_browser.set_path(step.script_path)
        self.file_browser.path_changed.connect(self._on_file_changed)

        self.payload_field = HexInputField(self, self.scaler, min_bytes=1)
        self.payload_field.set_value(step.payload)
        self.payload_field.bytes_changed.connect(self._on_payload_changed)

        self.mode_label = QLabel(step.mode.value.title(), self)
        self.mode_label.setProperty("role", "secondary")
        self.status_led = LedIndicator("idle", 14, self, self.scaler)
        self.status_label = QLabel("Idle", self)
        self.duration_label = QLabel("", self)
        self.duration_label.setProperty("role", "secondary")
        self.run_button = ScalableButton("Run", "play", self, self.scaler)
        self.run_button.clicked.connect(lambda: self.run_requested.emit(self.step))

        header = QHBoxLayout()
        header.setSpacing(self.spacing(6))
        header.addWidget(self.drag_handle)
        header.addWidget(self.order_label)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.status_led)
        header.addWidget(self.status_label)
        header.addWidget(self.enabled_box)
        header.addWidget(self.collapse_button)
        header.addWidget(self.remove_button)

        self.body = QFrame(self)
        body_layout = QGridLayout(self.body)
        body_layout.setSpacing(self.spacing(6))
        body_layout.addWidget(QLabel("Test file:", self), 0, 0)
        body_layout.addWidget(self.file_browser, 0, 1, 1, 2)
        body_layout.addWidget(QLabel("Payload:", self), 1, 0)
        body_layout.addWidget(self.payload_field, 1, 1)
        body_layout.addWidget(self.mode_label, 1, 2)
        body_layout.addWidget(self.duration_label, 2, 1)
        body_layout.addWidget(self.run_button, 2, 2, Qt.AlignmentFlag.AlignRight)

        layout = QVBoxLayout(self)
        margin = self.spacing(8)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(self.spacing(6))
        layout.addLayout(header)
        layout.addWidget(self.body)
        self.apply_font(FontRole.BODY)

    # -- state ---------------------------------------------------------------
    def set_expanded(self, expanded: bool) -> None:
        """Collapse or expand the body of the card."""
        self.body.setVisible(expanded)
        self.collapse_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def set_order(self, order: int) -> None:
        """Update the displayed sequence number."""
        self.step.order = order
        self.order_label.setText(str(order))

    def set_status(self, status: TestStatus, message: str = "", duration_ms: float = 0.0) -> None:
        """Update the LED, the status text and the duration."""
        mapping = {
            TestStatus.IDLE: "idle",
            TestStatus.RUNNING: "running",
            TestStatus.PASS: "pass",
            TestStatus.FAIL: "fail",
            TestStatus.ERROR: "error",
            TestStatus.SKIPPED: "skipped",
            TestStatus.CANCELLED: "cancelled",
        }
        self.status_led.set_state(mapping.get(status, "idle"))
        self.status_label.setText(status.value.title())
        self.status_label.setStyleSheet(f"color:{state_color(mapping.get(status, 'idle'))};")
        self.duration_label.setText(f"{duration_ms:.1f} ms" if duration_ms else "")
        if message:
            self.setToolTip(message)

    def apply_result(self, result: TestResult) -> None:
        """Update the card from a :class:`TestResult`."""
        self.set_status(result.status, result.message, result.duration_ms)

    def set_running(self, running: bool) -> None:
        """Disable the run button while the step executes."""
        self.run_button.setEnabled(not running)
        if running:
            self.set_status(TestStatus.RUNNING)

    # -- events ----------------------------------------------------------------
    def _on_enabled(self, checked: bool) -> None:
        """Store the enabled flag."""
        self.step.enabled = checked
        self.setEnabled(True)
        self.title_label.setEnabled(checked)
        self.step_changed.emit(self.step)

    def _on_file_changed(self, path: str) -> None:
        """Store the mapped script and switch the execution mode."""
        self.step.script_path = path
        self.step.mode = ExecutionMode.SCRIPT if path else ExecutionMode.PAYLOAD
        self.mode_label.setText(self.step.mode.value.title())
        self.step_changed.emit(self.step)

    def _on_payload_changed(self, data: bytes) -> None:
        """Store the entered payload."""
        self.step.payload = data
        self.step_changed.emit(self.step)


__all__ = ["ServiceGridWidget"]
