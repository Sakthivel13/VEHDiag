"""Response slicer panel."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QVBoxLayout, QWidget

from src.data_processing.response_slicer import SliceProfile

from ...dpi_scaler import DPIScaler
from ...widgets.data_slicer_widget import DataSlicerWidget
from ...widgets.hex_input_field import HexInputField
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.scalable_label import HeadingLabel


class ResponseSlicerPanel(ResponsiveWidget):
    """Lets the operator slice a response into named, converted fields.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with ``{name: value}`` whenever the slices change.
    values_changed = Signal(dict)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the data entry row and the slicer widget."""
        super().__init__(parent, scaler)

        self.data_field = HexInputField(self, self.scaler, placeholder="62 F1 90 57 42 41 5A")
        self.data_field.bytes_changed.connect(self._on_data_changed)
        self.paste_button = ScalableButton("Paste", "copy", self, self.scaler)
        self.paste_button.clicked.connect(self._paste)
        self.load_last_button = ScalableButton("Load last response", "refresh", self, self.scaler)
        self.save_profile_button = ScalableButton("Save profile", "save", self, self.scaler)
        self.save_profile_button.clicked.connect(self.save_profile)
        self.load_profile_button = ScalableButton("Load profile", "folder_open", self, self.scaler)
        self.load_profile_button.clicked.connect(self.load_profile)

        self.slicer = DataSlicerWidget(self, self.scaler)
        self.slicer.slices_changed.connect(self.values_changed.emit)

        entry_box = QGroupBox("Response data", self)
        entry_layout = QHBoxLayout(entry_box)
        entry_layout.setSpacing(self.spacing(6))
        entry_layout.addWidget(self.data_field, 1)
        entry_layout.addWidget(self.paste_button)
        entry_layout.addWidget(self.load_last_button)

        profile_row = QHBoxLayout()
        profile_row.addStretch(1)
        profile_row.addWidget(self.save_profile_button)
        profile_row.addWidget(self.load_profile_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(8))
        layout.addWidget(HeadingLabel("Response slicer", 3, self, self.scaler))
        layout.addWidget(entry_box)
        layout.addWidget(self.slicer, 1)
        layout.addLayout(profile_row)

    # -- API -----------------------------------------------------------------
    def set_data(self, data: bytes, auto_detect: bool = True) -> None:
        """Load *data* into the slicer, optionally creating default slices."""
        self.data_field.set_value(data)
        if auto_detect and data and not self.slicer.current_profile().slices:
            self.slicer.auto_detect()

    def values(self) -> dict[str, Any]:
        """Return the current slice values."""
        return self.slicer.values()

    def save_profile(self) -> Path | None:
        """Ask for a destination and save the slice profile."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save slice profile", str(Path.home() / "slices.yaml"), "YAML files (*.yaml)"
        )
        if not path:
            return None
        return self.slicer.current_profile().save(path)

    def load_profile(self) -> Path | None:
        """Ask for a file and load the slice profile from it."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load slice profile", str(Path.home()), "YAML files (*.yaml *.yml)"
        )
        if not path:
            return None
        self.slicer.load_profile(SliceProfile.load(path))
        return Path(path)

    # -- events ----------------------------------------------------------------
    def _on_data_changed(self, data: bytes) -> None:
        """Forward new data to the slicer widget."""
        self.slicer.set_data(data)

    def _paste(self) -> None:
        """Paste hexadecimal data from the clipboard."""
        from PySide6.QtGui import QGuiApplication

        self.data_field.setText(QGuiApplication.clipboard().text())


__all__ = ["ResponseSlicerPanel"]
