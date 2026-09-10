"""Diagnostic panel controller.

Every diagnostic operation runs on a worker thread; the results are delivered
back to the widgets through Qt signals so the UI thread is never blocked.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal

from src.communication.transport_layer import TransportLayer
from src.core.configuration_manager import ConfigurationManager, get_config
from src.core.event_bus import EventBus, get_event_bus
from src.core.models.did_model import DIDRegistry
from src.diagnostics.service_dispatcher import ServiceDispatcher
from src.diagnostics.services.data_services.read_data_by_id import ReadDataByIdentifier
from src.diagnostics.services.dtc_services.clear_dtc import ClearDiagnosticInformation
from src.diagnostics.services.dtc_services.dtc_extended_reader import DTCExtendedReader
from src.diagnostics.services.dtc_services.dtc_snapshot_reader import DTCSnapshotReader
from src.diagnostics.services.dtc_services.read_dtc_information import ReadDTCInformation
from src.diagnostics.services.io_control.io_control_by_id import InputOutputControlByIdentifier
from src.diagnostics.services.misc_services.tester_present_scheduler import TesterPresentScheduler
from src.diagnostics.services.routine_control.routine_control import RoutineControl
from src.diagnostics.services.security.security_access import SecurityAccess
from src.diagnostics.services.session_control.diagnostic_session_control import (
    DiagnosticSessionControl,
)
from src.diagnostics.uds_client import UDSClient, UDSClientConfig

_logger = logging.getLogger(__name__)


class DiagnosticWorker(QThread):
    """Executes one diagnostic callable off the UI thread."""

    #: Emitted with the return value.
    succeeded = Signal(object)
    #: Emitted with the exception when the call raised.
    failed = Signal(object)

    def __init__(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Store the callable and its arguments."""
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        """Run the callable and emit the outcome."""
        try:
            self.succeeded.emit(self.function(*self.args, **self.kwargs))
        except Exception as exc:  # noqa: BLE001 - surfaced in the UI
            _logger.exception("diagnostic operation failed")
            self.failed.emit(exc)


class DiagnosticController(QObject):
    """Connects the diagnostic panel to the UDS services.

    Args:
        panel: The diagnostic main panel.
        window: The main window, used for toasts and the status bar.
        config: Application configuration.
        registry: Known DID definitions.
        event_bus: Shared event bus.
    """

    #: Emitted with the diagnostic client once a transport is attached.
    client_ready = Signal(object)

    def __init__(
        self,
        panel: Any,
        window: Any = None,
        config: ConfigurationManager | None = None,
        registry: DIDRegistry | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Wire every panel signal to a diagnostic operation."""
        super().__init__()
        self.panel = panel
        self.window = window
        self.config = config or get_config()
        self.registry = registry or DIDRegistry()
        self.bus = event_bus or get_event_bus()
        self.client: UDSClient | None = None
        self.dispatcher: ServiceDispatcher | None = None
        self.tester_present: TesterPresentScheduler | None = None
        self._workers: list[DiagnosticWorker] = []
        self._continuous = QTimer(self)
        self._continuous.timeout.connect(self._on_continuous_tick)
        self._continuous_dids: list[int] = []

        panel.session_view.session_requested.connect(self.change_session)
        panel.read_did_view.read_requested.connect(self.read_dids)
        panel.read_did_view.continuous_toggled.connect(self.set_continuous_read)
        panel.read_dtc_view.read_requested.connect(self.read_dtcs)
        panel.read_dtc_view.snapshot_requested.connect(self.read_snapshot)
        panel.read_dtc_view.extended_requested.connect(self.read_extended)
        panel.clear_dtc_view.clear_requested.connect(self.clear_dtcs)
        panel.security_view.unlock_requested.connect(self.unlock_security)
        panel.security_view.seed_requested.connect(self.request_seed)
        panel.security_view.key_submitted.connect(self.send_key)
        panel.io_control_view.control_requested.connect(self.io_control)
        panel.routine_view.routine_requested.connect(self.routine_control)
        panel.tester_present_view.send_requested.connect(self.send_tester_present)
        panel.tester_present_view.scheduler_toggled.connect(self.set_tester_present)
        panel.raw_view.request_submitted.connect(self.send_raw)

    # -- lifecycle ----------------------------------------------------------
    def attach_transport(self, transport: TransportLayer) -> UDSClient:
        """Create the UDS client for *transport* and enable the panel."""
        self.client = UDSClient(
            transport,
            UDSClientConfig(
                p2_client_ms=float(self.config.get("diagnostics.p2_client_ms", 150)),
                p2_star_client_ms=float(self.config.get("diagnostics.p2_star_client_ms", 5000)),
                max_pending_responses=int(self.config.get("diagnostics.max_pending_responses", 20)),
                retry_on_busy=bool(self.config.get("diagnostics.retry_on_busy", True)),
                max_retries=int(self.config.get("diagnostics.max_retries", 3)),
            ),
            self.bus,
        )
        self.dispatcher = ServiceDispatcher(self.client)
        self.tester_present = TesterPresentScheduler(
            self.client, float(self.config.get("diagnostics.tester_present_interval_ms", 2000))
        )
        self.panel.set_connected(True)
        self.client_ready.emit(self.client)
        return self.client

    def detach(self) -> None:
        """Release the client when the connection is closed."""
        self._continuous.stop()
        if self.tester_present is not None:
            self.tester_present.stop()
        self.client = None
        self.dispatcher = None
        self.panel.set_connected(False)

    # -- session -------------------------------------------------------------
    def change_session(self, session: int) -> None:
        """Change the diagnostic session."""
        if not self._require_client():
            return
        view = self.panel.session_view
        view.set_busy(True)
        self._run(
            lambda: DiagnosticSessionControl(self.client).execute(session),
            lambda result: self._on_session(result),
            lambda _e: view.set_busy(False),
        )

    def _on_session(self, result: Any) -> None:
        """Apply a session change result to the UI."""
        view = self.panel.session_view
        view.set_busy(False)
        view.set_active_session(
            result.session,
            result.timing.p2_server_ms,
            result.timing.p2_star_server_ms,
            float(self.config.get("diagnostics.s3_client_ms", 4000)),
        )
        if result.response is not None:
            view.log_exchange(result.response.request, result.response.raw)
        if self.window is not None:
            self.window.status.set_session(result.descriptor.label)
            self.window.toolbar.set_session(result.session)
        if self.tester_present is not None and bool(
            self.config.get("diagnostics.tester_present_enabled", True)
        ):
            self.tester_present.sync_with_session()
            self.panel.tester_present_view.set_active(self.tester_present.is_running)
        self._notify(str(result), "success" if result.accepted else "warning")

    # -- data identifiers ------------------------------------------------------
    def read_dids(self, dids: list[int]) -> None:
        """Read one or several data identifiers."""
        if not self._require_client():
            return
        view = self.panel.read_did_view
        view.set_busy(True)
        service = ReadDataByIdentifier(self.client, self.registry)
        self._run(
            lambda: service.read_many(list(dids)),
            lambda values: (view.set_busy(False), view.show_values(values)),
            lambda _e: view.set_busy(False),
        )

    def set_continuous_read(self, enabled: bool, interval_ms: int) -> None:
        """Start or stop the continuous DID read."""
        self._continuous_dids = self.panel.read_did_view.listed_dids()
        if enabled and self._continuous_dids:
            self._continuous.start(max(100, interval_ms))
        else:
            self._continuous.stop()

    def _on_continuous_tick(self) -> None:
        """Read the monitored DIDs once."""
        if self.client is not None and self._continuous_dids:
            self.read_dids(self._continuous_dids)

    # -- DTCs --------------------------------------------------------------------
    def read_dtcs(self, sub_function: int, status_mask: int) -> None:
        """Read the DTCs matching the mask."""
        if not self._require_client():
            return
        view = self.panel.read_dtc_view
        view.set_busy(True)
        catalogue = self.config.definitions("dtc_definitions").get("catalogue")
        service = ReadDTCInformation(self.client, catalogue)
        self._run(
            lambda: service.execute(sub_function, status_mask),
            lambda report: (view.set_busy(False), view.show_report(report),
                            self._notify(f"{len(report)} DTC(s) read", "info")),
            lambda _e: view.set_busy(False),
        )

    def read_snapshot(self, dtc: int) -> None:
        """Read the freeze frame of one DTC."""
        if not self._require_client():
            return
        self._run(
            lambda: DTCSnapshotReader(self.client).read(dtc),
            lambda result: self.panel.read_dtc_view.show_detail(result),
        )

    def read_extended(self, dtc: int) -> None:
        """Read the extended data of one DTC."""
        if not self._require_client():
            return
        self._run(
            lambda: DTCExtendedReader(self.client).read(dtc),
            lambda result: self.panel.read_dtc_view.show_detail(result),
        )

    def clear_dtcs(self, group: int) -> None:
        """Clear the DTC memory."""
        if not self._require_client():
            return
        view = self.panel.clear_dtc_view
        view.set_busy(True)
        self._run(
            lambda: ClearDiagnosticInformation(self.client).execute(group),
            lambda result: (view.set_busy(False), view.show_result(result),
                            self._notify(result.summary,
                                         "success" if result.accepted else "warning")),
            lambda _e: view.set_busy(False),
        )

    # -- security ------------------------------------------------------------------
    def unlock_security(self, level: int, source: str, algorithm: str, path: str) -> None:
        """Run the complete unlock sequence."""
        if not self._require_client():
            return
        view = self.panel.security_view
        view.set_busy(True)
        service = SecurityAccess(self.client, algorithm)
        if source in ("External library", "Python script") and path:
            try:
                service.load_external(path)
            except Exception as exc:  # noqa: BLE001 - reported to the operator
                view.set_busy(False)
                self._notify(f"could not load the algorithm: {exc}", "error")
                return
        self._run(
            lambda: service.execute(level),
            lambda result: (view.set_busy(False), view.show_result(result),
                            self._update_security(result)),
            lambda _e: view.set_busy(False),
        )

    def request_seed(self, level: int) -> None:
        """Request only the seed."""
        if not self._require_client():
            return
        service = SecurityAccess(self.client, self.panel.security_view.algorithm())
        self._run(
            lambda: service.request_seed(level),
            lambda seed: (self.panel.security_view.show_seed(seed),
                          self.panel.security_view.show_key(service.compute(seed, level))),
        )

    def send_key(self, level: int, key: bytes) -> None:
        """Submit a manually entered key."""
        if not self._require_client():
            return
        service = SecurityAccess(self.client)
        self._run(
            lambda: service.send_key(level, key),
            lambda ok: (self.panel.security_view.set_unlocked(bool(ok)),
                        self._notify("unlocked" if ok else "key rejected",
                                     "success" if ok else "error")),
        )

    def _update_security(self, result: Any) -> None:
        """Mirror the security state in the status bar."""
        if self.window is not None:
            self.window.status.set_security(result.unlocked, result.level)
        self._notify(str(result), "success" if result.unlocked else "warning")

    # -- control services -----------------------------------------------------------
    def io_control(self, did: int, parameter: int, state: bytes, mask: bytes) -> None:
        """Run an input/output control request."""
        if not self._require_client():
            return
        view = self.panel.io_control_view
        view.set_busy(True)
        service = InputOutputControlByIdentifier(self.client)
        self._run(
            lambda: service.execute(did, parameter, state, mask),
            lambda result: (view.set_busy(False), view.show_result(result)),
            lambda _e: view.set_busy(False),
        )

    def routine_control(self, sub_function: int, routine_id: int, option: bytes) -> None:
        """Run a routine control request."""
        if not self._require_client():
            return
        view = self.panel.routine_view
        view.set_busy(True)
        service = RoutineControl(self.client)
        self._run(
            lambda: service.execute(routine_id, sub_function, option),
            lambda result: (view.set_busy(False), view.show_result(result)),
            lambda _e: view.set_busy(False),
        )

    # -- tester present ----------------------------------------------------------------
    def send_tester_present(self, suppress: bool) -> None:
        """Send one TesterPresent request."""
        if not self._require_client():
            return
        self._run(lambda: self.client.tester_present(suppress),
                  lambda _r: self._notify("tester present sent", "info"))

    def set_tester_present(self, enabled: bool, interval_ms: int, suppress: bool) -> None:
        """Start or stop the automatic keep-alive."""
        if self.tester_present is None:
            return
        self.tester_present.suppress_response = suppress
        if enabled:
            self.tester_present.start(float(interval_ms))
        else:
            self.tester_present.stop()
        self.panel.tester_present_view.update_statistics(
            self.tester_present.statistics.sent,
            self.tester_present.statistics.failed,
            self.tester_present.statistics.last_sent_at,
        )

    # -- raw ---------------------------------------------------------------------------
    def send_raw(self, payload: bytes, functional: bool) -> None:
        """Send a raw UDS payload."""
        if not self._require_client():
            return
        view = self.panel.raw_view
        view.set_busy(True)
        self._run(
            lambda: self.client.send_request(payload, functional=functional),
            lambda response: (
                view.set_busy(False),
                view.show_response(response.request, response.raw, response.summary(),
                                   response.elapsed_ms),
            ),
            lambda _e: view.set_busy(False),
        )

    # -- helpers ----------------------------------------------------------------------------
    def _require_client(self) -> bool:
        """Return ``True`` when a client is available, warning otherwise."""
        if self.client is None:
            self._notify("Connect to a VCI first", "warning")
            return False
        return True

    def _run(
        self,
        function: Callable[[], Any],
        on_success: Callable[[Any], Any],
        on_error: Callable[[Exception], Any] | None = None,
    ) -> DiagnosticWorker:
        """Run *function* on a worker thread and dispatch the result."""
        worker = DiagnosticWorker(function)
        # Queue explicitly: the callbacks touch widgets and start QTimers, and
        # an auto connection can still run them on the worker thread when the
        # controller itself lives there.
        worker.succeeded.connect(on_success, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(
            lambda exc: self._handle_error(exc, on_error),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        self._workers.append(worker)
        worker.start()
        return worker

    def _handle_error(self, error: Exception, on_error: Callable[[Exception], Any] | None) -> None:
        """Report a failed diagnostic operation."""
        if on_error is not None:
            on_error(error)
        self._notify(str(error), "error")
        if self.window is not None:
            from ..dialogs.error_dialog import ErrorDialog

            ErrorDialog.from_exception(error, self.window).exec()

    def _notify(self, message: str, level: str = "info") -> None:
        """Show a toast and a status bar message."""
        if self.window is None:
            _logger.info("%s", message)
            return
        toasts = getattr(self.window, "toasts", None)
        if toasts is not None:
            getattr(toasts, level, toasts.info)(message)
        status = getattr(self.window, "status", None)
        if status is not None:
            status.set_message(message)


__all__ = ["DiagnosticController", "DiagnosticWorker"]
