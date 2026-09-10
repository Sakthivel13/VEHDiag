"""ClearDiagnosticInformation (SID 0x14) panel."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.diagnostics.services.dtc_services.clear_dtc import ClearResult
from src.diagnostics.services.dtc_services.dtc_parser import GROUPS

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel
from ....widgets.table_widget_enhanced import EnhancedTableWidget


class ClearDTCView(ResponsiveWidget):
    """UI for clearing diagnostic trouble codes.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the DTC group value the operator confirmed.
    clear_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the group selector and the before/after comparison table."""
        super().__init__(parent, scaler)

        self.group_box = QComboBox(self)
        for key, bounds in GROUPS.items():
            label = key.title() if key != "all" else "All DTCs"
            value = 0xFFFFFF if key == "all" else bounds[0]
            self.group_box.addItem(f"{label} (0x{value:06X})", value)

        self.specific_field = HexInputField(self, self.scaler, max_bytes=3,
                                            placeholder="specific DTC, e.g. C0 73 00")
        self.clear_button = ScalableButton("Clear DTCs", "clear", self, self.scaler, danger=True)
        self.clear_button.clicked.connect(self._on_clear)

        self.result_label = QLabel("No clear operation performed yet", self)
        self.result_label.setProperty("role", "secondary")
        self.comparison_table = EnhancedTableWidget(["Code", "Before", "After"], self, self.scaler)
        self.history_table = EnhancedTableWidget(["Time", "Group", "Result", "Cleared"], self,
                                                 self.scaler)
        self.history_table.setMaximumHeight(self.px(140))

        request_box = QGroupBox("Clear diagnostic information (SID 0x14)", self)
        request_layout = QGridLayout(request_box)
        request_layout.setSpacing(self.spacing(8))
        request_layout.addWidget(QLabel("DTC group:", self), 0, 0)
        request_layout.addWidget(self.group_box, 0, 1)
        request_layout.addWidget(QLabel("Specific DTC:", self), 1, 0)
        request_layout.addWidget(self.specific_field, 1, 1)
        request_layout.addWidget(self.clear_button, 2, 1, Qt.AlignmentFlag.AlignLeft)

        result_box = QGroupBox("Before / after comparison", self)
        result_layout = QVBoxLayout(result_box)
        result_layout.addWidget(self.result_label)
        result_layout.addWidget(self.comparison_table)

        history_box = QGroupBox("History", self)
        history_layout = QVBoxLayout(history_box)
        history_layout.addWidget(self.history_table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Clear DTC information", 3, self, self.scaler))
        layout.addWidget(request_box)
        layout.addWidget(result_box, 1)
        layout.addWidget(history_box)

    # -- API -----------------------------------------------------------------
    def selected_group(self) -> int:
        """Return the DTC group value chosen by the operator."""
        specific = self.specific_field.value()
        if len(specific) == 3:
            return int.from_bytes(specific, "big")
        return int(self.group_box.currentData())

    def show_result(self, result: ClearResult) -> None:
        """Display the outcome and the before/after comparison."""
        import time

        self.result_label.setText(result.summary)
        before = {d.display_code: d for d in (result.before or [])}
        after = {d.display_code: d for d in (result.after or [])}
        rows = [
            {
                "Code": code,
                "Before": f"0x{before[code].status.value:02X}" if code in before else "-",
                "After": f"0x{after[code].status.value:02X}" if code in after else "cleared",
            }
            for code in sorted(set(before) | set(after))
        ]
        self.comparison_table.set_rows(rows)
        self.history_table.append_row(
            {
                "Time": time.strftime("%H:%M:%S"),
                "Group": f"0x{result.group:06X}",
                "Result": "accepted" if result.accepted else "rejected",
                "Cleared": result.cleared_count,
            }
        )

    def set_busy(self, busy: bool) -> None:
        """Show the spinner while the clear request runs."""
        self.clear_button.set_loading(busy)

    # -- events ----------------------------------------------------------------
    def _on_clear(self) -> None:
        """Ask for confirmation and emit the clear request."""
        group = self.selected_group()
        answer = QMessageBox.warning(
            self,
            "Clear diagnostic trouble codes",
            f"Clear DTC group 0x{group:06X}?\n\n"
            "This permanently deletes the fault memory of the ECU and cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.clear_requested.emit(group)


__all__ = ["ClearDTCView"]
