"""Main application window.

Navigation model
----------------
The window uses **two rows of tabs at the top and nothing else**.  The first
row selects the workspace, the second row - built by the workspace itself -
selects the section inside it::

    +--------------------------------------------------------------+
    |  Menu bar                                                     |
    +--------------------------------------------------------------+
    |  Toolbar                                                      |
    +--------------------------------------------------------------+
    | Connection | Diagnostics | Developer | Analysis | Logs | ...  |  <- workspaces
    +--------------------------------------------------------------+
    | Session | Read DID | Read DTC | Clear DTC | Security | ...    |  <- sections
    +--------------------------------------------------------------+
    |  Diagnostics > Read DTC                                       |  <- breadcrumb
    |                                                               |
    |  Section content                                              |
    |                                                               |
    +--------------------------------------------------------------+
    |  Status bar                                                   |
    +--------------------------------------------------------------+

Earlier revisions also listed every diagnostic section in a left hand
navigation tree and pushed the converter and the log into side/bottom docks.
That duplicated the same commands in two places with two different
behaviours, so the tree and the docks were removed: a section is a top tab,
always, in every workspace.
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QResizeEvent
from PySide6.QtWidgets import QMainWindow, QMenu, QMenuBar, QWidget

from src.core.configuration_manager import ConfigurationManager, get_config
from src.core.enums.protocol_enums import ConnectionState
from src.core.event_bus import EventBus, EventType, get_event_bus
from src.core.models.did_model import DIDRegistry

from .dpi_scaler import DPIScaler
from .font_manager import FontManager
from .icon_manager import IconManager
from .panels.connection_panel.connection_panel import ConnectionPanel
from .panels.data_analysis_panel.data_analysis_workspace import DataAnalysisWorkspace
from .panels.developer_panel.developer_mode_panel import DeveloperModePanel
from .panels.diagnostic_panel.diagnostic_main_panel import DiagnosticMainPanel
from .panels.log_panel.log_workspace import LogWorkspace
from .panels.settings_panel.settings_main_panel import SettingsMainPanel
from .responsive_layout import LayoutSpec, ResponsiveLayout
from .screen_manager import ScreenManager, WindowGeometry
from .theme_manager import ThemeManager
from .widgets.status_bar_widget import StatusBarWidget
from .widgets.tab_widget_enhanced import EnhancedTabWidget
from .widgets.toast_notification import ToastManager
from .widgets.toolbar_widget import ToolbarWidget

_logger = logging.getLogger(__name__)

#: Historical navigation names mapped onto the current workspace titles.
WORKSPACE_ALIASES: dict[str, str] = {
    "Response slicer": "Data analysis",
    "Slicer": "Data analysis",
    "Data monitor": "Data analysis",
    "Converter": "Data analysis",
    "Sliced data converter": "Data analysis",
    "Log viewer": "Logs",
    "Trace viewer": "Logs",
    "Log": "Logs",
    "Developer": "Developer mode",
}


class MainWindow(QMainWindow):
    """The application main window.

    The window owns every panel and exposes them as attributes so the
    controllers can wire the signals without digging through the layout.

    Args:
        config: Application configuration.
        event_bus: Shared event bus.
        registry: DID definitions passed to the diagnostic panel.
    """

    #: Emitted when the window is about to close.
    closing = Signal()

    def __init__(
        self,
        config: ConfigurationManager | None = None,
        event_bus: EventBus | None = None,
        registry: DIDRegistry | None = None,
    ) -> None:
        """Build the whole window."""
        super().__init__()
        self.config = config or get_config()
        self.bus = event_bus or get_event_bus()
        self.scaler = DPIScaler.from_screen()
        self.fonts = FontManager(self.scaler, str(self.config.get("ui.font_family", "Roboto")),
                                 str(self.config.get("ui.monospace_family", "Roboto Mono")))
        self.icons = IconManager(self.scaler)
        self.theme = ThemeManager(self.scaler, self.bus, str(self.config.get("ui.theme", "dark")))
        self.screens = ScreenManager(self.scaler)
        self.layout_engine = ResponsiveLayout(self.scaler)

        self.setWindowTitle(str(self.config.get("application.name", "Vehicle Diagnostics Platform")))
        icon = self.icons.icon("app_icon", size=32)
        if icon is not None:
            self.setWindowIcon(icon)

        self._build_panels(registry)
        self._build_toolbar()
        self._build_menu()
        self._build_status_bar()
        self._apply_geometry()
        self.toasts = ToastManager(self, self.scaler)
        self.layout_engine.add_listener(self._on_breakpoint_changed)
        self._apply_layout(self.layout_engine.compute(self.width(), self.height()))

    # -- construction -------------------------------------------------------
    def _build_panels(self, registry: DIDRegistry | None) -> None:
        """Create the workspace tab bar and every workspace.

        Only workspaces are added here.  Each workspace owns its own section
        tab bar, so the window never has to know that ``Diagnostics`` contains
        ``Read DTC``: it just asks the workspace to show that section.
        """
        self.tabs = EnhancedTabWidget(self, self.scaler, level="primary")
        self.connection_panel = ConnectionPanel(self, self.scaler)
        self.diagnostic_panel = DiagnosticMainPanel(self, self.scaler, registry)
        self.developer_panel = DeveloperModePanel(self, self.scaler)
        self.analysis_workspace = DataAnalysisWorkspace(self, self.scaler)
        self.log_workspace = LogWorkspace(self, self.scaler)
        self.settings_panel = SettingsMainPanel(self, self.scaler, self.config)

        # Section panels stay reachable under their historical names so the
        # controllers and the test-suite keep addressing them directly.
        self.slicer_panel = self.analysis_workspace.slicer_panel
        self.converter_panel = self.analysis_workspace.converter_panel
        self.monitor_panel = self.analysis_workspace.monitor_panel
        self.plot_panel = self.analysis_workspace.plot_panel
        self.log_panel = self.log_workspace.log_panel
        self.trace_panel = self.log_workspace.trace_panel

        for panel, title, icon in self.workspaces():
            self.tabs.add_panel(panel, title, icon)
        self.setCentralWidget(self.tabs)

        self.tabs.tab_title_activated.connect(self._on_workspace_changed)
        self.diagnostic_panel.analyse_requested.connect(self.analyse_data)

    def workspaces(self) -> list[tuple[QWidget, str, str]]:
        """Return ``(panel, title, icon)`` for every top level workspace."""
        return [
            (self.connection_panel, "Connection", "connect"),
            (self.diagnostic_panel, "Diagnostics", "ecu"),
            (self.developer_panel, "Developer mode", "developer"),
            (self.analysis_workspace, "Data analysis", "convert"),
            (self.log_workspace, "Logs", "log"),
            (self.settings_panel, "Settings", "settings"),
        ]

    def _build_toolbar(self) -> None:
        """Create and install the main toolbar."""
        self.toolbar = ToolbarWidget(self, self.scaler)
        self.toolbar.setObjectName("MainToolbar")
        self.addToolBar(self.toolbar)
        self.toolbar.developer_toggled.connect(self.toggle_developer_mode)
        self.toolbar.settings_requested.connect(lambda: self.tabs.select_by_title("Settings"))
        self.toolbar.theme_toggled.connect(self.toggle_theme)

    def _build_menu(self) -> None:
        """Create the menu bar."""
        bar: QMenuBar = self.menuBar()

        file_menu = bar.addMenu("&File")
        self._add_action(file_menu, "New project", "Ctrl+N", lambda: self.toasts.info("New project"))
        self._add_action(file_menu, "Open project...", "Ctrl+O",
                         lambda: self.toasts.info("Open project"))
        self._add_action(file_menu, "Save project", "Ctrl+S",
                         lambda: self.toasts.info("Save project"))
        file_menu.addSeparator()
        self._add_action(file_menu, "Export log...", "Ctrl+E", self.log_panel.export)
        file_menu.addSeparator()
        self._add_action(file_menu, "Quit", "Ctrl+Q", self.close)

        edit_menu = bar.addMenu("&Edit")
        self._add_action(edit_menu, "Preferences", "Ctrl+,",
                         lambda: self.tabs.select_by_title("Settings"))

        view_menu = bar.addMenu("&View")
        # Ctrl+1..9 jump straight to a workspace tab, as documented in the
        # shortcut table; there are no docks left to toggle.
        for number, (_panel, title, _icon) in enumerate(self.workspaces(), start=1):
            self._add_action(
                view_menu, title, f"Ctrl+{number}",
                lambda checked=False, t=title: self.navigate(t),
            )
        view_menu.addSeparator()
        self._add_action(view_menu, "Toggle theme", "Ctrl+T", self.toggle_theme)
        self._add_action(view_menu, "Full screen", "F11", self.toggle_fullscreen)

        diagnostics_menu = bar.addMenu("&Diagnostics")
        for title in self.diagnostic_panel.sections():
            self._add_action(
                diagnostics_menu, title, "",
                lambda checked=False, t=title: self.navigate("Diagnostics", t),
            )

        tools_menu = bar.addMenu("&Tools")
        self._add_action(tools_menu, "Developer mode", "Ctrl+D",
                         lambda: self.toolbar.developer_action.toggle())
        self._add_action(tools_menu, "Response slicer", "",
                         lambda: self.navigate("Data analysis", "Response slicer"))
        self._add_action(tools_menu, "Log viewer", "Ctrl+L",
                         lambda: self.navigate("Logs", "Log viewer"))
        self._add_action(tools_menu, "Trace viewer", "",
                         lambda: self.navigate("Logs", "Trace viewer"))

        help_menu = bar.addMenu("&Help")
        self._add_action(help_menu, "Documentation", "F1", self.show_help)
        self._add_action(help_menu, "About", "", self.show_about)

    def _build_status_bar(self) -> None:
        """Create and install the status bar."""
        self.status = StatusBarWidget(self, self.scaler)
        self.setStatusBar(self.status)
        self.status.set_message("Ready")

    def _add_action(self, menu: QMenu, text: str, shortcut: str, handler: Any) -> QAction:
        """Create a menu action with an optional shortcut."""
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(handler)
        menu.addAction(action)
        return action

    def _apply_geometry(self) -> None:
        """Restore the persisted window geometry.

        The minimum size is applied first: Qt clamps a geometry to the minimum
        at the moment it is set, so ordering it the other way silently shrinks
        a restored window on small screens.
        """
        minimum = self.layout_engine.minimum_window_size()
        self.setMinimumSize(minimum[0], minimum[1])

        start_maximized = bool(self.config.get("ui.start_maximized", True))
        if bool(self.config.get("ui.remember_geometry", True)):
            geometry = self.screens.load_geometry()
            # A fresh install has nothing persisted; honour the preference.
            if not self.screens.state_file.is_file():
                geometry.maximized = start_maximized
            self.screens.apply_to_window(self, geometry)
        else:
            self.screens.apply_to_window(
                self, self.screens.default_geometry(maximized=start_maximized)
            )

    # -- behaviour ----------------------------------------------------------
    def apply_theme(self, name: str | None = None) -> None:
        """Apply a theme to the whole application.

        The generated theme stylesheet is combined with the hand written
        ``custom_widgets.qss`` fragment so the dynamic properties used by the
        custom widgets (``accent``, ``danger``, ``state``, ``valid`` ...) are
        styled as well.
        """
        if name:
            self.theme.set_theme(name)
        self.theme.invalidate()
        from PySide6.QtWidgets import QApplication

        from .styles import custom_widget_qss

        application = QApplication.instance()
        if application is not None:
            # Order matters: generated theme, then the custom widget rules for
            # the same palette, then the operator's override file which must
            # always win.
            override = self.theme.load_qss_file(
                self.config.theme_path(self.theme.theme_name)
            )
            extra = custom_widget_qss(self.theme.palette)
            if override:
                extra = f"{extra}\n{override}"
            application.setStyleSheet(self.theme.stylesheet(extra=extra))
        self.icons.set_color(self.theme.palette.text_primary)

    def toggle_theme(self) -> str:
        """Switch between the dark and the light theme."""
        name = self.theme.toggle()
        self.apply_theme()
        self.config.set("ui.theme", name)
        self.toasts.info(f"{name.title()} theme applied")
        return name

    def toggle_developer_mode(self, enabled: bool) -> None:
        """Show or hide the developer mode tab."""
        if enabled:
            self.tabs.select_by_title("Developer mode")
        self.config.set("application.developer_mode", enabled)

    def toggle_fullscreen(self) -> None:
        """Toggle the full screen state of the window."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def navigate(self, section: str, item: str = "") -> bool:
        """Activate ``section`` and, when given, the sub-tab ``item``.

        This is the single entry point for every navigation request, whether
        it comes from the menu bar, the toolbar, a controller or a keyboard
        shortcut, so a section can never be reached through two code paths
        that disagree with each other.

        Args:
            section: Workspace title, e.g. ``"Diagnostics"``.
            item: Optional section title inside the workspace, e.g.
                ``"Read DTC"``.

        Returns:
            ``True`` when the workspace was found.
        """
        title = WORKSPACE_ALIASES.get(section, section)
        if not self.tabs.select_by_title(title):
            return False
        if item:
            panel = self.tabs.currentWidget()
            show = getattr(panel, "show_view", None)
            if callable(show):
                show(item)
        return True

    def analyse_data(self, data: bytes) -> None:
        """Send *data* to the analysis workspace and open the slicer."""
        self.analysis_workspace.set_data(data)
        self.navigate("Data analysis", "Slicer")

    def set_connection_state(self, state: ConnectionState, vci: str = "", protocol: str = "",
                             bitrate: int = 0) -> None:
        """Reflect the connection state across the whole window."""
        connected = state is ConnectionState.CONNECTED
        self.toolbar.set_connected(connected)
        self.status.set_connection(state, vci, protocol, bitrate)
        self.connection_panel.set_state(state)
        self.diagnostic_panel.set_connected(connected)
        self.diagnostic_panel.breadcrumb.set_detail(
            f"{vci} \u00b7 {protocol}".strip(" \u00b7") if connected else "not connected"
        )

    def show_about(self) -> None:
        """Open the about dialog."""
        from .dialogs.about_dialog import AboutDialog

        AboutDialog(self, self.scaler).exec()

    def show_help(self) -> None:
        """Open the documentation directory in the file manager."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from pathlib import Path

        docs = Path(__file__).resolve().parents[1] / "docs"
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs)))

    # -- Qt events -------------------------------------------------------------
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt naming
        """Recompute the responsive layout after a resize."""
        super().resizeEvent(event)
        spec = self.layout_engine.on_resize(self.width(), self.height())
        if spec is not None:
            self._apply_layout(spec)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt naming
        """Persist the geometry and notify the application controller."""
        if bool(self.config.get("ui.remember_geometry", True)):
            self.screens.save_geometry(self.screens.capture_from_window(self))
        self.closing.emit()
        self.bus.publish(EventType.SYSTEM_SHUTDOWN, {}, "MainWindow")
        super().closeEvent(event)

    # -- layout -----------------------------------------------------------------
    def _apply_layout(self, spec: LayoutSpec) -> None:
        """Adapt the two tab rows to the current breakpoint.

        There are no docks to show or hide any more, so the only responsive
        decision left is whether the section tabs still fit as text.  On a
        COMPACT screen they collapse to icons with tooltips instead of
        disappearing behind scroll arrows.
        """
        compact = spec.compact_tabs
        for panel, _title, _icon in self.workspaces():
            setter = getattr(panel, "set_compact", None)
            if callable(setter):
                setter(compact)
        self.status.set_breakpoint(spec.breakpoint.label)
        if self.fonts.update_for_width(self.width()):
            self.apply_theme()

    def _on_breakpoint_changed(self, spec: LayoutSpec) -> None:
        """React to a breakpoint change."""
        self._apply_layout(spec)
        self.bus.publish(
            EventType.UI_BREAKPOINT_CHANGED, {"breakpoint": spec.breakpoint.value}, "MainWindow"
        )

    def _on_workspace_changed(self, title: str) -> None:
        """Announce the active workspace on the status bar and the bus."""
        self.status.set_message(title, 2000)
        self.bus.publish(EventType.UI_PANEL_CHANGED, {"panel": title}, "MainWindow")


__all__ = ["MainWindow", "WORKSPACE_ALIASES"]
