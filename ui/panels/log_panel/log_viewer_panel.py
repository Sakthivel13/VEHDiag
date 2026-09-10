"""Main log viewer panel with toolbar, filters and detail view."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.core.models.log_entry_model import LogEntry, LogLevel
from src.logging_system.log_filter import LogFilter
from src.logging_system.log_formatter import LogFormatter

from ...dpi_scaler import DPIScaler
from ...widgets.log_viewer_widget import LogViewerWidget
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.search_filter_widget import SearchFilterWidget


class LogViewerPanel(ResponsiveWidget):
    """The bottom log panel of the main window.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted when the operator pauses or resumes logging.
    pause_toggled = Signal(bool)
    #: Emitted when the operator clears the log.
    clear_requested = Signal()
    #: Emitted with ``(path, format)`` when the operator exports the log.
    export_requested = Signal(str, str)
    #: Emitted with the active filter whenever it changes.
    filter_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the toolbar, the table and the detail view."""
        super().__init__(parent, scaler)
        self.formatter = LogFormatter()
        self._paused = False

        self.pause_button = ScalableButton("Pause", "pause", self, self.scaler)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.clear_button = ScalableButton("Clear", "clear", self, self.scaler)
        self.clear_button.clicked.connect(self._on_clear)
        self.export_button = ScalableButton("Export", "export", self, self.scaler)
        self.export_button.clicked.connect(self.export)
        self.level_box = QComboBox(self)
        for level in (LogLevel.TRACE, LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING,
                      LogLevel.ERROR):
            self.level_box.addItem(level.name, level.value)
        self.level_box.setCurrentIndex(2)
        self.level_box.currentIndexChanged.connect(self._emit_filter)
        self.search = SearchFilterWidget(self, self.scaler, "Search the log...")
        self.search.search_changed.connect(lambda _t: self._emit_filter())
        self.search.filter_selected.connect(lambda _f: self._emit_filter())
        self.autoscroll_box = QCheckBox("Auto-scroll", self)
        self.autoscroll_box.setChecked(True)
        self.absolute_box = QCheckBox("Absolute time", self)
        self.count_label = QLabel("0 entries", self)
        self.count_label.setProperty("role", "secondary")

        self.viewer = LogViewerWidget(self, self.scaler)
        self.viewer.entry_selected.connect(self.show_detail)
        self.autoscroll_box.toggled.connect(self.viewer.set_auto_scroll)
        self.absolute_box.toggled.connect(self.viewer.set_absolute_time)

        self.detail_view = QPlainTextEdit(self)
        self.detail_view.setReadOnly(True)
        self.detail_view.setProperty("role", "mono")
        self.detail_view.setMaximumHeight(self.px(150))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(6))
        toolbar.addWidget(self.pause_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addWidget(self.export_button)
        toolbar.addWidget(QLabel("Level:", self))
        toolbar.addWidget(self.level_box)
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.autoscroll_box)
        toolbar.addWidget(self.absolute_box)
        toolbar.addWidget(self.count_label)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.addWidget(self.viewer)
        splitter.addWidget(self.detail_view)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(6), self.spacing(6), self.spacing(6), self.spacing(6))
        layout.setSpacing(self.spacing(6))
        layout.addLayout(toolbar)
        layout.addWidget(splitter, 1)

    # -- content -------------------------------------------------------------
    def add_entry(self, entry: LogEntry) -> None:
        """Queue an entry for display."""
        if self._paused:
            return
        self.viewer.add_entry(entry)
        self.count_label.setText(
            f"{self.viewer.entry_count() + len(self.viewer._pending)} entries"
        )

    def set_entries(self, entries: list[LogEntry]) -> None:
        """Replace the displayed entries."""
        self.viewer.set_entries(entries)
        self.count_label.setText(f"{len(entries)} entries")

    def clear(self) -> None:
        """Remove every displayed entry."""
        self.viewer.clear()
        self.detail_view.clear()
        self.count_label.setText("0 entries")

    def show_detail(self, entry: LogEntry) -> None:
        """Show the full detail of the selected entry."""
        from src.logging_system.timestamped_logger import TimestampedLogger

        lines = [
            f"Timestamp   : {entry.formatted_time(True)}",
            f"Level       : {entry.level.name}",
            f"Category    : {entry.category.value}",
            f"Direction   : {entry.direction or '-'}",
            f"Protocol    : {entry.protocol or '-'} | Channel: {entry.channel or '-'}",
            f"Identifier  : {entry.can_id or '-'}",
            f"Data ({len(entry.data):3d}) : {entry.hex_data or '-'}",
            f"Decoded     : {entry.decoded_service} {entry.decoded_detail}".rstrip(),
            f"Delta       : {TimestampedLogger.format_delta(entry.delta_us)}",
        ]
        if entry.message:
            lines.append(f"Message     : {entry.message}")
        self.detail_view.setPlainText("\n".join(lines))

    # -- filters ---------------------------------------------------------------
    def current_filter(self) -> LogFilter:
        """Return the filter described by the toolbar."""
        log_filter = self.search.build_filter()
        log_filter.min_level = LogLevel(int(self.level_box.currentData()))
        return log_filter

    def export(self) -> Path | None:
        """Ask for a destination and emit the export request."""
        path, selected = QFileDialog.getSaveFileName(
            self,
            "Export log",
            str(Path.home() / "diagnostic_log.csv"),
            "CSV (*.csv);;JSON (*.json);;HTML (*.html);;Text (*.txt);;Vector ASC (*.asc);;PCAP (*.pcap)",
        )
        if not path:
            return None
        suffix = Path(path).suffix.lower().lstrip(".")
        fmt = {"csv": "CSV", "json": "JSON", "html": "HTML", "txt": "TEXT",
               "asc": "ASC", "pcap": "PCAP"}.get(suffix, "CSV")
        self.export_requested.emit(path, fmt)
        return Path(path)

    # -- events ----------------------------------------------------------------
    def _toggle_pause(self) -> None:
        """Pause or resume the live display."""
        self._paused = not self._paused
        self.pause_button.setText("Resume" if self._paused else "Pause")
        self.pause_button.set_icon("play" if self._paused else "pause")
        self.pause_toggled.emit(self._paused)

    def _on_clear(self) -> None:
        """Clear the view and notify the controller."""
        self.clear()
        self.clear_requested.emit()

    def _emit_filter(self) -> None:
        """Emit the current filter."""
        self.filter_changed.emit(self.current_filter())


__all__ = ["LogViewerPanel"]
