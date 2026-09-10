"""Tests for the DPI scaling and the responsive layout engine."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from ui.dpi_scaler import BASELINE_DPI, DPIScaler, ScreenMetrics  # noqa: E402
from ui.font_manager import FontManager, base_size_for_width  # noqa: E402
from ui.responsive_layout import Breakpoint, ResponsiveLayout, classify_width  # noqa: E402
from ui.styles.style_constants import FontRole  # noqa: E402

pytestmark = pytest.mark.ui


class TestDPIScaling:
    """Scaling of fonts, spacing and icons."""

    @pytest.mark.parametrize(
        ("dpi", "expected"), [(96, 1.0), (120, 1.25), (144, 1.5), (168, 1.75), (192, 2.0)]
    )
    def test_scale_factors(self, dpi: float, expected: float) -> None:
        """Every common Windows scaling step is handled."""
        scaler = DPIScaler(ScreenMetrics(dpi=dpi))
        assert scaler.scale == pytest.approx(expected)

    @pytest.mark.parametrize("dpi", [96, 120, 144, 192])
    def test_values_grow_with_dpi(self, dpi: float) -> None:
        """Sizes never shrink when the DPI increases."""
        baseline = DPIScaler(ScreenMetrics(dpi=BASELINE_DPI))
        scaler = DPIScaler(ScreenMetrics(dpi=dpi))
        assert scaler.px(16) >= baseline.px(16)
        assert scaler.font(13) >= baseline.font(13)
        assert scaler.icon(20) >= baseline.icon(20)

    def test_borders_never_disappear(self) -> None:
        """A one pixel border stays visible at every scale."""
        for dpi in (72, 96, 144, 192):
            assert DPIScaler(ScreenMetrics(dpi=dpi)).border(1) >= 1

    def test_scale_is_clamped(self) -> None:
        """Extreme DPI values are clamped to a usable range."""
        assert DPIScaler(ScreenMetrics(dpi=20)).scale >= 0.75
        assert DPIScaler(ScreenMetrics(dpi=1000)).scale <= 3.0

    def test_user_factor(self) -> None:
        """An additional user zoom is applied on top."""
        scaler = DPIScaler(ScreenMetrics(dpi=96))
        scaler.set_user_factor(1.5)
        assert scaler.px(10) == 15


class TestBreakpoints:
    """Window width classification."""

    @pytest.mark.parametrize(
        ("width", "expected"),
        [
            (1280, Breakpoint.COMPACT),
            (1366, Breakpoint.STANDARD),
            (1600, Breakpoint.STANDARD),
            (1920, Breakpoint.WIDE),
            (2560, Breakpoint.ULTRA_WIDE),
            (3840, Breakpoint.ULTRA_WIDE),
        ],
    )
    def test_classification(self, width: int, expected: Breakpoint) -> None:
        """Every tested resolution maps to the documented breakpoint."""
        assert classify_width(width) is expected

    @pytest.mark.parametrize("width", [1280, 1366, 1920, 2560, 3840])
    def test_layout_is_consistent(self, scaler, width: int) -> None:
        """The computed layout is usable at every resolution."""
        layout = ResponsiveLayout(scaler)
        spec = layout.compute(width)
        assert spec.columns >= 1
        assert spec.log_height > 0
        assert spec.content_margin > 0
        assert spec.navigation_width >= 0

    def test_compact_hides_side_panels(self, scaler) -> None:
        """Small screens hide the optional docks."""
        spec = ResponsiveLayout(scaler).compute(1280)
        assert not spec.visibility.navigation
        assert not spec.visibility.analysis
        assert spec.visibility.log

    def test_wide_shows_everything(self, scaler) -> None:
        """Wide screens show every panel."""
        spec = ResponsiveLayout(scaler).compute(2560)
        assert spec.visibility.navigation
        assert spec.visibility.analysis

    def test_listener_fires_on_change(self, scaler) -> None:
        """A breakpoint change notifies the listeners."""
        layout = ResponsiveLayout(scaler)
        seen: list[str] = []
        layout.add_listener(lambda spec: seen.append(spec.breakpoint.value))
        layout.on_resize(1280)
        layout.on_resize(2560)
        assert "ULTRA_WIDE" in seen

    def test_debounce(self, scaler) -> None:
        """Tiny resizes are ignored."""
        layout = ResponsiveLayout(scaler, debounce_px=50)
        assert layout.on_resize(1920) is not None
        assert layout.on_resize(1930) is None


class TestFontScaling:
    """Font sizes across breakpoints."""

    @pytest.mark.parametrize(
        ("width", "expected"), [(1280, 11), (1366, 13), (1920, 14), (2560, 16), (3840, 16)]
    )
    def test_base_size(self, width: int, expected: int) -> None:
        """The base size follows the documented breakpoints."""
        assert base_size_for_width(width) == expected

    def test_role_hierarchy(self, scaler) -> None:
        """Headings are larger than the body text."""
        fonts = FontManager(scaler)
        assert fonts.size(FontRole.HEADING_1) > fonts.size(FontRole.HEADING_2)
        assert fonts.size(FontRole.HEADING_2) > fonts.size(FontRole.BODY)
        assert fonts.size(FontRole.BODY) > fonts.size(FontRole.STATUS)

    def test_all_sizes_readable(self) -> None:
        """No role ever produces an unreadably small font."""
        for dpi in (96, 144, 192):
            fonts = FontManager(DPIScaler(ScreenMetrics(dpi=dpi)))
            for role in FontRole:
                assert fonts.size(role) >= 8


class TestShippedStylesheets:
    """The ``*.qss`` template files shipped in :mod:`ui.styles`."""

    def test_every_theme_file_is_populated(self) -> None:
        """The templates must not be empty placeholders.

        They were scaffolded as zero byte files; the themes still worked
        because :class:`ThemeManager` generates QSS in code, which hid the
        problem from every other test.
        """
        from ui.styles import QSS_FILES, qss_file

        for theme in QSS_FILES:
            path = qss_file(theme)
            assert path.is_file(), f"{path.name} is missing"
            text = path.read_text(encoding="utf-8")
            assert len(text) > 1000, f"{path.name} holds only {len(text)} characters"
            assert "QWidget" in text, f"{path.name} has no QWidget rule"

    def test_custom_widget_fragment_is_populated(self) -> None:
        """The generated fragment styles the custom dynamic properties.

        ``accent`` and ``danger`` are owned by the base theme; the fragment
        covers the properties the generated stylesheet does not know about.
        """
        from ui.styles import custom_widget_qss

        text = custom_widget_qss()
        assert len(text) > 500
        for marker in ('state="error"', 'valid="false"', 'status="PASS"', "Toast"):
            assert marker in text, f"{marker} is not styled"

    def test_base_theme_styles_the_button_variants(self) -> None:
        """Accent and danger buttons are coloured by the theme itself."""
        from ui.theme_manager import ThemeManager

        qss = ThemeManager().stylesheet()
        for marker in ('QPushButton[accent="true"]', 'QPushButton[danger="true"]'):
            assert marker in qss, f"{marker} is not styled"

    def test_theme_files_carry_the_specification_palette(self) -> None:
        """Each generated file quotes the colours of its own palette."""
        from ui.styles import QSS_FILES, qss_file
        from ui.styles.style_constants import PALETTES

        for theme in QSS_FILES:
            text = qss_file(theme).read_text(encoding="utf-8")
            palette = PALETTES[theme]
            assert palette.background in text
            assert palette.primary in text

    def test_qt_parses_every_template(self, qtbot) -> None:
        """Qt must accept the files without dropping the stylesheet."""
        from PySide6.QtWidgets import QApplication, QPushButton

        from ui.styles import QSS_FILES, custom_widget_qss, qss_file

        application = QApplication.instance()
        assert application is not None
        previous = application.styleSheet()
        try:
            for theme in QSS_FILES:
                combined = qss_file(theme).read_text(encoding="utf-8") + custom_widget_qss()
                application.setStyleSheet(combined)
                button = QPushButton("probe")
                qtbot.addWidget(button)
                button.setProperty("accent", "true")
                button.resize(120, 32)
                assert not button.grab().isNull()
                assert application.styleSheet() == combined
        finally:
            application.setStyleSheet(previous)


class TestPaletteRefinements:
    """The derived tokens that give the interface depth and legibility."""

    def test_elevation_increases_monotonically(self) -> None:
        """Each elevation step must be visibly lighter on a dark theme."""
        from ui.styles.style_constants import DARK_PALETTE, relative_luminance

        levels = [relative_luminance(DARK_PALETTE.elevate(i)) for i in range(4)]
        assert levels == sorted(levels)
        assert levels[0] < levels[-1]

    def test_specification_colours_are_unchanged(self) -> None:
        """The refinement must not alter the mandated palette."""
        from ui.styles.style_constants import DARK_PALETTE, LIGHT_PALETTE

        assert DARK_PALETTE.background == "#1E1E2E"
        assert DARK_PALETTE.surface == "#282840"
        assert DARK_PALETTE.primary == "#7C3AED"
        assert LIGHT_PALETTE.background == "#F8FAFC"
        assert LIGHT_PALETTE.primary == "#7C3AED"

    def test_body_text_meets_wcag_aa(self) -> None:
        """Primary text must clear the 4.5:1 contrast threshold."""
        from ui.styles.style_constants import PALETTES, contrast_ratio

        for name, palette in PALETTES.items():
            ratio = contrast_ratio(palette.text_primary, palette.background)
            assert ratio >= 4.5, f"{name} primary text is only {ratio:.2f}:1"

    def test_secondary_text_meets_large_text_aa(self) -> None:
        """Secondary text must clear at least the 3:1 large-text threshold."""
        from ui.styles.style_constants import PALETTES, contrast_ratio

        for name, palette in PALETTES.items():
            ratio = contrast_ratio(palette.text_secondary, palette.background)
            assert ratio >= 3.0, f"{name} secondary text is only {ratio:.2f}:1"

    def test_on_colour_picks_the_readable_foreground(self) -> None:
        """Filled accents must carry legible text."""
        from ui.styles.style_constants import DARK_PALETTE, contrast_ratio

        for accent in (
            DARK_PALETTE.primary,
            DARK_PALETTE.success,
            DARK_PALETTE.warning,
            DARK_PALETTE.error,
        ):
            assert contrast_ratio(DARK_PALETTE.on(accent), accent) >= 3.0

    def test_every_derived_token_is_a_colour(self) -> None:
        """The QSS template interpolates these directly."""
        import re

        from ui.styles.style_constants import PALETTES

        pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
        for palette in PALETTES.values():
            for key, value in palette.as_dict().items():
                if key == "name":
                    continue
                assert pattern.match(value), f"{key}={value!r} is not a hex colour"


class TestStylesheetQuality:
    """Rules the generated stylesheet must always contain."""

    def test_focus_ring_is_defined(self) -> None:
        """Keyboard focus must be visible on inputs and buttons."""
        from ui.theme_manager import ThemeManager

        qss = ThemeManager().stylesheet()
        assert "QPushButton:focus" in qss
        assert "QLineEdit:focus" in qss

    def test_hover_and_pressed_states_exist(self) -> None:
        """Interactive affordance separates a tool from a mockup."""
        from ui.theme_manager import ThemeManager

        qss = ThemeManager().stylesheet()
        for rule in ("QPushButton:hover", "QPushButton:pressed", "QTabBar::tab:hover"):
            assert rule in qss

    def test_no_unresolved_placeholders(self) -> None:
        """Every ``{token}`` must have been interpolated."""
        import re

        from ui.theme_manager import ThemeManager

        for theme in ("dark", "light", "high_contrast"):
            manager = ThemeManager()
            manager.set_theme(theme)
            qss = manager.stylesheet()
            assert not re.search(r"\{[a-z_]+\}", qss), f"{theme} has an unresolved token"


class TestTableReadability:
    """Regressions for clipped headers, which looked unfinished."""

    def test_header_is_never_clipped_by_short_content(self, qtbot, scaler) -> None:
        """A narrow column must still show its full header label."""
        from PySide6.QtGui import QFontMetrics

        from ui.widgets.table_widget_enhanced import EnhancedTableWidget

        table = EnhancedTableWidget(["ID", "PROTOCOL", "DESCRIPTION"], scaler=scaler)
        qtbot.addWidget(table)
        table.set_rows([{"ID": "1", "PROTOCOL": "CAN", "DESCRIPTION": "x"}])
        metrics = QFontMetrics(table.horizontalHeader().font())
        for index, title in enumerate(table.columns):
            assert table.columnWidth(index) >= metrics.horizontalAdvance(title), title

    def test_wide_column_is_clamped(self, qtbot, scaler) -> None:
        """One verbose cell must not push the other columns off screen."""
        from ui.widgets.table_widget_enhanced import EnhancedTableWidget

        table = EnhancedTableWidget(["Note"], scaler=scaler)
        qtbot.addWidget(table)
        table.set_rows([{"Note": "x" * 4000}])
        assert table.columnWidth(0) <= scaler.px(420)


class TestWindowStartsMaximised:
    """The main window is a workspace: it opens filling the screen."""

    def test_default_geometry_is_maximised(self) -> None:
        """A fresh install has no persisted state and must maximise."""
        from ui.screen_manager import ScreenManager

        assert ScreenManager().default_geometry().maximized is True

    def test_maximised_can_be_opted_out(self) -> None:
        """The preference is honoured when switched off."""
        from ui.screen_manager import ScreenManager

        assert ScreenManager().default_geometry(maximized=False).maximized is False

    def test_apply_to_window_sets_the_window_state(self, qtbot, tmp_path) -> None:
        """The state must be set before show(), not via showMaximized()."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMainWindow

        from ui.screen_manager import ScreenManager, WindowGeometry

        window = QMainWindow()
        qtbot.addWidget(window)
        manager = ScreenManager(state_file=tmp_path / "state.json")
        manager.apply_to_window(window, WindowGeometry(maximized=True))
        assert window.windowState() & Qt.WindowState.WindowMaximized

    def test_apply_to_window_clears_the_state(self, qtbot, tmp_path) -> None:
        """A restored non-maximised geometry must not stay maximised."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMainWindow

        from ui.screen_manager import ScreenManager, WindowGeometry

        window = QMainWindow()
        qtbot.addWidget(window)
        manager = ScreenManager(state_file=tmp_path / "state.json")
        manager.apply_to_window(window, WindowGeometry(maximized=True))
        manager.apply_to_window(window, WindowGeometry(maximized=False))
        assert not window.windowState() & Qt.WindowState.WindowMaximized

    def test_main_window_maximises_on_a_fresh_profile(self, qtbot, tmp_path) -> None:
        """End to end: a new user gets a maximised window."""
        from PySide6.QtCore import Qt

        from ui.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.screens.state_file = tmp_path / "absent.json"
        window._apply_geometry()
        assert window.windowState() & Qt.WindowState.WindowMaximized

    def test_setting_is_exposed_in_the_ui(self) -> None:
        """The operator can change the behaviour from Settings."""
        from ui.panels.settings_panel.display_settings import paths

        assert "ui.start_maximized" in paths()

    def test_default_configuration_enables_it(self) -> None:
        """The shipped configuration turns the behaviour on."""
        from src.core.configuration_manager import ConfigurationManager

        assert ConfigurationManager().get("ui.start_maximized") is True


class TestThemeAppliesEverywhere:
    """Every painted colour must follow the active theme."""

    def _themes(self):
        """Return the bundled palettes."""
        from ui.styles.style_constants import PALETTES

        return PALETTES

    def test_semantic_colours_are_legible_in_every_theme(self) -> None:
        """No status colour may fall below the 3:1 graphical threshold."""
        from ui.styles.semantic_colors import semantic, set_active_palette
        from ui.styles.style_constants import contrast_ratio

        tokens = ("error", "warning", "success", "muted", "primary", "tx", "rx", "info")
        for name, palette in self._themes().items():
            set_active_palette(palette)
            for token in tokens:
                ratio = contrast_ratio(semantic(token), palette.background)
                assert ratio >= 3.0, f"{name}/{token} is only {ratio:.2f}:1"

    def test_dtc_severity_colour_follows_the_theme(self) -> None:
        """A confirmed DTC is a different red on the light theme."""
        from ui.panels.diagnostic_panel.read_dtc_panel.dtc_status_display import status_colour
        from ui.styles.semantic_colors import set_active_palette

        seen = set()
        for palette in self._themes().values():
            set_active_palette(palette)
            seen.add(status_colour(0x08))
        assert len(seen) > 1, "the DTC colour never changed with the theme"

    def test_led_state_colour_follows_the_theme(self) -> None:
        """The LED indicator resolves against the palette it is given."""
        from ui.styles.style_constants import (
            DARK_PALETTE,
            LIGHT_PALETTE,
            state_color,
        )

        assert state_color("pass", DARK_PALETTE) == DARK_PALETTE.success
        assert state_color("pass", LIGHT_PALETTE) == LIGHT_PALETTE.success
        assert state_color("pass", DARK_PALETTE) != state_color("pass", LIGHT_PALETTE)

    def test_theme_manager_publishes_the_palette(self) -> None:
        """Switching a theme updates the semantic colour service."""
        from ui.styles.semantic_colors import active_palette
        from ui.theme_manager import ThemeManager

        manager = ThemeManager()
        for name in ("dark", "light", "high_contrast"):
            manager.set_theme(name)
            assert active_palette().name == name

    def test_no_panel_hardcodes_a_status_colour(self) -> None:
        """Panels must paint through the semantic service.

        A literal such as ``#22C55E`` renders at about 2:1 on the light theme,
        which is why every status colour has to be resolved at paint time.
        """
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[2] / "ui" / "panels"
        banned = re.compile(r'["\'](#(?:EF4444|F59E0B|22C55E|94A3B8))["\']', re.I)
        offenders = []
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for number, line in enumerate(path.read_text().splitlines(), start=1):
                if banned.search(line) and "semantic(" not in line:
                    offenders.append(f"{path.name}:{number}")
        assert not offenders, f"hardcoded status colours: {offenders}"

    def test_plot_series_follow_the_theme(self, qtbot, scaler) -> None:
        """Chart lines are recoloured for the active theme."""
        from ui.panels.data_analysis_panel import DataPlotPanel
        from ui.styles.semantic_colors import set_active_palette
        from ui.styles.style_constants import DARK_PALETTE, LIGHT_PALETTE, contrast_ratio

        colours = {}
        for palette in (DARK_PALETTE, LIGHT_PALETTE):
            set_active_palette(palette)
            panel = DataPlotPanel(scaler=scaler)
            qtbot.addWidget(panel)
            panel.append("rpm", 800.0)
            colour = panel.series["rpm"].color
            colours[palette.name] = colour
            assert contrast_ratio(colour, palette.background) >= 3.0
        assert colours["dark"] != colours["light"]

    def test_button_icon_colour_follows_the_theme(self, qtbot, scaler) -> None:
        """Icon tint must contrast with the button fill."""
        from ui.styles.semantic_colors import set_active_palette
        from ui.styles.style_constants import LIGHT_PALETTE, contrast_ratio
        from ui.widgets.scalable_button import ScalableButton

        set_active_palette(LIGHT_PALETTE)
        button = ScalableButton("Run", scaler=scaler)
        qtbot.addWidget(button)
        button.setProperty("accent", "true")
        assert contrast_ratio(button.color_hint(), LIGHT_PALETTE.primary) >= 3.0

    def test_every_panel_repaints_under_every_theme(self, qtbot, scaler) -> None:
        """A theme switch must not break any panel's paint path."""
        from ui.main_window import MainWindow
        from ui.styles.style_constants import PALETTES

        window = MainWindow()
        qtbot.addWidget(window)
        window.resize(1600, 900)
        for name in PALETTES:
            window.apply_theme(name)
            for index in range(window.tabs.count()):
                window.tabs.setCurrentIndex(index)
                assert not window.grab().isNull(), f"{name} tab {index} failed to paint"


class TestCustomWidgetFragmentFollowsTheTheme:
    """The appended fragment must not override the theme's accent."""

    def test_fragment_uses_the_requested_palette(self) -> None:
        """Each theme produces its own accent colours."""
        from ui.styles import custom_widget_qss
        from ui.styles.style_constants import PALETTES

        for palette in PALETTES.values():
            fragment = custom_widget_qss(palette)
            assert palette.error in fragment
            assert palette.success in fragment

    def test_fragment_leaks_no_foreign_accent(self) -> None:
        """The violet default must not appear on the high contrast theme."""
        from ui.styles import custom_widget_qss
        from ui.styles.style_constants import DARK_PALETTE, HIGH_CONTRAST_PALETTE

        fragment = custom_widget_qss(HIGH_CONTRAST_PALETTE)
        assert DARK_PALETTE.primary not in fragment
        assert HIGH_CONTRAST_PALETTE.primary in fragment

    def test_static_file_no_longer_carries_rules(self) -> None:
        """The deprecated file must stay comment-only.

        A literal rule there is appended after the theme and wins the cascade,
        which is what painted the accent button violet on every theme.
        """
        from ui.styles import STYLES_DIR

        text = (STYLES_DIR / "custom_widgets.qss").read_text(encoding="utf-8")
        body = [
            line
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith(("/*", "*", "*/"))
        ]
        assert not body, f"custom_widgets.qss still declares rules: {body[:3]}"

    def test_applied_stylesheet_matches_the_theme(self, qtbot) -> None:
        """End to end: the live stylesheet carries the active accent."""
        from PySide6.QtWidgets import QApplication

        from ui.main_window import MainWindow
        from ui.styles.style_constants import PALETTES

        window = MainWindow()
        qtbot.addWidget(window)
        application = QApplication.instance()
        assert application is not None
        for name, palette in PALETTES.items():
            window.apply_theme(name)
            qss = application.styleSheet()
            assert palette.primary in qss, f"{name} lost its accent"
            foreign = [
                other.primary
                for key, other in PALETTES.items()
                if key != name and other.primary != palette.primary
            ]
            for colour in foreign:
                assert f"background-color: {colour};" not in qss, (
                    f"{name} leaked the {colour} accent"
                )
