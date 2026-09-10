"""RoutineControl (SID 0x31) panel."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from src.core.enums.session_enums import RoutineControlType
from src.diagnostics.services.routine_control.routine_control import RoutineResult
from src.diagnostics.services.routine_control.routine_types import STANDARD_ROUTINES

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.led_indicator import LedIndicator
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.response_data_viewer import ResponseDataViewer
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel


class RoutineControlView(ResponsiveWidget):
    """UI for starting, stopping and polling ECU routines.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with ``(sub_function, routine_id, option_record)``.
    routine_requested = Signal(int, int, bytes)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the routine selector and the result view."""
        super().__init__(parent, scaler)

        self.routine_box = QComboBox(self)
        self.routine_box.setEditable(True)
        for routine_id, name in STANDARD_ROUTINES.items():
            self.routine_box.addItem(f"{routine_id:04X} - {name}", routine_id)
        self.routine_box.currentIndexChanged.connect(self._on_routine_selected)

        self.routine_field = HexInputField(self, self.scaler, min_bytes=2, max_bytes=2,
                                           placeholder="0202")
        self.option_field = HexInputField(self, self.scaler, placeholder="option record (optional)")

        self.start_button = ScalableButton("Start", "play", self, self.scaler, accent=True)
        self.start_button.clicked.connect(
            lambda: self._request(int(RoutineControlType.START_ROUTINE))
        )
        self.stop_button = ScalableButton("Stop", "stop", self, self.scaler)
        self.stop_button.clicked.connect(
            lambda: self._request(int(RoutineControlType.STOP_ROUTINE))
        )
        self.results_button = ScalableButton("Request results", "refresh", self, self.scaler)
        self.results_button.clicked.connect(
            lambda: self._request(int(RoutineControlType.REQUEST_ROUTINE_RESULTS))
        )

        self.state_led = LedIndicator("idle", 14, self, self.scaler)
        self.state_label = QLabel("Idle", self)
        self.response_view = ResponseDataViewer(self, self.scaler)

        request_box = QGroupBox("Routine control (SID 0x31)", self)
        grid = QGridLayout(request_box)
        grid.setSpacing(self.spacing(8))
        grid.addWidget(QLabel("Known routines:", self), 0, 0)
        grid.addWidget(self.routine_box, 0, 1, 1, 3)
        grid.addWidget(QLabel("Routine identifier:", self), 1, 0)
        grid.addWidget(self.routine_field, 1, 1)
        grid.addWidget(QLabel("Option record:", self), 2, 0)
        grid.addWidget(self.option_field, 2, 1, 1, 3)
        grid.addWidget(self.start_button, 3, 1)
        grid.addWidget(self.stop_button, 3, 2)
        grid.addWidget(self.results_button, 3, 3)

        status_box = QGroupBox("Result", self)
        status_layout = QGridLayout(status_box)
        status_layout.addWidget(self.state_led, 0, 0)
        status_layout.addWidget(self.state_label, 0, 1)
        status_layout.addWidget(self.response_view, 1, 0, 1, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Routine control", 3, self, self.scaler))
        layout.addWidget(request_box)
        layout.addWidget(status_box, 1)
        self._on_routine_selected(0)

    # -- API -----------------------------------------------------------------
    def routine_id(self) -> int | None:
        """Return the routine identifier entered by the operator."""
        data = self.routine_field.value()
        return int.from_bytes(data, "big") if len(data) == 2 else None

    def show_result(self, result: RoutineResult) -> None:
        """Display the outcome of a routine control request."""
        self.state_label.setText(str(result))
        self.state_led.set_state(
            "pass" if result.succeeded else "fail" if result.accepted else "error"
        )
        if result.response is not None:
            self.response_view.set_data(result.response.raw, str(result))

    def set_busy(self, busy: bool) -> None:
        """Show the spinner while the routine runs."""
        self.start_button.set_loading(busy)
        self.state_led.set_state("running" if busy else self.state_led.state)

    # -- events ----------------------------------------------------------------
    def _on_routine_selected(self, index: int) -> None:
        """Fill the identifier field from the known routines list."""
        routine_id = self.routine_box.itemData(index)
        if routine_id:
            self.routine_field.set_value(int(routine_id).to_bytes(2, "big"))

    def _request(self, sub_function: int) -> None:
        """Emit the routine request."""
        routine_id = self.routine_id()
        if routine_id is not None:
            self.routine_requested.emit(sub_function, routine_id, self.option_field.value())


__all__ = ["RoutineControlView"]
