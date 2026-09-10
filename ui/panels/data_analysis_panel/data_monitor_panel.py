"""Real-time DID monitoring panel."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.models.did_model import DIDValue

from ...dpi_scaler import DPIScaler
from ...widgets.hex_input_field import HexInputField
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.scalable_label import HeadingLabel
from ...widgets.table_widget_enhanced import EnhancedTableWidget


class DataMonitorPanel(ResponsiveWidget):
    """Polls a list of DIDs and shows their live values with min/max tracking.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with ``(dids, interval_ms)`` when monitoring starts.
    monitoring_started = Signal(list, int)
    #: Emitted when monitoring stops.
    monitoring_stopped = Signal()

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the DID list and the monitoring controls."""
        super().__init__(parent, scaler)
        self.history: dict[int, list[float]] = {}

        self.did_field = HexInputField(self, self.scaler, min_bytes=2, max_bytes=2,
                                       placeholder="F1 A0")
        self.add_button = ScalableButton("Add DID", "add", self, self.scaler)
        self.add_button.clicked.connect(self.add_did)
        self.remove_button = ScalableButton("Remove", "remove", self, self.scaler)
        self.remove_button.clicked.connect(self.remove_selected)
        self.interval_box = QSpinBox(self)
        self.interval_box.setRange(100, 60000)
        self.interval_box.setSingleStep(100)
        self.interval_box.setValue(500)
        self.interval_box.setSuffix(" ms")
        self.start_button = ScalableButton("Start", "play", self, self.scaler, accent=True)
        self.start_button.clicked.connect(self._on_start)
        self.stop_button = ScalableButton("Stop", "stop", self, self.scaler)
        self.stop_button.clicked.connect(self._on_stop)
        self.stop_button.setEnabled(False)
        self.highlight_box = QCheckBox("Highlight changes", self)
        self.highlight_box.setChecked(True)

        self.table = EnhancedTableWidget(
            ["DID", "Name", "Raw", "Value", "Unit", "Min", "Max", "Updated"], self, self.scaler
        )

        controls = QGroupBox("Monitored identifiers", self)
        controls_layout = QVBoxLayout(controls)
        row = QHBoxLayout()
        row.setSpacing(self.spacing(6))
        row.addWidget(QLabel("DID:", self))
        row.addWidget(self.did_field)
        row.addWidget(self.add_button)
        row.addWidget(self.remove_button)
        row.addStretch(1)
        row.addWidget(QLabel("Interval:", self))
        row.addWidget(self.interval_box)
        row.addWidget(self.start_button)
        row.addWidget(self.stop_button)
        row.addWidget(self.highlight_box)
        controls_layout.addLayout(row)
        controls_layout.addWidget(self.table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(8))
        layout.addWidget(HeadingLabel("Data monitor", 3, self, self.scaler))
        layout.addWidget(controls, 1)

    # -- list management ----------------------------------------------------
    def add_did(self, did: int | None = None) -> None:
        """Add a DID to the monitored list."""
        if did is None:
            data = self.did_field.value()
            if len(data) != 2:
                return
            did = int.from_bytes(data, "big")
        self.table.append_row(
            {
                "DID": f"{did:04X}",
                "Name": "",
                "Raw": "",
                "Value": "",
                "Unit": "",
                "Min": "",
                "Max": "",
                "Updated": "",
            }
        )

    def remove_selected(self) -> None:
        """Remove the selected rows."""
        keep = [
            row
            for row in self.table.rows()
            if row not in self.table.selected_rows()
        ]
        self.table.set_rows(keep)

    def monitored_dids(self) -> list[int]:
        """Return every monitored DID."""
        result: list[int] = []
        for row in self.table.rows():
            try:
                result.append(int(str(row.get("DID", "")), 16))
            except ValueError:
                continue
        return result

    # -- updates -------------------------------------------------------------
    def update_values(self, values: list[DIDValue]) -> None:
        """Refresh the table with freshly read values."""
        import time

        by_did = {value.did: value for value in values}
        rows = self.table.rows()
        for row in rows:
            try:
                did = int(str(row.get("DID", "")), 16)
            except ValueError:
                continue
            value = by_did.get(did)
            if value is None:
                continue
            row["Name"] = value.name
            row["Raw"] = value.hex_value
            row["Value"] = str(value.parsed)
            row["Unit"] = value.unit
            row["Updated"] = time.strftime("%H:%M:%S")
            numeric = self._numeric(value.parsed)
            if numeric is not None:
                series = self.history.setdefault(did, [])
                series.append(numeric)
                del series[:-200]
                row["Min"] = f"{min(series):g}"
                row["Max"] = f"{max(series):g}"
        self.table.set_rows(rows)

    def set_running(self, running: bool) -> None:
        """Toggle the start and stop buttons."""
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    @staticmethod
    def _numeric(value: Any) -> float | None:
        """Return *value* as a float when possible."""
        try:
            return float(str(value).split()[0])
        except (TypeError, ValueError, IndexError):
            return None

    # -- events ----------------------------------------------------------------
    def _on_start(self) -> None:
        """Emit the monitoring start request."""
        dids = self.monitored_dids()
        if dids:
            self.set_running(True)
            self.monitoring_started.emit(dids, self.interval_box.value())

    def _on_stop(self) -> None:
        """Emit the monitoring stop request."""
        self.set_running(False)
        self.monitoring_stopped.emit()


__all__ = ["DataMonitorPanel"]
