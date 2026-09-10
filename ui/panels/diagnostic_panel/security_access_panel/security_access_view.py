"""SecurityAccess (SID 0x27) panel."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.diagnostics.services.security.security_access import SecurityAccessResult
from src.diagnostics.services.security.security_algorithms import available_algorithms

from ....dpi_scaler import DPIScaler
from ....widgets.file_browser_widget import FileBrowserWidget
from ....widgets.hex_input_field import HexInputField
from ....widgets.led_indicator import LedIndicator
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel

#: Sources the seed-key algorithm can come from.
ALGORITHM_SOURCES: tuple[str, ...] = ("Built-in", "External library", "Python script", "Manual key")


class SecurityAccessView(ResponsiveWidget):
    """UI for the seed request and key submission sequence.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the security level for a seed request.
    seed_requested = Signal(int)
    #: Emitted with ``(level, key)`` when the operator submits a key.
    key_submitted = Signal(int, bytes)
    #: Emitted with ``(level, source, algorithm, path)`` for a full unlock.
    unlock_requested = Signal(int, str, str, str)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the level selector, the algorithm row and the status block."""
        super().__init__(parent, scaler)
        self.delay_remaining = 0.0

        self.level_box = QComboBox(self)
        for level in range(0x01, 0x20, 2):
            self.level_box.addItem(f"Level 0x{level:02X}", level)
        self.level_box.addItem("Programming level 0x11", 0x11)

        self.source_box = QComboBox(self)
        self.source_box.addItems(ALGORITHM_SOURCES)
        self.source_box.currentIndexChanged.connect(self._on_source_changed)

        self.algorithm_box = QComboBox(self)
        self.algorithm_box.addItems(available_algorithms())

        self.file_browser = FileBrowserWidget(
            self, self.scaler, "Select the seed-key implementation",
            "Seed-key implementations (*.dll *.so *.dylib *.py)"
        )
        self.file_browser.setVisible(False)

        self.seed_field = HexInputField(self, self.scaler, placeholder="seed from the ECU")
        self.seed_field.setReadOnly(True)
        self.key_field = HexInputField(self, self.scaler, placeholder="computed or manual key")

        self.request_seed_button = ScalableButton("Request seed", "play", self, self.scaler)
        self.request_seed_button.clicked.connect(
            lambda: self.seed_requested.emit(self.selected_level())
        )
        self.send_key_button = ScalableButton("Send key", "play", self, self.scaler)
        self.send_key_button.clicked.connect(
            lambda: self.key_submitted.emit(self.selected_level(), self.key_field.value())
        )
        self.auto_button = ScalableButton("Auto unlock", "run_all", self, self.scaler, accent=True)
        self.auto_button.clicked.connect(self._on_auto_unlock)

        self.state_led = LedIndicator("locked", 14, self, self.scaler)
        self.state_label = QLabel("LOCKED", self)
        self.attempts_label = QLabel("Attempts: 0", self)
        self.delay_label = QLabel("Delay: none", self)
        self.steps_view = QPlainTextEdit(self)
        self.steps_view.setReadOnly(True)
        self.steps_view.setProperty("role", "mono")
        self.steps_view.setMaximumHeight(self.px(140))

        request_box = QGroupBox("Security access (SID 0x27)", self)
        grid = QGridLayout(request_box)
        grid.setSpacing(self.spacing(8))
        grid.addWidget(QLabel("Security level:", self), 0, 0)
        grid.addWidget(self.level_box, 0, 1)
        grid.addWidget(QLabel("Algorithm source:", self), 1, 0)
        grid.addWidget(self.source_box, 1, 1)
        grid.addWidget(QLabel("Built-in algorithm:", self), 2, 0)
        grid.addWidget(self.algorithm_box, 2, 1)
        grid.addWidget(QLabel("Implementation file:", self), 3, 0)
        grid.addWidget(self.file_browser, 3, 1)
        grid.addWidget(QLabel("Seed:", self), 4, 0)
        grid.addWidget(self.seed_field, 4, 1)
        grid.addWidget(QLabel("Key:", self), 5, 0)
        grid.addWidget(self.key_field, 5, 1)
        grid.addWidget(self.request_seed_button, 6, 0)
        grid.addWidget(self.send_key_button, 6, 1, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.auto_button, 6, 2)

        status_box = QGroupBox("Status", self)
        status_layout = QGridLayout(status_box)
        status_layout.addWidget(self.state_led, 0, 0)
        status_layout.addWidget(self.state_label, 0, 1)
        status_layout.addWidget(self.attempts_label, 0, 2)
        status_layout.addWidget(self.delay_label, 0, 3)
        status_layout.addWidget(self.steps_view, 1, 0, 1, 4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Security access", 3, self, self.scaler))
        layout.addWidget(request_box)
        layout.addWidget(status_box, 1)

        self._countdown = QTimer(self)
        self._countdown.setInterval(500)
        self._countdown.timeout.connect(self._tick)

    # -- API -----------------------------------------------------------------
    def selected_level(self) -> int:
        """Return the security level chosen by the operator."""
        return int(self.level_box.currentData())

    def algorithm(self) -> str:
        """Return the selected built-in algorithm name."""
        return self.algorithm_box.currentText()

    def source(self) -> str:
        """Return the selected algorithm source."""
        return self.source_box.currentText()

    def show_seed(self, seed: bytes) -> None:
        """Display the seed returned by the ECU."""
        self.seed_field.set_value(seed)
        self.steps_view.appendPlainText(f"seed received: {seed.hex(' ').upper()}")

    def show_key(self, key: bytes) -> None:
        """Display the computed key."""
        self.key_field.set_value(key)
        self.steps_view.appendPlainText(f"key computed: {key.hex(' ').upper()}")

    def show_result(self, result: SecurityAccessResult) -> None:
        """Update the whole status block from an unlock attempt."""
        if result.seed:
            self.seed_field.set_value(result.seed)
        if result.key:
            self.key_field.set_value(result.key)
        self.set_unlocked(result.unlocked)
        self.attempts_label.setText(f"Attempts: {result.attempts}")
        if result.delay_remaining_s > 0:
            self.start_delay(result.delay_remaining_s)
        self.steps_view.appendPlainText(str(result))

    def set_unlocked(self, unlocked: bool) -> None:
        """Update the lock indicator."""
        self.state_led.set_state("unlocked" if unlocked else "locked")
        self.state_label.setText("UNLOCKED" if unlocked else "LOCKED")

    def start_delay(self, seconds: float) -> None:
        """Start the security delay countdown."""
        self.delay_remaining = seconds
        self.state_led.set_state("warning")
        self._countdown.start()

    def set_busy(self, busy: bool) -> None:
        """Show the spinner while an unlock is running."""
        self.auto_button.set_loading(busy)

    def log(self, message: str) -> None:
        """Append a line to the step visualisation."""
        self.steps_view.appendPlainText(message)

    # -- events ----------------------------------------------------------------
    def _on_source_changed(self, index: int) -> None:
        """Show or hide the widgets matching the selected source."""
        source = ALGORITHM_SOURCES[index]
        self.algorithm_box.setVisible(source == "Built-in")
        self.file_browser.setVisible(source in ("External library", "Python script"))
        self.key_field.setReadOnly(source != "Manual key")

    def _on_auto_unlock(self) -> None:
        """Emit the full unlock request."""
        self.steps_view.clear()
        self.unlock_requested.emit(
            self.selected_level(), self.source(), self.algorithm(), self.file_browser.path()
        )

    def _tick(self) -> None:
        """Advance the security delay countdown."""
        self.delay_remaining = max(0.0, self.delay_remaining - 0.5)
        if self.delay_remaining <= 0:
            self._countdown.stop()
            self.delay_label.setText("Delay: none")
            self.state_led.set_state("locked")
        else:
            self.delay_label.setText(f"Delay: {self.delay_remaining:.1f} s")


__all__ = ["SecurityAccessView", "ALGORITHM_SOURCES"]
