"""Example plugin showing the extension points of the platform."""
from __future__ import annotations

from typing import Any

from plugins.plugin_base import PluginBase


class ExamplePlugin(PluginBase):
    """Logs every diagnostic session change and adds one custom DID."""

    plugin_id = "custom.example"
    name = "Example plugin"
    version = "1.0.0"
    description = "Demonstrates event subscriptions and DID registration"

    def on_initialize(self, context: Any) -> None:
        """Subscribe to session changes and register a demo DID."""
        from src.core.event_bus import EventType

        self.register_dids({0xFD00: {"name": "Example plugin counter", "format": "DEC_UNSIGNED"}})
        self.subscribe(EventType.DIAG_SESSION_CHANGED, self._on_session_changed)
        self.log("ready")

    def _on_session_changed(self, event: Any) -> None:
        """Log every session change."""
        self.log(f"session changed to {event.get('label', event.get('session'))}")

    def on_shutdown(self) -> None:
        """Nothing to release."""
        self.log("stopped")


__all__ = ["ExamplePlugin"]
