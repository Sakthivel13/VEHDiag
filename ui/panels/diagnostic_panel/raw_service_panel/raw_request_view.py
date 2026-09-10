"""Raw UDS request panel."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QWidget

from ....dpi_scaler import DPIScaler
from ....widgets.payload_input_widget import PayloadInputWidget
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.response_data_viewer import ResponseDataViewer
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel
from ....widgets.table_widget_enhanced import EnhancedTableWidget


class RawRequestView(ResponsiveWidget):
    """Send an arbitrary UDS payload and inspect the answer.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with ``(payload, functional)`` when the operator sends a request.
    request_submitted = Signal(bytes, bool)
    #: Emitted with the response bytes when *Analyse* is pressed.
    analyse_requested = Signal(bytes)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the payload entry, the response view and the history table."""
        super().__init__(parent, scaler)

        self.payload_input = PayloadInputWidget(self, self.scaler)
        self.payload_input.submitted.connect(lambda payload: self._send(payload))
        self.send_button = ScalableButton("Send", "play", self, self.scaler, accent=True)
        self.send_button.clicked.connect(lambda: self._send(self.payload_input.payload()))
        self.functional_button = ScalableButton("Send functional", "run_all", self, self.scaler)
        self.functional_button.clicked.connect(
            lambda: self._send(self.payload_input.payload(), functional=True)
        )

        self.response_view = ResponseDataViewer(self, self.scaler)
        self.analyse_button = ScalableButton("Analyse", "convert", self, self.scaler)
        self.analyse_button.clicked.connect(
            lambda: self.analyse_requested.emit(self.response_view.data())
        )

        self.history_table = EnhancedTableWidget(
            ["Time", "Request", "Response", "Result", "Duration"], self, self.scaler
        )
        self.history_table.row_activated.connect(self._on_history_activated)

        request_box = QGroupBox("Raw request", self)
        request_layout = QVBoxLayout(request_box)
        request_layout.setSpacing(self.spacing(6))
        request_layout.addWidget(self.payload_input)
        buttons = QHBoxLayout()
        buttons.addWidget(self.send_button)
        buttons.addWidget(self.functional_button)
        buttons.addStretch(1)
        request_layout.addLayout(buttons)

        response_box = QGroupBox("Response", self)
        response_layout = QVBoxLayout(response_box)
        response_layout.addWidget(self.response_view)
        response_layout.addWidget(self.analyse_button, 0, Qt.AlignmentFlag.AlignLeft)

        history_box = QGroupBox("History", self)
        history_layout = QVBoxLayout(history_box)
        history_layout.addWidget(self.history_table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Raw service request", 3, self, self.scaler))
        layout.addWidget(request_box)
        layout.addWidget(response_box, 1)
        layout.addWidget(history_box, 1)

    # -- API -----------------------------------------------------------------
    def show_response(self, request: bytes, response: bytes, summary: str = "",
                      duration_ms: float = 0.0, decoded: str = "") -> None:
        """Display a response and append it to the history."""
        import time

        self.response_view.set_data(response, decoded or summary)
        self.history_table.append_row(
            {
                "Time": time.strftime("%H:%M:%S"),
                "Request": request.hex(" ").upper(),
                "Response": response.hex(" ").upper() or "(none)",
                "Result": summary,
                "Duration": f"{duration_ms:.1f} ms",
            }
        )
        self.payload_input.remember(request)

    def set_busy(self, busy: bool) -> None:
        """Show the spinner while the request is running."""
        self.send_button.set_loading(busy)

    def _send(self, payload: bytes, functional: bool = False) -> None:
        """Emit the request when the payload is valid."""
        if payload:
            self.request_submitted.emit(payload, functional)

    def _on_history_activated(self, row: dict[str, Any]) -> None:
        """Reload a payload from the history into the entry field."""
        self.payload_input.set_payload(str(row.get("Request", "")))


__all__ = ["RawRequestView"]
