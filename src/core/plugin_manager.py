"""Plugin discovery, loading and lifecycle management."""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..utils.file_utils import iter_files
from .configuration_manager import ConfigurationManager, get_config
from .event_bus import EventBus, EventType, get_event_bus
from .interfaces.i_plugin import IPlugin

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LoadedPlugin:
    """A plugin instance plus its provenance.

    Attributes:
        instance: The plugin object.
        path: File the plugin was loaded from.
        enabled: Whether the plugin is currently active.
        error: Error message when loading or initialising failed.
    """

    instance: IPlugin
    path: Path
    enabled: bool = True
    error: str = ""

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return self.instance.name or type(self.instance).__name__

    @property
    def identifier(self) -> str:
        """Return the plugin identifier."""
        return self.instance.plugin_id or self.name

    def info(self) -> dict[str, Any]:
        """Return the metadata shown in the plugin settings page.

        The ``identifier`` key is always present: the settings page keys its
        enable/disable list on it, so it must never fall back to ``"?"`` even
        when the plugin does not report one itself.
        """
        data = dict(self.instance.get_info())
        data.update(
            {
                "identifier": self.identifier,
                "name": data.get("name") or self.name,
                "path": str(self.path),
                "enabled": self.enabled,
                "error": self.error,
            }
        )
        return data


class PluginManager:
    """Discovers, loads and unloads plugins.

    Plugins are Python modules under the configured directories that define a
    subclass of :class:`IPlugin`.

    Args:
        config: Application configuration.
        event_bus: Shared event bus.

    Example:
        >>> manager = PluginManager()
        >>> isinstance(manager.discover(), list)
        True
    """

    def __init__(
        self,
        config: ConfigurationManager | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Create the manager with an empty registry."""
        self.config = config or get_config()
        self.bus = event_bus or get_event_bus()
        self.plugins: dict[str, LoadedPlugin] = {}

    # -- discovery ----------------------------------------------------------
    def directories(self) -> list[Path]:
        """Return the configured plugin directories that exist."""
        raw = self.config.get("plugins.directories", ["plugins"])
        if isinstance(raw, str):
            raw = [part.strip() for part in raw.split(",") if part.strip()]
        root = Path(__file__).resolve().parents[2]
        result: list[Path] = []
        for entry in raw or []:
            candidate = Path(entry)
            if not candidate.is_absolute():
                candidate = root / candidate
            if candidate.is_dir():
                result.append(candidate)
        return result

    def discover(self) -> list[Path]:
        """Return every candidate plugin file."""
        files: list[Path] = []
        for directory in self.directories():
            for path in iter_files(directory, (".py",)):
                if path.name.startswith("_") or path.name == "plugin_base.py":
                    continue
                files.append(path)
        return files

    # -- loading --------------------------------------------------------------
    def load(self, path: str | Path, context: Any = None) -> LoadedPlugin | None:
        """Import one plugin file and initialise the plugin it defines."""
        file_path = Path(path).expanduser()
        disabled = {str(name) for name in self.config.get("plugins.disabled", [])}
        module_name = f"vdp_plugin_{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            _logger.warning("could not import the plugin %s", file_path)
            return None
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - a bad plugin must not stop the app
            _logger.exception("plugin %s failed to import", file_path.name)
            return LoadedPlugin(_BrokenPlugin(file_path.stem, str(exc)), file_path, False, str(exc))

        for _name, candidate in inspect.getmembers(module, inspect.isclass):
            if not issubclass(candidate, IPlugin) or inspect.isabstract(candidate):
                continue
            if candidate.__module__ != module.__name__:
                continue
            try:
                instance = candidate()
            except Exception as exc:  # noqa: BLE001
                _logger.exception("plugin %s could not be instantiated", candidate.__name__)
                return LoadedPlugin(
                    _BrokenPlugin(candidate.__name__, str(exc)), file_path, False, str(exc)
                )
            loaded = LoadedPlugin(instance, file_path, instance.plugin_id not in disabled)
            if loaded.enabled:
                try:
                    instance.initialize(context)
                except Exception as exc:  # noqa: BLE001
                    loaded.enabled = False
                    loaded.error = str(exc)
                    _logger.exception("plugin %s failed to initialise", loaded.name)
            self.plugins[loaded.identifier] = loaded
            self.bus.publish(
                EventType.SYSTEM_PLUGIN_LOADED,
                {"plugin": loaded.name, "enabled": loaded.enabled},
                "PluginManager",
            )
            _logger.info("loaded plugin %s from %s", loaded.name, file_path.name)
            return loaded
        return None

    def discover_and_load(self, context: Any = None) -> list[LoadedPlugin]:
        """Load every discovered plugin and return the successful ones."""
        result: list[LoadedPlugin] = []
        for path in self.discover():
            loaded = self.load(path, context)
            if loaded is not None and loaded.enabled:
                result.append(loaded)
        return result

    def unload(self, identifier: str) -> bool:
        """Shut a plugin down and remove it from the registry."""
        loaded = self.plugins.pop(identifier, None)
        if loaded is None:
            return False
        try:
            loaded.instance.shutdown()
        except Exception:  # noqa: BLE001
            _logger.exception("plugin %s failed to shut down", loaded.name)
        return True

    def shutdown_all(self) -> None:
        """Shut every loaded plugin down."""
        for identifier in list(self.plugins):
            self.unload(identifier)

    # -- introspection -----------------------------------------------------------
    def get(self, identifier: str) -> IPlugin | None:
        """Return the plugin instance registered under *identifier*."""
        loaded = self.plugins.get(identifier)
        return loaded.instance if loaded is not None else None

    def loaded_names(self) -> list[str]:
        """Return the names of the loaded plugins."""
        return sorted(plugin.name for plugin in self.plugins.values() if plugin.enabled)

    def describe(self) -> list[dict[str, Any]]:
        """Return the metadata of every plugin for the settings page."""
        return [plugin.info() for plugin in self.plugins.values()]

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.plugins)


class _BrokenPlugin(IPlugin):
    """Placeholder representing a plugin that failed to load."""

    def __init__(self, name: str, error: str) -> None:
        """Store the failure information."""
        self.plugin_id = f"broken.{name}"
        self.name = name
        self.version = "0.0.0"
        self.description = f"failed to load: {error}"

    def initialize(self, context: Any) -> None:
        """Do nothing; the plugin is not usable."""

    def shutdown(self) -> None:
        """Do nothing; the plugin is not usable."""


__all__ = ["PluginManager", "LoadedPlugin"]
