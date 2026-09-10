"""Settings controller applying configuration changes at runtime."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal

from src.core.configuration_manager import ConfigurationManager, get_config
from src.core.event_bus import EventBus, EventType, get_event_bus
from src.core.models.log_entry_model import LogLevel

_logger = logging.getLogger(__name__)


class SettingsController(QObject):
    """Applies settings changes to the running application.

    Args:
        panel: The settings panel.
        window: The main window.
        config: Application configuration.
        event_bus: Shared event bus.
    """

    #: Emitted with the applied values.
    applied = Signal(dict)

    def __init__(
        self,
        panel: Any,
        window: Any = None,
        config: ConfigurationManager | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Wire the panel signals."""
        super().__init__()
        self.panel = panel
        self.window = window
        self.config = config or get_config()
        self.bus = event_bus or get_event_bus()
        panel.settings_applied.connect(self.apply)
        panel.defaults_restored.connect(self.on_defaults_restored)

    def apply(self, values: dict[str, Any]) -> None:
        """Apply the settings that take effect immediately."""
        if "ui.theme" in values and self.window is not None:
            self.window.apply_theme(str(values["ui.theme"]))
        if "ui.accent_color" in values and self.window is not None:
            accent = str(values["ui.accent_color"]).strip()
            if accent.startswith("#"):
                self.window.theme.set_accent(accent)
                self.window.apply_theme()
        if "logging.level" in values:
            manager = getattr(self.window, "log_manager", None)
            if manager is None and self.window is not None:
                controller = getattr(self.window, "controller", None)
                manager = getattr(controller, "log_manager", None) if controller else None
            if manager is not None:
                manager.set_level(LogLevel.parse(str(values["logging.level"])))
        if "ui.base_font_pt" in values and self.window is not None:
            self.window.fonts.set_base_size(int(values["ui.base_font_pt"]))
            self.window.apply_theme()
        self.bus.publish(EventType.SYSTEM_CONFIG_CHANGED, {"values": values}, "SettingsController")
        self.applied.emit(values)
        self._notify("Settings applied", "success")

    def on_defaults_restored(self) -> None:
        """React to the defaults being restored."""
        if self.window is not None:
            self.window.apply_theme(str(self.config.get("ui.theme", "dark")))
        self._notify("Default settings restored", "info")

    def _notify(self, message: str, level: str = "info") -> None:
        """Show a toast if a window is available."""
        if self.window is None:
            return
        toasts = getattr(self.window, "toasts", None)
        if toasts is not None:
            getattr(toasts, level, toasts.info)(message)


__all__ = ["SettingsController"]
