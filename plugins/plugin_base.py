"""Base class for platform plugins."""
from __future__ import annotations

import logging
from typing import Any

from src.core.interfaces.i_plugin import IPlugin

_logger = logging.getLogger(__name__)


class PluginBase(IPlugin):
    """Convenience base class implementing the boring parts of :class:`IPlugin`.

    Subclasses override :meth:`on_initialize` and :meth:`on_shutdown` and may
    use the registration helpers to contribute services, drivers, seed-key
    algorithms or DID definitions.
    """

    plugin_id = "plugin.base"
    name = "Base plugin"
    version = "1.0.0"
    description = "A plugin that does nothing"

    def __init__(self) -> None:
        """Create the plugin without a context."""
        self.context: Any = None
        self.active = False

    # -- lifecycle ----------------------------------------------------------
    def initialize(self, context: Any) -> None:
        """Store the context and run the subclass hook."""
        self.context = context
        self.on_initialize(context)
        self.active = True
        _logger.info("plugin %s initialised", self.name)

    def shutdown(self) -> None:
        """Run the subclass hook and mark the plugin inactive."""
        try:
            self.on_shutdown()
        finally:
            self.active = False

    def on_initialize(self, context: Any) -> None:
        """Hook invoked when the plugin is loaded; override in subclasses."""

    def on_shutdown(self) -> None:
        """Hook invoked before the plugin is unloaded; override in subclasses."""

    # -- registration helpers -----------------------------------------------------
    def register_dids(self, definitions: dict[int, dict[str, Any]]) -> int:
        """Add OEM specific DID definitions to the registry.

        Returns:
            The number of definitions that were registered.
        """
        if self.context is None:
            return 0
        from src.core.models.did_model import DIDDefinition
        from src.core.enums.data_format_enums import DataFormat

        registry = getattr(self.context, "registry", None)
        if registry is None:
            return 0
        for did, entry in definitions.items():
            registry.add(
                DIDDefinition(
                    did=did,
                    name=str(entry.get("name", "")),
                    description=str(entry.get("description", "")),
                    length=entry.get("length"),
                    data_format=DataFormat(str(entry.get("format", "HEX"))),
                    unit=str(entry.get("unit", "")),
                )
            )
        return len(definitions)

    def register_seed_key(self, name: str, algorithm: Any) -> None:
        """Register an OEM seed-key algorithm."""
        from src.diagnostics.services.security.security_algorithms import register_algorithm

        register_algorithm(name, algorithm)

    def register_vci_driver(self, name: str, factory: Any) -> None:
        """Register an additional VCI driver."""
        from src.communication.vci_drivers.vci_factory import register_driver

        register_driver(name, factory)

    def subscribe(self, event_type: Any, handler: Any) -> int | None:
        """Subscribe to an event on the shared bus."""
        bus = getattr(self.context, "bus", None)
        return bus.subscribe(event_type, handler) if bus is not None else None

    def log(self, message: str) -> None:
        """Write an informational message to the platform log."""
        logs = getattr(self.context, "logs", None)
        if logs is not None:
            logs.info(f"[{self.name}] {message}")
        else:
            _logger.info("[%s] %s", self.name, message)


__all__ = ["PluginBase"]
