"""Main diagnostic panel hosting one *top* tab per UDS service.

Navigation model
----------------
The platform has exactly two navigation rows and both of them are at the top
of the window:

1. the workspace row of :class:`~ui.main_window.MainWindow`
   (Connection / Diagnostics / Developer mode / ...), and
2. the section row built here (Session / Read DID / Read DTC / ...).

The diagnostic sections used to be duplicated in a left hand navigation tree,
which meant the same command existed in two places with two different
behaviours.  Everything now lives in the section tab bar, and a breadcrumb
spells the resulting path out in words.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from src.core.models.did_model import DIDRegistry

from ...dpi_scaler import DPIScaler
from ...widgets.breadcrumb_widget import BreadcrumbWidget
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.tab_widget_enhanced import EnhancedTabWidget
from .clear_dtc_panel.clear_dtc_view import ClearDTCView
from .io_control_panel.io_control_view import IOControlView
from .raw_service_panel.raw_request_view import RawRequestView
from .read_did_panel.read_did_view import ReadDIDView
from .read_dtc_panel.read_dtc_view import ReadDTCView
from .routine_control_panel.routine_control_view import RoutineControlView
from .security_access_panel.security_access_view import SecurityAccessView
from .session_control_panel.session_control_view import SessionControlView
from .tester_present_panel.tester_present_view import TesterPresentView
from .transfer_panel.flash_manager_view import FlashManagerView
from .transfer_panel.flash_panel import FlashPanel

#: Icon used for every diagnostic section, keyed by section title.
SECTION_ICONS: dict[str, str] = {
    "Session": "play",
    "Read DID": "search",
    "Read DTC": "dtc",
    "Clear DTC": "clear",
    "Security": "plugin",
    "I/O control": "settings",
    "Routine": "run_all",
    "Flash / transfer": "flash",
    "ECU flashing": "flash",
    "Tester present": "refresh",
    "Raw request": "file_hex",
}

#: Accepted aliases so older navigation entries keep working.
SECTION_ALIASES: dict[str, str] = {
    "Session control": "Session",
    "Security access": "Security",
    "Routine control": "Routine",
    "IO control": "I/O control",
    "Flash": "Flash / transfer",
    "Transfer": "Flash / transfer",
    "Flashing": "ECU flashing",
}


class DiagnosticMainPanel(ResponsiveWidget):
    """Tabbed container holding every diagnostic service view.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        registry: DID definitions passed to the ReadDID view.

    Attributes:
        tabs: The section tab bar shown at the top of the workspace.
        views: ``{title: widget}`` in tab bar order.
        breadcrumb: The ``Diagnostics › <section>`` indicator.

    Example:
        >>> # panel = DiagnosticMainPanel()
        >>> # panel.session_view.session_requested.connect(controller.change_session)
        >>> None
    """

    #: Emitted with the raw bytes the operator wants to analyse.
    analyse_requested = Signal(bytes)
    #: Emitted with the title of the section the operator selected.
    section_changed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        registry: DIDRegistry | None = None,
    ) -> None:
        """Create every service view and place it in a scrollable top tab."""
        super().__init__(parent, scaler)
        self.tabs = EnhancedTabWidget(self, self.scaler, level="sub")

        self.session_view = SessionControlView(self, self.scaler)
        self.read_did_view = ReadDIDView(self, self.scaler, registry)
        self.read_dtc_view = ReadDTCView(self, self.scaler)
        self.clear_dtc_view = ClearDTCView(self, self.scaler)
        self.security_view = SecurityAccessView(self, self.scaler)
        self.io_control_view = IOControlView(self, self.scaler)
        self.routine_view = RoutineControlView(self, self.scaler)
        self.transfer_view = FlashManagerView(self, self.scaler)
        self.flash_panel = FlashPanel(self, self.scaler)
        self.tester_present_view = TesterPresentView(self, self.scaler)
        self.raw_view = RawRequestView(self, self.scaler)

        self.views: dict[str, QWidget] = {
            "Session": self.session_view,
            "Read DID": self.read_did_view,
            "Read DTC": self.read_dtc_view,
            "Clear DTC": self.clear_dtc_view,
            "Security": self.security_view,
            "I/O control": self.io_control_view,
            "Routine": self.routine_view,
            "Flash / transfer": self.transfer_view,
            "ECU flashing": self.flash_panel,
            "Tester present": self.tester_present_view,
            "Raw request": self.raw_view,
        }
        for title, view in self.views.items():
            self.tabs.add_panel(self._scrollable(view), title, SECTION_ICONS.get(title, ""))

        self.breadcrumb = BreadcrumbWidget(self, self.scaler)
        self.breadcrumb.set_path("Diagnostics", self.tabs.current_title())
        self.tabs.tab_title_activated.connect(self._on_section_changed)

        self.read_did_view.analyse_requested.connect(self.analyse_requested.emit)
        self.raw_view.analyse_requested.connect(self.analyse_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.spacing(10), self.spacing(6), self.spacing(10), self.spacing(6)
        )
        layout.setSpacing(self.spacing(4))
        layout.addWidget(self.breadcrumb)
        layout.addWidget(self.tabs, 1)

    def _scrollable(self, widget: QWidget) -> QScrollArea:
        """Wrap *widget* into a scroll area so small screens still work."""
        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setWidget(widget)
        return area

    # -- API -----------------------------------------------------------------
    def sections(self) -> list[str]:
        """Return every section title in tab bar order."""
        return list(self.views)

    def show_view(self, title: str) -> bool:
        """Activate the section tab called *title*.

        Args:
            title: A section title or one of :data:`SECTION_ALIASES`.

        Returns:
            ``True`` when a matching tab was found.
        """
        resolved = SECTION_ALIASES.get(title, title)
        return self.tabs.select_by_title(resolved)

    def set_connected(self, connected: bool) -> None:
        """Enable or disable every section depending on the connection state."""
        self.tabs.set_all_enabled(connected, "Connect to a VCI first")
        self.breadcrumb.set_detail("" if connected else "not connected")

    def current_view(self) -> QWidget | None:
        """Return the service view currently displayed."""
        return self.views.get(self.tabs.current_title())

    def set_compact(self, compact: bool) -> None:
        """Collapse the section tabs to icons on narrow screens."""
        self.tabs.set_compact(compact)

    def _on_section_changed(self, title: str) -> None:
        """Keep the breadcrumb in sync with the section tab bar."""
        self.breadcrumb.set_path("Diagnostics", title)
        self.section_changed.emit(title)


__all__ = ["DiagnosticMainPanel", "SECTION_ALIASES", "SECTION_ICONS"]
