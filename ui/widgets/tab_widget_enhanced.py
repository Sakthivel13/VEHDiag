"""Enhanced tab widget with badges and close protection."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QTabWidget, QWidget

from ..dpi_scaler import DPIScaler


class EnhancedTabWidget(QTabWidget):
    """A tab widget supporting per-tab badges, disabled tabs and nesting.

    The platform uses a strictly two level navigation model: the primary tab
    bar of the main window selects the *workspace* (Connection, Diagnostics,
    ...) and a secondary tab bar inside that workspace selects the *section*
    (Read DTC, Clear DTC, ...).  The ``level`` argument styles the bar so the
    two rows never look alike and the operator always knows which row he is
    interacting with.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        closable: Show a close button on every tab.
        level: ``"primary"`` for the workspace bar, ``"sub"`` for the section
            bar of a workspace.  The value is exported as the ``navlevel``
            dynamic property so the theme can style each row differently.
        movable: Allow the operator to reorder tabs by dragging.  Navigation
            bars keep a fixed, documented order, so this defaults to ``False``.

    Example:
        >>> # tabs = EnhancedTabWidget(level="sub")
        >>> # tabs.add_panel(view, "Read DTC", "dtc")
        >>> None
    """

    #: Emitted with the index of the newly selected tab.
    tab_activated = Signal(int)
    #: Emitted with the title of the newly selected tab.
    tab_title_activated = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        closable: bool = False,
        level: str = "primary",
        movable: bool = False,
    ) -> None:
        """Configure the tab bar."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self._titles: dict[int, str] = {}
        self._icon_names: dict[int, str] = {}
        self._compact = False
        self.level = level
        self.setTabsClosable(closable)
        self.setMovable(movable)
        self.setDocumentMode(True)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.TextElideMode.ElideNone)
        self.setProperty("navlevel", level)
        bar = self.tabBar()
        if bar is not None:
            # Without an expanding bar Qt clips the final tab instead of
            # scrolling to it, which loses "Tester present" on 1080p screens.
            bar.setExpanding(False)
            bar.setDrawBase(False)
            icon_px = self.scaler.icon(18 if level == "primary" else 15)
            bar.setIconSize(QSize(icon_px, icon_px))
            bar.setUsesScrollButtons(True)
            bar.setProperty("navlevel", level)
        self.currentChanged.connect(self.tab_activated.emit)
        self.currentChanged.connect(self._emit_title)

    # -- tabs ----------------------------------------------------------------
    def add_panel(self, widget: QWidget, title: str, icon_name: str = "") -> int:
        """Add a tab and return its index."""
        index = self.addTab(widget, title)
        self._titles[index] = title
        self._icon_names[index] = icon_name
        self.setTabToolTip(index, title)
        if icon_name:
            from ..icon_manager import IconManager

            icon = IconManager(self.scaler).icon(icon_name)
            if icon is not None:
                self.setTabIcon(index, icon)
        return index

    def titles(self) -> list[str]:
        """Return every tab title in bar order."""
        return [self._titles.get(i, self.tabText(i)) for i in range(self.count())]

    def title_at(self, index: int) -> str:
        """Return the registered title of the tab at *index*."""
        return self._titles.get(index, self.tabText(index))

    def current_title(self) -> str:
        """Return the title of the tab currently displayed."""
        return self.title_at(self.currentIndex())

    def set_compact(self, compact: bool) -> None:
        """Show icons only when *compact*, so narrow screens keep every tab.

        On a 1366 px wide screen eleven diagnostic sections do not fit as
        text; without this the last sections disappear behind scroll arrows
        and look "missing" to the operator.

        Args:
            compact: ``True`` to hide the tab labels, ``False`` to restore.
        """
        if compact == self._compact:
            return
        self._compact = compact
        for index in range(self.count()):
            title = self._titles.get(index, self.tabText(index))
            has_icon = bool(self._icon_names.get(index))
            self.setTabText(index, "" if compact and has_icon else title)

    def _emit_title(self, index: int) -> None:
        """Re-emit the current change as a title based signal."""
        self.tab_title_activated.emit(self.title_at(index))

    def set_badge(self, index: int, count: int) -> None:
        """Show a numeric badge next to the tab title."""
        base = self._titles.get(index, self.tabText(index))
        self.setTabText(index, f"{base} ({count})" if count else base)

    def set_tab_enabled(self, index: int, enabled: bool, reason: str = "") -> None:
        """Enable or disable a tab and explain why in the tooltip."""
        self.setTabEnabled(index, enabled)
        self.setTabToolTip(index, reason if not enabled else self._titles.get(index, ""))

    def set_all_enabled(self, enabled: bool, reason: str = "") -> None:
        """Enable or disable every tab (used when disconnecting)."""
        for index in range(self.count()):
            self.set_tab_enabled(index, enabled, reason)

    def select_by_title(self, title: str) -> bool:
        """Activate the first tab whose title matches *title*."""
        for index, name in self._titles.items():
            if name == title:
                self.setCurrentIndex(index)
                return True
        return False


__all__ = ["EnhancedTabWidget"]
