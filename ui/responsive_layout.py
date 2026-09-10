"""Breakpoint based responsive layout engine."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

_logger = logging.getLogger(__name__)


class Breakpoint(str, Enum):
    """Layout breakpoints derived from the window width."""

    COMPACT = "COMPACT"
    STANDARD = "STANDARD"
    WIDE = "WIDE"
    ULTRA_WIDE = "ULTRA_WIDE"

    @property
    def columns(self) -> int:
        """Return the number of content columns for this breakpoint."""
        return {
            Breakpoint.COMPACT: 1,
            Breakpoint.STANDARD: 2,
            Breakpoint.WIDE: 3,
            Breakpoint.ULTRA_WIDE: 4,
        }[self]

    @property
    def label(self) -> str:
        """Return the label shown in the status bar."""
        return self.value.replace("_", " ").title()


#: Lower bound (inclusive) of each breakpoint in logical pixels.
BREAKPOINT_WIDTHS: tuple[tuple[int, Breakpoint], ...] = (
    (2560, Breakpoint.ULTRA_WIDE),
    (1920, Breakpoint.WIDE),
    (1366, Breakpoint.STANDARD),
    (0, Breakpoint.COMPACT),
)


@dataclass(slots=True)
class PanelVisibility:
    """Which optional panels are shown at a given breakpoint.

    .. note::
       Since the navigation moved entirely into the two rows of top tabs the
       main window no longer owns a navigation sidebar, an analysis sidebar or
       a log dock, so these flags are advisory only.  They are kept because
       plugins and embedded views still use them to decide how much chrome
       they can afford, and because they describe the breakpoints faithfully.
    """

    navigation: bool = True
    analysis: bool = True
    log: bool = True

    def as_dict(self) -> dict[str, bool]:
        """Return the visibility flags as a mapping."""
        return {"navigation": self.navigation, "analysis": self.analysis, "log": self.log}


#: Default panel visibility per breakpoint.
DEFAULT_VISIBILITY: dict[Breakpoint, PanelVisibility] = {
    Breakpoint.COMPACT: PanelVisibility(navigation=False, analysis=False, log=True),
    Breakpoint.STANDARD: PanelVisibility(navigation=True, analysis=False, log=True),
    Breakpoint.WIDE: PanelVisibility(navigation=True, analysis=True, log=True),
    Breakpoint.ULTRA_WIDE: PanelVisibility(navigation=True, analysis=True, log=True),
}


@dataclass(slots=True)
class LayoutSpec:
    """Concrete layout parameters for one breakpoint.

    Attributes:
        breakpoint: The active breakpoint.
        columns: Number of content columns.
        navigation_width: Advisory width for an optional navigation sidebar.
        analysis_width: Advisory width for an optional analysis sidebar.
        log_height: Advisory height for an embedded log view.
        content_margin: Margin around the central content.
        spacing: Spacing between widgets.
        visibility: Which optional panels are shown.
    """

    breakpoint: Breakpoint
    columns: int
    navigation_width: int
    analysis_width: int
    log_height: int
    content_margin: int
    spacing: int
    visibility: PanelVisibility

    @property
    def compact_tabs(self) -> bool:
        """Whether section tabs should collapse to icons at this breakpoint."""
        return self.breakpoint is Breakpoint.COMPACT

    def as_dict(self) -> dict[str, Any]:
        """Return the specification as a mapping for the controllers."""
        return {
            "breakpoint": self.breakpoint.value,
            "compact_tabs": self.compact_tabs,
            "columns": self.columns,
            "navigation_width": self.navigation_width,
            "analysis_width": self.analysis_width,
            "log_height": self.log_height,
            "content_margin": self.content_margin,
            "spacing": self.spacing,
            **self.visibility.as_dict(),
        }


def classify_width(width: int) -> Breakpoint:
    """Return the breakpoint matching a window *width*.

    Example:
        >>> classify_width(1280).value
        'COMPACT'
        >>> classify_width(1920).value
        'WIDE'
        >>> classify_width(3840).value
        'ULTRA_WIDE'
    """
    for threshold, breakpoint in BREAKPOINT_WIDTHS:
        if width >= threshold:
            return breakpoint
    return Breakpoint.COMPACT


class ResponsiveLayout:
    """Computes the layout parameters for the current window size.

    Args:
        scaler: DPI scaler used to convert the logical sizes.
        debounce_px: Minimum width change before a recalculation happens.

    Example:
        >>> from ui.dpi_scaler import DPIScaler
        >>> layout = ResponsiveLayout(DPIScaler())
        >>> spec = layout.compute(1920)
        >>> spec.breakpoint.value, spec.columns
        ('WIDE', 3)
    """

    def __init__(self, scaler: Any, debounce_px: int = 24) -> None:
        """Create the layout engine."""
        self.scaler = scaler
        self.debounce_px = debounce_px
        self.current: Breakpoint = Breakpoint.STANDARD
        self._last_width = 0
        self._listeners: list[Callable[[LayoutSpec], None]] = []

    def compute(self, width: int, height: int = 0) -> LayoutSpec:
        """Return the :class:`LayoutSpec` for a window of *width* pixels."""
        breakpoint = classify_width(width)
        visibility = DEFAULT_VISIBILITY[breakpoint]
        base_nav = {Breakpoint.COMPACT: 0, Breakpoint.STANDARD: 200,
                    Breakpoint.WIDE: 240, Breakpoint.ULTRA_WIDE: 280}[breakpoint]
        base_analysis = {Breakpoint.COMPACT: 0, Breakpoint.STANDARD: 0,
                         Breakpoint.WIDE: 320, Breakpoint.ULTRA_WIDE: 380}[breakpoint]
        base_log = {Breakpoint.COMPACT: 140, Breakpoint.STANDARD: 180,
                    Breakpoint.WIDE: 220, Breakpoint.ULTRA_WIDE: 260}[breakpoint]
        base_margin = 8 if breakpoint is Breakpoint.COMPACT else 12
        return LayoutSpec(
            breakpoint=breakpoint,
            columns=breakpoint.columns,
            navigation_width=self.scaler.px(base_nav),
            analysis_width=self.scaler.px(base_analysis),
            log_height=self.scaler.px(base_log),
            content_margin=self.scaler.px(base_margin),
            spacing=self.scaler.spacing(8),
            visibility=visibility,
        )

    def on_resize(self, width: int, height: int = 0) -> LayoutSpec | None:
        """Handle a resize event, debounced and breakpoint aware.

        Returns:
            The new :class:`LayoutSpec` when a recalculation happened, else
            ``None``.
        """
        if abs(width - self._last_width) < self.debounce_px:
            return None
        self._last_width = width
        spec = self.compute(width, height)
        changed = spec.breakpoint is not self.current
        self.current = spec.breakpoint
        if changed:
            _logger.debug("breakpoint changed to %s at %d px", spec.breakpoint.value, width)
            for listener in list(self._listeners):
                try:
                    listener(spec)
                except Exception:  # noqa: BLE001
                    _logger.exception("layout listener failed")
        return spec

    def add_listener(self, listener: Callable[[LayoutSpec], None]) -> None:
        """Register a callback invoked when the breakpoint changes."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[LayoutSpec], None]) -> None:
        """Remove a previously registered callback."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def minimum_window_size(self) -> tuple[int, int]:
        """Return the smallest usable window size in device pixels."""
        return self.scaler.px(1024), self.scaler.px(640)

    def recommended_window_size(self, screen_width: int, screen_height: int) -> tuple[int, int]:
        """Return 80% of the screen, clamped to the minimum size."""
        minimum = self.minimum_window_size()
        return (
            max(minimum[0], int(screen_width * 0.8)),
            max(minimum[1], int(screen_height * 0.8)),
        )


__all__ = [
    "Breakpoint",
    "BREAKPOINT_WIDTHS",
    "DEFAULT_VISIBILITY",
    "LayoutSpec",
    "PanelVisibility",
    "ResponsiveLayout",
    "classify_width",
]
