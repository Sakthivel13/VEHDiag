"""ReadDTCInformation (SID 0x19) panel."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.models.dtc_model import DTC, DTC_STATUS_BITS, DTCReport
from src.diagnostics.services.dtc_services.dtc_status_mask import BIT_ABBREVIATIONS, StatusMask
from src.diagnostics.services.dtc_services.dtc_sub_functions import selectable_sub_functions

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel
from ....widgets.table_widget_enhanced import EnhancedTableWidget

def status_colors() -> dict[str, str]:
    """Return the DTC row colours for the active theme.

    Resolved on each call rather than captured at import time so the table
    recolours when the operator switches theme.

    Example:
        >>> from ui.styles.semantic_colors import semantic
        >>> status_colors()["confirmed"] == semantic("confirmed")
        True
    """
    from ....styles.semantic_colors import semantic

    return {
        "confirmed": semantic("confirmed"),
        "pending": semantic("pending"),
        "clean": semantic("clean"),
    }


class ReadDTCView(ResponsiveWidget):
    """UI for reading diagnostic trouble codes.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with ``(sub_function, status_mask)``.
    read_requested = Signal(int, int)
    #: Emitted with the DTC whose snapshot should be read.
    snapshot_requested = Signal(int)
    #: Emitted with the DTC whose extended data should be read.
    extended_requested = Signal(int)
    #: Emitted with the export format chosen by the operator.
    export_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the sub-function selector, the mask row and the results table."""
        super().__init__(parent, scaler)
        self.report: DTCReport | None = None

        self.sub_function_box = QComboBox(self)
        for spec in selectable_sub_functions():
            self.sub_function_box.addItem(f"{spec.hex_value} {spec.label}", spec.value)
        self.sub_function_box.setCurrentIndex(1)

        self.mask_boxes: dict[int, QCheckBox] = {}
        mask_row = QHBoxLayout()
        mask_row.setSpacing(self.spacing(8))
        for bit, name in DTC_STATUS_BITS.items():
            box = QCheckBox(BIT_ABBREVIATIONS[bit], self)
            box.setToolTip(name)
            box.setChecked(bit in (0, 1, 2, 3))
            self.mask_boxes[bit] = box
            mask_row.addWidget(box)
        mask_row.addStretch(1)

        self.dtc_mask_field = HexInputField(self, self.scaler, max_bytes=3, placeholder="FF FF FF")
        self.read_button = ScalableButton("Read DTCs", "play", self, self.scaler, accent=True)
        self.read_button.clicked.connect(self._on_read)

        self.count_label = QLabel("No DTCs read", self)
        self.count_label.setProperty("role", "secondary")
        self.results_table = EnhancedTableWidget(
            ["Code", "Description", "Status", "Confirmed", "Pending", "Severity", "Occurrences"],
            self,
            self.scaler,
        )
        self.results_table.itemSelectionChanged.connect(self._on_selection)

        self.detail_label = QLabel("Select a DTC to see its status bits", self)
        self.detail_label.setWordWrap(True)
        self.snapshot_button = ScalableButton("Read snapshot", "search", self, self.scaler)
        self.snapshot_button.clicked.connect(self._on_snapshot)
        self.extended_button = ScalableButton("Read extended data", "search", self, self.scaler)
        self.extended_button.clicked.connect(self._on_extended)
        self.export_csv_button = ScalableButton("Export CSV", "export", self, self.scaler)
        self.export_csv_button.clicked.connect(lambda: self.export_requested.emit("CSV"))
        self.export_html_button = ScalableButton("Export HTML", "export", self, self.scaler)
        self.export_html_button.clicked.connect(lambda: self.export_requested.emit("HTML"))

        request_box = QGroupBox("Read DTC information (SID 0x19)", self)
        request_layout = QGridLayout(request_box)
        request_layout.setSpacing(self.spacing(8))
        request_layout.addWidget(QLabel("Sub-function:", self), 0, 0)
        request_layout.addWidget(self.sub_function_box, 0, 1, 1, 3)
        request_layout.addWidget(QLabel("Status mask:", self), 1, 0)
        request_layout.addLayout(mask_row, 1, 1, 1, 3)
        request_layout.addWidget(QLabel("DTC mask:", self), 2, 0)
        request_layout.addWidget(self.dtc_mask_field, 2, 1)
        request_layout.addWidget(self.read_button, 2, 3, Qt.AlignmentFlag.AlignRight)

        results_box = QGroupBox("Results", self)
        results_layout = QVBoxLayout(results_box)
        results_layout.setSpacing(self.spacing(6))
        results_layout.addWidget(self.count_label)
        results_layout.addWidget(self.results_table, 1)
        actions = QHBoxLayout()
        actions.addWidget(self.snapshot_button)
        actions.addWidget(self.extended_button)
        actions.addStretch(1)
        actions.addWidget(self.export_csv_button)
        actions.addWidget(self.export_html_button)
        results_layout.addLayout(actions)

        detail_box = QGroupBox("DTC detail", self)
        detail_layout = QVBoxLayout(detail_box)
        detail_layout.addWidget(self.detail_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Read DTC information", 3, self, self.scaler))
        layout.addWidget(request_box)
        layout.addWidget(results_box, 1)
        layout.addWidget(detail_box)

    # -- API -----------------------------------------------------------------
    def status_mask(self) -> int:
        """Return the status mask assembled from the checkboxes."""
        mask = 0
        for bit, box in self.mask_boxes.items():
            if box.isChecked():
                mask |= 1 << bit
        return mask or 0xFF

    def sub_function(self) -> int:
        """Return the selected sub-function."""
        return int(self.sub_function_box.currentData())

    def show_report(self, report: DTCReport) -> None:
        """Display the DTCs of *report* in the results table."""
        self.report = report
        rows: list[dict[str, Any]] = []
        colors = status_colors()
        for dtc in report:
            rows.append(
                {
                    "Code": dtc.display_code,
                    "Description": dtc.name,
                    "Status": f"0x{dtc.status.value:02X}",
                    "Confirmed": "yes" if dtc.status.confirmed else "",
                    "Pending": "yes" if dtc.status.pending else "",
                    "Severity": "" if dtc.severity is None else f"0x{dtc.severity:02X}",
                    "Occurrences": (
                        dtc.extended_records[0].occurrence_counter
                        if dtc.extended_records
                        else ""
                    ),
                    "_color": colors["confirmed"]
                    if dtc.status.confirmed
                    else colors["pending"]
                    if dtc.status.pending
                    else colors["clean"],
                    "_raw": dtc.code,
                }
            )
        self.results_table.set_rows(rows, color_key="_color")
        self.count_label.setText(
            f"{len(report)} DTC(s): {report.confirmed_count} confirmed, "
            f"{report.pending_count} pending"
        )

    def selected_dtc(self) -> int | None:
        """Return the raw code of the selected DTC."""
        rows = self.results_table.selected_rows()
        if not rows:
            return None
        raw = rows[0].get("_raw")
        return int(raw) if raw is not None else None

    def show_detail(self, dtc: DTC) -> None:
        """Show the decoded status bits of *dtc*."""
        bits = "\n".join(
            f"  [{'x' if dtc.status.bit(bit) else ' '}] {name}"
            for bit, name in DTC_STATUS_BITS.items()
        )
        snapshots = (
            f"\nSnapshots: {len(dtc.snapshots)}" if dtc.snapshots else ""
        )
        extended = (
            f"\nExtended records: {len(dtc.extended_records)}" if dtc.extended_records else ""
        )
        self.detail_label.setText(
            f"DTC {dtc.display_code} (0x{dtc.code:06X}) {dtc.name}\n"
            f"Status 0x{dtc.status.value:02X}\n{bits}{snapshots}{extended}"
        )

    def set_busy(self, busy: bool) -> None:
        """Show the spinner while a read is running."""
        self.read_button.set_loading(busy)

    def rows(self) -> list[dict[str, Any]]:
        """Return the displayed rows (used by the export)."""
        return self.results_table.rows()

    # -- events ----------------------------------------------------------------
    def _on_read(self) -> None:
        """Emit the read request."""
        self.read_requested.emit(self.sub_function(), self.status_mask())

    def _on_selection(self) -> None:
        """Update the detail box for the selected DTC."""
        if self.report is None:
            return
        code = self.selected_dtc()
        for dtc in self.report:
            if dtc.code == code:
                self.show_detail(dtc)
                return

    def _on_snapshot(self) -> None:
        """Request the snapshot of the selected DTC."""
        code = self.selected_dtc()
        if code is not None:
            self.snapshot_requested.emit(code)

    def _on_extended(self) -> None:
        """Request the extended data of the selected DTC."""
        code = self.selected_dtc()
        if code is not None:
            self.extended_requested.emit(code)


__all__ = ["ReadDTCView"]
