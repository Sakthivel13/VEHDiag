"""Appearance and responsiveness settings page.

Covers the theme, the accent colour, the font families and the base font size,
plus the DPI and layout behaviour described by the design specification: the
font breakpoints (<1366 px small, 1366-1920 medium, 1920-2560 large, >2560
extra large) and the layout breakpoints of the same widths.

Example:
    >>> from ui.panels.settings_panel.display_settings import (
    ...     SETTINGS, THEMES, paths, preview_text)
    >>> THEMES
    ('dark', 'light', 'high_contrast')
    >>> "ui.theme" in paths()
    True
    >>> preview_text("dark")
    'Dark theme: background #1E1E2E, primary #7C3AED'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from src.core.configuration_manager import ConfigurationManager

from ...dpi_scaler import DPIScaler
from ...styles.style_constants import PALETTES
from .general_settings import SettingSpec, SettingsPage

__all__ = ["ProfileNames", "DisplaySettingsPage", "SETTINGS", "THEMES", "paths", "preview_text"]

#: Themes offered by the theme drop-down.
THEMES: tuple[str, ...] = ("dark", "light", "high_contrast")

#: Named DPI scaling profiles offered next to the automatic detection.
ProfileNames: tuple[str, ...] = ("auto", "100%", "125%", "150%", "175%", "200%")

#: Every setting shown on the display page.
SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec("ui.theme", "Theme", "choice", choices=THEMES),
    SettingSpec("ui.accent_color", "Accent colour", tooltip="Hexadecimal colour, e.g. #7C3AED."),
    SettingSpec("ui.font_family", "Font family"),
    SettingSpec("ui.monospace_family", "Monospace family"),
    SettingSpec("ui.base_font_pt", "Base font size", "int", minimum=8, maximum=24, suffix=" pt"),
    SettingSpec("ui.dpi_profile", "DPI scaling", "choice", choices=ProfileNames),
    SettingSpec("ui.remember_geometry", "Remember window geometry", "bool"),
    SettingSpec(
        "ui.start_maximized",
        "Start maximised",
        "bool",
        tooltip="Open the main window filling the screen, which is what a\n"
        "diagnostics workspace normally wants.",
    ),
    SettingSpec("ui.show_splash", "Show the splash screen", "bool"),
    SettingSpec("ui.animations_enabled", "Enable animations", "bool"),
    SettingSpec("ui.compact_mode", "Force the compact layout", "bool"),
    SettingSpec(
        "ui.toast_timeout_ms", "Toast timeout", "int",
        minimum=1000, maximum=20000, suffix=" ms",
    ),
    SettingSpec(
        "ui.table_row_height", "Table row height", "int",
        minimum=16, maximum=48, suffix=" px",
    ),
)


def paths() -> list[str]:
    """Return every configuration path edited by this page.

    Example:
        >>> "ui.base_font_pt" in paths()
        True
    """
    return [spec.path for spec in SETTINGS]


def preview_text(theme: str) -> str:
    """Return the one line description of *theme* shown under the selector.

    Args:
        theme: A key of :data:`~ui.styles.style_constants.PALETTES`.

    Example:
        >>> preview_text("nope")
        'unknown theme'
    """
    palette = PALETTES.get(theme)
    if palette is None:
        return "unknown theme"
    label = theme.replace("_", " ").title()
    return f"{label} theme: background {palette.background}, primary {palette.primary}"


class DisplaySettingsPage(SettingsPage):
    """The appearance settings page.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        config: Configuration manager backing the editors.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        config: ConfigurationManager | None = None,
    ) -> None:
        """Build the page from :data:`SETTINGS`."""
        super().__init__(SETTINGS, "Appearance", parent, scaler, config)

    def theme(self) -> str:
        """Return the theme currently selected on the page."""
        return str(self.values().get("ui.theme", "dark"))

    def preview(self) -> str:
        """Return the preview text of the selected theme."""
        return preview_text(self.theme())
