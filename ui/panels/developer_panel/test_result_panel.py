"""Test result table with export actions."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.core.models.test_sequence_model import TestResult, TestStatus
from src.test_execution.test_result_collector import ResultSummary, TestResultCollector

from ...dpi_scaler import DPIScaler
from ...styles.style_constants import state_color
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.table_widget_enhanced import EnhancedTableWidget


class TestResultPanel(ResponsiveWidget):
    """Displays the executed steps and lets the operator export a report.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the result whose details the operator opened.
    detail_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the results table and the export buttons."""
        super().__init__(parent, scaler)
        self.collector = TestResultCollector()

        self.table = EnhancedTableWidget(
            ["#", "Service", "Name", "Status", "Duration", "Request", "Response", "Details"],
            self,
            self.scaler,
        )
        self.table.row_activated.connect(self._on_row_activated)
        self.summary_label = QLabel("No results yet", self)
        self.summary_label.setProperty("role", "secondary")

        self.export_html = ScalableButton("Export HTML", "export", self, self.scaler)
        self.export_html.clicked.connect(lambda: self.export("html"))
        self.export_csv = ScalableButton("Export CSV", "export", self, self.scaler)
        self.export_csv.clicked.connect(lambda: self.export("csv"))
        self.export_json = ScalableButton("Export JSON", "export", self, self.scaler)
        self.export_json.clicked.connect(lambda: self.export("json"))
        self.clear_button = ScalableButton("Clear results", "clear", self, self.scaler)
        self.clear_button.clicked.connect(self.clear)

        box = QGroupBox("Execution results", self)
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(self.spacing(6))
        box_layout.addWidget(self.table)
        buttons = QHBoxLayout()
        buttons.addWidget(self.summary_label, 1)
        buttons.addWidget(self.export_html)
        buttons.addWidget(self.export_csv)
        buttons.addWidget(self.export_json)
        buttons.addWidget(self.clear_button)
        box_layout.addLayout(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(box)

    # -- content -------------------------------------------------------------
    def add_result(self, result: TestResult) -> None:
        """Append one result to the table."""
        self.collector.add(result)
        row = result.as_row()
        self.table.append_row(
            {
                "#": row["order"],
                "Service": row["service"],
                "Name": row["name"],
                "Status": row["status"],
                "Duration": f"{row['duration_ms']} ms",
                "Request": row["request"],
                "Response": row["response"],
                "Details": row["details"],
            }
        )
        self._colorise_last_row(result.status)
        self.update_summary()

    def set_results(self, results: list[TestResult]) -> None:
        """Replace the whole table content."""
        self.collector.clear()
        self.table.clear_rows()
        for result in results:
            self.add_result(result)

    def clear(self) -> None:
        """Remove every result."""
        self.collector.clear()
        self.table.clear_rows()
        self.summary_label.setText("No results yet")

    def update_summary(self, summary: ResultSummary | None = None) -> None:
        """Refresh the summary bar."""
        self.summary_label.setText((summary or self.collector.summary()).as_text())

    def summary(self) -> ResultSummary:
        """Return the aggregated summary."""
        return self.collector.summary()

    # -- export ----------------------------------------------------------------
    def export(self, kind: str) -> Path | None:
        """Ask for a destination and write the report in *kind* format."""
        filters = {
            "html": ("HTML report (*.html)", ".html"),
            "csv": ("CSV file (*.csv)", ".csv"),
            "json": ("JSON file (*.json)", ".json"),
        }
        caption, suffix = filters.get(kind, filters["html"])
        path, _ = QFileDialog.getSaveFileName(
            self, "Export test report", str(Path.home() / f"test_report{suffix}"), caption
        )
        if not path:
            return None
        target = Path(path)
        if kind == "csv":
            return self.collector.to_csv(target)
        if kind == "json":
            return self.collector.to_json(target)
        return self.collector.to_html(target)

    # -- helpers ---------------------------------------------------------------
    def _colorise_last_row(self, status: TestStatus) -> None:
        """Colour the status cell of the last row."""
        from PySide6.QtGui import QColor

        row = self.table.rowCount() - 1
        item = self.table.item(row, 3)
        if item is None:
            return
        mapping = {
            TestStatus.PASS: "pass",
            TestStatus.FAIL: "fail",
            TestStatus.ERROR: "error",
            TestStatus.SKIPPED: "skipped",
            TestStatus.CANCELLED: "cancelled",
        }
        item.setForeground(QColor(state_color(mapping.get(status, "idle"))))

    def _on_row_activated(self, row: dict[str, Any]) -> None:
        """Emit the detail request for a double clicked row."""
        self.detail_requested.emit(row)


__all__ = ["TestResultPanel"]
