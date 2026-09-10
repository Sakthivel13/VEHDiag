"""Application lifecycle controller.

The controller owns the non-UI services (configuration, event bus, logging,
plugins, connection manager) and drives them through a defined lifecycle:

``INITIALIZING -> CONFIGURED -> STARTING -> RUNNING -> SHUTTING_DOWN -> STOPPED``

It works with or without a user interface, so the same object powers the GUI
application and the headless demo.
"""
from __future__ import annotations

import logging
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from ..communication.connection_manager import ConnectionManager, ConnectionProfile
from ..communication.vci_drivers.vci_scanner import DetectedVCI, VCIScanner
from ..core.models.did_model import DIDRegistry
from ..diagnostics.service_dispatcher import ServiceDispatcher
from ..diagnostics.services.data_services.read_data_by_id import build_registry
from ..diagnostics.uds_client import UDSClient
from ..logging_system.log_manager import LogManager, set_log_manager
from ..utils.platform_utils import app_data_dir, system_info
from .configuration_manager import ConfigurationManager, get_config, set_config
from .event_bus import EventBus, EventType, get_event_bus
from .plugin_manager import PluginManager

_logger = logging.getLogger(__name__)

#: Version of the platform.
VERSION = "0.1.0"


class ApplicationState(str, Enum):
    """Lifecycle states of the application."""

    INITIALIZING = "INITIALIZING"
    CONFIGURED = "CONFIGURED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass(slots=True)
class ApplicationContext:
    """Everything a plugin or a controller needs from the application.

    Attributes:
        config: The configuration manager.
        bus: The shared event bus.
        logs: The central log manager.
        connections: The connection manager.
        registry: The DID definition registry.
        version: Platform version.
    """

    config: ConfigurationManager
    bus: EventBus
    logs: LogManager
    connections: ConnectionManager
    registry: DIDRegistry
    version: str = VERSION


class Application:
    """Owns the non-UI services and drives the application lifecycle.

    Args:
        config: Configuration manager; created when omitted.
        event_bus: Shared event bus; created when omitted.
        headless: Skip everything that needs a user interface.

    Example:
        >>> app = Application(headless=True)
        >>> app.initialize()
        >>> app.state.value
        'CONFIGURED'
        >>> transport = app.connect()
        >>> client = app.create_client()
        >>> client.change_session(0x03).is_positive()
        True
        >>> app.shutdown()
        >>> app.state.value
        'STOPPED'
    """

    def __init__(
        self,
        config: ConfigurationManager | None = None,
        event_bus: EventBus | None = None,
        headless: bool = False,
    ) -> None:
        """Create the application in the ``INITIALIZING`` state."""
        self.state = ApplicationState.INITIALIZING
        self.headless = headless
        self.config = config or get_config()
        self.bus = event_bus or get_event_bus()
        self.logs: LogManager | None = None
        self.plugins: PluginManager | None = None
        self.connections: ConnectionManager | None = None
        self.scanner = VCIScanner(self.bus)
        self.registry = DIDRegistry()
        self.client: UDSClient | None = None
        self.dispatcher: ServiceDispatcher | None = None
        self.detected_devices: list[DetectedVCI] = []
        self.crash_handler_installed = False
        self._shutdown_hooks: list[Callable[[], None]] = []

    # -- lifecycle ----------------------------------------------------------
    def initialize(self) -> ApplicationContext:
        """Create every service in the documented order.

        Returns:
            The :class:`ApplicationContext` other layers work with.
        """
        set_config(self.config)
        self.bus.publish(EventType.SYSTEM_STARTUP, {"version": VERSION}, "Application")

        self.logs = LogManager(self.config, self.bus)
        set_log_manager(self.logs)
        self.logs.info(f"Vehicle Diagnostics Platform {VERSION} starting")
        for key, value in system_info().items():
            self.logs.debug(f"{key}: {value}")

        self.registry = build_registry(self.config.did_definitions())
        self.logs.info(f"loaded {len(self.registry)} data identifier definitions")

        self.plugins = PluginManager(self.config, self.bus)
        if bool(self.config.get("plugins.enabled", True)):
            loaded = self.plugins.discover_and_load(self.context())
            self.logs.info(f"loaded {len(loaded)} plugin(s)")

        self.connections = ConnectionManager(self.config, self.bus)
        self.state = ApplicationState.CONFIGURED
        return self.context()

    def start(self) -> None:
        """Move to the running state and announce readiness."""
        self.state = ApplicationState.STARTING
        self.detected_devices = self.scanner.scan()
        if self.logs is not None:
            self.logs.info(f"{len(self.detected_devices)} VCI interface(s) detected")
        self.state = ApplicationState.RUNNING
        self.bus.publish(EventType.SYSTEM_READY, {"devices": len(self.detected_devices)},
                         "Application")

    def shutdown(self) -> None:
        """Release every resource in reverse creation order."""
        if self.state in (ApplicationState.STOPPED, ApplicationState.SHUTTING_DOWN):
            return
        self.state = ApplicationState.SHUTTING_DOWN
        self.bus.publish(EventType.SYSTEM_SHUTDOWN, {}, "Application")
        for hook in reversed(self._shutdown_hooks):
            try:
                hook()
            except Exception:  # noqa: BLE001 - shutdown must never fail
                _logger.exception("shutdown hook failed")
        if self.connections is not None:
            try:
                self.connections.disconnect()
            except Exception:  # noqa: BLE001
                _logger.exception("failed to close the connection")
        if self.plugins is not None:
            self.plugins.shutdown_all()
        if self.logs is not None:
            self.logs.info("shutdown complete")
            self.logs.flush()
            self.logs.close()
        try:
            self.config.save()
        except Exception:  # noqa: BLE001
            _logger.exception("failed to save the configuration")
        self.bus.set_enabled(False)
        self.state = ApplicationState.STOPPED

    def add_shutdown_hook(self, hook: Callable[[], None]) -> None:
        """Register a callable invoked during :meth:`shutdown`."""
        self._shutdown_hooks.append(hook)

    # -- convenience API -------------------------------------------------------
    def context(self) -> ApplicationContext:
        """Return the current :class:`ApplicationContext`.

        Raises:
            RuntimeError: :meth:`initialize` has not been called.
        """
        if self.logs is None or self.connections is None:
            # Allow the context to be built during initialise as well.
            self.logs = self.logs or LogManager(self.config, self.bus)
            self.connections = self.connections or ConnectionManager(self.config, self.bus)
        return ApplicationContext(
            config=self.config,
            bus=self.bus,
            logs=self.logs,
            connections=self.connections,
            registry=self.registry,
            version=VERSION,
        )

    def connect(self, profile: ConnectionProfile | None = None) -> Any:
        """Open the diagnostic connection and return the transport."""
        if self.connections is None:
            self.initialize()
        assert self.connections is not None
        return self.connections.connect(profile)

    def disconnect(self) -> None:
        """Close the diagnostic connection."""
        if self.connections is not None:
            self.connections.disconnect()
        self.client = None
        self.dispatcher = None

    def create_client(self) -> UDSClient:
        """Create the UDS client for the active transport.

        Raises:
            RuntimeError: No connection is open.
        """
        if self.connections is None or self.connections.transport is None:
            raise RuntimeError("connect before creating a diagnostic client")
        from ..diagnostics.uds_client import UDSClientConfig

        self.client = UDSClient(
            self.connections.transport,
            UDSClientConfig(
                p2_client_ms=float(self.config.get("diagnostics.p2_client_ms", 150)),
                p2_star_client_ms=float(self.config.get("diagnostics.p2_star_client_ms", 5000)),
            ),
            self.bus,
        )
        self.dispatcher = ServiceDispatcher(self.client)
        return self.client

    # -- diagnostics ------------------------------------------------------------
    def install_exception_handler(self) -> None:
        """Route uncaught exceptions to the log and a crash report file."""
        original = sys.excepthook

        def handler(kind: type[BaseException], value: BaseException, tb: Any) -> None:
            """Log the exception and write a crash report."""
            message = "".join(traceback.format_exception(kind, value, tb))
            _logger.critical("uncaught exception:\n%s", message)
            if self.logs is not None:
                self.logs.critical(f"uncaught exception: {value}")
            self.write_crash_report(message)
            self.bus.publish(EventType.SYSTEM_ERROR, {"error": str(value)}, "Application")
            original(kind, value, tb)

        sys.excepthook = handler
        self.crash_handler_installed = True

    def write_crash_report(self, details: str) -> Path:
        """Write a crash report and return its path."""
        directory = app_data_dir() / "crash_reports"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"crash_{datetime.now():%Y%m%d_%H%M%S}.txt"
        header = [f"Vehicle Diagnostics Platform {VERSION}", ""]
        header += [f"{key}: {value}" for key, value in system_info().items()]
        target.write_text("\n".join(header) + "\n\n" + details, encoding="utf-8")
        return target

    def info(self) -> dict[str, Any]:
        """Return a mapping describing the running application."""
        return {
            "version": VERSION,
            "state": self.state.value,
            "headless": self.headless,
            "devices": [device.label for device in self.detected_devices],
            "plugins": self.plugins.loaded_names() if self.plugins else [],
            "connection": self.connections.get_info() if self.connections else {},
            "dids": len(self.registry),
        }

    def __enter__(self) -> "Application":
        """Initialise and start the application for a ``with`` block."""
        self.initialize()
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        """Shut the application down when leaving the ``with`` block."""
        self.shutdown()


__all__ = ["Application", "ApplicationContext", "ApplicationState", "VERSION"]
