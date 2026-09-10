"""Graphical and tabular view of the firmware memory layout.

The widget paints every :class:`~src.core.models.file_transfer_model.MemorySegment`
of a :class:`~src.data_processing.file_parsers.memory_map.MemoryMap` on a
horizontal address bar and lists the segments and the gaps below it.

Example:
    >>> from ui.panels.diagnostic_panel.transfer_panel.memory_layout_view import (
    ...     segment_bars, segment_rows)
    >>> from src.core.models.file_transfer_model import MemorySegment
    >>> from src.data_processing.file_parsers.memory_map import MemoryMap
    >>> memory = MemoryMap()
    >>> memory.add(MemorySegment(0x0000, b"\\x00" * 256))
    >>> memory.add(MemorySegment(0x0200, b"\\x00" * 256))
    >>> bars = segment_bars(memory)
    >>> round(bars[0]["start_fraction"], 3), round(bars[0]["width_fraction"], 3)
    (0.0, 0.333)
    >>> [row["Kind"] for row in segment_rows(memory)]
    ['segment', 'gap', 'segment']
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.core.models.file_transfer_model import MemorySegment
from src.data_processing.file_parsers.memory_map import MemoryGap, MemoryMap
from src.utils.file_utils import human_size

from ....dpi_scaler import DPIScaler
from ....styles.style_constants import DARK_PALETTE
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_label import HeadingLabel
from ....widgets.table_widget_enhanced import EnhancedTableWidget
from ....styles.semantic_colors import semantic

__all__ = [
    "COLUMNS",
    "MemoryLayoutBar",
    "MemoryLayoutView",
    "segment_bars",
    "segment_rows",
]

#: Column titles of the layout table.
COLUMNS: list[str] = ["Kind", "Start", "End", "Size", "Share"]

#: Colour used to paint a mapped segment.
SEGMENT_COLOR = semantic("primary")

#: Colour used to paint an unmapped gap.
GAP_COLOR = semantic("border")


def segment_bars(memory: MemoryMap) -> list[dict[str, Any]]:
    """Return the normalised geometry of every segment.

    Args:
        memory: The memory map to describe.

    Returns:
        One mapping per segment with ``start_fraction`` and ``width_fraction``
        in the range 0..1, plus the segment itself under ``segment``.

    Example:
        >>> segment_bars(MemoryMap())
        []
    """
    span = memory.span
    if span <= 0:
        return []
    base = memory.start_address
    return [
        {
            "segment": segment,
            "start_fraction": (segment.address - base) / span,
            "width_fraction": segment.size / span,
        }
        for segment in memory.segments
    ]


def segment_rows(memory: MemoryMap) -> list[dict[str, Any]]:
    """Return the table rows describing the segments and the gaps.

    Example:
        >>> segment_rows(MemoryMap())
        []
    """
    if not memory.segments:
        return []
    span = max(1, memory.span)
    entries: list[tuple[int, int, str]] = [
        (segment.address, segment.end_address, "segment") for segment in memory.segments
    ]
    entries += [(gap.start, gap.end, "gap") for gap in memory.gaps()]
    entries.sort(key=lambda item: item[0])
    return [
        {
            "Kind": kind,
            "Start": f"0x{start:08X}",
            "End": f"0x{end:08X}",
            "Size": human_size(end - start),
            "Share": f"{100.0 * (end - start) / span:.1f} %",
            "_color": SEGMENT_COLOR if kind == "segment" else GAP_COLOR,
        }
        for start, end, kind in entries
    ]


class MemoryLayoutBar(QWidget):
    """A horizontal bar painting the mapped and unmapped address ranges.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Create the bar with a fixed scaled height."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.memory = MemoryMap()
        self.setMinimumHeight(self.scaler.px(36))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_memory(self, memory: MemoryMap) -> None:
        """Display *memory* and repaint."""
        self.memory = memory
        self.setToolTip(
            f"0x{memory.start_address:08X}..0x{memory.end_address:08X}  "
            f"({human_size(memory.total_size)} mapped)"
            if memory.segments
            else "no firmware loaded"
        )
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt naming
        """Paint the gap background and one rectangle per segment."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        painter.fillRect(rect, QColor(GAP_COLOR))
        for bar in segment_bars(self.memory):
            left = rect.left() + bar["start_fraction"] * rect.width()
            width = max(1.0, bar["width_fraction"] * rect.width())
            painter.fillRect(
                QRectF(left, rect.top() + 2, width, rect.height() - 4), QColor(SEGMENT_COLOR)
            )
        painter.end()


class MemoryLayoutView(ResponsiveWidget):
    """Shows the memory layout as a bar plus a segment and gap table.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        bar: The graphical address bar.
        table: The segment and gap table.
    """

    #: Emitted with the loaded memory map after every :meth:`set_memory` call.
    layout_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the heading, the bar, the summary and the table."""
        super().__init__(parent, scaler)
        self.memory = MemoryMap()

        self.bar = MemoryLayoutBar(self, self.scaler)
        self.range_label = QLabel("no firmware loaded", self)
        self.range_label.setProperty("role", "secondary")
        self.table = EnhancedTableWidget(COLUMNS, self, self.scaler)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(HeadingLabel("Memory layout", 3, self, self.scaler))
        layout.addWidget(self.bar)
        layout.addWidget(self.range_label)
        layout.addWidget(self.table, 1)

    # -- API -----------------------------------------------------------------
    def set_memory(self, memory: MemoryMap) -> None:
        """Display *memory*."""
        self.memory = memory
        self.bar.set_memory(memory)
        self.table.set_rows(segment_rows(memory), color_key="_color")
        self.range_label.setText(self.summary())
        self.layout_changed.emit(memory)

    def set_segments(self, segments: list[MemorySegment]) -> None:
        """Build a memory map from *segments* and display it."""
        memory = MemoryMap()
        memory.extend(segments)
        self.set_memory(memory)

    def clear(self) -> None:
        """Reset the view."""
        self.set_memory(MemoryMap())

    def gaps(self) -> list[MemoryGap]:
        """Return the unmapped regions of the displayed layout."""
        return self.memory.gaps()

    def summary(self) -> str:
        """Return the one line summary shown under the bar.

        Example:
            >>> # view.summary() -> '0x00000000..0x00000300, 512 B in 2 segments, 1 gap'
            >>> None
        """
        if not self.memory.segments:
            return "no firmware loaded"
        gaps = self.memory.gaps()
        return (
            f"0x{self.memory.start_address:08X}..0x{self.memory.end_address:08X}, "
            f"{human_size(self.memory.total_size)} in {len(self.memory.segments)} segment(s), "
            f"{len(gaps)} gap(s)"
        )
