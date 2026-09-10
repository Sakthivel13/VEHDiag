"""Theme-aware semantic colours for panel painting.

Panels must never hard-code a hexadecimal colour. A literal such as
``#22C55E`` is readable on the dark background but collapses to roughly 2:1
contrast on the light one, so a table that looks fine in the dark theme
becomes unreadable the moment the operator switches.

This module owns the *current* palette and resolves a semantic name - ``ok``,
``warning``, ``tx``, ``rx`` - to a colour that is guaranteed legible against
the active background.

Example:
    >>> from ui.styles.semantic_colors import set_active_palette, semantic
    >>> from ui.styles.style_constants import DARK_PALETTE, LIGHT_PALETTE
    >>> _ = set_active_palette(DARK_PALETTE)
    >>> semantic("error") == DARK_PALETTE.error
    True
    >>> _ = set_active_palette(LIGHT_PALETTE)
    >>> semantic("error") == LIGHT_PALETTE.error
    True
    >>> _ = set_active_palette(DARK_PALETTE)
"""
from __future__ import annotations

from typing import Iterable

from .style_constants import (
    DARK_PALETTE,
    ColorPalette,
    blend,
    contrast_ratio,
    relative_luminance,
)

__all__ = [
    "MIN_CONTRAST",
    "active_palette",
    "readable",
    "semantic",
    "series_colors",
    "set_active_palette",
    "severity_color",
    "status_color",
]

#: Minimum contrast ratio a painted colour must reach against the background.
#:
#: 3.0 is the WCAG AA threshold for large text and graphical objects, which is
#: what table cells, plot lines and status dots are.
MIN_CONTRAST = 3.0

#: The palette every lookup resolves against.
_ACTIVE: ColorPalette = DARK_PALETTE


def set_active_palette(palette: ColorPalette) -> ColorPalette:
    """Make *palette* the one semantic lookups resolve against.

    :class:`~ui.theme_manager.ThemeManager` calls this on every theme change,
    so panels repainting afterwards pick up the new colours automatically.

    Args:
        palette: The palette of the theme that was just applied.

    Returns:
        The palette that was installed.
    """
    global _ACTIVE
    _ACTIVE = palette
    return _ACTIVE


def active_palette() -> ColorPalette:
    """Return the palette currently used for semantic lookups."""
    return _ACTIVE


def readable(colour: str, background: str | None = None, minimum: float = MIN_CONTRAST) -> str:
    """Darken or lighten *colour* until it is legible on *background*.

    The hue is preserved; only the lightness moves, so a warning stays amber
    and a success stays green while becoming readable on a white panel.

    Args:
        colour: The desired colour.
        background: Surface it is painted on; the active background when
            omitted.
        minimum: Contrast ratio to reach.

    Returns:
        The adjusted colour, or the original when it already passes.

    Example:
        >>> from ui.styles.style_constants import LIGHT_PALETTE, contrast_ratio
        >>> fixed = readable("#22C55E", LIGHT_PALETTE.background)
        >>> contrast_ratio(fixed, LIGHT_PALETTE.background) >= 3.0
        True
        >>> readable("#000000", "#FFFFFF")
        '#000000'
    """
    surface = background or _ACTIVE.background
    if contrast_ratio(colour, surface) >= minimum:
        return colour
    # Move away from the background: darken on light surfaces, lighten on dark.
    target = "#000000" if relative_luminance(surface) > 0.4 else "#FFFFFF"
    best = colour
    for step in range(1, 21):
        candidate = blend(colour, target, step * 0.05)
        best = candidate
        if contrast_ratio(candidate, surface) >= minimum:
            return candidate
    return best


def semantic(name: str, background: str | None = None) -> str:
    """Return the legible colour for the semantic *name*.

    Args:
        name: One of ``ok``/``success``, ``warning``, ``error``/``fail``,
            ``info``, ``primary``, ``secondary``/``muted``, ``tx``, ``rx``,
            ``idle``, ``running``, ``border`` or ``text``.
        background: Surface the colour is painted on.

    Returns:
        A hexadecimal colour that clears :data:`MIN_CONTRAST`.

    Example:
        >>> semantic("nonsense") == active_palette().text_primary
        True
    """
    palette = _ACTIVE
    table = {
        "ok": palette.success,
        "success": palette.success,
        "pass": palette.success,
        "warning": palette.warning,
        "pending": palette.warning,
        "error": palette.error,
        "fail": palette.error,
        "confirmed": palette.error,
        "info": palette.info,
        "primary": palette.primary,
        "accent": palette.primary,
        "secondary": palette.text_secondary,
        "muted": palette.text_secondary,
        "idle": palette.text_secondary,
        "clean": palette.success,
        "running": palette.secondary,
        "tx": palette.tx,
        "rx": palette.rx,
        "border": palette.border,
        "text": palette.text_primary,
    }
    colour = table.get(name.lower(), palette.text_primary)
    # Borders are decorative, not text: they may stay low contrast.
    if name.lower() == "border":
        return colour
    return readable(colour, background)


def severity_color(severity: str, background: str | None = None) -> str:
    """Return the colour for a DTC severity class.

    Example:
        >>> severity_color("confirmed") == semantic("error")
        True
    """
    return semantic(severity, background)


def status_color(status: str, background: str | None = None) -> str:
    """Return the colour for a test or transfer status.

    Example:
        >>> status_color("PASS") == semantic("success")
        True
    """
    return semantic(status, background)


def series_colors(count: int, background: str | None = None) -> list[str]:
    """Return *count* distinguishable, legible plot colours.

    Args:
        count: How many series need a colour.
        background: Surface the chart is painted on.

    Returns:
        A list of hexadecimal colours, cycling when *count* exceeds the base
        set.

    Example:
        >>> len(series_colors(8))
        8
        >>> series_colors(1)[0] == semantic("primary")
        True
    """
    palette = _ACTIVE
    base: Iterable[str] = (
        palette.primary,
        palette.secondary,
        palette.success,
        palette.warning,
        palette.error,
        palette.info,
        palette.text_secondary,
    )
    cycle = list(base)
    return [readable(cycle[i % len(cycle)], background) for i in range(max(0, count))]
