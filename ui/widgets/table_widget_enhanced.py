"""Enhanced table widget with sorting, filtering and CSV export."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ..dpi_scaler import DPIScaler


class EnhancedTableWidget(QTableWidget):
    """A table with sorting, row colouring, filtering and export.

    Args:
        columns: Column titles.
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the data of the row the user double clicked.
    row_activated = Signal(dict)

    def __init__(
        self,
        columns: list[str] | None = None,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
    ) -> None:
        """Create the table with *columns*."""
        super().__init__(0, len(columns or []), parent)
        self.scaler = scaler or DPIScaler()
        self.columns = list(columns or [])
        self._rows: list[dict[str, Any]] = []

        if self.columns:
            self.setHorizontalHeaderLabels(self.columns)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(self.scaler.px(28))
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setCornerButtonEnabled(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        header = self.horizontalHeader()
        header.setSectionsMovable(True)
        header.setHighlightSections(False)
        header.setMinimumSectionSize(self.scaler.px(64))
        header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        # Interactive + a sensible initial width beats ResizeToContents, which
        # clips the header label whenever the cell text is shorter than it.
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.cellDoubleClicked.connect(self._on_double_click)
        if self.columns:
            self.auto_size_columns()

    # -- sizing ---------------------------------------------------------------
    def auto_size_columns(self, max_width: int = 420) -> None:
        """Size every column to fit its header *and* its content.

        ``resizeColumnsToContents`` alone measures the cells only, so a short
        column such as ``ID`` under a long header renders as ``ROTOCOL``. This
        takes the wider of the two and clamps the result so one verbose column
        cannot push the rest off screen.

        Args:
            max_width: Upper bound for a single column, in design pixels.
        """
        header = self.horizontalHeader()
        metrics = QFontMetrics(header.font())
        padding = self.scaler.px(28)
        limit = self.scaler.px(max_width)
        # The last section stretches to fill the viewport, which would defeat
        # the clamp below; restore it once the widths are settled.
        stretched = header.stretchLastSection()
        header.setStretchLastSection(False)
        self.resizeColumnsToContents()
        for index, title in enumerate(self.columns):
            content = self.columnWidth(index)
            needed = metrics.horizontalAdvance(str(title)) + padding
            width = max(content, needed, header.minimumSectionSize())
            self.setColumnWidth(index, min(width, limit))
        header.setStretchLastSection(stretched and len(self.columns) > 1)

    # -- content -------------------------------------------------------------
    def set_rows(self, rows: list[dict[str, Any]], color_key: str = "") -> None:
        """Replace the content with *rows* (a list of mappings)."""
        self._rows = list(rows)
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, column in enumerate(self.columns):
                value = row.get(column, row.get(column.lower().replace(" ", "_"), ""))
                item = QTableWidgetItem(str(value))
                if color_key and (colour := row.get(color_key)):
                    item.setForeground(QColor(str(colour)))
                self.setItem(row_index, column_index, item)
        self.setSortingEnabled(True)
        self.auto_size_columns()

    def append_row(self, row: dict[str, Any], color_key: str = "_c") -> int:
        """Append one row and return its index.

        Sorting is suspended while the row is inserted: with it enabled Qt
        re-sorts after the first cell is set, so the remaining cells land on
        the wrong row and the table appears blank.

        Args:
            row: Mapping of column title to value.
            color_key: Key holding the row foreground colour, if any.

        Returns:
            The index of the inserted row.
        """
        self._rows.append(row)
        sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)
        index = self.rowCount()
        self.insertRow(index)
        colour = row.get(color_key)
        for column_index, column in enumerate(self.columns):
            value = row.get(column, row.get(column.lower().replace(" ", "_"), ""))
            item = QTableWidgetItem(str(value))
            if colour:
                item.setForeground(QColor(str(colour)))
            self.setItem(index, column_index, item)
        self.setSortingEnabled(sorting)
        return index

    def rows(self) -> list[dict[str, Any]]:
        """Return the underlying row mappings."""
        return list(self._rows)

    def clear_rows(self) -> None:
        """Remove every row."""
        self._rows.clear()
        self.setRowCount(0)

    def selected_rows(self) -> list[dict[str, Any]]:
        """Return the mappings of the selected rows."""
        indices = sorted({index.row() for index in self.selectedIndexes()})
        return [self._rows[i] for i in indices if i < len(self._rows)]

    # -- filtering -------------------------------------------------------------
    def apply_filter(self, text: str) -> int:
        """Hide rows that do not contain *text*; return the visible count."""
        needle = text.strip().lower()
        visible = 0
        for row_index in range(self.rowCount()):
            match = not needle
            if needle:
                for column_index in range(self.columnCount()):
                    item = self.item(row_index, column_index)
                    if item is not None and needle in item.text().lower():
                        match = True
                        break
            self.setRowHidden(row_index, not match)
            visible += int(match)
        return visible

    # -- export ----------------------------------------------------------------
    def export_csv(self, path: str | Path) -> Path:
        """Write the visible rows to a CSV file."""
        target = Path(path).expanduser()
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.columns)
            for row_index in range(self.rowCount()):
                if self.isRowHidden(row_index):
                    continue
                writer.writerow(
                    [
                        (self.item(row_index, c).text() if self.item(row_index, c) else "")
                        for c in range(self.columnCount())
                    ]
                )
        return target

    def copy_selection(self) -> str:
        """Copy the selected rows to the clipboard as tab separated text."""
        indices = sorted({index.row() for index in self.selectedIndexes()})
        lines = []
        for row_index in indices:
            lines.append(
                "\t".join(
                    (self.item(row_index, c).text() if self.item(row_index, c) else "")
                    for c in range(self.columnCount())
                )
            )
        text = "\n".join(lines)
        QGuiApplication.clipboard().setText(text)
        return text

    # -- events ----------------------------------------------------------------
    def _on_double_click(self, row: int, _column: int) -> None:
        """Emit :attr:`row_activated` for the double clicked row."""
        if row < len(self._rows):
            self.row_activated.emit(self._rows[row])

    def _show_context_menu(self, position: Any) -> None:
        """Show the copy/export context menu."""
        menu = QMenu(self)
        copy = QAction("Copy selection", self)
        copy.triggered.connect(self.copy_selection)
        menu.addAction(copy)
        select_all = QAction("Select all", self)
        select_all.triggered.connect(self.selectAll)
        menu.addAction(select_all)
        menu.exec(self.mapToGlobal(position))


__all__ = ["EnhancedTableWidget"]
