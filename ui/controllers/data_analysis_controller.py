"""Data analysis controller for the slicer, converter and monitor panels."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from src.core.models.did_model import DIDRegistry
from src.data_processing.data_converter import DataConverter
from src.data_processing.response_slicer import ResponseSlicer
from src.diagnostics.services.data_services.read_data_by_id import ReadDataByIdentifier
from src.diagnostics.uds_client import UDSClient

_logger = logging.getLogger(__name__)


class DataAnalysisController(QObject):
    """Feeds diagnostic responses into the analysis panels.

    Args:
        slicer_panel: The response slicer panel.
        converter_panel: The data converter panel.
        monitor_panel: The DID monitor panel.
        window: The main window used for notifications.
        registry: Known DID definitions.
    """

    #: Emitted with the slice values after every recalculation.
    values_ready = Signal(dict)

    def __init__(
        self,
        slicer_panel: Any,
        converter_panel: Any,
        monitor_panel: Any = None,
        window: Any = None,
        registry: DIDRegistry | None = None,
    ) -> None:
        """Wire the analysis panels together."""
        super().__init__()
        self.slicer_panel = slicer_panel
        self.converter_panel = converter_panel
        self.monitor_panel = monitor_panel
        self.window = window
        self.registry = registry or DIDRegistry()
        self.slicer = ResponseSlicer()
        self.converter = DataConverter()
        self.client: UDSClient | None = None
        self.last_response: bytes = b""

        slicer_panel.values_changed.connect(self.values_ready.emit)
        slicer_panel.load_last_button.clicked.connect(self.load_last_response)
        if monitor_panel is not None:
            monitor_panel.monitoring_started.connect(self.start_monitoring)
            monitor_panel.monitoring_stopped.connect(self.stop_monitoring)

        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._poll_monitor)
        self._monitored: list[int] = []

    # -- lifecycle ----------------------------------------------------------
    def attach_client(self, client: UDSClient) -> None:
        """Bind the controller to a diagnostic client."""
        self.client = client
        client.add_listener(self._on_response)

    def detach(self) -> None:
        """Stop monitoring and release the client."""
        self.stop_monitoring()
        if self.client is not None:
            self.client.remove_listener(self._on_response)
        self.client = None

    # -- analysis ------------------------------------------------------------
    def analyse(self, data: bytes) -> dict[str, Any]:
        """Load *data* into the slicer and the converter and return the values."""
        self.last_response = bytes(data)
        self.slicer_panel.set_data(self.last_response)
        self.converter_panel.set_data(self.last_response)
        return self.slicer_panel.values()

    def load_last_response(self) -> bytes:
        """Load the most recent diagnostic response into the slicer."""
        if self.last_response:
            self.analyse(self.last_response)
        return self.last_response

    def _on_response(self, response: Any) -> None:
        """Remember every response so *load last* works."""
        if getattr(response, "raw", b""):
            self.last_response = bytes(response.raw)

    # -- monitoring -----------------------------------------------------------
    def start_monitoring(self, dids: list[int], interval_ms: int) -> None:
        """Start polling *dids* every *interval_ms* milliseconds."""
        if self.client is None:
            self._notify("Connect to a VCI before monitoring", "warning")
            if self.monitor_panel is not None:
                self.monitor_panel.set_running(False)
            return
        self._monitored = list(dids)
        self._monitor_timer.start(max(100, interval_ms))

    def stop_monitoring(self) -> None:
        """Stop the periodic polling."""
        self._monitor_timer.stop()
        self._monitored = []

    def _poll_monitor(self) -> None:
        """Read the monitored DIDs once and refresh the table."""
        if self.client is None or not self._monitored or self.monitor_panel is None:
            return
        service = ReadDataByIdentifier(self.client, self.registry)
        try:
            values = service.read_many(self._monitored, batch_size=1)
        except Exception as exc:  # noqa: BLE001 - keep polling
            _logger.debug("monitor poll failed: %s", exc)
            return
        self.monitor_panel.update_values(values)

    def _notify(self, message: str, level: str = "info") -> None:
        """Show a toast if a window is available."""
        if self.window is None:
            return
        toasts = getattr(self.window, "toasts", None)
        if toasts is not None:
            getattr(toasts, level, toasts.info)(message)


__all__ = ["DataAnalysisController"]
