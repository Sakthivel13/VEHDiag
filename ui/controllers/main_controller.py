"""Main window controller wiring every sub-controller together."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal

from src.communication.connection_manager import ConnectionManager
from src.communication.transport_layer import TransportLayer
from src.core.configuration_manager import ConfigurationManager, get_config
from src.core.event_bus import Event, EventBus, EventType, get_event_bus
from src.core.models.did_model import DIDRegistry
from src.logging_system.log_manager import LogManager

from .connection_controller import ConnectionController
from .data_analysis_controller import DataAnalysisController
from .developer_mode_controller import DeveloperModeController
from .diagnostic_controller import DiagnosticController
from .file_transfer_controller import FileTransferController
from .log_controller import LogController
from .settings_controller import SettingsController
from .test_execution_controller import TestExecutionController

_logger = logging.getLogger(__name__)


class MainController(QObject):
    """Owns every controller and keeps the window in sync with the backend.

    Args:
        window: The main window.
        config: Application configuration.
        log_manager: The central log manager.
        registry: Known DID definitions.
        event_bus: Shared event bus.
    """

    #: Emitted when the application is fully wired and ready.
    ready = Signal()

    def __init__(
        self,
        window: Any,
        config: ConfigurationManager | None = None,
        log_manager: LogManager | None = None,
        registry: DIDRegistry | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Create every sub-controller and connect the cross-panel signals."""
        super().__init__()
        self.window = window
        self.config = config or get_config()
        self.bus = event_bus or get_event_bus()
        self.registry = registry or DIDRegistry()
        self.log_manager = log_manager or LogManager(self.config, self.bus)
        self.connection_manager = ConnectionManager(self.config, self.bus)

        self.connection = ConnectionController(
            window.connection_panel, self.connection_manager, window, self.bus
        )
        self.diagnostics = DiagnosticController(
            window.diagnostic_panel, window, self.config, self.registry, self.bus
        )
        self.developer = DeveloperModeController(window.developer_panel, window, self.bus)
        self.analysis = DataAnalysisController(
            window.slicer_panel, window.converter_panel, window.monitor_panel, window, self.registry
        )
        self.transfers = FileTransferController(
            window.diagnostic_panel.transfer_view, window
        )
        self.batch = TestExecutionController(window)
        self.logs = LogController(
            window.log_panel,
            self.log_manager,
            window,
            live_trace=getattr(window.analysis_workspace, "trace", None),
        )
        self.settings = SettingsController(window.settings_panel, window, self.config, self.bus)

        self.connection.connected.connect(self._on_connected)
        self.connection.disconnected.connect(self._on_disconnected)
        self.diagnostics.client_ready.connect(self.developer.attach_client)
        self.diagnostics.client_ready.connect(self.analysis.attach_client)
        self.diagnostics.client_ready.connect(self.transfers.attach_client)
        self.diagnostics.client_ready.connect(self.batch.attach_client)
        # The flashing panel drives its own runner, so it only needs the client.
        flash_panel = getattr(self.window.diagnostic_panel, "flash_panel", None)
        if flash_panel is not None:
            self.diagnostics.client_ready.connect(
                lambda client: flash_panel.set_client(client, self.connection_manager)
            )
        window.closing.connect(self.shutdown)
        window.toolbar.connect_requested.connect(
            lambda: self.connection.connect_to(window.connection_panel.profile())
        )
        window.toolbar.disconnect_requested.connect(self.connection.disconnect)
        window.toolbar.session_requested.connect(self.diagnostics.change_session)
        window.toolbar.run_all_requested.connect(self.developer.run_all)
        window.toolbar.cancel_requested.connect(self.developer.cancel)
        window.toolbar.run_requested.connect(self._run_current_step)

        self.bus.subscribe(EventType.COMM_ERROR, self._on_comm_error)
        self.bus.subscribe(EventType.DIAG_NRC_RECEIVED, self._on_nrc)
        self.bus.subscribe(EventType.COMM_MESSAGE_TX, self._on_traffic)
        self.bus.subscribe(EventType.COMM_MESSAGE_RX, self._on_traffic)
        self._tx_count = 0
        self._rx_count = 0

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        """Finish the startup sequence and announce readiness."""
        self.window.apply_theme()
        self.connection.scan()
        if bool(self.config.get("application.developer_mode", False)):
            self.window.toolbar.developer_action.setChecked(True)
        self.bus.publish(EventType.SYSTEM_READY, {}, "MainController")
        self.window.status.set_message("Ready")
        self.ready.emit()

    def shutdown(self) -> None:
        """Release every resource in a defined order."""
        _logger.info("shutting down")
        try:
            self.batch.detach()
            self.transfers.detach()
            self.developer.detach()
            self.diagnostics.detach()
            self.analysis.detach()
            self.connection.disconnect()
        finally:
            self.log_manager.flush()
            self.log_manager.close()
            self.config.save()

    # -- connection events ------------------------------------------------------
    def _on_connected(self, transport: TransportLayer) -> None:
        """Create the diagnostic client and enable the panels."""
        client = self.diagnostics.attach_transport(transport)
        self.window.status.set_session(client.state.session_label)
        self.window.status.set_security(False)

    def _on_disconnected(self) -> None:
        """Disable the diagnostic panels."""
        self.diagnostics.detach()
        self.developer.detach()
        self.analysis.detach()
        self.transfers.detach()
        self.batch.detach()

    def _run_current_step(self) -> None:
        """Run the step selected in the developer panel."""
        cards = self.window.developer_panel.editor.cards
        if cards:
            self.developer.run_step(cards[0].step)

    # -- event bus handlers -------------------------------------------------------
    def _on_comm_error(self, event: Event) -> None:
        """Show communication errors as a toast."""
        message = str(event.get("error") or event.get("reason") or "communication error")
        self.window.toasts.error(message)

    def _on_nrc(self, event: Event) -> None:
        """Show negative responses as a warning toast."""
        self.window.toasts.warning(str(event.get("info", "negative response")))

    def _on_traffic(self, event: Event) -> None:
        """Update the TX/RX counters in the status bar."""
        if event.type is EventType.COMM_MESSAGE_TX:
            self._tx_count += 1
        else:
            self._rx_count += 1
        self.window.status.set_counters(self._tx_count, self._rx_count)


__all__ = ["MainController"]
