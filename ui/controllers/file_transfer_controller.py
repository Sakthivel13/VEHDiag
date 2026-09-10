"""File transfer controller driving the flash panel."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from src.core.models.file_transfer_model import TransferProgress
from src.data_processing.file_parsers import parse_firmware_file
from src.diagnostics.services.security.security_access import SecurityAccess
from src.diagnostics.services.session_control.diagnostic_session_control import (
    DiagnosticSessionControl,
)
from src.diagnostics.services.transfer_services.transfer_manager import (
    TransferManager,
    TransferOptions,
    TransferReport,
)
from src.diagnostics.uds_client import UDSClient

_logger = logging.getLogger(__name__)


class _TransferThread(QThread):
    """Runs the flash sequence off the UI thread."""

    #: Emitted with the progress after every block.
    progressed = Signal(object)
    #: Emitted with ``(index, state)`` when a sequence step changes.
    step_changed = Signal(int, str)
    #: Emitted with the list of reports when the transfer finished.
    finished_transfer = Signal(object)
    #: Emitted with the exception when the transfer crashed.
    failed = Signal(object)

    def __init__(
        self,
        client: UDSClient,
        files: list[Path],
        options: TransferOptions,
        base_address: int | None,
        security_level: int,
        algorithm: str,
    ) -> None:
        """Store the parameters of the run."""
        super().__init__()
        self.client = client
        self.files = files
        self.options = options
        self.base_address = base_address
        self.security_level = security_level
        self.algorithm = algorithm
        self.manager: TransferManager | None = None

    def run(self) -> None:
        """Execute the standard programming sequence."""
        reports: list[TransferReport] = []
        try:
            session = DiagnosticSessionControl(self.client)
            self.step_changed.emit(0, "running")
            session.enter_extended()
            self.step_changed.emit(0, "done")

            self.step_changed.emit(1, "running")
            self.client.control_dtc_setting(False)
            self.step_changed.emit(1, "done")

            self.step_changed.emit(2, "running")
            self.client.communication_control(0x03, 0x01)
            self.step_changed.emit(2, "done")

            self.step_changed.emit(3, "running")
            session.enter_programming()
            self.step_changed.emit(3, "done")

            self.step_changed.emit(4, "running")
            unlocked = SecurityAccess(self.client, self.algorithm).execute(self.security_level)
            self.step_changed.emit(4, "done" if unlocked.unlocked else "failed")

            self.manager = TransferManager(self.client, self.options, self.progressed.emit)
            for path in self.files:
                segments = parse_firmware_file(path, base_address=self.base_address)
                self.step_changed.emit(5, "running")
                for report in self.manager.download_segments(segments):
                    reports.append(report)
                    if not report.successful:
                        self.step_changed.emit(6, "failed")
                        self.finished_transfer.emit(reports)
                        return
            self.step_changed.emit(5, "done")
            self.step_changed.emit(6, "done")
            self.step_changed.emit(7, "done")
            self.finished_transfer.emit(reports)
        except Exception as exc:  # noqa: BLE001 - surfaced in the UI
            _logger.exception("transfer failed")
            self.failed.emit(exc)


class FileTransferController(QObject):
    """Connects the flash panel to the transfer manager.

    Args:
        panel: The flash manager view.
        window: The main window used for notifications.
    """

    #: Emitted with the reports when a transfer completes.
    transfer_completed = Signal(object)

    def __init__(self, panel: Any, window: Any = None) -> None:
        """Wire the panel signals."""
        super().__init__()
        self.panel = panel
        self.window = window
        self.client: UDSClient | None = None
        self._thread: _TransferThread | None = None

        panel.transfer_requested.connect(self.start)
        panel.cancel_requested.connect(self.cancel)
        panel.pause_requested.connect(self.pause)

    # -- lifecycle ----------------------------------------------------------
    def attach_client(self, client: UDSClient) -> None:
        """Bind the controller to a diagnostic client."""
        self.client = client

    def detach(self) -> None:
        """Cancel a running transfer and release the client."""
        self.cancel()
        self.client = None

    # -- actions ---------------------------------------------------------------
    def start(self, files: list[Path]) -> None:
        """Start the flash sequence for *files*."""
        if self.client is None:
            self._notify("Connect to a VCI before flashing", "warning")
            return
        if not files:
            return
        options = TransferOptions(
            block_size=self._block_size(),
            verify_after_transfer=self.panel.verify_checksum.isChecked(),
        )
        self.panel.set_busy(True)
        self._thread = _TransferThread(
            self.client, list(files), options, self.panel.base_address(), 0x11, "add_constant"
        )
        self._thread.progressed.connect(self.panel.update_progress)
        self._thread.step_changed.connect(self.panel.set_step_state)
        self._thread.finished_transfer.connect(self._on_finished)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

    def cancel(self) -> None:
        """Abort the running transfer."""
        if self._thread is not None and self._thread.manager is not None:
            self._thread.manager.cancel()
        self.panel.set_busy(False)

    def pause(self, paused: bool) -> None:
        """Pause or resume the running transfer."""
        if self._thread is None or self._thread.manager is None:
            return
        if paused:
            self._thread.manager.pause()
        else:
            self._thread.manager.resume()

    # -- callbacks ------------------------------------------------------------
    def _on_finished(self, reports: list[TransferReport]) -> None:
        """Report the outcome of the transfer."""
        self.panel.set_busy(False)
        for report in reports:
            self.panel.log(report.summary())
        successful = bool(reports) and all(report.successful for report in reports)
        self.transfer_completed.emit(reports)
        self._notify(
            "Transfer completed" if successful else "Transfer failed",
            "success" if successful else "error",
        )

    def _on_failed(self, error: Exception) -> None:
        """Report a crashed transfer."""
        self.panel.set_busy(False)
        self.panel.log(f"error: {error}")
        self._notify(f"Transfer failed: {error}", "error")

    def _block_size(self) -> int:
        """Return the block size chosen in the panel."""
        text = self.panel.block_size_box.currentText()
        return int(text) if text.isdigit() else 0

    def _notify(self, message: str, level: str = "info") -> None:
        """Show a toast and a status bar message."""
        if self.window is None:
            _logger.info("%s", message)
            return
        toasts = getattr(self.window, "toasts", None)
        if toasts is not None:
            getattr(toasts, level, toasts.info)(message)


__all__ = ["FileTransferController"]
