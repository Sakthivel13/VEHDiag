"""DPI aware scaling of fonts, spacing, icons and widget sizes."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

_logger = logging.getLogger(__name__)

#: Reference DPI: every base size in the code assumes this density.
BASELINE_DPI = 96.0

#: Scale factors are clamped to this range to keep the layout usable.
MIN_SCALE = 0.75
MAX_SCALE = 3.0


@dataclass(slots=True)
class ScreenMetrics:
    """Physical properties of one screen.

    Attributes:
        width: Horizontal resolution in pixels.
        height: Vertical resolution in pixels.
        dpi: Logical dots per inch reported by the platform.
        device_pixel_ratio: Ratio between device and logical pixels.
        name: Human readable screen name.
    """

    width: int = 1920
    height: int = 1080
    dpi: float = BASELINE_DPI
    device_pixel_ratio: float = 1.0
    name: str = "primary"

    @property
    def scale(self) -> float:
        """Return the scale factor relative to :data:`BASELINE_DPI`."""
        return max(MIN_SCALE, min(MAX_SCALE, self.dpi / BASELINE_DPI))

    @property
    def is_high_dpi(self) -> bool:
        """Return ``True`` for displays denser than 120 DPI."""
        return self.dpi > 120.0

    @property
    def label(self) -> str:
        """Return ``"1920x1080 @ 96 DPI (100%)"`` for the settings panel."""
        return f"{self.width}x{self.height} @ {self.dpi:.0f} DPI ({self.scale * 100:.0f}%)"


class DPIScaler:
    """Convert design-time sizes into device pixels.

    Every hard-coded pixel value in the UI goes through this class, so the
    application scales correctly from 1280x720 at 100% up to 4K at 200%.

    Example:
        >>> scaler = DPIScaler(ScreenMetrics(dpi=144))
        >>> scaler.scale
        1.5
        >>> scaler.px(16)
        24
        >>> scaler.font(13)
        20
    """

    def __init__(self, metrics: ScreenMetrics | None = None) -> None:
        """Create the scaler for the given screen metrics."""
        self.metrics = metrics or ScreenMetrics()
        self._user_factor = 1.0

    # -- factors ------------------------------------------------------------
    @property
    def scale(self) -> float:
        """Return the effective scale factor including the user override."""
        return round(self.metrics.scale * self._user_factor, 4)

    def set_user_factor(self, factor: float) -> None:
        """Apply an additional user chosen zoom factor."""
        self._user_factor = max(0.5, min(2.0, factor))

    def update(self, metrics: ScreenMetrics) -> bool:
        """Apply new screen metrics; return ``True`` when the scale changed."""
        previous = self.scale
        self.metrics = metrics
        return abs(previous - self.scale) > 1e-6

    # -- scalar helpers --------------------------------------------------------
    def px(self, value: float) -> int:
        """Scale a pixel value, rounding to the nearest device pixel."""
        return max(1, int(round(value * self.scale)))

    def font(self, base_pt: float) -> int:
        """Scale a font size in points."""
        return max(6, int(round(base_pt * self.scale)))

    def spacing(self, base_px: float = 8) -> int:
        """Scale a spacing/margin value."""
        return self.px(base_px)

    def radius(self, base_px: float = 6) -> int:
        """Scale a corner radius."""
        return self.px(base_px)

    def border(self, base_px: float = 1) -> int:
        """Scale a border width, never returning zero."""
        return max(1, int(round(base_px * self.scale)))

    def icon(self, base_px: float = 20) -> int:
        """Scale an icon edge length."""
        return self.px(base_px)

    def size(self, width: float, height: float) -> tuple[int, int]:
        """Scale a widget size and return ``(width, height)``."""
        return self.px(width), self.px(height)

    # -- Qt helpers -------------------------------------------------------------
    def qsize(self, width: float, height: float) -> Any:
        """Return a scaled ``QSize`` when PySide6 is available."""
        try:
            from PySide6.QtCore import QSize
        except ImportError:  # pragma: no cover - headless environments
            return self.size(width, height)
        return QSize(*self.size(width, height))

    def qmargins(self, left: float, top: float, right: float, bottom: float) -> Any:
        """Return scaled ``QMargins`` when PySide6 is available."""
        try:
            from PySide6.QtCore import QMargins
        except ImportError:  # pragma: no cover
            return (self.px(left), self.px(top), self.px(right), self.px(bottom))
        return QMargins(self.px(left), self.px(top), self.px(right), self.px(bottom))

    @classmethod
    def from_screen(cls, screen: Any | None = None) -> "DPIScaler":
        """Build a scaler from a ``QScreen`` (or the primary screen)."""
        metrics = ScreenMetrics()
        try:
            from PySide6.QtGui import QGuiApplication

            target = screen or QGuiApplication.primaryScreen()
            if target is not None:
                geometry = target.geometry()
                metrics = ScreenMetrics(
                    width=geometry.width(),
                    height=geometry.height(),
                    dpi=float(target.logicalDotsPerInch()),
                    device_pixel_ratio=float(target.devicePixelRatio()),
                    name=target.name() or "primary",
                )
        except Exception:  # noqa: BLE001 - headless fallback
            _logger.debug("no Qt screen available; using default metrics")
        return cls(metrics)

    def describe(self) -> dict[str, Any]:
        """Return a mapping shown in the display settings panel."""
        return {
            "screen": self.metrics.label,
            "scale": f"{self.scale * 100:.0f}%",
            "device_pixel_ratio": self.metrics.device_pixel_ratio,
            "high_dpi": self.metrics.is_high_dpi,
            "base_spacing_px": self.spacing(8),
            "base_font_px": self.font(13),
        }

    def __repr__(self) -> str:  # noqa: D105 - trivial
        return f"<DPIScaler {self.metrics.label} factor={self.scale}>"


__all__ = ["DPIScaler", "ScreenMetrics", "BASELINE_DPI", "MIN_SCALE", "MAX_SCALE"]
