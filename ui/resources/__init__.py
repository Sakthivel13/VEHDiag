"""Bundled UI resources (icons, fonts and Qt resource bundles).

The package exposes the on-disk locations of the shipped assets so that other
modules never have to build paths by hand.

Example:
    >>> from ui.resources import ICONS_DIR
    >>> ICONS_DIR.name
    'icons'
"""
from __future__ import annotations

from pathlib import Path

#: Directory holding this package.
RESOURCES_DIR = Path(__file__).resolve().parent

#: Directory holding the shipped SVG icons.
ICONS_DIR = RESOURCES_DIR / "icons"

#: Directory holding the bundled font files.
FONTS_DIR = RESOURCES_DIR / "fonts"

#: Directory holding raster images such as the splash screen.
IMAGES_DIR = RESOURCES_DIR / "images"

#: The compiled Qt resource collection, when it has been generated.
QRC_FILE = RESOURCES_DIR / "resources.qrc"


def icon_path(name: str) -> Path:
    """Return the absolute path of the SVG icon called *name*.

    Args:
        name: Icon name with or without the ``.svg`` suffix.

    Returns:
        The path of the icon file (which may not exist).

    Example:
        >>> icon_path("play").suffix
        '.svg'
    """
    return ICONS_DIR / (name if name.endswith(".svg") else f"{name}.svg")


def available_icons() -> list[str]:
    """Return the sorted names of every shipped icon, without the suffix."""
    if not ICONS_DIR.is_dir():
        return []
    return sorted(path.stem for path in ICONS_DIR.glob("*.svg"))


__all__ = [
    "FONTS_DIR",
    "ICONS_DIR",
    "IMAGES_DIR",
    "QRC_FILE",
    "RESOURCES_DIR",
    "available_icons",
    "icon_path",
]
