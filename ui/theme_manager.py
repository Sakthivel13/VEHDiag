"""Theme management: palette selection and QSS generation.

The manager generates the whole stylesheet from a :class:`ColorPalette` and the
DPI scaler, so a theme change or a DPI change simply regenerates the QSS and
re-applies it - no restart required.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.core.event_bus import EventBus, EventType, get_event_bus

from .dpi_scaler import DPIScaler
from .styles.style_constants import (
    PALETTES,
    ColorPalette,
    DARK_PALETTE,
    Radius,
    Spacing,
)

_logger = logging.getLogger(__name__)


class ThemeManager:
    """Builds and applies the application stylesheet.

    Args:
        scaler: DPI scaler used to size borders, radii and padding.
        event_bus: Bus used to announce theme changes.
        theme: Initial theme name (``dark``, ``light`` or ``high_contrast``).

    Example:
        >>> from ui.dpi_scaler import DPIScaler
        >>> manager = ThemeManager(DPIScaler())
        >>> "QWidget" in manager.stylesheet()
        True
        >>> manager.set_theme("light")
        >>> manager.palette.name
        'light'
    """

    def __init__(
        self,
        scaler: DPIScaler | None = None,
        event_bus: EventBus | None = None,
        theme: str = "dark",
    ) -> None:
        """Create the manager with the requested theme."""
        self.scaler = scaler or DPIScaler()
        self.bus = event_bus or get_event_bus()
        self.palette: ColorPalette = PALETTES.get(theme, DARK_PALETTE)
        self.accent_override: str = ""
        self._cache: str = ""
        self._install_palette()

    # -- theme selection ----------------------------------------------------
    @property
    def theme_name(self) -> str:
        """Return the name of the active theme."""
        return self.palette.name

    def available_themes(self) -> list[str]:
        """Return the names of the bundled themes."""
        return sorted(PALETTES)

    def _install_palette(self) -> None:
        """Publish the active palette to the semantic colour service.

        Panels paint through :mod:`ui.styles.semantic_colors`, so this has to
        happen before any repaint or a table would keep the previous theme's
        colours.
        """
        from .styles.semantic_colors import set_active_palette

        set_active_palette(self.palette)

    def set_theme(self, name: str) -> None:
        """Activate the theme called *name* and publish the change."""
        palette = PALETTES.get(name)
        if palette is None:
            _logger.warning("unknown theme %r; keeping %s", name, self.palette.name)
            return
        self.palette = palette
        self._cache = ""
        self._install_palette()
        self.bus.publish(EventType.UI_THEME_CHANGED, {"theme": name}, "ThemeManager")

    def toggle(self) -> str:
        """Switch between the dark and the light theme."""
        self.set_theme("light" if self.palette.name == "dark" else "dark")
        return self.palette.name

    def set_accent(self, color: str) -> None:
        """Override the primary accent colour."""
        self.accent_override = color
        self._cache = ""
        self.bus.publish(EventType.UI_THEME_CHANGED, {"accent": color}, "ThemeManager")

    @property
    def accent(self) -> str:
        """Return the effective accent colour."""
        return self.accent_override or self.palette.primary

    def colors(self) -> dict[str, str]:
        """Return the palette (with the accent override) as a mapping."""
        values = self.palette.as_dict()
        values["primary"] = self.accent
        values["border_focus"] = self.accent
        return values

    # -- stylesheet ----------------------------------------------------------
    def stylesheet(self, extra: str = "") -> str:
        """Return the complete QSS for the active theme and DPI."""
        if not self._cache:
            self._cache = self._build()
        return self._cache + ("\n" + extra if extra else "")

    def apply(self, application: Any | None = None, extra: str = "") -> str:
        """Apply the stylesheet to *application* and return the QSS text."""
        qss = self.stylesheet(extra)
        target = application
        if target is None:
            try:
                from PySide6.QtWidgets import QApplication

                target = QApplication.instance()
            except ImportError:  # pragma: no cover - headless
                target = None
        if target is not None:
            target.setStyleSheet(qss)
        return qss

    def invalidate(self) -> None:
        """Drop the cached stylesheet (after a DPI change)."""
        self._cache = ""

    def load_qss_file(self, path: str | Path) -> str:
        """Read an additional QSS file and append it to the stylesheet."""
        file_path = Path(path).expanduser()
        if not file_path.is_file():
            return ""
        return file_path.read_text(encoding="utf-8")

    # -- generation -----------------------------------------------------------
    def _build(self) -> str:
        """Generate the QSS from the palette and the scaler.

        The stylesheet follows a few deliberate rules that separate a
        professional engineering tool from a hobby project:

        * **Depth comes from luminance, not outlines.** Panels are raised with
          :meth:`ColorPalette.elevate` and only separated by hairline borders
          where a real edge exists.
        * **One accent.** Violet marks the primary action and the active
          selection; everything else is neutral so status colours stand out.
        * **Consistent 4 px rhythm.** Every padding, radius and gap is a
          multiple of the base unit, scaled for the current DPI.
        * **Visible focus.** Keyboard focus always draws a ring, which is a
          hard requirement for bench work with gloves on a laptop trackpad.
        """
        c = self.colors()
        s = self.scaler
        # -- rhythm ----------------------------------------------------------
        pad_v, pad_h = s.px(6), s.px(14)
        radius = s.radius(Radius.MD)
        radius_sm = s.radius(Radius.SM)
        radius_lg = s.px(10)
        border = s.border(1)
        gap = s.spacing(Spacing.XS)
        control_h = s.px(30)
        row_h = s.px(26)
        header_h = s.px(30)
        mono = '"JetBrains Mono", "Roboto Mono", "DejaVu Sans Mono", "Consolas", monospace'
        # Navigation type sizes follow the documented font roles: the
        # workspace row uses BODY (x1.0), the section row and the breadcrumb
        # use BODY_SMALL (x0.9), so the hierarchy survives every breakpoint.
        from .font_manager import FontManager
        from .styles.style_constants import FontRole

        fonts = FontManager(s)
        body = fonts.size(FontRole.BODY)
        small = fonts.size(FontRole.BODY_SMALL)
        return f"""
/* ============================================================================
 * Vehicle Diagnostics Platform - {c['name']} theme
 * Generated at DPI scale {s.scale:.2f}. Do not edit by hand.
 * ==========================================================================*/

/* ---- base ---------------------------------------------------------------- */
QWidget {{
    background-color: {c['background']};
    color: {c['text_primary']};
    selection-background-color: {c['primary']};
    selection-color: {c['on_primary']};
}}
QMainWindow, QDialog {{ background-color: {c['background']}; }}
QWidget:disabled {{ color: {c['text_disabled']}; }}

/* ---- typography ---------------------------------------------------------- */
/* No min-height here: QFormLayout sizes a row from its tallest item, and a
 * forced label height makes short rows overlap on compact screens. */
QLabel {{ background: transparent; }}
QLabel[role="heading"] {{ color: {c['text_primary']}; font-weight: 600; }}
QLabel[role="secondary"] {{ color: {c['text_secondary']}; }}
QLabel[role="mono"] {{ font-family: {mono}; }}
QLabel[role="caption"] {{
    color: {c['text_secondary']};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* ---- containers ---------------------------------------------------------- */
QGroupBox {{
    background-color: {c['elevated_1']};
    border: {border}px solid {c['border_subtle']};
    border-radius: {radius_lg}px;
    margin-top: {s.px(14)}px;
    padding: {s.px(14)}px {s.px(12)}px {s.px(12)}px {s.px(12)}px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {s.px(12)}px;
    padding: 0 {s.px(6)}px;
    color: {c['text_secondary']};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QFrame#Card {{
    background-color: {c['elevated_1']};
    border: {border}px solid {c['border_subtle']};
    border-radius: {radius_lg}px;
}}
QFrame[role="separator"], QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    background: {c['border_subtle']};
    border: none;
    max-height: {border}px;
}}

/* ---- buttons ------------------------------------------------------------- */
QPushButton {{
    background-color: {c['elevated_2']};
    color: {c['text_primary']};
    border: {border}px solid {c['border_subtle']};
    border-radius: {radius_sm}px;
    padding: {pad_v}px {pad_h}px;
    min-height: {control_h}px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {c['hover']};
    border-color: {c['border']};
}}
QPushButton:pressed {{ background-color: {c['pressed']}; }}
QPushButton:focus {{ border: {s.px(2)}px solid {c['border_focus']}; outline: none; }}
QPushButton:disabled {{
    background-color: {c['elevated_1']};
    color: {c['text_disabled']};
    border-color: {c['border_subtle']};
}}
QPushButton[accent="true"] {{
    background-color: {c['primary']};
    border-color: {c['primary']};
    color: {c['on_primary']};
    font-weight: 600;
}}
QPushButton[accent="true"]:hover {{ background-color: {c['primary_hover']}; border-color: {c['primary_hover']}; }}
QPushButton[accent="true"]:pressed {{ background-color: {c['primary_press']}; }}
QPushButton[accent="true"]:disabled {{ background-color: {c['primary_soft']}; color: {c['text_disabled']}; }}
QPushButton[danger="true"] {{
    background-color: {c['error']};
    border-color: {c['error']};
    color: {c['on_error']};
    font-weight: 600;
}}
QPushButton[danger="true"]:hover {{ background-color: {c['error_hover']}; border-color: {c['error_hover']}; }}
QPushButton[flat="true"] {{ background: transparent; border-color: transparent; }}
QPushButton[flat="true"]:hover {{ background: {c['hover']}; }}

/* ---- inputs -------------------------------------------------------------- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {c['background']};
    color: {c['text_primary']};
    border: {border}px solid {c['border']};
    border-radius: {radius_sm}px;
    padding: {s.px(5)}px {s.px(10)}px;
    min-height: {control_h}px;
    selection-background-color: {c['primary']};
    selection-color: {c['on_primary']};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border-color: {c['text_disabled']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: {s.px(2)}px solid {c['border_focus']};
    padding: {s.px(4)}px {s.px(9)}px;
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background-color: {c['elevated_1']};
    color: {c['text_disabled']};
}}
QLineEdit[valid="false"] {{ border-color: {c['error']}; background-color: {c['error_soft']}; }}
QLineEdit[valid="true"] {{ border-color: {c['success']}; }}
QLineEdit[role="mono"], QPlainTextEdit[role="mono"], QTextEdit[role="mono"] {{
    font-family: {mono};
    letter-spacing: 0.5px;
}}
QComboBox::drop-down {{
    border: none;
    width: {s.px(22)}px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}}
QComboBox QAbstractItemView {{
    background-color: {c['elevated_2']};
    border: {border}px solid {c['border']};
    border-radius: {radius_sm}px;
    padding: {s.px(4)}px;
    selection-background-color: {c['primary']};
    selection-color: {c['on_primary']};
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: transparent;
    border: none;
    width: {s.px(16)}px;
}}

/* ---- tabs: two navigation levels ---------------------------------------- */
/* Level 1 - workspaces. A solid raised bar across the top of the window. */
QTabWidget::pane {{
    border: none;
    border-top: {border}px solid {c['border_subtle']};
    background: transparent;
    top: -{border}px;
}}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent;
    color: {c['text_secondary']};
    border: none;
    border-bottom: {s.px(2)}px solid transparent;
    padding: {s.px(8)}px {s.px(16)}px;
    margin-right: {s.px(2)}px;
    font-weight: 500;
}}
QTabBar::tab:hover {{ color: {c['text_primary']}; background: {c['elevated_1']}; }}
QTabBar::tab:selected {{
    color: {c['text_primary']};
    border-bottom: {s.px(2)}px solid {c['primary']};
    font-weight: 600;
}}
QTabBar::tab:disabled {{ color: {c['text_disabled']}; }}

QTabWidget[navlevel="primary"]::pane {{
    border-top: {border}px solid {c['border']};
}}
QTabBar[navlevel="primary"] {{
    background: {c['elevated_1']};
    border-bottom: {border}px solid {c['border']};
}}
QTabBar[navlevel="primary"]::tab {{
    padding: {s.px(11)}px {s.px(22)}px;
    margin-right: 0px;
    border-bottom: {s.px(3)}px solid transparent;
    font-size: {body}pt;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
QTabBar[navlevel="primary"]::tab:hover {{ background: {c['hover']}; }}
QTabBar[navlevel="primary"]::tab:selected {{
    background: {c['surface']};
    color: {c['primary']};
    border-bottom: {s.px(3)}px solid {c['primary']};
}}

/* Level 2 - sections inside a workspace. Lighter, pill shaped, inset. */
QTabWidget[navlevel="sub"]::pane {{
    border-top: {border}px solid {c['border_subtle']};
}}
QTabBar[navlevel="sub"] {{ background: transparent; }}
QTabBar[navlevel="sub"]::tab {{
    padding: {s.px(6)}px {s.px(14)}px;
    margin: {s.px(4)}px {s.px(3)}px {s.px(6)}px 0px;
    border: {border}px solid transparent;
    border-radius: {radius_sm}px;
    color: {c['text_secondary']};
    font-size: {small}pt;
    font-weight: 500;
}}
QTabBar[navlevel="sub"]::tab:hover {{
    background: {c['hover']};
    border-color: {c['border_subtle']};
    color: {c['text_primary']};
}}
QTabBar[navlevel="sub"]::tab:selected {{
    background: {c['primary']};
    color: {c['on_primary']};
    border-color: {c['primary']};
    font-weight: 600;
}}
QTabBar[navlevel="sub"]::tab:disabled {{
    background: transparent;
    border-color: transparent;
    color: {c['text_disabled']};
}}
QTabBar::scroller {{ width: {s.px(28)}px; }}

/* ---- breadcrumb ---------------------------------------------------------- */
QLabel#Breadcrumb {{
    color: {c['text_secondary']};
    font-size: {small}pt;
    font-weight: 600;
    letter-spacing: 0.4px;
    padding: {s.px(2)}px 0px;
}}

/* ---- tables and trees ---------------------------------------------------- */
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background-color: {c['elevated_1']};
    color: {c['text_secondary']};
    border: none;
    border-bottom: {border}px solid {c['border']};
    padding: {s.px(7)}px {s.px(10)}px;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    min-height: {header_h}px;
}}
QHeaderView::section:hover {{ background-color: {c['elevated_2']}; color: {c['text_primary']}; }}
QTableView, QTreeView, QListView, QTableWidget, QListWidget {{
    background-color: {c['elevated_1']};
    alternate-background-color: {c['background']};
    border: {border}px solid {c['border_subtle']};
    border-radius: {radius}px;
    gridline-color: {c['border_subtle']};
    outline: none;
}}
QTableView::item, QTreeView::item, QListView::item {{
    padding: {s.px(4)}px {s.px(6)}px;
    min-height: {row_h}px;
    border: none;
}}
QTableView::item:hover, QTreeView::item:hover, QListView::item:hover {{
    background-color: {c['hover']};
}}
QTableView::item:selected, QTreeView::item:selected, QListView::item:selected {{
    background-color: {c['primary']};
    color: {c['on_primary']};
}}
QTreeView::branch {{ background: transparent; }}
QTableCornerButton::section {{ background: {c['elevated_1']}; border: none; }}

/* ---- scrollbars ---------------------------------------------------------- */
QScrollBar:vertical {{
    background: transparent;
    width: {s.px(12)}px;
    margin: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: {s.px(12)}px;
    margin: 0;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {c['elevated_3']};
    border-radius: {s.px(6)}px;
    min-height: {s.px(28)}px;
    min-width: {s.px(28)}px;
    margin: {s.px(2)}px;
}}
QScrollBar::handle:hover {{ background: {c['text_disabled']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- menus and toolbars -------------------------------------------------- */
QMenuBar {{
    background-color: {c['elevated_1']};
    border-bottom: {border}px solid {c['border_subtle']};
    padding: {s.px(2)}px;
}}
QMenuBar::item {{
    background: transparent;
    padding: {s.px(6)}px {s.px(12)}px;
    border-radius: {radius_sm}px;
}}
QMenuBar::item:selected {{ background: {c['hover']}; }}
QMenu {{
    background-color: {c['elevated_2']};
    border: {border}px solid {c['border']};
    border-radius: {radius}px;
    padding: {s.px(6)}px;
}}
QMenu::item {{
    padding: {s.px(7)}px {s.px(28)}px {s.px(7)}px {s.px(12)}px;
    border-radius: {radius_sm}px;
}}
QMenu::item:selected {{ background-color: {c['primary']}; color: {c['on_primary']}; }}
QMenu::separator {{
    height: {border}px;
    background: {c['border_subtle']};
    margin: {s.px(5)}px {s.px(8)}px;
}}
QToolBar {{
    background: {c['elevated_1']};
    border: none;
    border-bottom: {border}px solid {c['border_subtle']};
    padding: {s.px(5)}px {s.px(8)}px;
    spacing: {gap}px;
}}
QToolBar::separator {{
    background: {c['border_subtle']};
    width: {border}px;
    margin: {s.px(5)}px {s.px(8)}px;
}}
QToolButton {{
    background: transparent;
    border: {border}px solid transparent;
    border-radius: {radius_sm}px;
    padding: {s.px(6)}px {s.px(10)}px;
    color: {c['text_primary']};
}}
QToolButton:hover {{ background: {c['hover']}; }}
QToolButton:pressed {{ background: {c['pressed']}; }}
QToolButton:checked {{
    background: {c['primary_soft']};
    border-color: {c['primary']};
    color: {c['text_primary']};
}}

/* ---- status bar, docks, splitters ---------------------------------------- */
QStatusBar {{
    background: {c['elevated_1']};
    border-top: {border}px solid {c['border_subtle']};
    color: {c['text_secondary']};
    min-height: {s.px(26)}px;
}}
QStatusBar::item {{ border: none; }}
QDockWidget {{ color: {c['text_secondary']}; titlebar-close-icon: none; }}
QDockWidget::title {{
    background: {c['elevated_1']};
    padding: {s.px(7)}px {s.px(10)}px;
    border-bottom: {border}px solid {c['border_subtle']};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {c['primary_soft']}; }}
QSplitter::handle:horizontal {{ width: {s.px(6)}px; }}
QSplitter::handle:vertical {{ height: {s.px(6)}px; }}

/* ---- selection controls -------------------------------------------------- */
QCheckBox, QRadioButton {{ spacing: {s.px(8)}px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: {s.px(16)}px;
    height: {s.px(16)}px;
    border: {s.px(2)}px solid {c['text_disabled']};
    background: {c['background']};
}}
QCheckBox::indicator {{ border-radius: {s.px(4)}px; }}
QRadioButton::indicator {{ border-radius: {s.px(9)}px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {c['primary']}; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {c['primary']};
    border-color: {c['primary']};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    border-color: {c['border_subtle']};
    background: {c['elevated_1']};
}}

/* ---- progress ------------------------------------------------------------ */
QProgressBar {{
    background-color: {c['elevated_2']};
    border: none;
    border-radius: {s.px(5)}px;
    height: {s.px(10)}px;
    text-align: center;
    color: {c['text_secondary']};
    font-size: 11px;
}}
QProgressBar::chunk {{ background-color: {c['primary']}; border-radius: {s.px(5)}px; }}

/* ---- tooltips ------------------------------------------------------------ */
QToolTip {{
    background-color: {c['elevated_3']};
    color: {c['text_primary']};
    border: {border}px solid {c['border']};
    padding: {s.px(6)}px {s.px(10)}px;
    border-radius: {radius_sm}px;
    opacity: 240;
}}

/* ---- application specific ------------------------------------------------ */
QWidget#LedIndicator {{ background: transparent; }}
QFrame#Toast {{
    background-color: {c['elevated_3']};
    border: {border}px solid {c['border']};
    border-radius: {radius_lg}px;
    padding: {s.px(12)}px {s.px(16)}px;
}}
QWidget#ServiceGrid, QFrame#ServiceCard {{
    background-color: {c['elevated_1']};
    border: {border}px solid {c['border_subtle']};
    border-radius: {radius}px;
}}
QWidget#ServiceGrid[dragging="true"], QFrame#ServiceCard[dragging="true"] {{
    border: {border}px dashed {c['primary']};
}}
QWidget#SidePanel {{
    background-color: {c['elevated_1']};
    border-right: {border}px solid {c['border_subtle']};
}}
QTableView#LogTable {{
    font-family: {mono};
    alternate-background-color: {c['elevated_1']};
    background-color: {c['background']};
}}
"""


__all__ = ["ThemeManager"]
