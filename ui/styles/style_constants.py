"""Colour, spacing, typography and animation constants."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

#: Base spacing unit; every margin and padding is a multiple of it.
SPACING_UNIT = 4


def parse_hex(colour: str) -> tuple[int, int, int]:
    """Return the ``(r, g, b)`` components of a ``#RRGGBB`` string.

    Args:
        colour: Hexadecimal colour, with or without the leading ``#``.

    Returns:
        The three 0..255 components.

    Example:
        >>> parse_hex("#1E1E2E")
        (30, 30, 46)
        >>> parse_hex("fff")
        (255, 255, 255)
    """
    text = colour.lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def to_hex(rgb: tuple[int, int, int]) -> str:
    """Return the ``#RRGGBB`` string for *rgb*.

    Example:
        >>> to_hex((30, 30, 46))
        '#1E1E2E'
    """
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, int(round(v)))) for v in rgb))


def blend(base: str, other: str, weight: float) -> str:
    """Linearly blend *base* towards *other*.

    Args:
        base: The starting colour.
        other: The colour blended in.
        weight: Fraction of *other*, clamped to ``0.0``..``1.0``.

    Example:
        >>> blend("#000000", "#FFFFFF", 0.5)
        '#808080'
        >>> blend("#1E1E2E", "#FFFFFF", 0.0)
        '#1E1E2E'
    """
    ratio = max(0.0, min(1.0, weight))
    a, b = parse_hex(base), parse_hex(other)
    return to_hex(tuple(a[i] + (b[i] - a[i]) * ratio for i in range(3)))


def relative_luminance(colour: str) -> float:
    """Return the WCAG relative luminance of *colour* in ``0.0``..``1.0``.

    Example:
        >>> round(relative_luminance("#000000"), 3)
        0.0
        >>> round(relative_luminance("#FFFFFF"), 3)
        1.0
        >>> relative_luminance("#1E1E2E") < 0.1
        True
    """

    def channel(value: int) -> float:
        """Return the linearised value of one 0..255 channel."""
        srgb = value / 255.0
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in parse_hex(colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio between two colours.

    A ratio of 4.5 is the AA threshold for body text, 3.0 for large text.

    Example:
        >>> round(contrast_ratio("#FFFFFF", "#000000"), 1)
        21.0
        >>> contrast_ratio("#F8FAFC", "#1E1E2E") > 4.5
        True
    """
    a, b = relative_luminance(foreground), relative_luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


class Spacing:
    """Named spacing values in design pixels."""

    NONE = 0
    XXS = SPACING_UNIT          # 4
    XS = SPACING_UNIT * 2       # 8
    SM = SPACING_UNIT * 3       # 12
    MD = SPACING_UNIT * 4       # 16
    LG = SPACING_UNIT * 6       # 24
    XL = SPACING_UNIT * 8       # 32
    XXL = SPACING_UNIT * 12     # 48


class Radius:
    """Named corner radii in design pixels."""

    NONE = 0
    SM = 4
    MD = 6
    LG = 10
    XL = 16
    PILL = 999


class Duration:
    """Animation durations in milliseconds."""

    INSTANT = 0
    FAST = 120
    NORMAL = 200
    SLOW = 320
    TOAST = 4000


class ZIndex:
    """Stacking order of overlay elements."""

    BASE = 0
    PANEL = 10
    DROPDOWN = 100
    DIALOG = 500
    TOAST = 900
    TOOLTIP = 1000


@dataclass(frozen=True, slots=True)
class ColorPalette:
    """A complete colour palette for one theme."""

    name: str
    background: str
    surface: str
    surface_alt: str
    primary: str
    secondary: str
    success: str
    warning: str
    error: str
    info: str
    text_primary: str
    text_secondary: str
    text_disabled: str
    border: str
    border_focus: str
    selection: str
    tx: str
    rx: str

    def mix(self, other: str, weight: float) -> str:
        """Blend this palette's background with *other*.

        Used to derive elevation and hover tints that stay in-family instead
        of introducing new hard-coded colours.

        Args:
            other: Hexadecimal colour to blend towards.
            weight: Fraction of *other* in the result, ``0.0``..``1.0``.

        Returns:
            The blended colour as ``#RRGGBB``.

        Example:
            >>> DARK_PALETTE.mix("#FFFFFF", 0.0)
            '#1E1E2E'
            >>> DARK_PALETTE.mix("#FFFFFF", 1.0)
            '#FFFFFF'
        """
        return blend(self.background, other, weight)

    def elevate(self, level: int = 1) -> str:
        """Return a surface colour *level* steps above the background.

        Real tools convey depth with luminance, not with borders everywhere.

        Example:
            >>> DARK_PALETTE.elevate(0)
            '#1E1E2E'
            >>> DARK_PALETTE.elevate(2) != DARK_PALETTE.elevate(1)
            True
        """
        target = "#FFFFFF" if self.is_dark else "#0F172A"
        return blend(self.background, target, min(0.30, 0.045 * max(0, level)))

    @property
    def is_dark(self) -> bool:
        """Return ``True`` when the palette has a dark background.

        Example:
            >>> DARK_PALETTE.is_dark, LIGHT_PALETTE.is_dark
            (True, False)
        """
        return relative_luminance(self.background) < 0.4

    @property
    def hover(self) -> str:
        """Return the hover tint for interactive surfaces."""
        return blend(self.surface_alt, "#FFFFFF" if self.is_dark else "#000000", 0.07)

    @property
    def pressed(self) -> str:
        """Return the pressed tint for interactive surfaces."""
        return blend(self.surface_alt, "#000000" if self.is_dark else "#FFFFFF", 0.12)

    @property
    def border_subtle(self) -> str:
        """Return a low-contrast border used for internal separators."""
        return blend(self.background, self.border, 0.55)

    @property
    def overlay(self) -> str:
        """Return the scrim colour used behind modal dialogs."""
        return "#000000" if self.is_dark else "#0F172A"

    def on(self, colour: str) -> str:
        """Return the readable foreground for a filled *colour*.

        The choice maximises the WCAG contrast ratio rather than guessing from
        a luminance threshold, so amber and cyan accents stay legible.

        Example:
            >>> DARK_PALETTE.on("#7C3AED")
            '#FFFFFF'
            >>> DARK_PALETTE.on("#F59E0B")
            '#101014'
            >>> DARK_PALETTE.on("#22C55E")
            '#101014'
        """
        dark, light = "#101014", "#FFFFFF"
        return dark if contrast_ratio(dark, colour) >= contrast_ratio(light, colour) else light

    def as_dict(self) -> dict[str, str]:
        """Return the palette as a mapping for QSS templating."""
        return {
            "name": self.name,
            "background": self.background,
            "surface": self.surface,
            "surface_alt": self.surface_alt,
            "primary": self.primary,
            "secondary": self.secondary,
            "success": self.success,
            "warning": self.warning,
            "error": self.error,
            "info": self.info,
            "text_primary": self.text_primary,
            "text_secondary": self.text_secondary,
            "text_disabled": self.text_disabled,
            "border": self.border,
            "border_focus": self.border_focus,
            "selection": self.selection,
            "tx": self.tx,
            "rx": self.rx,
            # -- derived refinement tokens ---------------------------------
            "elevated_1": self.elevate(1),
            "elevated_2": self.elevate(2),
            "elevated_3": self.elevate(3),
            "hover": self.hover,
            "pressed": self.pressed,
            "border_subtle": self.border_subtle,
            "on_primary": self.on(self.primary),
            "on_success": self.on(self.success),
            "on_warning": self.on(self.warning),
            "on_error": self.on(self.error),
            "primary_hover": blend(self.primary, "#FFFFFF", 0.14),
            "primary_press": blend(self.primary, "#000000", 0.16),
            "error_hover": blend(self.error, "#FFFFFF", 0.14),
            "success_hover": blend(self.success, "#FFFFFF", 0.14),
            "primary_soft": blend(self.background, self.primary, 0.22),
            "success_soft": blend(self.background, self.success, 0.18),
            "warning_soft": blend(self.background, self.warning, 0.18),
            "error_soft": blend(self.background, self.error, 0.18),
            "info_soft": blend(self.background, self.info, 0.18),
        }


#: The default dark palette specified by the design.
DARK_PALETTE = ColorPalette(
    name="dark",
    background="#1E1E2E",
    surface="#282840",
    surface_alt="#31314D",
    primary="#7C3AED",
    secondary="#06B6D4",
    success="#22C55E",
    warning="#F59E0B",
    error="#EF4444",
    info="#38BDF8",
    text_primary="#F8FAFC",
    text_secondary="#94A3B8",
    text_disabled="#64748B",
    border="#374151",
    border_focus="#7C3AED",
    selection="#4C1D95",
    tx="#38BDF8",
    rx="#22C55E",
)

#: The light palette.
LIGHT_PALETTE = ColorPalette(
    name="light",
    background="#F8FAFC",
    surface="#FFFFFF",
    surface_alt="#F1F5F9",
    primary="#7C3AED",
    secondary="#0891B2",
    success="#16A34A",
    warning="#D97706",
    error="#DC2626",
    info="#0284C7",
    text_primary="#1E293B",
    text_secondary="#64748B",
    text_disabled="#94A3B8",
    border="#E2E8F0",
    border_focus="#7C3AED",
    selection="#DDD6FE",
    tx="#0284C7",
    rx="#16A34A",
)

#: The high contrast palette used for accessibility.
HIGH_CONTRAST_PALETTE = ColorPalette(
    name="high_contrast",
    background="#000000",
    surface="#0A0A0A",
    surface_alt="#141414",
    primary="#FFFF00",
    secondary="#00FFFF",
    success="#00FF00",
    warning="#FFAA00",
    error="#FF3333",
    info="#00CCFF",
    text_primary="#FFFFFF",
    text_secondary="#E0E0E0",
    text_disabled="#909090",
    border="#FFFFFF",
    border_focus="#FFFF00",
    selection="#333300",
    tx="#00FFFF",
    rx="#00FF00",
)

#: All bundled palettes keyed by their name.
PALETTES: dict[str, ColorPalette] = {
    "dark": DARK_PALETTE,
    "light": LIGHT_PALETTE,
    "high_contrast": HIGH_CONTRAST_PALETTE,
}


class FontRole(str, Enum):
    """Semantic font roles and their multiplier of the base size."""

    HEADING_1 = "HEADING_1"
    HEADING_2 = "HEADING_2"
    HEADING_3 = "HEADING_3"
    BODY = "BODY"
    BODY_SMALL = "BODY_SMALL"
    MONOSPACE = "MONOSPACE"
    BUTTON = "BUTTON"
    LABEL = "LABEL"
    STATUS = "STATUS"

    @property
    def multiplier(self) -> float:
        """Return the multiplier applied to the base font size."""
        return {
            FontRole.HEADING_1: 1.8,
            FontRole.HEADING_2: 1.4,
            FontRole.HEADING_3: 1.2,
            FontRole.BODY: 1.0,
            FontRole.BODY_SMALL: 0.9,
            FontRole.MONOSPACE: 1.0,
            FontRole.BUTTON: 1.0,
            FontRole.LABEL: 0.95,
            FontRole.STATUS: 0.85,
        }[self]


#: Status colours used by the LED indicators, keyed by a semantic state name.
STATE_COLORS: dict[str, str] = {
    "idle": "#64748B",
    "running": "#38BDF8",
    "pass": "#22C55E",
    "fail": "#EF4444",
    "error": "#DC2626",
    "skipped": "#F59E0B",
    "cancelled": "#F59E0B",
    "connected": "#22C55E",
    "disconnected": "#64748B",
    "warning": "#F59E0B",
    "locked": "#EF4444",
    "unlocked": "#22C55E",
}


def state_color(state: str, palette: ColorPalette = DARK_PALETTE) -> str:
    """Return the colour for a semantic *state* name, taken from *palette*.

    The colour is resolved from the palette rather than a fixed table, so an
    LED indicator or a status dot follows the active theme instead of staying
    dark-theme green on a white panel.

    Args:
        state: Semantic state such as ``pass``, ``fail`` or ``connected``.
        palette: Palette to resolve against.

    Returns:
        A hexadecimal colour; the secondary text colour for unknown states.

    Example:
        >>> state_color("pass") == DARK_PALETTE.success
        True
        >>> state_color("pass", LIGHT_PALETTE) == LIGHT_PALETTE.success
        True
        >>> state_color("unknown") == DARK_PALETTE.text_secondary
        True
    """
    mapping = {
        "idle": palette.text_disabled,
        "running": palette.info,
        "connecting": palette.info,
        "pass": palette.success,
        "ok": palette.success,
        "fail": palette.error,
        "error": palette.error,
        "skipped": palette.warning,
        "cancelled": palette.warning,
        "warning": palette.warning,
        "connected": palette.success,
        "disconnected": palette.text_disabled,
        "locked": palette.error,
        "unlocked": palette.success,
    }
    return mapping.get(state.strip().lower(), palette.text_secondary)


__all__ = [
    "SPACING_UNIT",
    "Spacing",
    "Radius",
    "Duration",
    "ZIndex",
    "ColorPalette",
    "DARK_PALETTE",
    "LIGHT_PALETTE",
    "HIGH_CONTRAST_PALETTE",
    "PALETTES",
    "FontRole",
    "STATE_COLORS",
    "state_color",
]
