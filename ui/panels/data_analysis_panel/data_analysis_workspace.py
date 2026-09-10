"""Data analysis workspace: slicer, sliced-data converter and live trace.

Layout::

    +-------------------------------------------------------------+
    |  Data analysis > Slicer                                      |  breadcrumb
    +-------------------------------------------------------------+
    | Slicer | Monitor | Plot |                                    |  section tabs
    +------------------------------+------------------------------+
    |  Data slicer                 |  Sliced data converter        |
    |  byte map + slice table      |  the selected slice, in every |
    |                              |  representation               |
    +------------------------------+------------------------------+
    |  Live trace (TX/RX, colour coded, always visible)            |
    +-------------------------------------------------------------+

The slicer and the converter are deliberately **not** separate tabs: the
converter's whole job is to expand the field the operator just selected in the
slicer, so putting them behind different tabs meant never seeing the two
together.  They now share one splitter and the selection is wired straight
through.  The live trace sits underneath every section so the traffic that
produced the bytes stays on screen while they are analysed.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QScrollArea, QSplitter, QVBoxLayout, QWidget

from ...dpi_scaler import DPIScaler
from ...widgets.breadcrumb_widget import BreadcrumbWidget
from ...widgets.live_trace_widget import LiveTraceWidget
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.tab_widget_enhanced import EnhancedTabWidget
from .data_converter_panel import DataConverterPanel
from .data_monitor_panel import DataMonitorPanel
from .data_plot_panel import DataPlotPanel
from .response_slicer_panel import ResponseSlicerPanel

#: Icon used for every analysis section, keyed by section title.
SECTION_ICONS: dict[str, str] = {
    "Slicer": "file_hex",
    "Monitor": "refresh",
    "Plot": "chart",
}


class DataAnalysisWorkspace(ResponsiveWidget):
    """Hosts the slicer/converter pair, the monitor, the plot and the trace.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        slicer_panel: The response slicer (left half of the Slicer section).
        converter_panel: The sliced data converter (right half).
        monitor_panel: The live DID monitor section.
        plot_panel: The live chart section.
        trace: The always-visible live trace strip at the bottom.
    """

    #: Emitted with the title of the section the operator selected.
    section_changed = Signal(str)
    #: Emitted with the bytes pushed into the slicer.
    data_loaded = Signal(bytes)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Create the sections, the trace strip and the slicer wiring."""
        super().__init__(parent, scaler)
        self.slicer_panel = ResponseSlicerPanel(self, self.scaler)
        self.converter_panel = DataConverterPanel(self, self.scaler)
        self.monitor_panel = DataMonitorPanel(self, self.scaler)
        self.plot_panel = DataPlotPanel(self, self.scaler)
        self.trace = LiveTraceWidget(self, self.scaler)

        self.slice_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.slice_splitter.addWidget(self._scrollable(self.slicer_panel))
        self.slice_splitter.addWidget(self._scrollable(self.converter_panel))
        self.slice_splitter.setStretchFactor(0, 3)
        self.slice_splitter.setStretchFactor(1, 2)
        self.slice_splitter.setChildrenCollapsible(False)

        self.views: dict[str, QWidget] = {
            "Slicer": self.slice_splitter,
            "Monitor": self._scrollable(self.monitor_panel),
            "Plot": self._scrollable(self.plot_panel),
        }
        self.tabs = EnhancedTabWidget(self, self.scaler, level="sub")
        for title, view in self.views.items():
            self.tabs.add_panel(view, title, SECTION_ICONS.get(title, ""))

        self.breadcrumb = BreadcrumbWidget(self, self.scaler)
        self.breadcrumb.set_path("Data analysis", self.tabs.current_title())
        self.tabs.tab_title_activated.connect(self._on_section_changed)

        # -- slicer -> converter -------------------------------------------
        # Selecting a slice sends only that field to the converter, so the
        # converter always describes the field whose name is highlighted.
        self.slicer_panel.slicer.slice_selected.connect(self._on_slice_selected)
        # -- trace -> slicer ------------------------------------------------
        # Double clicking a traced frame loads it for slicing; this is the
        # fast path from "I saw that response" to "show me its fields".
        self.trace.frame_activated.connect(self.set_data)

        self.splitter = QSplitter(Qt.Orientation.Vertical, self)
        top = QWidget(self)
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(self.spacing(4))
        top_layout.addWidget(self.tabs, 1)
        self.splitter.addWidget(top)
        self.splitter.addWidget(self.trace)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setChildrenCollapsible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.spacing(10), self.spacing(6), self.spacing(10), self.spacing(6)
        )
        layout.setSpacing(self.spacing(4))
        layout.addWidget(self.breadcrumb)
        layout.addWidget(self.splitter, 1)

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
        """Activate the analysis section called *title*.

        ``"Response slicer"`` and ``"Converter"`` both resolve to the combined
        *Slicer* section, because that is now where each of them lives.
        """
        resolved = {
            "Response slicer": "Slicer",
            "Converter": "Slicer",
            "Sliced data converter": "Slicer",
            "Data monitor": "Monitor",
        }.get(title, title)
        return self.tabs.select_by_title(resolved)

    def set_data(self, data: bytes) -> None:
        """Push *data* into the slicer and mirror it in the converter."""
        payload = bytes(data)
        self.slicer_panel.set_data(payload)
        self.converter_panel.set_data(payload)
        self.converter_panel.set_source("whole response")
        self.data_loaded.emit(payload)

    def set_compact(self, compact: bool) -> None:
        """Stack the slicer over the converter on narrow screens."""
        self.tabs.set_compact(compact)
        self.slice_splitter.setOrientation(
            Qt.Orientation.Vertical if compact else Qt.Orientation.Horizontal
        )

    # -- events ----------------------------------------------------------------
    def _on_slice_selected(self, definition: Any, raw: bytes) -> None:
        """Send the selected slice, and only it, to the converter."""
        if definition is None or not raw:
            return
        self.converter_panel.set_data(raw)
        self.converter_panel.set_source(getattr(definition, "name", "") or "slice")
        scaling = getattr(definition, "scaling", None)
        if callable(scaling):
            self.converter_panel.apply_scaling(scaling())

    def _on_section_changed(self, title: str) -> None:
        """Keep the breadcrumb in sync with the section tab bar."""
        self.breadcrumb.set_path("Data analysis", title)
        self.section_changed.emit(title)


__all__ = ["DataAnalysisWorkspace", "SECTION_ICONS"]
