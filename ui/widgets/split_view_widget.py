"""Resizable split panel container with state persistence."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSplitter, QWidget

from ..dpi_scaler import DPIScaler


class SplitViewWidget(QSplitter):
    """A splitter that remembers its sizes and can collapse panes.

    Args:
        orientation: Splitter orientation.
        parent: Parent widget.
        scaler: Shared DPI scaler.
        name: Identifier used when persisting the sizes.
    """

    #: Emitted with the new sizes whenever the user drags a handle.
    sizes_changed = Signal(list)

    def __init__(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        name: str = "split",
    ) -> None:
        """Create the splitter."""
        super().__init__(orientation, parent)
        self.scaler = scaler or DPIScaler()
        self.name = name
        self._stored_sizes: dict[int, int] = {}
        self.setChildrenCollapsible(True)
        self.setHandleWidth(self.scaler.px(4))
        self.splitterMoved.connect(lambda *_: self.sizes_changed.emit(self.sizes()))

    # -- panes ---------------------------------------------------------------
    def add_pane(self, widget: QWidget, stretch: int = 1, collapsible: bool = True) -> int:
        """Add *widget* as a new pane and return its index."""
        index = self.count()
        self.addWidget(widget)
        self.setStretchFactor(index, stretch)
        self.setCollapsible(index, collapsible)
        return index

    def collapse_pane(self, index: int) -> None:
        """Collapse the pane at *index*, remembering its size."""
        sizes = self.sizes()
        if not 0 <= index < len(sizes) or sizes[index] == 0:
            return
        self._stored_sizes[index] = sizes[index]
        sizes[index] = 0
        self.setSizes(sizes)
        self.sizes_changed.emit(sizes)

    def expand_pane(self, index: int, size: int | None = None) -> None:
        """Restore a collapsed pane."""
        sizes = self.sizes()
        if not 0 <= index < len(sizes):
            return
        sizes[index] = size or self._stored_sizes.get(index, self.scaler.px(240))
        self.setSizes(sizes)
        self.sizes_changed.emit(sizes)

    def toggle_pane(self, index: int) -> bool:
        """Collapse or expand the pane and return the new visibility."""
        sizes = self.sizes()
        if not 0 <= index < len(sizes):
            return False
        if sizes[index] == 0:
            self.expand_pane(index)
            return True
        self.collapse_pane(index)
        return False

    def is_collapsed(self, index: int) -> bool:
        """Return ``True`` when the pane at *index* is collapsed."""
        sizes = self.sizes()
        return 0 <= index < len(sizes) and sizes[index] == 0

    # -- persistence ----------------------------------------------------------
    def save_sizes(self) -> list[int]:
        """Return the current pane sizes."""
        return self.sizes()

    def restore_sizes(self, sizes: list[int]) -> None:
        """Restore previously saved pane sizes."""
        if sizes and len(sizes) == self.count():
            self.setSizes(sizes)


__all__ = ["SplitViewWidget"]
