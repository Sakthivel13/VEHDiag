"""DiagnosticSessionControl (SID 0x10) panel."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.core.enums.session_enums import SessionType, session_name
from src.diagnostics.services.session_control.session_types import STANDARD_SESSIONS

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.led_indicator import LedIndicator
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel


class SessionControlView(ResponsiveWidget):
    """UI for switching the diagnostic session.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the requested session sub-function.
    session_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the session selector, the status block and the log."""
        super().__init__(parent, scaler)
        self.remaining_ms = 0.0

        self.session_box = QComboBox(self)
        for descriptor in STANDARD_SESSIONS:
            self.session_box.addItem(f"{descriptor.hex_value} {descriptor.label}", descriptor.value)
        self.session_box.setCurrentIndex(2)
        self.session_box.currentIndexChanged.connect(self._on_session_selected)

        self.custom_field = HexInputField(self, self.scaler, max_bytes=1, placeholder="0x__")
        self.send_button = ScalableButton("Send request", "play", self, self.scaler, accent=True)
        self.send_button.clicked.connect(self._on_send)

        self.state_led = LedIndicator("idle", 14, self, self.scaler)
        self.current_label = QLabel("defaultSession (0x01)", self)
        self.p2_label = QLabel("P2: 50 ms", self)
        self.p2_star_label = QLabel("P2*: 5000 ms", self)
        self.timer_bar = QProgressBar(self)
        self.timer_bar.setRange(0, 100)
        self.timer_bar.setFormat("S3 timer: %v%")
        self.history_view = QPlainTextEdit(self)
        self.history_view.setReadOnly(True)
        self.history_view.setProperty("role", "mono")
        self.history_view.setMaximumHeight(self.px(150))

        request_box = QGroupBox("Diagnostic session control (SID 0x10)", self)
        request_layout = QGridLayout(request_box)
        request_layout.setSpacing(self.spacing(8))
        request_layout.addWidget(QLabel("Session type:", self), 0, 0)
        request_layout.addWidget(self.session_box, 0, 1)
        request_layout.addWidget(QLabel("Custom sub-function:", self), 1, 0)
        request_layout.addWidget(self.custom_field, 1, 1)
        request_layout.addWidget(self.send_button, 2, 1, Qt.AlignmentFlag.AlignLeft)

        status_box = QGroupBox("Status", self)
        status_layout = QGridLayout(status_box)
        status_layout.setSpacing(self.spacing(8))
        status_layout.addWidget(self.state_led, 0, 0)
        status_layout.addWidget(self.current_label, 0, 1, 1, 3)
        status_layout.addWidget(self.p2_label, 1, 1)
        status_layout.addWidget(self.p2_star_label, 1, 2)
        status_layout.addWidget(self.timer_bar, 2, 1, 1, 3)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Session control", 3, self, self.scaler))
        layout.addWidget(request_box)
        layout.addWidget(status_box)
        layout.addWidget(QLabel("Request / response log:", self))
        layout.addWidget(self.history_view, 1)

        self._countdown = QTimer(self)
        self._countdown.setInterval(200)
        self._countdown.timeout.connect(self._tick)

    # -- API -----------------------------------------------------------------
    def selected_session(self) -> int:
        """Return the session sub-function chosen by the operator."""
        custom = self.custom_field.value()
        return custom[0] if custom else int(self.session_box.currentData())

    def set_active_session(self, session: int, p2_ms: float = 50.0, p2_star_ms: float = 5000.0,
                           s3_ms: float = 4000.0) -> None:
        """Update the status block after a successful session change."""
        self.current_label.setText(f"{session_name(session)} (0x{session:02X})")
        self.p2_label.setText(f"P2: {p2_ms:.0f} ms")
        self.p2_star_label.setText(f"P2*: {p2_star_ms:.0f} ms")
        default = session == int(SessionType.DEFAULT)
        self.state_led.set_state("connected" if not default else "idle")
        self.remaining_ms = 0.0 if default else s3_ms
        self._s3_total = max(1.0, s3_ms)
        if default:
            self._countdown.stop()
            self.timer_bar.setValue(0)
        else:
            self._countdown.start()

    def log_exchange(self, request: bytes, response: bytes) -> None:
        """Append a request/response pair to the log view."""
        self.history_view.appendPlainText(f"TX: {request.hex(' ').upper()}")
        if response:
            self.history_view.appendPlainText(f"RX: {response.hex(' ').upper()}")
        else:
            self.history_view.appendPlainText("RX: (no response)")

    def set_busy(self, busy: bool) -> None:
        """Show the spinner on the send button while a request is running."""
        self.send_button.set_loading(busy)

    def reset_timer(self) -> None:
        """Restart the S3 countdown after any diagnostic activity."""
        if self._countdown.isActive():
            self.remaining_ms = getattr(self, "_s3_total", 4000.0)

    # -- events ----------------------------------------------------------------
    def _on_session_selected(self, _index: int) -> None:
        """Clear the custom field when a standard session is chosen."""
        self.custom_field.clear()

    def _on_send(self) -> None:
        """Emit the session request."""
        self.session_requested.emit(self.selected_session())

    def _tick(self) -> None:
        """Advance the S3 countdown bar."""
        total = getattr(self, "_s3_total", 4000.0)
        self.remaining_ms = max(0.0, self.remaining_ms - 200.0)
        self.timer_bar.setValue(int(self.remaining_ms / total * 100))
        self.timer_bar.setFormat(f"S3 timer: {self.remaining_ms / 1000.0:.1f} s remaining")
        if self.remaining_ms <= 0:
            self._countdown.stop()
            self.state_led.set_state("warning")


__all__ = ["SessionControlView"]
