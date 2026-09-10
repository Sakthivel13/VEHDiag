"""Stylesheet helpers: palettes, constants and responsive fragments.

The package groups everything the theme engine needs:

* :mod:`~ui.styles.style_constants` — the colour palettes required by the
  design specification, spacing/radius scales and the font role table,
* :mod:`~ui.styles.responsive_styles` — the breakpoint dependent QSS fragment,
* the shipped ``*.qss`` files used as the base of each theme.

Example:
    >>> from ui.styles import DARK_PALETTE, qss_file
    >>> DARK_PALETTE.background
    '#1E1E2E'
    >>> qss_file("dark").name
    'dark_theme.qss'
"""
from __future__ import annotations

from pathlib import Path

from .responsive_styles import (
    METRICS,
    ResponsiveMetrics,
    control_metrics,
    density_name,
    responsive_stylesheet,
    table_row_height,
)
from .style_constants import (
    DARK_PALETTE,
    HIGH_CONTRAST_PALETTE,
    LIGHT_PALETTE,
    PALETTES,
    ColorPalette,
    Duration,
    FontRole,
    Radius,
    Spacing,
    state_color,
)

#: Directory containing the shipped QSS files.
STYLES_DIR = Path(__file__).resolve().parent

#: Mapping of theme name to the QSS file that seeds it.
QSS_FILES: dict[str, str] = {
    "dark": "dark_theme.qss",
    "light": "light_theme.qss",
    "high_contrast": "high_contrast.qss",
}


def qss_file(theme: str) -> Path:
    """Return the path of the base QSS file of *theme*.

    Args:
        theme: Theme name (``dark``, ``light`` or ``high_contrast``).

    Returns:
        The path of the stylesheet; the dark theme is used as a fallback.

    Example:
        >>> qss_file("unknown").name
        'dark_theme.qss'
    """
    return STYLES_DIR / QSS_FILES.get(theme, QSS_FILES["dark"])


def custom_widget_qss(palette: ColorPalette | None = None) -> str:
    """Return the custom widget rules, coloured for *palette*.

    The fragment is appended after the generated theme, so it must be built
    from the active palette. A static file with literal colours would win the
    cascade and repaint every accent button violet on the high contrast theme.

    Args:
        palette: Palette to colour the fragment with; the active one when
            omitted.

    Returns:
        A QSS fragment styling the dynamic properties of the custom widgets.

    Example:
        >>> qss = custom_widget_qss(HIGH_CONTRAST_PALETTE)
        >>> HIGH_CONTRAST_PALETTE.primary in qss
        True
        >>> "#7C3AED" in custom_widget_qss(HIGH_CONTRAST_PALETTE)
        False
    """
    from .semantic_colors import active_palette

    c = (palette or active_palette()).as_dict()
    return f"""
/* ---- custom widget dynamic properties (theme: {c['name']}) --------------- */
*[state="success"], *[state="ok"], *[state="pass"] {{ color: {c['success']}; }}
*[state="warning"] {{ color: {c['warning']}; }}
*[state="error"], *[state="fail"] {{ color: {c['error']}; }}
*[state="idle"] {{ color: {c['text_secondary']}; }}
*[state="running"] {{ color: {c['secondary']}; }}
*[state="active"] {{ color: {c['text_primary']}; font-weight: 600; }}

QLineEdit[valid="false"] {{ border-color: {c['error']}; background-color: {c['error_soft']}; }}
QLineEdit[valid="true"] {{ border-color: {c['success']}; }}

QFrame#Toast[level="success"] {{ border-left: 3px solid {c['success']}; }}
QFrame#Toast[level="warning"] {{ border-left: 3px solid {c['warning']}; }}
QFrame#Toast[level="error"] {{ border-left: 3px solid {c['error']}; }}
QFrame#Toast[level="info"] {{ border-left: 3px solid {c['info']}; }}

QToolButton#SectionHeader {{
    background: transparent;
    border: none;
    font-weight: 600;
    text-align: left;
}}
QToolButton#SectionHeader:hover {{ color: {c['primary']}; }}

QFrame#ServiceCard[status="RUNNING"] {{ border-left: 3px solid {c['secondary']}; }}
QFrame#ServiceCard[status="PASS"] {{ border-left: 3px solid {c['success']}; }}
QFrame#ServiceCard[status="FAIL"] {{ border-left: 3px solid {c['error']}; }}
QFrame#ServiceCard[status="ERROR"] {{ border-left: 3px solid {c['error']}; }}
QFrame#ServiceCard[status="SKIPPED"] {{ border-left: 3px solid {c['text_secondary']}; }}
QFrame#ServiceCard[dragging="true"] {{ border: 1px dashed {c['primary']}; }}

QProgressBar[state="ok"]::chunk {{ background-color: {c['success']}; }}
QProgressBar[state="warning"]::chunk {{ background-color: {c['warning']}; }}
QProgressBar[state="error"]::chunk {{ background-color: {c['error']}; }}

QLabel#StatusDetail {{ color: {c['text_secondary']}; }}
"""


__all__ = [
    "ColorPalette",
    "DARK_PALETTE",
    "Duration",
    "FontRole",
    "HIGH_CONTRAST_PALETTE",
    "LIGHT_PALETTE",
    "METRICS",
    "PALETTES",
    "QSS_FILES",
    "Radius",
    "ResponsiveMetrics",
    "STYLES_DIR",
    "Spacing",
    "control_metrics",
    "custom_widget_qss",
    "density_name",
    "qss_file",
    "responsive_stylesheet",
    "state_color",
    "table_row_height",
]
