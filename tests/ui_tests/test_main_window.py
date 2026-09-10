"""Tests for the main window and its controllers."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from src.core.enums.protocol_enums import ConnectionState  # noqa: E402

pytestmark = pytest.mark.ui


class TestConstruction:
    """The window builds correctly."""

    def test_panels_exist(self, main_window) -> None:
        """Every panel is created and reachable."""
        for attribute in (
            "connection_panel",
            "diagnostic_panel",
            "developer_panel",
            "slicer_panel",
            "monitor_panel",
            "trace_panel",
            "settings_panel",
            "log_panel",
            "converter_panel",
        ):
            assert getattr(main_window, attribute) is not None

    def test_tabs(self, main_window) -> None:
        """The workspace tab bar lists every workspace."""
        titles = main_window.tabs.titles()
        assert titles == [
            "Connection",
            "Diagnostics",
            "Developer mode",
            "Data analysis",
            "Logs",
            "Settings",
        ]

    def test_no_side_navigation(self, main_window) -> None:
        """Navigation is tabs only: no tree and no dock widgets remain."""
        from PySide6.QtWidgets import QDockWidget

        assert not main_window.findChildren(QDockWidget)
        assert not hasattr(main_window, "navigation_dock")
        assert not hasattr(main_window, "navigation")

    def test_sections_are_top_tabs(self, main_window) -> None:
        """Every diagnostic service is a tab of the section bar, not a tree row."""
        sections = main_window.diagnostic_panel.tabs.titles()
        for expected in ("Session", "Read DID", "Read DTC", "Clear DTC", "Security"):
            assert expected in sections
        assert main_window.diagnostic_panel.tabs.level == "sub"
        assert main_window.tabs.level == "primary"

    def test_workspaces_expose_sections(self, main_window) -> None:
        """Each workspace answers ``show_view`` so navigation is uniform."""
        for panel, title, _icon in main_window.workspaces():
            if title == "Connection":
                continue
            assert callable(getattr(panel, "show_view", None)), title
            assert panel.sections(), title

    def test_menu_bar(self, main_window) -> None:
        """The menu bar carries the documented menus."""
        titles = [action.text() for action in main_window.menuBar().actions()]
        assert "&File" in titles
        assert "&Diagnostics" in titles
        assert "&Help" in titles

    def test_toolbar_actions(self, main_window) -> None:
        """The toolbar exposes the main actions."""
        assert main_window.toolbar.connect_action.isEnabled()
        assert not main_window.toolbar.disconnect_action.isEnabled()

    def test_minimum_size(self, main_window) -> None:
        """The window enforces a usable minimum size."""
        assert main_window.minimumWidth() >= 1024
        assert main_window.minimumHeight() >= 640


class TestBehaviour:
    """Interaction with the window."""

    def test_navigation(self, main_window) -> None:
        """``navigate`` selects the workspace tab and then the section tab."""
        assert main_window.navigate("Diagnostics", "Read DTC")
        assert main_window.tabs.current_title() == "Diagnostics"
        assert main_window.diagnostic_panel.tabs.current_title() == "Read DTC"

    def test_navigation_breadcrumb(self, main_window) -> None:
        """The breadcrumb spells the active two level path out."""
        main_window.navigate("Diagnostics", "Clear DTC")
        assert main_window.diagnostic_panel.breadcrumb.text() == "Diagnostics \u203a Clear DTC"

    def test_navigation_aliases(self, main_window) -> None:
        """Historical names still resolve to the workspace that owns them."""
        assert main_window.navigate("Trace viewer")
        assert main_window.tabs.current_title() == "Logs"
        assert main_window.navigate("Diagnostics", "Session control")
        assert main_window.diagnostic_panel.tabs.current_title() == "Session"

    def test_compact_tabs(self, main_window) -> None:
        """Section tabs collapse to icons instead of scrolling out of view."""
        spec = main_window.layout_engine.compute(1280, 720)
        main_window._apply_layout(spec)
        bar = main_window.diagnostic_panel.tabs
        assert bar.tabText(0) == ""
        assert bar.tabToolTip(0) == "Session"
        main_window._apply_layout(main_window.layout_engine.compute(1920, 1080))
        assert bar.tabText(0) == "Session"

    def test_theme_toggle(self, main_window) -> None:
        """Switching the theme regenerates the stylesheet."""
        first = main_window.theme.theme_name
        second = main_window.toggle_theme()
        assert second != first
        assert main_window.theme.stylesheet()

    def test_connection_state(self, main_window) -> None:
        """The connection state propagates to the toolbar and the panels."""
        main_window.set_connection_state(ConnectionState.CONNECTED, "Virtual", "CAN", 500000)
        assert main_window.toolbar.disconnect_action.isEnabled()
        assert main_window.status.connection.text_label.text() == "Connected"
        main_window.set_connection_state(ConnectionState.DISCONNECTED)
        assert main_window.toolbar.connect_action.isEnabled()

    def test_analyse_data(self, main_window) -> None:
        """Analysing a response fills the slicer and the converter."""
        main_window.analyse_data(bytes.fromhex("62F1905742415A"))
        assert main_window.slicer_panel.slicer.data() == bytes.fromhex("62F1905742415A")
        assert main_window.converter_panel.data() == bytes.fromhex("62F1905742415A")
        assert main_window.tabs.current_title() == "Data analysis"
        assert main_window.analysis_workspace.tabs.current_title() == "Slicer"

    @pytest.mark.parametrize(
        ("width", "height"), [(1280, 720), (1366, 768), (1920, 1080), (2560, 1440), (3840, 2160)]
    )
    def test_resolutions(self, main_window, width: int, height: int) -> None:
        """The window lays out correctly at every supported resolution."""
        main_window.resize(width, height)
        spec = main_window.layout_engine.compute(width, height)
        main_window._apply_layout(spec)
        assert main_window.status.breakpoint_label.text()
        assert main_window.centralWidget() is not None

    def test_toast_notifications(self, main_window) -> None:
        """Toasts can be shown and cleared."""
        main_window.toasts.success("connected")
        main_window.toasts.error("failed")
        assert len(main_window.toasts._toasts) == 2
        main_window.toasts.clear()


class TestControllerWiring:
    """The controllers connect the UI to the backend."""

    @pytest.fixture()
    def controller(self, qtbot, main_window, config, event_bus):
        """Return a fully wired main controller."""
        from src.logging_system.log_manager import LogManager
        from ui.controllers.main_controller import MainController

        logs = LogManager(config, event_bus, use_file=False, use_database=False)
        instance = MainController(main_window, config, logs, main_window.diagnostic_panel.read_did_view.registry, event_bus)
        yield instance
        instance.shutdown()

    def test_controllers_created(self, controller) -> None:
        """Every sub-controller exists."""
        assert controller.connection is not None
        assert controller.diagnostics is not None
        assert controller.developer is not None
        assert controller.analysis is not None
        assert controller.logs is not None

    def test_connect_flow(self, qtbot, controller, main_window) -> None:
        """Connecting through the controller enables the diagnostic panels."""
        with qtbot.waitSignal(controller.connection.connected, timeout=10000):
            controller.connection.connect_to(main_window.connection_panel.profile())
        assert controller.connection.is_connected
        assert controller.diagnostics.client is not None
        assert main_window.toolbar.disconnect_action.isEnabled()

    def test_diagnostic_flow(self, qtbot, controller, main_window) -> None:
        """A session change performed through the controller updates the view."""
        with qtbot.waitSignal(controller.connection.connected, timeout=10000):
            controller.connection.connect_to(main_window.connection_panel.profile())
        controller.diagnostics.change_session(0x03)
        qtbot.waitUntil(
            lambda: "extended" in main_window.diagnostic_panel.session_view.current_label.text(),
            timeout=10000,
        )
        assert "0x03" in main_window.diagnostic_panel.session_view.current_label.text()

    def test_read_dtcs_through_controller(self, qtbot, controller, main_window) -> None:
        """Reading DTCs fills the results table."""
        with qtbot.waitSignal(controller.connection.connected, timeout=10000):
            controller.connection.connect_to(main_window.connection_panel.profile())
        controller.diagnostics.read_dtcs(0x02, 0xFF)
        qtbot.waitUntil(
            lambda: main_window.diagnostic_panel.read_dtc_view.results_table.rowCount() == 3,
            timeout=10000,
        )

    def test_log_streaming(self, qtbot, controller, main_window) -> None:
        """Diagnostic activity ends up in the log viewer."""
        with qtbot.waitSignal(controller.connection.connected, timeout=10000):
            controller.connection.connect_to(main_window.connection_panel.profile())
        controller.diagnostics.change_session(0x03)
        qtbot.waitUntil(
            lambda: controller.log_manager.count() > 0,
            timeout=10000,
        )
