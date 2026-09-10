"""Connection panel controller.

Runs the connect and scan operations on background threads so the UI never
blocks, and mirrors the resulting state back into the window.
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from src.communication.connection_manager import ConnectionManager, ConnectionProfile
from src.communication.transport_layer import TransportLayer
from src.communication.vci_drivers.vci_scanner import DetectedVCI, VCIScanner
from src.core.enums.protocol_enums import ConnectionState
from src.core.event_bus import EventBus, get_event_bus

_logger = logging.getLogger(__name__)


class _Worker(QThread):
    """Runs one callable on a background thread and reports the outcome."""

    #: Emitted with the return value of the callable.
    finished_ok = Signal(object)
    #: Emitted with the exception when the callable raised.
    failed = Signal(object)

    def __init__(self, function: Any, *args: Any, **kwargs: Any) -> None:
        """Store the callable and its arguments."""
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        """Execute the callable and emit the result."""
        try:
            self.finished_ok.emit(self.function(*self.args, **self.kwargs))
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            _logger.exception("background operation failed")
            self.failed.emit(exc)


class ConnectionController(QObject):
    """Wires the connection panel to the :class:`ConnectionManager`.

    Args:
        panel: The connection panel.
        manager: The connection manager.
        window: The main window (used for toasts and the status bar).
        event_bus: Shared event bus.
    """

    #: Emitted with the transport once the connection succeeded.
    connected = Signal(object)
    #: Emitted when the connection was closed.
    disconnected = Signal()

    def __init__(
        self,
        panel: Any,
        manager: ConnectionManager | None = None,
        window: Any = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Connect the panel signals to the manager."""
        super().__init__()
        self.panel = panel
        self.manager = manager or ConnectionManager()
        self.window = window
        self.bus = event_bus or get_event_bus()
        self.scanner = VCIScanner(self.bus)
        self.transport: TransportLayer | None = None
        self._worker: _Worker | None = None

        panel.connect_requested.connect(self.connect_to)
        panel.disconnect_requested.connect(self.disconnect)
        panel.scan_requested.connect(self.scan)

    # -- actions -------------------------------------------------------------
    def connect_to(self, profile: ConnectionProfile) -> None:
        """Open the connection described by *profile* on a worker thread."""
        self._set_state(ConnectionState.CONNECTING)
        self._worker = _Worker(self.manager.connect, profile)
        self._worker.finished_ok.connect(self._on_connected)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def disconnect(self) -> None:
        """Close the connection."""
        self._set_state(ConnectionState.DISCONNECTING)
        try:
            self.manager.disconnect()
        finally:
            self.transport = None
            self._set_state(ConnectionState.DISCONNECTED)
            self.disconnected.emit()
            self._notify("Disconnected", "info")

    def scan(self) -> None:
        """Scan for connected VCI hardware on a worker thread."""
        self._worker = _Worker(self.scanner.scan)
        self._worker.finished_ok.connect(self._on_scanned)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def reconnect(self) -> bool:
        """Reconnect using the last profile."""
        return self.manager.reconnect()

    @property
    def is_connected(self) -> bool:
        """Return ``True`` when a transport is available."""
        return self.manager.is_connected

    # -- callbacks ------------------------------------------------------------
    def _on_connected(self, transport: TransportLayer) -> None:
        """Store the transport and update the UI."""
        self.transport = transport
        self._set_state(ConnectionState.CONNECTED)
        self.connected.emit(transport)
        profile = self.manager.profile
        self._notify(
            f"Connected: {profile.vci_type.display_name} / {profile.protocol.value}", "success"
        )

    def _on_scanned(self, devices: list[DetectedVCI]) -> None:
        """Show the detected devices in the panel."""
        self.panel.show_devices(devices)
        self._notify(f"{len(devices)} interface(s) detected", "info")

    def _on_failed(self, error: Exception) -> None:
        """Report a failed operation to the operator."""
        self._set_state(ConnectionState.ERROR, str(error))
        self._notify(f"Connection failed: {error}", "error")
        if self.window is not None:
            from ..dialogs.error_dialog import ErrorDialog

            ErrorDialog.from_exception(error, self.window).exec()

    # -- helpers ---------------------------------------------------------------
    def _set_state(self, state: ConnectionState, message: str = "") -> None:
        """Propagate the connection state to the panel and the window."""
        self.panel.set_state(state, message)
        if self.window is not None:
            profile = self.manager.profile
            self.window.set_connection_state(
                state, profile.vci_type.display_name, profile.protocol.value, profile.bitrate
            )

    def _notify(self, message: str, level: str = "info") -> None:
        """Show a toast and a status bar message."""
        if self.window is None:
            return
        toasts = getattr(self.window, "toasts", None)
        if toasts is not None:
            getattr(toasts, level, toasts.info)(message)
        status = getattr(self.window, "status", None)
        if status is not None:
            status.set_message(message)


__all__ = ["ConnectionController"]
