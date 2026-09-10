"""Enhanced navigation tree.

.. note::
   This widget is **no longer the primary navigation of the main window**.
   The application navigates with two rows of top tabs (workspace row,
   section row); a left hand tree listing the same sections duplicated every
   command and was removed.  The widget is kept as a general purpose,
   DPI aware tree for panels that genuinely need a hierarchy (ODX/A2L
   browsing, plugin trees) and :data:`NAVIGATION_TREE` is kept in sync with
   the tab structure so it can still drive a "quick jump" palette.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QWidget

from ..dpi_scaler import DPIScaler

#: Workspace/section map, mirroring the two rows of tabs of the main window.
#: Every ``(section, icon)`` pair here is an actual sub-tab title, so
#: ``MainWindow.navigate(section, item)`` accepts any entry unchanged.
NAVIGATION_TREE: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    ("Connection", "connect", ()),
    (
        "Diagnostics",
        "ecu",
        (
            ("Session", "play"),
            ("Read DID", "search"),
            ("Read DTC", "dtc"),
            ("Clear DTC", "clear"),
            ("Security", "plugin"),
            ("I/O control", "settings"),
            ("Routine", "run_all"),
            ("Flash / transfer", "flash"),
            ("ECU flashing", "flash"),
            ("Tester present", "refresh"),
            ("Raw request", "file_hex"),
        ),
    ),
    ("Developer mode", "developer", (("Test sequence", "run_all"),
                                      ("Code generator", "developer"),
                                      ("Script editor", "file_hex"))),
    ("Data analysis", "convert", (("Response slicer", "file_hex"), ("Converter", "convert"),
                                   ("Monitor", "refresh"), ("Plot", "chart"))),
    ("Logs", "log", (("Log viewer", "log"), ("Trace viewer", "search"))),
    ("Settings", "settings", (("General", "settings"), ("Protocols", "connect"),
                               ("Diagnostics", "ecu"), ("Display", "theme"),
                               ("Logging", "log"), ("Plugins", "plugin"))),
)


class EnhancedTreeView(QTreeWidget):
    """The navigation tree of the main window.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the selected ``(section, item)`` pair.
    navigation_selected = Signal(str, str)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the tree with the default navigation structure."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.setHeaderHidden(True)
        self.setIndentation(self.scaler.px(14))
        self.setAnimated(True)
        self.setExpandsOnDoubleClick(True)
        self.itemClicked.connect(self._on_item_clicked)
        self.build_default()

    def build_default(self) -> None:
        """Populate the tree with :data:`NAVIGATION_TREE`."""
        from ..icon_manager import IconManager

        icons = IconManager(self.scaler)
        self.clear()
        for section, icon_name, children in NAVIGATION_TREE:
            parent = QTreeWidgetItem(self, [section])
            parent.setData(0, Qt.ItemDataRole.UserRole, (section, ""))
            icon = icons.icon(icon_name, size=16)
            if icon is not None:
                parent.setIcon(0, icon)
            for label, child_icon in children:
                child = QTreeWidgetItem(parent, [label])
                child.setData(0, Qt.ItemDataRole.UserRole, (section, label))
                child_icon_obj = icons.icon(child_icon, size=14)
                if child_icon_obj is not None:
                    child.setIcon(0, child_icon_obj)
            parent.setExpanded(section in ("Connection", "Diagnostics"))

    def select_path(self, section: str, item: str = "") -> bool:
        """Select the node identified by ``(section, item)``."""
        for index in range(self.topLevelItemCount()):
            top = self.topLevelItem(index)
            if top.text(0) != section:
                continue
            if not item:
                self.setCurrentItem(top)
                return True
            for child_index in range(top.childCount()):
                child = top.child(child_index)
                if child.text(0) == item:
                    top.setExpanded(True)
                    self.setCurrentItem(child)
                    return True
        return False

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Emit the navigation signal for the clicked node."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple):
            self.navigation_selected.emit(data[0], data[1])


__all__ = ["EnhancedTreeView", "NAVIGATION_TREE"]
