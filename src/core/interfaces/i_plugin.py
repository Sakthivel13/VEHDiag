"""Abstract plugin interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IPlugin(ABC):
    """Contract implemented by every platform plugin.

    Plugins are discovered under ``plugins/`` and may register additional
    diagnostic services, VCI drivers, seed-key algorithms or UI panels.
    """

    #: Unique plugin identifier, e.g. ``"oem.volkswagen"``.
    plugin_id: str = ""
    #: Human readable plugin name.
    name: str = ""
    #: Semantic version string.
    version: str = "0.0.0"
    #: Short description shown in the plugin manager.
    description: str = ""

    @abstractmethod
    def initialize(self, context: Any) -> None:
        """Called once when the plugin is loaded.

        Args:
            context: The application context giving access to the event bus,
                configuration manager and service registries.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Called before the plugin is unloaded; release all resources."""

    def get_info(self) -> dict[str, str]:
        """Return metadata displayed by the plugin manager UI."""
        return {
            "id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
        }


__all__ = ["IPlugin"]
