"""DPI and breakpoint aware font management."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dpi_scaler import DPIScaler
from .styles.style_constants import FontRole

_logger = logging.getLogger(__name__)

#: Base font size in points per screen width breakpoint.
BASE_SIZES: tuple[tuple[int, int], ...] = (
    (2560, 16),
    (1920, 14),
    (1366, 13),
    (0, 11),
)

#: Font files bundled with the application.
BUNDLED_FONTS: tuple[str, ...] = (
    "Roboto-Regular.ttf",
    "Roboto-Bold.ttf",
    "Roboto-Light.ttf",
    "RobotoMono-Regular.ttf",
    "RobotoMono-Bold.ttf",
)


def base_size_for_width(width: int) -> int:
    """Return the base font size in points for a screen *width*.

    Example:
        >>> base_size_for_width(1280)
        11
        >>> base_size_for_width(1920)
        14
        >>> base_size_for_width(3840)
        16
    """
    for threshold, size in BASE_SIZES:
        if width >= threshold:
            return size
    return BASE_SIZES[-1][1]


@dataclass(slots=True)
class FontSpec:
    """A concrete font description.

    Attributes:
        family: Font family name.
        size_pt: Size in points after scaling.
        bold: Use the bold weight.
        italic: Use the italic style.
    """

    family: str
    size_pt: int
    bold: bool = False
    italic: bool = False

    def to_css(self) -> str:
        """Return the CSS fragment describing the font."""
        weight = "600" if self.bold else "400"
        style = "italic" if self.italic else "normal"
        return f"font-family:'{self.family}'; font-size:{self.size_pt}pt; font-weight:{weight}; font-style:{style};"


class FontManager:
    """Provides scaled fonts for every semantic role.

    Args:
        scaler: DPI scaler used to convert point sizes.
        family: Proportional font family.
        monospace_family: Monospace family used for hexadecimal data.
        resource_dir: Directory holding the bundled ``.ttf`` files.

    Example:
        >>> from ui.dpi_scaler import DPIScaler
        >>> manager = FontManager(DPIScaler())
        >>> manager.size(FontRole.BODY) > 0
        True
        >>> manager.size(FontRole.HEADING_1) > manager.size(FontRole.BODY)
        True
    """

    def __init__(
        self,
        scaler: DPIScaler | None = None,
        family: str = "Roboto",
        monospace_family: str = "Roboto Mono",
        resource_dir: str | Path | None = None,
    ) -> None:
        """Create the manager and remember the requested families."""
        self.scaler = scaler or DPIScaler()
        self.family = family
        self.monospace_family = monospace_family
        self.resource_dir = (
            Path(resource_dir) if resource_dir else Path(__file__).parent / "resources" / "fonts"
        )
        self.base_pt = base_size_for_width(self.scaler.metrics.width)
        self.loaded_families: list[str] = []

    # -- sizing -------------------------------------------------------------
    def size(self, role: FontRole = FontRole.BODY) -> int:
        """Return the scaled point size for *role*."""
        return self.scaler.font(self.base_pt * role.multiplier)

    def spec(self, role: FontRole = FontRole.BODY, bold: bool = False) -> FontSpec:
        """Return a :class:`FontSpec` for *role*."""
        family = self.monospace_family if role is FontRole.MONOSPACE else self.family
        return FontSpec(
            family=family,
            size_pt=self.size(role),
            bold=bold or role in (FontRole.HEADING_1, FontRole.HEADING_2),
        )

    def update_for_width(self, width: int) -> bool:
        """Recompute the base size for a new window width.

        Returns:
            ``True`` when the base size changed.
        """
        new_base = base_size_for_width(width)
        changed = new_base != self.base_pt
        self.base_pt = new_base
        return changed

    def set_base_size(self, size_pt: int) -> None:
        """Override the base font size chosen by the breakpoint logic."""
        self.base_pt = max(8, min(24, size_pt))

    # -- Qt integration ---------------------------------------------------------
    def qfont(self, role: FontRole = FontRole.BODY, bold: bool = False) -> Any:
        """Return a ``QFont`` for *role* (or a :class:`FontSpec` when headless)."""
        spec = self.spec(role, bold)
        try:
            from PySide6.QtGui import QFont
        except ImportError:  # pragma: no cover - headless
            return spec
        font = QFont(spec.family, spec.size_pt)
        font.setBold(spec.bold)
        font.setItalic(spec.italic)
        if role is FontRole.MONOSPACE:
            font.setStyleHint(QFont.StyleHint.Monospace)
        return font

    def load_bundled_fonts(self) -> list[str]:
        """Register the bundled ``.ttf`` files with Qt.

        Returns:
            The families that were registered successfully.
        """
        try:
            from PySide6.QtGui import QFontDatabase
        except ImportError:  # pragma: no cover - headless
            return []
        families: list[str] = []
        for name in BUNDLED_FONTS:
            path = self.resource_dir / name
            if not path.is_file():
                continue
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id >= 0:
                families.extend(QFontDatabase.applicationFontFamilies(font_id))
        self.loaded_families = sorted(set(families))
        if self.loaded_families:
            _logger.info("loaded bundled fonts: %s", ", ".join(self.loaded_families))
        return self.loaded_families

    def apply_to_application(self, application: Any | None = None) -> None:
        """Set the body font as the default application font."""
        target = application
        if target is None:
            try:
                from PySide6.QtWidgets import QApplication

                target = QApplication.instance()
            except ImportError:  # pragma: no cover
                return
        if target is not None:
            target.setFont(self.qfont(FontRole.BODY))

    def describe(self) -> dict[str, Any]:
        """Return a mapping of every role and its resulting size."""
        return {
            "family": self.family,
            "monospace": self.monospace_family,
            "base_pt": self.base_pt,
            "scale": self.scaler.scale,
            "sizes": {role.value: self.size(role) for role in FontRole},
        }


__all__ = ["FontManager", "FontSpec", "BASE_SIZES", "BUNDLED_FONTS", "base_size_for_width"]
