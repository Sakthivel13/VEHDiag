"""Time series plot of the values collected by the data monitor.

The platform deliberately avoids a heavy plotting dependency, so the chart is
painted directly with :class:`QPainter`. The maths — down-sampling, axis
scaling and the mapping from values to pixels — lives in free functions so it
can be unit tested head-lessly.

Example:
    >>> from ui.panels.data_analysis_panel.data_plot_panel import (
    ...     Series, axis_bounds, downsample, normalise)
    >>> axis_bounds([1.0, 2.0, 3.0], padding=0.0)
    (1.0, 3.0)
    >>> axis_bounds([5.0, 5.0])
    (4.5, 5.5)
    >>> axis_bounds([])
    (0.0, 1.0)
    >>> downsample([1, 2, 3, 4, 5, 6], 3)
    [1, 3, 5]
    >>> downsample([1, 2], 5)
    [1, 2]
    >>> normalise(5.0, 0.0, 10.0)
    0.5
    >>> series = Series("rpm")
    >>> series.append(800.0); series.append(900.0)
    >>> series.latest(), len(series)
    (900.0, 2)
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Iterable, Sequence

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.models.did_model import DIDValue

from ...dpi_scaler import DPIScaler
from ...styles.style_constants import DARK_PALETTE
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.scalable_label import HeadingLabel
from ...styles.semantic_colors import semantic

__all__ = [
    "PLOT_COLORS",
    "DataPlotPanel",
    "PlotCanvas",
    "Series",
    "axis_bounds",
    "downsample",
    "normalise",
]

#: Colour cycle used for the plotted series.
PLOT_COLORS: tuple[str, ...] = (
    semantic("primary"),
    semantic("running"),
    semantic("success"),
    semantic("warning"),
    semantic("error"),
    semantic("muted"),
)

#: Number of samples kept per series.
HISTORY_DEPTH = 2048


def axis_bounds(values: Sequence[float], padding: float = 0.05) -> tuple[float, float]:
    """Return the ``(minimum, maximum)`` of the value axis.

    A flat series is expanded by half a unit so the line is not drawn on the
    frame, and an empty series falls back to ``(0.0, 1.0)``.

    Args:
        values: The plotted values.
        padding: Fraction of the span added above and below.

    Example:
        >>> axis_bounds([0.0, 10.0], padding=0.0)
        (0.0, 10.0)
    """
    if not values:
        return 0.0, 1.0
    low, high = float(min(values)), float(max(values))
    if low == high:
        return low - 0.5, high + 0.5
    margin = (high - low) * padding
    return low - margin, high + margin


def downsample(values: Sequence[Any], limit: int) -> list[Any]:
    """Return at most *limit* evenly spaced samples of *values*.

    Args:
        values: The samples to reduce.
        limit: Maximum number of samples to keep (at least one).

    Example:
        >>> downsample([1, 2, 3], 1)
        [1]
    """
    count = len(values)
    target = max(1, int(limit))
    if count <= target:
        return list(values)
    step = count / target
    return [values[int(index * step)] for index in range(target)]


def normalise(value: float, low: float, high: float) -> float:
    """Map *value* from the range ``[low, high]`` into ``[0, 1]``.

    Example:
        >>> normalise(1.0, 1.0, 1.0)
        0.0
    """
    span = high - low
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, (value - low) / span))


@dataclass(slots=True)
class Series:
    """One plotted signal with its rolling sample buffer.

    Attributes:
        name: Display name of the series.
        color: Line colour.
        unit: Engineering unit appended to the legend.
        visible: Whether the series is drawn.
        values: The samples, oldest first.
        timestamps: The monotonic timestamp of each sample.
    """

    name: str
    color: str = PLOT_COLORS[0]
    unit: str = ""
    visible: bool = True
    values: Deque[float] = field(default_factory=lambda: deque(maxlen=HISTORY_DEPTH))
    timestamps: Deque[float] = field(default_factory=lambda: deque(maxlen=HISTORY_DEPTH))

    def append(self, value: float, timestamp: float | None = None) -> None:
        """Record one sample."""
        self.values.append(float(value))
        self.timestamps.append(timestamp if timestamp is not None else time.monotonic())

    def latest(self) -> float | None:
        """Return the most recent sample, or ``None`` when empty."""
        return self.values[-1] if self.values else None

    def bounds(self) -> tuple[float, float]:
        """Return the axis bounds of this series."""
        return axis_bounds(list(self.values))

    def legend_text(self) -> str:
        """Return the legend entry of the series.

        Example:
            >>> s = Series("temp", unit="degC")
            >>> s.append(21.5)
            >>> s.legend_text()
            'temp: 21.5 degC'
        """
        current = self.latest()
        if current is None:
            return f"{self.name}: -"
        unit = f" {self.unit}" if self.unit else ""
        return f"{self.name}: {current:g}{unit}"

    def clear(self) -> None:
        """Drop every sample."""
        self.values.clear()
        self.timestamps.clear()

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.values)


class PlotCanvas(QWidget):
    """Paints the series as polylines on a gridded background.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        palette: Colour palette used for the frame and the grid.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        palette: Any = DARK_PALETTE,
    ) -> None:
        """Create the canvas with a scaled minimum height."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.color_palette = palette
        self.series: list[Series] = []
        self.max_points = 600
        self.show_grid = True
        # 220 px is the comfortable height, but it must not be a hard floor:
        # inside the analysis scroll area on a 1280x720 screen the viewport is
        # ~306 px, and a floor that large left the layout unable to satisfy
        # both the canvas and the legend, so the canvas painted over the
        # legend text. Keep a usable minimum and let sizeHint ask for more.
        self.setMinimumHeight(self.scaler.px(130))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        """Return the comfortable plotting size."""
        return QSize(self.scaler.px(420), self.scaler.px(220))

    def set_series(self, series: list[Series]) -> None:
        """Display *series* and repaint."""
        self.series = series
        self.update()

    def visible_bounds(self) -> tuple[float, float]:
        """Return the axis bounds covering every visible series."""
        values: list[float] = []
        for entry in self.series:
            if entry.visible:
                values.extend(entry.values)
        return axis_bounds(values)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt naming
        """Paint the grid, the frame and one polyline per visible series."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.fillRect(rect, QColor(self.color_palette.background))

        if self.show_grid:
            grid_pen = QPen(QColor(self.color_palette.border))
            grid_pen.setWidth(1)
            painter.setPen(grid_pen)
            for step in range(1, 5):
                y = rect.top() + rect.height() * step / 5.0
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                x = rect.left() + rect.width() * step / 5.0
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        low, high = self.visible_bounds()
        for entry in self.series:
            if not entry.visible or len(entry) < 2:
                continue
            samples = downsample(list(entry.values), self.max_points)
            pen = QPen(QColor(entry.color))
            pen.setWidth(max(1, self.scaler.px(2)))
            painter.setPen(pen)
            points = [
                QPointF(
                    rect.left() + rect.width() * index / max(1, len(samples) - 1),
                    rect.bottom() - rect.height() * normalise(value, low, high),
                )
                for index, value in enumerate(samples)
            ]
            painter.drawPolyline(points)

        painter.setPen(QPen(QColor(self.color_palette.border)))
        painter.drawRect(rect)
        painter.end()


class DataPlotPanel(ResponsiveWidget):
    """Live chart of the values polled by the data monitor.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        series: ``{name: Series}`` in insertion order.
        canvas: The painting widget.
    """

    #: Emitted with the series names whenever a series is added or removed.
    series_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the canvas, the legend and the toolbar."""
        super().__init__(parent, scaler)
        self.series: dict[str, Series] = {}
        self.paused = False

        self.canvas = PlotCanvas(self, self.scaler, self.color_palette)
        self.legend_label = QLabel("no series", self)
        self.legend_label.setProperty("role", "secondary")
        self.legend_label.setWordWrap(True)
        # A word-wrapped QLabel reports heightForWidth and defaults to a
        # shrinkable vertical policy. Inside a scroll area the layout then
        # squeezes the legend below its own hint while the canvas keeps its
        # fixed minimum, so the canvas paints over the legend text. Minimum
        # means "never smaller than sizeHint", which is what a caption needs.
        self.legend_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )

        self.points_box = QSpinBox(self)
        self.points_box.setRange(50, HISTORY_DEPTH)
        self.points_box.setValue(600)
        self.points_box.setSuffix(" pts")
        self.points_box.valueChanged.connect(self._on_points_changed)

        self.grid_box = QCheckBox("Grid", self)
        self.grid_box.setChecked(True)
        self.grid_box.toggled.connect(self._on_grid_toggled)

        self.pause_button = ScalableButton("Pause", "pause", self, self.scaler)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.clear_button = ScalableButton("Clear", "clear", self, self.scaler)
        self.clear_button.clicked.connect(self.clear)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(4))
        toolbar.addWidget(QLabel("Window:", self))
        toolbar.addWidget(self.points_box)
        toolbar.addWidget(self.grid_box)
        toolbar.addStretch(1)
        toolbar.addWidget(self.pause_button)
        toolbar.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(HeadingLabel("Data plot", 3, self, self.scaler))
        layout.addLayout(toolbar)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.legend_label)

    # -- series management ---------------------------------------------------
    def add_series(self, name: str, unit: str = "") -> Series:
        """Create (or return) the series called *name*.

        The colour is taken from the *active* theme rather than the constant
        captured at import time, so a chart repaints correctly after a theme
        switch.
        """
        if name in self.series:
            return self.series[name]
        from ...styles.semantic_colors import series_colors

        color = series_colors(len(self.series) + 1)[-1]
        series = Series(name=name, color=color, unit=unit)
        self.series[name] = series
        self._refresh()
        self.series_changed.emit(list(self.series))
        return series

    def remove_series(self, name: str) -> bool:
        """Remove the series called *name*."""
        removed = self.series.pop(name, None) is not None
        if removed:
            self._refresh()
            self.series_changed.emit(list(self.series))
        return removed

    def append(self, name: str, value: float, unit: str = "") -> None:
        """Append *value* to the series *name*, creating it when needed."""
        if self.paused:
            return
        series = self.series.get(name) or self.add_series(name, unit)
        series.append(value)
        self._refresh()

    def append_values(self, values: Iterable[DIDValue]) -> int:
        """Append every numeric reading of *values* to its series.

        Returns:
            The number of samples that were appended.
        """
        appended = 0
        for value in values:
            number = self._numeric(value)
            if number is None:
                continue
            self.append(value.name or f"{value.did:04X}", number, value.unit)
            appended += 1
        return appended

    def set_visible(self, name: str, visible: bool) -> bool:
        """Show or hide the series *name*."""
        series = self.series.get(name)
        if series is None:
            return False
        series.visible = visible
        self._refresh()
        return True

    def clear(self) -> None:
        """Drop every sample of every series."""
        for series in self.series.values():
            series.clear()
        self._refresh()

    def reset(self) -> None:
        """Remove every series."""
        self.series.clear()
        self._refresh()
        self.series_changed.emit([])

    def toggle_pause(self) -> bool:
        """Freeze or resume the chart and return the new paused state."""
        self.paused = not self.paused
        self.pause_button.setText("Resume" if self.paused else "Pause")
        return self.paused

    def legend(self) -> str:
        """Return the legend text of every visible series."""
        visible = [s for s in self.series.values() if s.visible]
        return "   ".join(s.legend_text() for s in visible) if visible else "no series"

    # -- internals ------------------------------------------------------------
    @staticmethod
    def _numeric(value: DIDValue) -> float | None:
        """Return the numeric interpretation of *value*, or ``None``."""
        if isinstance(value.parsed, (int, float)) and not isinstance(value.parsed, bool):
            return float(value.parsed)
        if value.raw and len(value.raw) <= 8:
            return float(int.from_bytes(value.raw, "big"))
        return None

    def _refresh(self) -> None:
        """Push the series into the canvas and refresh the legend."""
        self.canvas.set_series(list(self.series.values()))
        self.legend_label.setText(self.legend())

    def _on_points_changed(self, value: int) -> None:
        """Change the number of painted samples."""
        self.canvas.max_points = value
        self.canvas.update()

    def _on_grid_toggled(self, checked: bool) -> None:
        """Show or hide the background grid."""
        self.canvas.show_grid = checked
        self.canvas.update()
