"""Base class for every custom widget of the platform."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import ColorPalette, DARK_PALETTE, FontRole

_logger = logging.getLogger(__name__)


class ResponsiveWidget(QWidget):
    """A DPI aware, theme aware base widget.

    Every custom widget inherits from this class so it automatically receives
    the shared :class:`DPIScaler`, reacts to theme changes and exposes a
    ``resized`` signal the layout engine can listen to.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler; a default one is created when omitted.
        palette: Colour palette used for custom painting.
    """

    #: Emitted with ``(width, height)`` whenever the widget is resized.
    resized = Signal(int, int)
    #: Emitted after the theme was applied.
    theme_applied = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        palette: ColorPalette | None = None,
    ) -> None:
        """Create the widget and store the scaler and palette."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.color_palette = palette or DARK_PALETTE
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    # -- scaling helpers ----------------------------------------------------
    def px(self, value: float) -> int:
        """Return *value* scaled to device pixels."""
        return self.scaler.px(value)

    def spacing(self, value: float = 8) -> int:
        """Return a scaled spacing value."""
        return self.scaler.spacing(value)

    def font_size(self, role: FontRole = FontRole.BODY) -> int:
        """Return the scaled font size for *role*."""
        from ..font_manager import FontManager

        return FontManager(self.scaler).size(role)

    def apply_font(self, role: FontRole = FontRole.BODY, bold: bool = False) -> None:
        """Apply the font of *role* to this widget."""
        from ..font_manager import FontManager

        font = FontManager(self.scaler).qfont(role, bold)
        if font is not None:
            self.setFont(font)

    # -- theme ---------------------------------------------------------------
    def apply_theme(self, palette: ColorPalette) -> None:
        """Store *palette* and let subclasses repaint."""
        self.color_palette = palette
        self.on_theme_changed(palette)
        self.update()
        self.theme_applied.emit(palette.name)

    def on_theme_changed(self, palette: ColorPalette) -> None:
        """Hook invoked after a theme change; override to repaint."""

    def apply_scale(self, scaler: DPIScaler) -> None:
        """Store a new *scaler* and let subclasses resize their content."""
        self.scaler = scaler
        self.on_scale_changed(scaler)
        self.updateGeometry()

    def on_scale_changed(self, scaler: DPIScaler) -> None:
        """Hook invoked after a DPI change; override to resize content."""

    # -- Qt overrides ----------------------------------------------------------
    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt naming
        """Emit :attr:`resized` after the widget geometry changed."""
        super().resizeEvent(event)
        self.resized.emit(self.width(), self.height())

    def set_accessible(self, name: str, description: str = "") -> None:
        """Set the accessible name and description for screen readers."""
        self.setAccessibleName(name)
        if description:
            self.setAccessibleDescription(description)
            self.setToolTip(description)

    def set_property_and_refresh(self, name: str, value: Any) -> None:
        """Set a dynamic QSS property and force a style refresh."""
        self.setProperty(name, value)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()


__all__ = ["ResponsiveWidget"]
