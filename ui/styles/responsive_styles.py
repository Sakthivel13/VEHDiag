"""Breakpoint dependent style fragments.

The :mod:`~ui.theme_manager` builds the bulk of the stylesheet from the colour
palette.  This module adds the part of the stylesheet that depends on the
current *layout breakpoint* rather than on the theme: paddings, control heights,
table row heights and the visibility of decorative elements.

Everything in this module is pure Python and returns plain strings so it can be
unit tested without a running ``QApplication``.

Example:
    >>> from ui.responsive_layout import Breakpoint
    >>> qss = responsive_stylesheet(Breakpoint.COMPACT)
    >>> "QPushButton" in qss
    True
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..responsive_layout import Breakpoint

__all__ = [
    "METRICS",
    "ResponsiveMetrics",
    "compact_overrides",
    "control_metrics",
    "density_name",
    "responsive_stylesheet",
    "table_row_height",
]


@dataclass(frozen=True, slots=True)
class ResponsiveMetrics:
    """Pixel metrics used by the widgets of one breakpoint.

    Attributes:
        control_height: Height of buttons, combo boxes and line edits.
        padding_h: Horizontal padding inside controls.
        padding_v: Vertical padding inside controls.
        spacing: Default spacing between two widgets of a layout.
        margin: Default layout margin.
        table_row: Height of one table row.
        icon: Icon edge length.
        radius: Corner radius of controls.
        show_icon_labels: Show the text next to toolbar icons.
        show_status_details: Show the verbose status-bar sections.
    """

    control_height: int
    padding_h: int
    padding_v: int
    spacing: int
    margin: int
    table_row: int
    icon: int
    radius: int
    show_icon_labels: bool
    show_status_details: bool

    def as_dict(self) -> dict[str, Any]:
        """Return the metrics as a plain mapping.

        Example:
            >>> METRICS[Breakpoint.STANDARD].as_dict()["icon"]
            20
        """
        return asdict(self)


#: One metric set per layout breakpoint.
METRICS: dict[Breakpoint, ResponsiveMetrics] = {
    Breakpoint.COMPACT: ResponsiveMetrics(
        control_height=26,
        padding_h=8,
        padding_v=3,
        spacing=4,
        margin=6,
        table_row=22,
        icon=16,
        radius=4,
        show_icon_labels=False,
        show_status_details=False,
    ),
    Breakpoint.STANDARD: ResponsiveMetrics(
        control_height=30,
        padding_h=12,
        padding_v=5,
        spacing=8,
        margin=10,
        table_row=26,
        icon=20,
        radius=6,
        show_icon_labels=True,
        show_status_details=True,
    ),
    Breakpoint.WIDE: ResponsiveMetrics(
        control_height=34,
        padding_h=16,
        padding_v=7,
        spacing=10,
        margin=14,
        table_row=30,
        icon=22,
        radius=6,
        show_icon_labels=True,
        show_status_details=True,
    ),
    Breakpoint.ULTRA_WIDE: ResponsiveMetrics(
        control_height=38,
        padding_h=20,
        padding_v=9,
        spacing=12,
        margin=18,
        table_row=34,
        icon=26,
        radius=8,
        show_icon_labels=True,
        show_status_details=True,
    ),
}


def control_metrics(breakpoint: Breakpoint) -> ResponsiveMetrics:
    """Return the metric set of *breakpoint*.

    Args:
        breakpoint: The active layout breakpoint.

    Returns:
        The matching :class:`ResponsiveMetrics`; the standard set is used as a
        fallback for unknown values.

    Example:
        >>> control_metrics(Breakpoint.WIDE).control_height
        34
    """
    return METRICS.get(breakpoint, METRICS[Breakpoint.STANDARD])


def density_name(breakpoint: Breakpoint) -> str:
    """Return the QSS density class of *breakpoint*.

    The name is set on the main window as the ``density`` dynamic property so
    stylesheets can address it with ``*[density="compact"]``.

    Example:
        >>> density_name(Breakpoint.ULTRA_WIDE)
        'spacious'
    """
    return {
        Breakpoint.COMPACT: "compact",
        Breakpoint.STANDARD: "standard",
        Breakpoint.WIDE: "comfortable",
        Breakpoint.ULTRA_WIDE: "spacious",
    }.get(breakpoint, "standard")


def table_row_height(breakpoint: Breakpoint, scale: float = 1.0) -> int:
    """Return the scaled table row height for *breakpoint*.

    Args:
        breakpoint: The active layout breakpoint.
        scale: DPI scale factor from :class:`~ui.dpi_scaler.DPIScaler`.

    Example:
        >>> table_row_height(Breakpoint.COMPACT)
        22
        >>> table_row_height(Breakpoint.COMPACT, 2.0)
        44
    """
    return int(round(control_metrics(breakpoint).table_row * max(0.5, scale)))


def responsive_stylesheet(breakpoint: Breakpoint, scale: float = 1.0) -> str:
    """Return the QSS fragment that adapts the widgets to *breakpoint*.

    The fragment is appended to the theme stylesheet produced by
    :class:`~ui.theme_manager.ThemeManager`, so it only contains geometric
    rules and never colours.

    Args:
        breakpoint: The active layout breakpoint.
        scale: DPI scale factor applied to every pixel value.

    Returns:
        A QSS string.

    Example:
        >>> "min-height" in responsive_stylesheet(Breakpoint.STANDARD)
        True
    """
    m = control_metrics(breakpoint)
    px = lambda value: int(round(value * max(0.5, scale)))  # noqa: E731 - local shorthand
    parts = [
        f"/* responsive fragment: {density_name(breakpoint)} */",
        "QPushButton, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {",
        f"    min-height: {px(m.control_height)}px;",
        f"    padding: {px(m.padding_v)}px {px(m.padding_h)}px;",
        f"    border-radius: {px(m.radius)}px;",
        "}",
        "QToolButton {",
        f"    padding: {px(m.padding_v)}px {px(m.padding_v)}px;",
        f"    border-radius: {px(m.radius)}px;",
        "}",
        "QGroupBox {",
        f"    margin-top: {px(m.margin)}px;",
        f"    padding: {px(m.margin)}px;",
        f"    border-radius: {px(m.radius)}px;",
        "}",
        "QTableWidget, QTableView, QTreeView {",
        f"    gridline-width: 1px;",
        "}",
        "QHeaderView::section {",
        f"    padding: {px(m.padding_v)}px {px(m.padding_h)}px;",
        "}",
        "QTabBar::tab {",
        f"    padding: {px(m.padding_v)}px {px(m.padding_h)}px;",
        f"    min-height: {px(m.control_height - 4)}px;",
        "}",
        "QScrollBar:vertical, QScrollBar:horizontal {",
        f"    width: {px(m.icon // 2 + 4)}px;",
        f"    height: {px(m.icon // 2 + 4)}px;",
        "}",
    ]
    if not m.show_status_details:
        parts += compact_overrides().splitlines()
    return "\n".join(parts) + "\n"


def compact_overrides() -> str:
    """Return the extra rules applied on narrow screens.

    Example:
        >>> "StatusDetail" in compact_overrides()
        True
    """
    return (
        "QLabel#StatusDetail { qproperty-visible: false; }\n"
        "QWidget#SidePanel { max-width: 220px; }\n"
    )
