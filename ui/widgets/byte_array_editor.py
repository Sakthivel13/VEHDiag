"""Hex-editor style byte array editor."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.utils.byte_utils import bytes_to_ascii

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole
from .responsive_widget import ResponsiveWidget


class ByteArrayEditor(ResponsiveWidget):
    """A grid of editable bytes with offset and ASCII columns.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        columns: Number of byte columns.
        read_only: Disable editing.
    """

    #: Emitted with the whole array whenever a byte changes.
    data_changed = Signal(bytes)
    #: Emitted with ``(start, length)`` when the selection changes.
    selection_changed = Signal(int, int)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        columns: int = 16,
        read_only: bool = False,
    ) -> None:
        """Build the table."""
        super().__init__(parent, scaler)
        self.columns = columns
        self._data = bytearray()
        self._updating = False

        self.table = QTableWidget(0, columns + 1, self)
        self.table.setHorizontalHeaderLabels(
            [f"{i:02X}" for i in range(columns)] + ["ASCII"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
            if read_only
            else QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.verticalHeader().setDefaultSectionSize(self.px(22))
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        header = self.table.horizontalHeader()
        for column in range(columns):
            self.table.setColumnWidth(column, self.px(34))
        header.setSectionResizeMode(columns, QHeaderView.ResizeMode.Stretch)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        self._apply_mono_font()

    # -- content -------------------------------------------------------------
    def set_data(self, data: bytes) -> None:
        """Replace the edited byte array."""
        self._updating = True
        self._data = bytearray(data)
        rows = max(1, (len(self._data) + self.columns - 1) // self.columns)
        self.table.setRowCount(rows)
        self.table.setVerticalHeaderLabels(
            [f"{row * self.columns:04X}" for row in range(rows)]
        )
        for row in range(rows):
            for column in range(self.columns):
                index = row * self.columns + column
                text = f"{self._data[index]:02X}" if index < len(self._data) else ""
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
            chunk = self._data[row * self.columns : (row + 1) * self.columns]
            ascii_item = QTableWidgetItem(bytes_to_ascii(bytes(chunk)))
            ascii_item.setFlags(ascii_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, self.columns, ascii_item)
        self._updating = False

    def data(self) -> bytes:
        """Return the current byte array."""
        return bytes(self._data)

    def insert_byte(self, index: int, value: int = 0x00) -> None:
        """Insert a byte at *index*."""
        self._data.insert(max(0, min(index, len(self._data))), value & 0xFF)
        self.set_data(bytes(self._data))
        self.data_changed.emit(self.data())

    def delete_byte(self, index: int) -> None:
        """Delete the byte at *index*."""
        if 0 <= index < len(self._data):
            del self._data[index]
            self.set_data(bytes(self._data))
            self.data_changed.emit(self.data())

    def selected_range(self) -> tuple[int, int]:
        """Return the ``(start, length)`` of the current selection."""
        items = self.table.selectedItems()
        indices = [
            item.row() * self.columns + item.column()
            for item in items
            if item.column() < self.columns
        ]
        if not indices:
            return 0, 0
        return min(indices), max(indices) - min(indices) + 1

    # -- events ----------------------------------------------------------------
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Validate an edited cell and update the array."""
        if self._updating or item.column() >= self.columns:
            return
        index = item.row() * self.columns + item.column()
        text = item.text().strip()
        if not text:
            return
        try:
            value = int(text, 16) & 0xFF
        except ValueError:
            self._updating = True
            item.setText(f"{self._data[index]:02X}" if index < len(self._data) else "")
            self._updating = False
            return
        while len(self._data) <= index:
            self._data.append(0)
        self._data[index] = value
        self._updating = True
        item.setText(f"{value:02X}")
        row_start = item.row() * self.columns
        chunk = self._data[row_start : row_start + self.columns]
        ascii_item = self.table.item(item.row(), self.columns)
        if ascii_item is not None:
            ascii_item.setText(bytes_to_ascii(bytes(chunk)))
        self._updating = False
        self.data_changed.emit(self.data())

    def _on_selection_changed(self) -> None:
        """Emit the selection range."""
        start, length = self.selected_range()
        self.selection_changed.emit(start, length)

    def _apply_mono_font(self) -> None:
        """Apply the monospace font to the table."""
        from ..font_manager import FontManager

        font = FontManager(self.scaler).qfont(FontRole.MONOSPACE)
        if font is not None:
            self.table.setFont(font)


__all__ = ["ByteArrayEditor"]
