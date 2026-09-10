"""Logs workspace grouping the log viewer and the communication trace.

``Log viewer`` used to live in a bottom dock while ``Trace viewer`` was a
central tab, so one navigation entry opened a dock and its sibling opened a
tab.  Both are now sections of a single workspace with a top tab bar.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ...dpi_scaler import DPIScaler
from ...widgets.breadcrumb_widget import BreadcrumbWidget
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.tab_widget_enhanced import EnhancedTabWidget
from .log_viewer_panel import LogViewerPanel
from .trace_viewer_panel import TraceViewerPanel

#: Icon used for every log section, keyed by section title.
SECTION_ICONS: dict[str, str] = {"Log viewer": "log", "Trace viewer": "search"}


class LogWorkspace(ResponsiveWidget):
    """Hosts the log viewer and the communication trace viewer.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        log_panel: The live log viewer section.
        trace_panel: The request/response trace section.
    """

    #: Emitted with the title of the section the operator selected.
    section_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Create the two log sections as top tabs."""
        super().__init__(parent, scaler)
        self.log_panel = LogViewerPanel(self, self.scaler)
        self.trace_panel = TraceViewerPanel(self, self.scaler)

        self.views: dict[str, QWidget] = {
            "Log viewer": self.log_panel,
            "Trace viewer": self.trace_panel,
        }
        self.tabs = EnhancedTabWidget(self, self.scaler, level="sub")
        for title, view in self.views.items():
            self.tabs.add_panel(view, title, SECTION_ICONS.get(title, ""))

        self.breadcrumb = BreadcrumbWidget(self, self.scaler)
        self.breadcrumb.set_path("Logs", self.tabs.current_title())
        self.tabs.tab_title_activated.connect(self._on_section_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.spacing(10), self.spacing(6), self.spacing(10), self.spacing(6)
        )
        layout.setSpacing(self.spacing(4))
        layout.addWidget(self.breadcrumb)
        layout.addWidget(self.tabs, 1)

    # -- API -----------------------------------------------------------------
    def sections(self) -> list[str]:
        """Return every section title in tab bar order."""
        return list(self.views)

    def show_view(self, title: str) -> bool:
        """Activate the log section called *title*."""
        return self.tabs.select_by_title(title)

    def set_compact(self, compact: bool) -> None:
        """Collapse the section tabs to icons on narrow screens."""
        self.tabs.set_compact(compact)

    def _on_section_changed(self, title: str) -> None:
        """Keep the breadcrumb in sync with the section tab bar."""
        self.breadcrumb.set_path("Logs", title)
        self.section_changed.emit(title)


__all__ = ["LogWorkspace", "SECTION_ICONS"]
