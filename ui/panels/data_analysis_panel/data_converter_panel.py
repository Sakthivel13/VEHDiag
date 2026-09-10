"""Sliced data converter panel.

This panel sits to the right of the slicer in the *Data analysis* workspace.
It always describes **one** piece of data - either the whole response or the
single slice highlighted in the slicer - in every representation at once, with
the slice's own scaling rule pre-filled so the physical value is correct
without retyping the factor and the offset.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.data_processing.converters.physical_value_converter import ScalingRule

from ...dpi_scaler import DPIScaler
from ...widgets.data_converter_widget import DataConverterWidget
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_label import HeadingLabel, ScalableLabel
from ...styles.style_constants import FontRole


class DataConverterPanel(ResponsiveWidget):
    """Hosts the :class:`DataConverterWidget` and names its data source.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        converter: The underlying conversion widget.
        source_label: Shows which slice is currently being converted.
    """

    #: Emitted with the parsed bytes whenever the input changes.
    value_changed = Signal(bytes)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the panel."""
        super().__init__(parent, scaler)
        self.converter = DataConverterWidget(self, self.scaler)
        self.converter.value_changed.connect(self.value_changed.emit)

        self.source_label = ScalableLabel(
            "no slice selected", FontRole.BODY_SMALL, self, self.scaler
        )
        self.source_label.setProperty("role", "secondary")
        self.source_label.setToolTip("Select a row in the slicer to convert that field alone")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(6))
        layout.addWidget(HeadingLabel("Sliced data converter", 3, self, self.scaler))
        layout.addWidget(self.source_label)
        layout.addWidget(self.converter, 1)

    # -- API -----------------------------------------------------------------
    def set_data(self, data: bytes) -> None:
        """Load raw *data* into the converter."""
        self.converter.set_data(data)

    def data(self) -> bytes:
        """Return the parsed bytes."""
        return self.converter.data()

    def set_source(self, name: str) -> str:
        """Name the slice currently being converted.

        Args:
            name: Slice name, or a phrase such as ``"whole response"``.

        Returns:
            The text written to the label.
        """
        text = f"converting: {name}" if name else "no slice selected"
        self.source_label.setText(text)
        return text

    def source(self) -> str:
        """Return the source description currently displayed."""
        return self.source_label.full_text()

    def apply_scaling(self, rule: ScalingRule) -> None:
        """Pre-fill the factor, offset and unit from a slice's scaling rule."""
        self.converter.factor_box.setValue(float(rule.factor))
        self.converter.offset_box.setValue(float(rule.offset))
        self.converter.unit_field.setText(str(rule.unit))


__all__ = ["DataConverterPanel"]
