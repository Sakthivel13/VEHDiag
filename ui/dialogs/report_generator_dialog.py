"""Diagnostic report generator dialog.

Assembles a single report from the data collected during a session: the ECU
identification, the DTC list, the DID readings, the test results and the
communication log. The report can be rendered as HTML, Markdown, plain text or
CSV and written to disk.

Example:
    >>> from ui.dialogs.report_generator_dialog import (
    ...     SECTIONS, ReportData, render_markdown, render_text)
    >>> [key for key, _ in SECTIONS][0]
    'identification'
    >>> data = ReportData(title="Session report", ecu_name="ECM")
    >>> "# Session report" in render_markdown(data)
    True
    >>> "ECM" in render_text(data)
    True
"""
from __future__ import annotations

import html
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.models.dtc_model import DTC
from src.core.models.did_model import DIDValue
from src.core.models.log_entry_model import LogEntry
from src.core.models.test_sequence_model import TestResult

from ..dpi_scaler import DPIScaler
from ..widgets.scalable_button import ScalableButton
from ..styles.layout_helpers import tune_form

__all__ = [
    "FORMATS",
    "ReportData",
    "ReportGeneratorDialog",
    "SECTIONS",
    "render_html",
    "render_markdown",
    "render_text",
]

#: Sections offered as checkboxes, as ``(key, label)`` pairs.
SECTIONS: tuple[tuple[str, str], ...] = (
    ("identification", "ECU identification"),
    ("dtcs", "Diagnostic trouble codes"),
    ("dids", "Data identifier readings"),
    ("tests", "Test results"),
    ("log", "Communication log"),
)

#: Output formats offered by the drop-down.
FORMATS: tuple[str, ...] = ("HTML", "Markdown", "Text", "CSV")


@dataclass(slots=True)
class ReportData:
    """Everything a report can contain.

    Attributes:
        title: Report title.
        ecu_name: Name of the diagnosed ECU.
        operator: Name of the person who ran the session.
        identification: ``{field: value}`` identification data.
        dtcs: The trouble codes read during the session.
        dids: The identifier readings.
        tests: The developer mode test results.
        log: The communication log entries.
        generated_at: Unix timestamp of the report.
    """

    title: str = "Diagnostic report"
    ecu_name: str = ""
    operator: str = ""
    identification: dict[str, str] = field(default_factory=dict)
    dtcs: list[DTC] = field(default_factory=list)
    dids: list[DIDValue] = field(default_factory=list)
    tests: list[TestResult] = field(default_factory=list)
    log: list[LogEntry] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def timestamp(self) -> str:
        """Return the generation time as ``YYYY-MM-DD HH:MM:SS``.

        Example:
            >>> len(ReportData().timestamp())
            19
        """
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.generated_at))

    def summary(self) -> str:
        """Return the one line summary printed under the title.

        Example:
            >>> ReportData().summary()
            '0 DTC(s), 0 DID reading(s), 0 test result(s), 0 log entrie(s)'
        """
        return (
            f"{len(self.dtcs)} DTC(s), {len(self.dids)} DID reading(s), "
            f"{len(self.tests)} test result(s), {len(self.log)} log entrie(s)"
        )


def _selected(sections: Iterable[str] | None) -> set[str]:
    """Return the requested section keys, defaulting to every section."""
    return set(sections) if sections is not None else {key for key, _ in SECTIONS}


def render_text(data: ReportData, sections: Iterable[str] | None = None) -> str:
    """Render *data* as a plain text report.

    Example:
        >>> "Diagnostic report" in render_text(ReportData())
        True
    """
    keys = _selected(sections)
    lines = [data.title, "=" * len(data.title), ""]
    lines.append(f"Generated: {data.timestamp()}")
    if data.ecu_name:
        lines.append(f"ECU: {data.ecu_name}")
    if data.operator:
        lines.append(f"Operator: {data.operator}")
    lines += ["", data.summary(), ""]
    if "identification" in keys and data.identification:
        lines.append("ECU identification")
        lines += [f"  {name}: {value}" for name, value in data.identification.items() if value]
        lines.append("")
    if "dtcs" in keys and data.dtcs:
        lines.append("Diagnostic trouble codes")
        lines += [
            f"  {dtc.display_code}  {dtc.name or 'unknown'}  status 0x{dtc.status.value:02X}"
            for dtc in data.dtcs
        ]
        lines.append("")
    if "dids" in keys and data.dids:
        lines.append("Data identifier readings")
        lines += [
            f"  {value.did:04X} {value.name}: {value.ascii_value} ({value.hex_value})"
            for value in data.dids
        ]
        lines.append("")
    if "tests" in keys and data.tests:
        lines.append("Test results")
        lines += [
            f"  {result.step.order:>3} {result.step.name}: {result.status.value} "
            f"({result.duration_ms:.1f} ms)"
            for result in data.tests
        ]
        lines.append("")
    if "log" in keys and data.log:
        lines.append(f"Communication log ({len(data.log)} entries)")
        lines += [f"  {entry}" for entry in data.log[:200]]
        lines.append("")
    return "\n".join(lines)


def render_markdown(data: ReportData, sections: Iterable[str] | None = None) -> str:
    """Render *data* as a Markdown report.

    Example:
        >>> render_markdown(ReportData(title="T")).splitlines()[0]
        '# T'
    """
    keys = _selected(sections)
    lines = [f"# {data.title}", "", f"*Generated {data.timestamp()}*", ""]
    if data.ecu_name:
        lines.append(f"- **ECU**: {data.ecu_name}")
    if data.operator:
        lines.append(f"- **Operator**: {data.operator}")
    lines += [f"- **Summary**: {data.summary()}", ""]
    if "identification" in keys and data.identification:
        lines += ["## ECU identification", "", "| Field | Value |", "| --- | --- |"]
        lines += [
            f"| {name} | {value} |" for name, value in data.identification.items() if value
        ]
        lines.append("")
    if "dtcs" in keys and data.dtcs:
        lines += [
            "## Diagnostic trouble codes",
            "",
            "| Code | Description | Status | Confirmed |",
            "| --- | --- | --- | --- |",
        ]
        lines += [
            f"| {dtc.display_code} | {dtc.name or 'unknown'} | "
            f"0x{dtc.status.value:02X} | {'yes' if dtc.status.confirmed else 'no'} |"
            for dtc in data.dtcs
        ]
        lines.append("")
    if "dids" in keys and data.dids:
        lines += ["## Data identifiers", "", "| DID | Name | Value |", "| --- | --- | --- |"]
        lines += [
            f"| {value.did:04X} | {value.name} | {value.ascii_value} |" for value in data.dids
        ]
        lines.append("")
    if "tests" in keys and data.tests:
        lines += ["## Test results", "", "| # | Step | Status | Duration |", "| --- | --- | --- | --- |"]
        lines += [
            f"| {r.step.order} | {r.step.name} | {r.status.value} | {r.duration_ms:.1f} ms |"
            for r in data.tests
        ]
        lines.append("")
    return "\n".join(lines)


def render_html(data: ReportData, sections: Iterable[str] | None = None) -> str:
    """Render *data* as a standalone HTML document.

    Example:
        >>> render_html(ReportData()).startswith("<!DOCTYPE html>")
        True
    """
    keys = _selected(sections)
    escape = html.escape
    parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        f"<title>{escape(data.title)}</title>",
        "<style>",
        "body{font-family:sans-serif;background:#1E1E2E;color:#F8FAFC;margin:2rem}",
        "h1,h2{color:#7C3AED}table{border-collapse:collapse;width:100%;margin-bottom:1.5rem}",
        "th,td{border:1px solid #374151;padding:.4rem .6rem;text-align:left}",
        "th{background:#282840}.muted{color:#94A3B8}",
        "</style></head><body>",
        f"<h1>{escape(data.title)}</h1>",
        f"<p class='muted'>Generated {escape(data.timestamp())} &mdash; {escape(data.summary())}</p>",
    ]
    if data.ecu_name or data.operator:
        parts.append(
            f"<p>ECU: <b>{escape(data.ecu_name)}</b> &nbsp; "
            f"Operator: <b>{escape(data.operator)}</b></p>"
        )
    if "identification" in keys and data.identification:
        parts.append("<h2>ECU identification</h2><table><tr><th>Field</th><th>Value</th></tr>")
        parts += [
            f"<tr><td>{escape(name)}</td><td>{escape(value)}</td></tr>"
            for name, value in data.identification.items()
            if value
        ]
        parts.append("</table>")
    if "dtcs" in keys and data.dtcs:
        parts.append(
            "<h2>Diagnostic trouble codes</h2><table>"
            "<tr><th>Code</th><th>Description</th><th>Status</th></tr>"
        )
        parts += [
            f"<tr><td>{escape(dtc.display_code)}</td>"
            f"<td>{escape(dtc.name or 'unknown')}</td>"
            f"<td>0x{dtc.status.value:02X}</td></tr>"
            for dtc in data.dtcs
        ]
        parts.append("</table>")
    if "dids" in keys and data.dids:
        parts.append("<h2>Data identifiers</h2><table><tr><th>DID</th><th>Name</th><th>Value</th></tr>")
        parts += [
            f"<tr><td>{value.did:04X}</td><td>{escape(value.name)}</td>"
            f"<td>{escape(value.ascii_value)}</td></tr>"
            for value in data.dids
        ]
        parts.append("</table>")
    if "tests" in keys and data.tests:
        parts.append("<h2>Test results</h2><table><tr><th>#</th><th>Step</th><th>Status</th></tr>")
        parts += [
            f"<tr><td>{r.step.order}</td><td>{escape(r.step.name)}</td>"
            f"<td>{escape(r.status.value)}</td></tr>"
            for r in data.tests
        ]
        parts.append("</table>")
    parts.append("</body></html>")
    return "\n".join(parts)


class ReportGeneratorDialog(QDialog):
    """Builds and exports a diagnostic session report.

    Args:
        data: The collected session data.
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        data: The report source data.
        preview: The rendered preview area.
    """

    #: Emitted with the written path after a successful export.
    report_saved = Signal(str)

    def __init__(
        self,
        data: ReportData | None = None,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
    ) -> None:
        """Build the option form, the preview and the export buttons."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.data = data or ReportData()

        self.setWindowTitle("Generate a diagnostic report")
        self.setModal(True)
        self.setMinimumSize(self.scaler.px(760), self.scaler.px(600))

        self.title_field = QLineEdit(self.data.title, self)
        self.title_field.textChanged.connect(self.refresh)
        self.operator_field = QLineEdit(self.data.operator, self)
        self.operator_field.textChanged.connect(self.refresh)
        self.format_box = QComboBox(self)
        self.format_box.addItems(FORMATS)
        self.format_box.currentIndexChanged.connect(self.refresh)

        self.section_boxes: dict[str, QCheckBox] = {}
        options = QGroupBox("Sections", self)
        options_layout = QVBoxLayout(options)
        for key, label in SECTIONS:
            box = QCheckBox(label, self)
            box.setChecked(True)
            box.toggled.connect(self.refresh)
            self.section_boxes[key] = box
            options_layout.addWidget(box)

        form = QFormLayout()

        tune_form(form, self.scaler)
        form.setSpacing(self.scaler.spacing(6))
        form.addRow("Title:", self.title_field)
        form.addRow("Operator:", self.operator_field)
        form.addRow("Format:", self.format_box)

        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)

        self.status_label = QLabel("", self)
        self.status_label.setProperty("role", "secondary")

        self.save_button = ScalableButton("Save as...", "save", self, self.scaler, accent=True)
        self.save_button.clicked.connect(self.save_dialog)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.buttons.rejected.connect(self.reject)
        self.buttons.addButton(self.save_button, QDialogButtonBox.ButtonRole.ActionRole)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.scaler.spacing(8))
        layout.addLayout(form)
        layout.addWidget(options)
        layout.addWidget(self.preview, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.buttons)

        self.refresh()

    # -- API -----------------------------------------------------------------
    def set_data(self, data: ReportData) -> None:
        """Replace the source data and refresh the preview."""
        self.data = data
        self.title_field.setText(data.title)
        self.operator_field.setText(data.operator)
        self.refresh()

    def sections(self) -> list[str]:
        """Return the section keys the operator selected."""
        return [key for key, box in self.section_boxes.items() if box.isChecked()]

    def render(self) -> str:
        """Render the report in the selected format."""
        self.data.title = self.title_field.text() or "Diagnostic report"
        self.data.operator = self.operator_field.text()
        sections = self.sections()
        chosen = self.format_box.currentText()
        if chosen == "HTML":
            return render_html(self.data, sections)
        if chosen == "Markdown":
            return render_markdown(self.data, sections)
        if chosen == "CSV":
            return self._render_csv(sections)
        return render_text(self.data, sections)

    def refresh(self) -> None:
        """Re-render the preview and update the status label."""
        text = self.render()
        self.preview.setPlainText(text)
        self.status_label.setText(
            f"{len(text)} characters, {len(self.sections())} section(s) selected"
        )

    def save(self, path: str | Path) -> Path:
        """Write the rendered report to *path*."""
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.render(), encoding="utf-8")
        self.report_saved.emit(str(target))
        self.status_label.setText(f"report written to {target}")
        return target

    def save_dialog(self) -> Path | None:
        """Ask where to save the report and write it."""
        suffix = {"HTML": ".html", "Markdown": ".md", "Text": ".txt", "CSV": ".csv"}[
            self.format_box.currentText()
        ]
        suggestion = str(Path.home() / f"diagnostic_report{suffix}")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the report", suggestion, f"Report (*{suffix});;All files (*)"
        )
        return self.save(path) if path else None

    # -- internals ------------------------------------------------------------
    def _render_csv(self, sections: Sequence[str]) -> str:
        """Render a flat CSV covering the selected sections."""
        rows = ["section,key,value"]
        if "identification" in sections:
            rows += [
                f"identification,{name},{value}"
                for name, value in self.data.identification.items()
                if value
            ]
        if "dtcs" in sections:
            rows += [
                f"dtc,{dtc.display_code},{dtc.name or 'unknown'} (0x{dtc.status.value:02X})"
                for dtc in self.data.dtcs
            ]
        if "dids" in sections:
            rows += [f"did,{value.did:04X},{value.ascii_value}" for value in self.data.dids]
        if "tests" in sections:
            rows += [
                f"test,{result.step.name},{result.status.value}" for result in self.data.tests
            ]
        return "\n".join(rows)
