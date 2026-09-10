"""Export dialog for the communication log.

Wraps :class:`~src.logging_system.log_exporter.LogExporter` with a small dialog
that lets the operator pick the format, the scope (everything or only the
filtered entries), the columns and the destination file. Long exports report
their progress and can be cancelled.

Example:
    >>> from ui.panels.log_panel.log_export_dialog import (
    ...     FORMAT_LABELS, default_filename, qt_name_filter)
    >>> FORMAT_LABELS["CSV"]
    'Comma separated values (*.csv)'
    >>> default_filename("CSV", "session42").endswith(".csv")
    True
    >>> default_filename("JSON").startswith("vdp_log_")
    True
    >>> "*.asc" in qt_name_filter()
    True
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.core.models.log_entry_model import LogEntry
from src.logging_system.log_exporter import ExportFormat, ExportOptions, LogExporter
from src.logging_system.log_formatter import LogFormatter

from ...dpi_scaler import DPIScaler
from ...styles.layout_helpers import tune_form

__all__ = [
    "FORMAT_LABELS",
    "LogExportDialog",
    "default_filename",
    "qt_name_filter",
]

#: File dialog label of each export format.
FORMAT_LABELS: dict[str, str] = {
    "CSV": "Comma separated values (*.csv)",
    "JSON": "JSON document (*.json)",
    "XML": "XML document (*.xml)",
    "TEXT": "Plain text (*.txt)",
    "HTML": "HTML report (*.html)",
    "ASC": "Vector ASCII trace (*.asc)",
    "BLF": "Vector binary log (*.blf)",
    "PCAP": "Packet capture (*.pcap)",
}


def default_filename(export_format: str, session: str = "") -> str:
    """Return the suggested file name for *export_format*.

    Args:
        export_format: The name of an :class:`ExportFormat` member.
        session: Optional session identifier included in the name.

    Returns:
        A file name with the conventional suffix of the format.

    Example:
        >>> default_filename("HTML", "s1").startswith("vdp_log_s1_")
        True
    """
    suffix = ExportFormat(export_format).suffix
    stamp = time.strftime("%Y%m%d_%H%M%S")
    middle = f"{session}_" if session else ""
    return f"vdp_log_{middle}{stamp}{suffix}"


def qt_name_filter() -> str:
    """Return the Qt file dialog filter covering every format.

    Example:
        >>> qt_name_filter().count(";;") == len(FORMAT_LABELS) - 1
        True
    """
    return ";;".join(FORMAT_LABELS[name] for name in FORMAT_LABELS)


class LogExportDialog(QDialog):
    """Asks for the export format, the scope and the destination file.

    Args:
        entries: Every entry currently held by the log panel.
        filtered: The entries left by the active filter.
        parent: Parent widget.
        scaler: Shared DPI scaler.
        exporter: Exporter used to write the file.

    Attributes:
        written_path: The path that was written, once the export succeeded.
    """

    #: Emitted with the written path after a successful export.
    export_finished = Signal(str)
    #: Emitted with ``(done, total)`` while the export runs.
    progress_changed = Signal(int, int)

    def __init__(
        self,
        entries: Sequence[LogEntry] | None = None,
        filtered: Sequence[LogEntry] | None = None,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        exporter: LogExporter | None = None,
    ) -> None:
        """Build the option form and the progress row."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.entries = list(entries or [])
        self.filtered = list(filtered if filtered is not None else self.entries)
        self.exporter = exporter or LogExporter(LogFormatter())
        self.written_path: Path | None = None

        self.setWindowTitle("Export the log")
        self.setModal(True)
        self.setMinimumWidth(self.scaler.px(480))

        self.format_box = QComboBox(self)
        for name in FORMAT_LABELS:
            self.format_box.addItem(name, name)
        self.format_box.currentIndexChanged.connect(self._refresh_summary)

        self.scope_box = QComboBox(self)
        self.scope_box.addItem(f"Filtered entries ({len(self.filtered)})", "filtered")
        self.scope_box.addItem(f"All entries ({len(self.entries)})", "all")
        self.scope_box.currentIndexChanged.connect(self._refresh_summary)

        self.pretty_box = QCheckBox("Pretty print JSON and XML", self)
        self.pretty_box.setChecked(True)
        self.open_box = QCheckBox("Reveal the file when finished", self)

        self.summary_label = QLabel("", self)
        self.summary_label.setProperty("role", "secondary")
        self.summary_label.setWordWrap(True)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)

        form = QFormLayout()

        tune_form(form, self.scaler)
        form.setSpacing(self.scaler.spacing(8))
        form.addRow("Format:", self.format_box)
        form.addRow("Scope:", self.scope_box)
        form.addRow("", self.pretty_box)
        form.addRow("", self.open_box)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.accepted.connect(self.run_export)
        self.buttons.rejected.connect(self._on_reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.scaler.spacing(8))
        layout.addLayout(form)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.buttons)

        self._refresh_summary()

    # -- API -----------------------------------------------------------------
    def selected_format(self) -> ExportFormat:
        """Return the export format chosen by the operator."""
        return ExportFormat(str(self.format_box.currentData()))

    def selected_entries(self) -> list[LogEntry]:
        """Return the entries covered by the selected scope."""
        return self.entries if self.scope_box.currentData() == "all" else self.filtered

    def options(self) -> ExportOptions:
        """Return the :class:`ExportOptions` built from the form."""
        return ExportOptions(
            pretty=self.pretty_box.isChecked(),
            title="Diagnostic log",
            include_filtered_only=self.scope_box.currentData() == "filtered",
        )

    def run_export(self, path: str | Path | None = None) -> Path | None:
        """Ask for a destination if needed and write the file.

        Args:
            path: Destination path; when omitted a file dialog is shown.

        Returns:
            The written path, or ``None`` when the operator cancelled.
        """
        export_format = self.selected_format()
        target = Path(path).expanduser() if path else self._ask_path(export_format)
        if target is None:
            return None
        entries = self.selected_entries()
        self.progress.setVisible(True)
        self.progress.setRange(0, max(1, len(entries)))
        try:
            written = self.exporter.export(
                entries, target, export_format, self.options(), self._on_progress
            )
        except (OSError, ValueError) as exc:  # pragma: no cover - IO paths
            self.summary_label.setText(f"export failed: {exc}")
            self.summary_label.setProperty("state", "error")
            self.progress.setVisible(False)
            return None
        self.written_path = written
        self.summary_label.setText(f"exported {len(entries)} entries to {written}")
        self.export_finished.emit(str(written))
        self.accept()
        return written

    def cancel_export(self) -> None:
        """Ask the exporter to stop as soon as possible."""
        self.exporter.cancel()

    # -- internals ------------------------------------------------------------
    def _ask_path(self, export_format: ExportFormat) -> Path | None:
        """Show the save dialog pre-filled for *export_format*."""
        suggestion = str(Path.home() / default_filename(export_format.value))
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export the log",
            suggestion,
            FORMAT_LABELS.get(export_format.value, "All files (*)"),
        )
        return Path(path) if path else None

    def _on_progress(self, done: int, total: int) -> None:
        """Update the progress bar and re-emit the progress."""
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)
        self.progress_changed.emit(done, total)

    def _on_reject(self) -> None:
        """Cancel a running export, then close the dialog."""
        self.cancel_export()
        self.reject()

    def _refresh_summary(self) -> None:
        """Refresh the label describing what will be written."""
        entries = self.selected_entries()
        export_format = self.selected_format()
        self.summary_label.setText(
            f"{len(entries)} entries will be written as {export_format.value} "
            f"({export_format.suffix})"
        )
        self.summary_label.setProperty("state", "")
