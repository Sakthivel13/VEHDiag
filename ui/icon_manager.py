"""SVG icon loading, caching and recolouring."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

#: Directory holding the bundled SVG icons.
ICON_DIR = Path(__file__).parent / "resources" / "icons"

#: Icons used by the toolbar in display order.
TOOLBAR_ICONS: tuple[str, ...] = (
    "connect",
    "disconnect",
    "play",
    "run_all",
    "cancel",
    "developer",
    "log",
    "convert",
    "settings",
    "theme",
)


class IconManager:
    """Loads SVG icons, recolours them and caches the results.

    Because the icons are stroke based and use ``currentColor``, recolouring is
    a simple text substitution, which keeps them crisp at any DPI.

    Args:
        scaler: DPI scaler used to size the rendered pixmaps.
        color: Default stroke colour.
        icon_dir: Directory holding the SVG files.

    Example:
        >>> manager = IconManager()
        >>> "svg" in manager.svg_source("play")
        True
        >>> manager.available()[:2]
        ['add', 'app_icon']
    """

    def __init__(
        self,
        scaler: Any | None = None,
        color: str = "#F8FAFC",
        icon_dir: str | Path | None = None,
    ) -> None:
        """Create the manager with an empty cache."""
        from .dpi_scaler import DPIScaler

        self.scaler = scaler or DPIScaler()
        self.color = color
        self.icon_dir = Path(icon_dir) if icon_dir else ICON_DIR
        self._source_cache: dict[str, str] = {}
        self._icon_cache: dict[tuple[str, str, int], Any] = {}

    # -- sources ------------------------------------------------------------
    def available(self) -> list[str]:
        """Return the names of every bundled icon."""
        if not self.icon_dir.is_dir():
            return []
        return sorted(path.stem for path in self.icon_dir.glob("*.svg"))

    def path(self, name: str) -> Path:
        """Return the file path of the icon called *name*."""
        return self.icon_dir / f"{name}.svg"

    def svg_source(self, name: str, color: str | None = None) -> str:
        """Return the SVG markup of *name* recoloured to *color*.

        Returns an empty string when the icon does not exist.
        """
        if name not in self._source_cache:
            file_path = self.path(name)
            if not file_path.is_file():
                _logger.debug("icon %r not found in %s", name, self.icon_dir)
                return ""
            self._source_cache[name] = file_path.read_text(encoding="utf-8")
        source = self._source_cache[name]
        return source.replace("currentColor", color or self.color)

    # -- Qt integration --------------------------------------------------------
    def icon(self, name: str, color: str | None = None, size: int = 20) -> Any:
        """Return a ``QIcon`` for *name*, cached per colour and size."""
        key = (name, color or self.color, self.scaler.icon(size))
        if key in self._icon_cache:
            return self._icon_cache[key]
        try:
            from PySide6.QtCore import QByteArray, QSize
            from PySide6.QtGui import QIcon, QPixmap
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtGui import QPainter
        except ImportError:  # pragma: no cover - headless
            return None
        markup = self.svg_source(name, color)
        if not markup:
            return QIcon()
        renderer = QSvgRenderer(QByteArray(markup.encode("utf-8")))
        edge = self.scaler.icon(size)
        pixmap = QPixmap(QSize(edge, edge))
        pixmap.fill(0)  # transparent
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        result = QIcon(pixmap)
        self._icon_cache[key] = result
        return result

    def pixmap(self, name: str, color: str | None = None, size: int = 20) -> Any:
        """Return a ``QPixmap`` for *name*."""
        icon = self.icon(name, color, size)
        if icon is None:
            return None
        edge = self.scaler.icon(size)
        from PySide6.QtCore import QSize

        return icon.pixmap(QSize(edge, edge))

    def set_color(self, color: str) -> None:
        """Change the default colour and drop the cached icons."""
        self.color = color
        self._icon_cache.clear()

    def invalidate(self) -> None:
        """Drop every cached icon (after a DPI or theme change)."""
        self._icon_cache.clear()

    def write_placeholder(self, name: str, body: str) -> Path:
        """Create a new icon file, used when a plugin ships its own icon."""
        markup = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
            'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>\n'
        )
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markup, encoding="utf-8")
        self._source_cache.pop(name, None)
        return target


__all__ = ["IconManager", "ICON_DIR", "TOOLBAR_ICONS"]
