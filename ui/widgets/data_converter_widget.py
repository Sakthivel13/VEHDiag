"""Multi-format data conversion widget."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.enums.data_format_enums import ByteOrder, DataFormat
from src.data_processing.converters.physical_value_converter import ScalingRule
from src.data_processing.data_converter import ConversionResult, DataConverter

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole
from .hex_input_field import HexInputField
from .responsive_widget import ResponsiveWidget


class DataConverterWidget(ResponsiveWidget):
    """Enter data in any format and see every other representation.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the parsed bytes whenever the input changes.
    value_changed = Signal(bytes)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the input row and the results table."""
        super().__init__(parent, scaler)
        self.converter = DataConverter()
        self._data = b""

        self.format_box = QComboBox(self)
        for fmt in (
            DataFormat.HEX,
            DataFormat.ASCII,
            DataFormat.DEC_UNSIGNED,
            DataFormat.BIN,
            DataFormat.BCD,
        ):
            self.format_box.addItem(fmt.display_name, fmt.value)
        self.format_box.currentIndexChanged.connect(self._recalculate)

        self.order_box = QComboBox(self)
        self.order_box.addItem("Big endian", ByteOrder.BIG_ENDIAN.value)
        self.order_box.addItem("Little endian", ByteOrder.LITTLE_ENDIAN.value)
        self.order_box.currentIndexChanged.connect(self._recalculate)

        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("41 42 43 44")
        self.input_field.setProperty("role", "mono")
        self.input_field.textChanged.connect(self._recalculate)

        self.factor_box = QDoubleSpinBox(self)
        self.factor_box.setRange(-1e6, 1e6)
        self.factor_box.setDecimals(6)
        self.factor_box.setValue(1.0)
        self.factor_box.valueChanged.connect(self._recalculate)
        self.offset_box = QDoubleSpinBox(self)
        self.offset_box.setRange(-1e6, 1e6)
        self.offset_box.setDecimals(6)
        self.offset_box.valueChanged.connect(self._recalculate)
        self.unit_field = QLineEdit(self)
        self.unit_field.setPlaceholderText("unit")
        self.unit_field.setMaximumWidth(self.px(80))
        self.unit_field.textChanged.connect(self._recalculate)

        self.results = QTableWidget(0, 3, self)
        self.results.setHorizontalHeaderLabels(["Format", "Value", ""])
        self.results.verticalHeader().setVisible(False)
        self.results.setColumnWidth(0, self.px(140))
        self.results.setColumnWidth(2, self.px(40))
        self.results.horizontalHeader().setStretchLastSection(False)
        self.results.horizontalHeader().setSectionResizeMode(1, self.results.horizontalHeader().ResizeMode.Stretch)

        input_row = QHBoxLayout()
        input_row.setSpacing(self.spacing(6))
        input_row.addWidget(QLabel("Format:", self))
        input_row.addWidget(self.format_box)
        input_row.addWidget(QLabel("Order:", self))
        input_row.addWidget(self.order_box)
        input_row.addWidget(self.input_field, 1)

        formula_row = QHBoxLayout()
        formula_row.setSpacing(self.spacing(6))
        formula_row.addWidget(QLabel("Physical = raw x", self))
        formula_row.addWidget(self.factor_box)
        formula_row.addWidget(QLabel("+", self))
        formula_row.addWidget(self.offset_box)
        formula_row.addWidget(self.unit_field)
        formula_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(6))
        layout.addLayout(input_row)
        layout.addLayout(formula_row)
        layout.addWidget(self.results, 1)
        self._apply_mono_font()

    # -- API -----------------------------------------------------------------
    def set_data(self, data: bytes) -> None:
        """Load raw *data* into the converter."""
        self.format_box.setCurrentIndex(0)
        self.input_field.setText(" ".join(f"{b:02X}" for b in data))

    def data(self) -> bytes:
        """Return the currently parsed bytes."""
        return self._data

    def result(self) -> ConversionResult:
        """Return the full conversion result for the current input."""
        return self.converter.convert_all(self._data, self._scaling())

    # -- internals -------------------------------------------------------------
    def _scaling(self) -> ScalingRule:
        """Return the scaling rule described by the formula row."""
        return ScalingRule(
            factor=self.factor_box.value(),
            offset=self.offset_box.value(),
            unit=self.unit_field.text().strip(),
        )

    def _recalculate(self, *_: Any) -> None:
        """Re-parse the input and refresh the results table."""
        source = DataFormat(self.format_box.currentData())
        try:
            self._data = self.converter.parse(self.input_field.text(), source)
            self.input_field.setProperty("valid", "true")
        except Exception:  # noqa: BLE001 - invalid intermediate input is normal
            self._data = b""
            self.input_field.setProperty("valid", "false")
        style = self.input_field.style()
        if style is not None:
            style.unpolish(self.input_field)
            style.polish(self.input_field)

        result = self.converter.convert_all(self._data, self._scaling())
        rows = result.as_rows()
        self.results.setRowCount(len(rows))
        for index, (name, value) in enumerate(rows):
            self.results.setItem(index, 0, QTableWidgetItem(name))
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.results.setItem(index, 1, item)
            button = QPushButton("copy", self)
            button.setFlat(True)
            button.clicked.connect(lambda _=False, text=value: QGuiApplication.clipboard().setText(text))
            self.results.setCellWidget(index, 2, button)
        self.value_changed.emit(self._data)

    def _apply_mono_font(self) -> None:
        """Apply the monospace font to the results table."""
        from ..font_manager import FontManager

        font = FontManager(self.scaler).qfont(FontRole.MONOSPACE)
        if font is not None:
            self.results.setFont(font)


__all__ = ["DataConverterWidget"]
