"""Application toolbar."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QComboBox, QLabel, QToolBar, QWidget

from src.core.enums.session_enums import SessionType

from ..dpi_scaler import DPIScaler


class ToolbarWidget(QToolBar):
    """The main toolbar with connection, execution and view actions.

    Args:
        parent: Parent window.
        scaler: Shared DPI scaler.
    """

    connect_requested = Signal()
    disconnect_requested = Signal()
    session_requested = Signal(int)
    run_requested = Signal()
    run_all_requested = Signal()
    cancel_requested = Signal()
    developer_toggled = Signal(bool)
    settings_requested = Signal()
    theme_toggled = Signal()

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the toolbar actions."""
        super().__init__("Main toolbar", parent)
        self.scaler = scaler or DPIScaler()
        edge = self.scaler.icon(20)
        self.setIconSize(QSize(edge, edge))
        self.setMovable(False)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        from ..icon_manager import IconManager

        self.icons = IconManager(self.scaler)

        self.connect_action = self._action("Connect", "connect", "Ctrl+Shift+C",
                                           self.connect_requested.emit)
        self.disconnect_action = self._action("Disconnect", "disconnect", "Ctrl+Shift+D",
                                              self.disconnect_requested.emit)
        self.disconnect_action.setEnabled(False)
        self.addSeparator()

        self.addWidget(QLabel(" Session: ", self))
        self.session_box = QComboBox(self)
        for session in (SessionType.DEFAULT, SessionType.PROGRAMMING,
                        SessionType.EXTENDED_DIAGNOSTIC, SessionType.SAFETY_SYSTEM_DIAGNOSTIC):
            self.session_box.addItem(f"0x{int(session):02X} {session.pretty_name}", int(session))
        self.session_box.setCurrentIndex(2)
        self.session_box.activated.connect(
            lambda index: self.session_requested.emit(int(self.session_box.itemData(index)))
        )
        self.addWidget(self.session_box)
        self.addSeparator()

        self.run_action = self._action("Run", "play", "F5", self.run_requested.emit)
        self.run_all_action = self._action("Run all", "run_all", "F6", self.run_all_requested.emit)
        self.cancel_action = self._action("Cancel", "cancel", "Escape", self.cancel_requested.emit)
        self.cancel_action.setEnabled(False)
        self.addSeparator()

        self.developer_action = self._action("Developer mode", "developer", "Ctrl+D", None)
        self.developer_action.setCheckable(True)
        self.developer_action.toggled.connect(self.developer_toggled.emit)

        self.settings_action = self._action("Settings", "settings", "Ctrl+,",
                                            self.settings_requested.emit)
        self.theme_action = self._action("Theme", "theme", "Ctrl+T", self.theme_toggled.emit)

    def _action(self, text: str, icon: str, shortcut: str, handler: Any) -> QAction:
        """Create, register and return one toolbar action."""
        action = QAction(text, self)
        icon_obj = self.icons.icon(icon)
        if icon_obj is not None:
            action.setIcon(icon_obj)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setToolTip(f"{text} ({shortcut})")
        if handler is not None:
            action.triggered.connect(handler)
        self.addAction(action)
        return action

    # -- state ---------------------------------------------------------------
    def set_connected(self, connected: bool) -> None:
        """Enable or disable the actions that need a connection."""
        self.connect_action.setEnabled(not connected)
        self.disconnect_action.setEnabled(connected)
        self.session_box.setEnabled(connected)
        self.run_action.setEnabled(connected)
        self.run_all_action.setEnabled(connected)

    def set_running(self, running: bool) -> None:
        """Toggle the cancel action while a sequence is executing."""
        self.cancel_action.setEnabled(running)
        self.run_action.setEnabled(not running)
        self.run_all_action.setEnabled(not running)

    def set_session(self, session: int) -> None:
        """Reflect the active session in the drop-down."""
        index = self.session_box.findData(session)
        if index >= 0:
            self.session_box.setCurrentIndex(index)


__all__ = ["ToolbarWidget"]
