"""Virtual scrolling log viewer able to display hundreds of thousands of rows."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.core.models.log_entry_model import LogEntry, LogLevel
from src.logging_system.timestamped_logger import TimestampedLogger

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import DARK_PALETTE, ColorPalette, FontRole

_logger = logging.getLogger(__name__)

#: Columns displayed by the viewer.
COLUMNS: tuple[str, ...] = (
    "Timestamp",
    "Delta",
    "Dir",
    "Protocol",
    "ID",
    "Data",
    "Len",
    "Decoded",
    "Level",
)


class LogTableModel(QAbstractTableModel):
    """A table model backed by a plain list of :class:`LogEntry` objects.

    The model never copies the entries and only formats the rows Qt actually
    paints, which keeps scrolling smooth with 500 000 entries.
    """

    def __init__(self, palette: ColorPalette = DARK_PALETTE, parent: QWidget | None = None) -> None:
        """Create an empty model."""
        super().__init__(parent)
        self.entries: list[LogEntry] = []
        self.palette_colors = palette
        self.absolute_time = False

    # -- Qt model interface -------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt naming
        """Return the number of log entries."""
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 - Qt naming
        """Return the number of columns."""
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(  # noqa: N802 - Qt naming
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        """Return the column titles."""
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return COLUMNS[section] if 0 <= section < len(COLUMNS) else None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return the cell content, colour or tooltip."""
        if not index.isValid() or index.row() >= len(self.entries):
            return None
        entry = self.entries[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._cell(entry, index.column())
        if role == Qt.ItemDataRole.ForegroundRole:
            return QBrush(QColor(self._row_color(entry)))
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{entry.decoded_service} {entry.decoded_detail}".strip() or entry.message
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in (1, 6):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def _cell(self, entry: LogEntry, column: int) -> str:
        """Return the formatted text of one cell."""
        if column == 0:
            return entry.formatted_time(self.absolute_time)
        if column == 1:
            return TimestampedLogger.format_delta(entry.delta_us) if entry.delta_us else ""
        if column == 2:
            return entry.direction
        if column == 3:
            return entry.protocol
        if column == 4:
            return entry.can_id
        if column == 5:
            return entry.hex_data or entry.message
        if column == 6:
            return str(len(entry.data)) if entry.data else ""
        if column == 7:
            return f"{entry.decoded_service} {entry.decoded_detail}".strip()
        if column == 8:
            return entry.level.name
        return ""

    def _row_color(self, entry: LogEntry) -> str:
        """Return the foreground colour of a row."""
        if entry.level >= LogLevel.ERROR:
            return self.palette_colors.error
        if entry.level == LogLevel.WARNING:
            return self.palette_colors.warning
        if entry.direction == "TX":
            return self.palette_colors.tx
        if entry.direction == "RX":
            return self.palette_colors.rx
        return self.palette_colors.text_primary

    # -- content management ---------------------------------------------------
    def set_entries(self, entries: list[LogEntry]) -> None:
        """Replace the whole content."""
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def append(self, entries: list[LogEntry]) -> None:
        """Append several entries without resetting the model."""
        if not entries:
            return
        first = len(self.entries)
        self.beginInsertRows(QModelIndex(), first, first + len(entries) - 1)
        self.entries.extend(entries)
        self.endInsertRows()

    def clear(self) -> None:
        """Remove every entry."""
        self.beginResetModel()
        self.entries = []
        self.endResetModel()

    def entry_at(self, row: int) -> LogEntry | None:
        """Return the entry displayed in *row*."""
        return self.entries[row] if 0 <= row < len(self.entries) else None


class LogViewerWidget(QWidget):
    """The log table plus auto-scroll, batching and a context menu.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        palette: Colour palette used for the row colours.
        batch_interval_ms: How often queued entries are flushed into the model.
    """

    #: Emitted with the entry the user selected.
    entry_selected = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        palette: ColorPalette = DARK_PALETTE,
        batch_interval_ms: int = 100,
    ) -> None:
        """Build the table view and start the batching timer."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.auto_scroll = True
        self._pending: list[LogEntry] = []

        self.model = LogTableModel(palette, self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(self.scaler.px(22))
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        self._configure_columns()
        self._apply_font()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

        self._timer = QTimer(self)
        self._timer.setInterval(batch_interval_ms)
        self._timer.timeout.connect(self._flush)
        self._timer.start()

    # -- content -------------------------------------------------------------
    def add_entry(self, entry: LogEntry) -> None:
        """Queue one entry for display (thread safe enough for Qt signals)."""
        self._pending.append(entry)

    def set_entries(self, entries: list[LogEntry]) -> None:
        """Replace the displayed entries."""
        self._pending.clear()
        self.model.set_entries(list(entries))
        if self.auto_scroll:
            self.table.scrollToBottom()

    def clear(self) -> None:
        """Remove every displayed entry."""
        self._pending.clear()
        self.model.clear()

    def selected_entries(self) -> list[LogEntry]:
        """Return the entries currently selected."""
        rows = {index.row() for index in self.table.selectionModel().selectedRows()}
        return [e for row in sorted(rows) if (e := self.model.entry_at(row)) is not None]

    def entry_count(self) -> int:
        """Return the number of displayed entries."""
        return self.model.rowCount()

    # -- behaviour --------------------------------------------------------------
    def set_auto_scroll(self, enabled: bool) -> None:
        """Enable or disable following the newest entry."""
        self.auto_scroll = enabled
        if enabled:
            self.table.scrollToBottom()

    def set_absolute_time(self, enabled: bool) -> None:
        """Switch between absolute and time-of-day timestamps."""
        self.model.absolute_time = enabled
        self.model.layoutChanged.emit()

    def scroll_to_row(self, row: int) -> None:
        """Scroll the table so *row* becomes visible."""
        index = self.model.index(max(0, min(row, self.model.rowCount() - 1)), 0)
        self.table.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.table.selectRow(index.row())

    def _flush(self) -> None:
        """Move the queued entries into the model."""
        if not self._pending:
            return
        batch, self._pending = self._pending, []
        self.model.append(batch)
        if self.auto_scroll:
            self.table.scrollToBottom()

    # -- helpers ------------------------------------------------------------------
    def _configure_columns(self) -> None:
        """Set sensible default widths and stretch the data column.

        Each width is also floored at the width of its own header label, so a
        narrow column never renders a clipped title such as ``ROTOCOL``.
        """
        from PySide6.QtGui import QFontMetrics

        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(self.scaler.px(48))
        header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        metrics = QFontMetrics(header.font())
        padding = self.scaler.px(26)
        widths = {0: 130, 1: 90, 2: 52, 3: 88, 4: 84, 5: 320, 6: 56, 7: 220, 8: 76}
        for column, width in widths.items():
            title = COLUMNS[column] if column < len(COLUMNS) else ""
            needed = metrics.horizontalAdvance(str(title)) + padding
            self.table.setColumnWidth(column, max(self.scaler.px(width), needed))
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionsMovable(True)
        header.setHighlightSections(False)
        header.setStretchLastSection(False)

    def _apply_font(self) -> None:
        """Apply the monospace font to the table."""
        from ..font_manager import FontManager

        font = FontManager(self.scaler).qfont(FontRole.MONOSPACE)
        if font is not None:
            self.table.setFont(font)

    def _on_selection(self, *_: Any) -> None:
        """Emit :attr:`entry_selected` for the first selected row."""
        entries = self.selected_entries()
        if entries:
            self.entry_selected.emit(entries[0])

    def _show_context_menu(self, position: Any) -> None:
        """Show the copy/filter context menu."""
        entries = self.selected_entries()
        if not entries:
            return
        entry = entries[0]
        menu = QMenu(self)

        def copy(text: str) -> None:
            QGuiApplication.clipboard().setText(text)

        from src.logging_system.log_formatter import LogFormatter

        formatter = LogFormatter()
        actions = {
            "Copy row": lambda: copy(formatter.to_text(entry)),
            "Copy hex data": lambda: copy(entry.hex_data),
            "Copy all selected": lambda: copy(
                "\n".join(formatter.to_text(e) for e in entries)
            ),
            "Set as time reference": lambda: self._set_reference(entry),
        }
        for label, handler in actions.items():
            action = QAction(label, self)
            action.triggered.connect(handler)
            menu.addAction(action)
        menu.exec(self.table.mapToGlobal(position))

    def _set_reference(self, entry: LogEntry) -> None:
        """Recompute the delta column relative to *entry*."""
        base = entry.timestamp_us
        for item in self.model.entries:
            item.delta_us = item.timestamp_us - base
        self.model.layoutChanged.emit()


__all__ = ["LogViewerWidget", "LogTableModel", "COLUMNS"]
