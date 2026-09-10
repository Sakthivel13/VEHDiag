"""Multi-monitor, geometry persistence and DPI change handling."""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.utils.file_utils import load_json, save_json
from src.utils.platform_utils import app_data_dir

from .dpi_scaler import DPIScaler, ScreenMetrics

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WindowGeometry:
    """Persisted window position, size and state.

    Attributes:
        x: Left position in pixels.
        y: Top position in pixels.
        width: Window width.
        height: Window height.
        maximized: The window was maximised.
        screen: Name of the screen the window was on.
        panel_sizes: Sizes of the splitters keyed by splitter name.
    """

    x: int = 100
    y: int = 100
    width: int = 1440
    height: int = 900
    maximized: bool = False
    screen: str = ""
    panel_sizes: dict[str, list[int]] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return the geometry as a JSON serialisable mapping."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WindowGeometry":
        """Build a geometry from its serialised representation."""
        return cls(
            x=int(data.get("x", 100)),
            y=int(data.get("y", 100)),
            width=int(data.get("width", 1440)),
            height=int(data.get("height", 900)),
            maximized=bool(data.get("maximized", False)),
            screen=str(data.get("screen", "")),
            panel_sizes=data.get("panel_sizes") or {},
        )


class ScreenManager:
    """Detects screens, computes window sizes and persists the geometry.

    Args:
        scaler: DPI scaler kept in sync with the active screen.
        state_file: File the geometry is stored in.

    Example:
        >>> from ui.dpi_scaler import DPIScaler
        >>> manager = ScreenManager(DPIScaler(), state_file="/tmp/vdp_geometry.json")
        >>> geometry = manager.default_geometry()
        >>> geometry.width > 0 and geometry.height > 0
        True
    """

    def __init__(self, scaler: DPIScaler | None = None, state_file: str | Path | None = None) -> None:
        """Create the manager and locate the geometry file."""
        self.scaler = scaler or DPIScaler()
        self.state_file = Path(state_file) if state_file else app_data_dir() / "window_state.json"
        self.screens: list[ScreenMetrics] = []
        self.refresh()

    # -- detection ----------------------------------------------------------
    def refresh(self) -> list[ScreenMetrics]:
        """Re-detect the connected screens."""
        self.screens = self._detect()
        return self.screens

    def _detect(self) -> list[ScreenMetrics]:
        """Return the metrics of every connected screen."""
        try:
            from PySide6.QtGui import QGuiApplication
        except ImportError:  # pragma: no cover - headless
            return [ScreenMetrics()]
        application = QGuiApplication.instance()
        if application is None:
            return [ScreenMetrics()]
        result: list[ScreenMetrics] = []
        for screen in QGuiApplication.screens():
            geometry = screen.geometry()
            result.append(
                ScreenMetrics(
                    width=geometry.width(),
                    height=geometry.height(),
                    dpi=float(screen.logicalDotsPerInch()),
                    device_pixel_ratio=float(screen.devicePixelRatio()),
                    name=screen.name() or "screen",
                )
            )
        return result or [ScreenMetrics()]

    @property
    def primary(self) -> ScreenMetrics:
        """Return the metrics of the primary screen."""
        return self.screens[0] if self.screens else ScreenMetrics()

    @property
    def screen_count(self) -> int:
        """Return the number of connected screens."""
        return len(self.screens)

    def find_screen(self, name: str) -> ScreenMetrics | None:
        """Return the screen called *name*, or ``None``."""
        for metrics in self.screens:
            if metrics.name == name:
                return metrics
        return None

    # -- geometry ---------------------------------------------------------------
    def default_geometry(self, maximized: bool = True) -> WindowGeometry:
        """Return the geometry used when nothing has been persisted yet.

        A diagnostics tool is a workspace application: the operator wants the
        trace, the service panels and the log visible at once, so the window
        starts maximised. The stored width and height are still a sensible
        80% of the screen, which is what the window restores to when it is
        un-maximised.

        Args:
            maximized: Start the window maximised.

        Returns:
            The default :class:`WindowGeometry`.

        Example:
            >>> ScreenManager().default_geometry().maximized
            True
            >>> ScreenManager().default_geometry(maximized=False).maximized
            False
        """
        screen = self.primary
        width = max(1024, int(screen.width * 0.8))
        height = max(640, int(screen.height * 0.8))
        return WindowGeometry(
            x=(screen.width - width) // 2,
            y=(screen.height - height) // 2,
            width=width,
            height=height,
            maximized=maximized,
            screen=screen.name,
        )

    def load_geometry(self) -> WindowGeometry:
        """Load the persisted geometry, falling back to the default."""
        data = load_json(self.state_file, default=None)
        if not data:
            return self.default_geometry()
        geometry = WindowGeometry.from_dict(data)
        return geometry if self.is_visible(geometry) else self.default_geometry()

    def save_geometry(self, geometry: WindowGeometry) -> Path:
        """Persist *geometry* to disk."""
        return save_json(self.state_file, geometry.as_dict())

    def is_visible(self, geometry: WindowGeometry) -> bool:
        """Return ``True`` when the window would be at least partly on screen."""
        for screen in self.screens:
            if (
                geometry.x < screen.width
                and geometry.y < screen.height
                and geometry.x + geometry.width > 0
                and geometry.y + geometry.height > 0
            ):
                return True
        return False

    # -- Qt helpers --------------------------------------------------------------
    def apply_to_window(self, window: Any, geometry: WindowGeometry | None = None) -> None:
        """Apply a geometry to a ``QMainWindow``.

        The normal geometry is always set first so the window has something
        sensible to restore to, then the maximised state is applied through
        :meth:`setWindowState`. Calling ``showMaximized()`` on a window that
        has not been shown yet is ignored by some platforms, whereas the
        window state survives the later ``show()``.

        Args:
            window: The window to position.
            geometry: Geometry to apply; the persisted one when omitted.
        """
        from PySide6.QtCore import Qt

        target = geometry or self.load_geometry()
        window.setGeometry(target.x, target.y, target.width, target.height)
        if target.maximized:
            window.setWindowState(window.windowState() | Qt.WindowState.WindowMaximized)
        else:
            window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMaximized)

    def capture_from_window(self, window: Any) -> WindowGeometry:
        """Read the current geometry from a ``QMainWindow``."""
        rectangle = window.geometry()
        screen_name = ""
        handle = getattr(window, "screen", None)
        if callable(handle):
            screen = handle()
            if screen is not None:
                screen_name = screen.name()
        return WindowGeometry(
            x=rectangle.x(),
            y=rectangle.y(),
            width=rectangle.width(),
            height=rectangle.height(),
            maximized=bool(window.isMaximized()),
            screen=screen_name,
        )

    def handle_screen_change(self, screen: Any | None = None) -> bool:
        """Update the scaler after the window moved to another screen.

        Returns:
            ``True`` when the DPI scale changed.
        """
        new_scaler = DPIScaler.from_screen(screen)
        return self.scaler.update(new_scaler.metrics)

    def describe(self) -> list[str]:
        """Return one description line per connected screen."""
        return [f"{metrics.name}: {metrics.label}" for metrics in self.screens]


__all__ = ["ScreenManager", "WindowGeometry"]
