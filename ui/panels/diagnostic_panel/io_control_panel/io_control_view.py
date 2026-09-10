"""InputOutputControlByIdentifier (SID 0x2F) panel."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from src.core.enums.session_enums import IOControlParameter
from src.diagnostics.services.io_control.io_control_by_id import PARAMETER_NAMES, IOControlResult

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.led_indicator import LedIndicator
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.response_data_viewer import ResponseDataViewer
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel


class IOControlView(ResponsiveWidget):
    """UI for overriding ECU input and output signals.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with ``(did, parameter, control_state, control_mask)``.
    control_requested = Signal(int, int, bytes, bytes)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the identifier row and the control parameter selector."""
        super().__init__(parent, scaler)

        self.did_field = HexInputField(self, self.scaler, min_bytes=2, max_bytes=2,
                                       placeholder="F1 A0")
        self.parameter_box = QComboBox(self)
        for value, name in PARAMETER_NAMES.items():
            self.parameter_box.addItem(f"0x{value:02X} {name}", value)
        self.parameter_box.setCurrentIndex(3)
        self.parameter_box.currentIndexChanged.connect(self._on_parameter_changed)

        self.state_field = HexInputField(self, self.scaler, placeholder="control state")
        self.mask_field = HexInputField(self, self.scaler, placeholder="control mask (optional)")

        self.apply_button = ScalableButton("Apply", "play", self, self.scaler, accent=True)
        self.apply_button.clicked.connect(self._on_apply)
        self.return_button = ScalableButton("Return control to ECU", "refresh", self, self.scaler)
        self.return_button.clicked.connect(
            lambda: self._emit(int(IOControlParameter.RETURN_CONTROL_TO_ECU))
        )
        self.reset_button = ScalableButton("Reset to default", "clear", self, self.scaler)
        self.reset_button.clicked.connect(
            lambda: self._emit(int(IOControlParameter.RESET_TO_DEFAULT))
        )

        self.state_led = LedIndicator("idle", 14, self, self.scaler)
        self.status_label = QLabel("No control active", self)
        self.response_view = ResponseDataViewer(self, self.scaler)

        request_box = QGroupBox("I/O control by identifier (SID 0x2F)", self)
        grid = QGridLayout(request_box)
        grid.setSpacing(self.spacing(8))
        grid.addWidget(QLabel("Data identifier:", self), 0, 0)
        grid.addWidget(self.did_field, 0, 1)
        grid.addWidget(QLabel("Control parameter:", self), 1, 0)
        grid.addWidget(self.parameter_box, 1, 1, 1, 2)
        grid.addWidget(QLabel("Control state:", self), 2, 0)
        grid.addWidget(self.state_field, 2, 1, 1, 2)
        grid.addWidget(QLabel("Control mask:", self), 3, 0)
        grid.addWidget(self.mask_field, 3, 1, 1, 2)
        grid.addWidget(self.apply_button, 4, 1)
        grid.addWidget(self.return_button, 4, 2)
        grid.addWidget(self.reset_button, 4, 3)

        status_box = QGroupBox("Result", self)
        status_layout = QGridLayout(status_box)
        status_layout.addWidget(self.state_led, 0, 0)
        status_layout.addWidget(self.status_label, 0, 1)
        status_layout.addWidget(self.response_view, 1, 0, 1, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Input / output control", 3, self, self.scaler))
        layout.addWidget(request_box)
        layout.addWidget(status_box, 1)

    # -- API -----------------------------------------------------------------
    def data_identifier(self) -> int | None:
        """Return the DID entered by the operator."""
        data = self.did_field.value()
        return int.from_bytes(data, "big") if len(data) == 2 else None

    def show_result(self, result: IOControlResult) -> None:
        """Display the outcome of an I/O control request."""
        self.status_label.setText(str(result))
        self.state_led.set_state("pass" if result.accepted else "fail")
        if result.response is not None:
            self.response_view.set_data(result.response.raw, str(result))

    def set_busy(self, busy: bool) -> None:
        """Show the spinner while the request runs."""
        self.apply_button.set_loading(busy)

    # -- events ----------------------------------------------------------------
    def _on_parameter_changed(self, index: int) -> None:
        """Enable the state field only for short term adjustments."""
        parameter = int(self.parameter_box.itemData(index))
        needs_state = parameter == int(IOControlParameter.SHORT_TERM_ADJUSTMENT)
        self.state_field.setEnabled(needs_state)
        self.mask_field.setEnabled(needs_state)

    def _on_apply(self) -> None:
        """Emit the request with the selected control parameter."""
        self._emit(int(self.parameter_box.currentData()))

    def _emit(self, parameter: int) -> None:
        """Emit a control request for *parameter*."""
        did = self.data_identifier()
        if did is None:
            return
        state = self.state_field.value() if parameter == 0x03 else b""
        self.control_requested.emit(did, parameter, state, self.mask_field.value())


__all__ = ["IOControlView"]
