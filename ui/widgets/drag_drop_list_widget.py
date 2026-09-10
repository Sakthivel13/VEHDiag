"""Drag and drop reorderable list."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QAction, QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QMenu, QWidget

from ..dpi_scaler import DPIScaler


class DragDropListWidget(QListWidget):
    """A list whose rows can be reordered by dragging.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        allow_remove: Show a *Remove* entry in the context menu.

    Example:
        >>> # widget = DragDropListWidget()
        >>> # widget.add_items(["Session", "Read DID"])
        >>> None
    """

    #: Emitted with ``(from_index, to_index)`` after a drag reorder.
    item_moved = Signal(int, int)
    #: Emitted with the new order of the item texts.
    order_changed = Signal(list)
    #: Emitted with the index of a removed row.
    item_removed = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        allow_remove: bool = True,
    ) -> None:
        """Configure the list for internal drag and drop."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.allow_remove = allow_remove
        self._drag_source = -1

        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setSpacing(self.scaler.px(2))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # -- content -------------------------------------------------------------
    def add_items(self, texts: list[str]) -> None:
        """Append several rows at once."""
        for text in texts:
            self.add_item(text)

    def add_item(self, text: str, data: Any = None) -> QListWidgetItem:
        """Append one row and return the created item."""
        item = QListWidgetItem(text, self)
        if data is not None:
            item.setData(Qt.ItemDataRole.UserRole, data)
        return item

    def order(self) -> list[str]:
        """Return the current row texts in display order."""
        return [self.item(index).text() for index in range(self.count())]

    def data_order(self) -> list[Any]:
        """Return the user data of every row in display order."""
        return [self.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.count())]

    def move_item(self, from_index: int, to_index: int) -> None:
        """Move a row programmatically."""
        if not 0 <= from_index < self.count():
            return
        to_index = max(0, min(to_index, self.count() - 1))
        item = self.takeItem(from_index)
        self.insertItem(to_index, item)
        self.setCurrentRow(to_index)
        self.item_moved.emit(from_index, to_index)
        self.order_changed.emit(self.order())

    def remove_current(self) -> None:
        """Remove the selected row."""
        index = self.currentRow()
        if index < 0:
            return
        self.takeItem(index)
        self.item_removed.emit(index)
        self.order_changed.emit(self.order())

    # -- drag and drop ----------------------------------------------------------
    def startDrag(self, actions: Any) -> None:  # noqa: N802 - Qt naming
        """Remember the source row before the drag starts."""
        self._drag_source = self.currentRow()
        super().startDrag(actions)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt naming
        """Emit the reorder signals after an internal move."""
        super().dropEvent(event)
        target = self.currentRow()
        if self._drag_source >= 0 and target != self._drag_source:
            self.item_moved.emit(self._drag_source, target)
        self._drag_source = -1
        self.order_changed.emit(self.order())

    # -- context menu ------------------------------------------------------------
    def _show_context_menu(self, position: Any) -> None:
        """Show the reorder context menu."""
        if self.currentRow() < 0:
            return
        menu = QMenu(self)
        up = QAction("Move up", self)
        up.triggered.connect(lambda: self.move_item(self.currentRow(), self.currentRow() - 1))
        down = QAction("Move down", self)
        down.triggered.connect(lambda: self.move_item(self.currentRow(), self.currentRow() + 1))
        menu.addAction(up)
        menu.addAction(down)
        if self.allow_remove:
            menu.addSeparator()
            remove = QAction("Remove", self)
            remove.triggered.connect(self.remove_current)
            menu.addAction(remove)
        menu.exec(self.mapToGlobal(position))


__all__ = ["DragDropListWidget"]
