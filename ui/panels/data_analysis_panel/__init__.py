"""Data analysis UI package."""
from __future__ import annotations

from .data_analysis_workspace import DataAnalysisWorkspace
from .data_converter_panel import DataConverterPanel
from .data_monitor_panel import DataMonitorPanel
from .data_plot_panel import DataPlotPanel, Series
from .response_slicer_panel import ResponseSlicerPanel

__all__ = [
    "DataAnalysisWorkspace",
    "DataConverterPanel",
    "DataMonitorPanel",
    "DataPlotPanel",
    "ResponseSlicerPanel",
    "Series",
]
