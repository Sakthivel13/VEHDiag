"""Flash / file transfer dialog.

Collects everything a download needs before it starts: the firmware file, the
target address and size, the block size, the data format identifier and the
optional verification step. Once running it shows the progress, the transfer
log and a cancel button.

Example:
    >>> from ui.dialogs.file_transfer_dialog import (
    ...     BLOCK_SIZES, block_count, format_identifier, validate_request)
    >>> 0x0400 in BLOCK_SIZES
    True
    >>> block_count(2048, 1024)
    2
    >>> block_count(2049, 1024)
    3
    >>> block_count(0, 1024)
    0
    >>> hex(format_identifier(compression=0, encryption=0))
    '0x0'
    >>> validate_request(size=0, block_size=1024)[1]
    'the transfer size must be positive'
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.enums.transfer_enums import TransferDirection, data_format_identifier
from src.core.models.file_transfer_model import TransferProgress
from src.data_processing.file_parsers import parse_firmware_file
from src.data_processing.file_parsers.memory_map import MemoryMap
from src.utils.file_utils import human_size

from ..dpi_scaler import DPIScaler
from ..panels.diagnostic_panel.transfer_panel.memory_layout_view import MemoryLayoutView
from ..panels.diagnostic_panel.transfer_panel.transfer_log_view import TransferLogView
from ..panels.diagnostic_panel.transfer_panel.transfer_progress_view import TransferProgressView
from ..widgets.file_browser_widget import FileBrowserWidget
from ..styles.layout_helpers import tune_form

__all__ = [
    "BLOCK_SIZES",
    "FileTransferDialog",
    "block_count",
    "format_identifier",
    "validate_request",
]

#: Block sizes offered by the drop-down.
BLOCK_SIZES: tuple[int, ...] = (0x0100, 0x0200, 0x0400, 0x0800, 0x1000, 0x2000)


def block_count(size: int, block_size: int) -> int:
    """Return how many TransferData blocks *size* bytes need.

    Example:
        >>> block_count(1024, 1024)
        1
    """
    if size <= 0 or block_size <= 0:
        return 0
    return (size + block_size - 1) // block_size


def format_identifier(compression: int = 0, encryption: int = 0) -> int:
    """Return the ISO 14229 dataFormatIdentifier byte.

    Example:
        >>> hex(format_identifier(compression=1, encryption=2))
        '0x12'
    """
    return data_format_identifier(compression, encryption)


def validate_request(
    size: int, block_size: int, address: int = 0, path: str | Path | None = None
) -> tuple[bool, str]:
    """Validate the parameters of a download request.

    Args:
        size: Number of bytes to transfer.
        block_size: Maximum block length.
        address: Target memory address.
        path: Firmware file, checked for existence when given.

    Returns:
        ``(is_valid, reason)``; *reason* is empty when the request is usable.

    Example:
        >>> validate_request(1024, 0)[1]
        'the block size must be positive'
        >>> validate_request(1024, 1024)
        (True, '')
    """
    if path is not None and not Path(path).expanduser().is_file():
        return False, "select an existing firmware file"
    if size <= 0:
        return False, "the transfer size must be positive"
    if block_size <= 0:
        return False, "the block size must be positive"
    if address < 0:
        return False, "the target address cannot be negative"
    return True, ""


class FileTransferDialog(QDialog):
    """Configures and monitors a firmware download.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        path: Firmware file pre-loaded into the dialog.

    Attributes:
        memory: The parsed memory map of the selected file.
        progress_view: The live progress widget.
        log_view: The step-by-step transfer log.
    """

    #: Emitted with the request mapping when the operator starts the transfer.
    transfer_requested = Signal(dict)
    #: Emitted when the operator cancels a running transfer.
    transfer_cancelled = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        path: str | Path | None = None,
    ) -> None:
        """Build the parameter form, the layout view and the progress area."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.memory = MemoryMap()
        self.running = False

        self.setWindowTitle("Transfer firmware")
        self.setModal(True)
        self.setMinimumSize(self.scaler.px(720), self.scaler.px(640))

        self.file_browser = FileBrowserWidget(
            self,
            self.scaler,
            caption="Select the firmware file",
            name_filter="Firmware (*.hex *.s19 *.srec *.mot *.bin *.elf);;All files (*)",
        )
        self.file_browser.path_changed.connect(self._on_file_changed)

        self.direction_box = QComboBox(self)
        for direction in TransferDirection:
            self.direction_box.addItem(direction.value, direction.value)

        self.address_field = QLineEdit("0", self)
        self.size_field = QLineEdit("0", self)
        self.block_box = QComboBox(self)
        self.block_box.setEditable(True)
        for size in BLOCK_SIZES:
            self.block_box.addItem(str(size), size)
        self.block_box.setCurrentText("1024")
        self.compression_box = QComboBox(self)
        self.compression_box.addItems(["0 - none", "1 - manufacturer specific"])
        self.encryption_box = QComboBox(self)
        self.encryption_box.addItems(["0 - none", "1 - manufacturer specific"])
        self.verify_box = QCheckBox("Verify with a CRC32 after the transfer", self)
        self.verify_box.setChecked(True)
        self.reset_box = QCheckBox("Reset the ECU when finished", self)

        self.layout_view = MemoryLayoutView(self, self.scaler)
        self.progress_view = TransferProgressView(self, self.scaler)
        self.progress_view.cancel_requested.connect(self.cancel)
        self.log_view = TransferLogView(self, self.scaler)

        self.status_label = QLabel("select a firmware file", self)
        self.status_label.setProperty("role", "secondary")
        self.status_label.setWordWrap(True)

        parameters = QGroupBox("Transfer parameters", self)
        form = QFormLayout(parameters)
        tune_form(form, self.scaler)
        form.setSpacing(self.scaler.spacing(6))
        form.addRow("File:", self.file_browser)
        form.addRow("Direction:", self.direction_box)
        form.addRow("Target address (hex):", self.address_field)
        form.addRow("Size (bytes):", self.size_field)
        form.addRow("Block size:", self.block_box)
        form.addRow("Compression:", self.compression_box)
        form.addRow("Encryption:", self.encryption_box)
        form.addRow("", self.verify_box)
        form.addRow("", self.reset_box)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        start_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if start_button is not None:
            start_button.setText("Start transfer")
            start_button.setProperty("accent", "true")
        self.buttons.accepted.connect(self.start)
        self.buttons.rejected.connect(self._on_reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.scaler.spacing(8))
        layout.addWidget(parameters)
        layout.addWidget(self.layout_view, 1)
        layout.addWidget(self.progress_view)
        layout.addWidget(self.log_view, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.buttons)

        if path:
            self.file_browser.set_path(path)

    # -- API -----------------------------------------------------------------
    def request(self) -> dict[str, Any]:
        """Return the request mapping described by the form."""
        return {
            "path": self.file_browser.path(),
            "direction": self.direction_box.currentText(),
            "address": self._hex(self.address_field.text()),
            "size": self._int(self.size_field.text()),
            "block_size": self._int(self.block_box.currentText(), 1024),
            "data_format": format_identifier(
                self.compression_box.currentIndex(), self.encryption_box.currentIndex()
            ),
            "verify": self.verify_box.isChecked(),
            "reset_after": self.reset_box.isChecked(),
            "segments": list(self.memory.segments),
        }

    def is_valid(self) -> bool:
        """Return ``True`` when the transfer may be started."""
        request = self.request()
        return validate_request(
            request["size"], request["block_size"], request["address"], request["path"] or None
        )[0]

    def start(self) -> dict[str, Any] | None:
        """Validate the form and emit :attr:`transfer_requested`."""
        request = self.request()
        valid, reason = validate_request(
            request["size"], request["block_size"], request["address"], request["path"] or None
        )
        if not valid:
            self.status_label.setText(reason)
            self.status_label.setProperty("state", "error")
            return None
        self.running = True
        self.log_view.start_session()
        self.log_view.log(
            "RequestDownload",
            f"0x{request['address']:08X}, {human_size(request['size'])}",
        )
        self.progress_view.set_busy(True)
        self.progress_view.set_phase("Request download")
        self.status_label.setText(
            f"{block_count(request['size'], request['block_size'])} block(s) to transfer"
        )
        self.transfer_requested.emit(request)
        return request

    def update_progress(self, progress: TransferProgress) -> None:
        """Forward *progress* to the embedded progress view."""
        self.progress_view.update_progress(progress)

    def finish(self, success: bool, message: str = "", crc: int | None = None) -> None:
        """Record the outcome of the transfer."""
        self.running = False
        self.progress_view.set_busy(False)
        self.progress_view.set_crc(crc)
        self.progress_view.set_phase("Done" if success else "Verifying")
        self.log_view.log(
            "Finished", message or ("transfer complete" if success else "transfer failed"),
            "ok" if success else "error",
        )
        self.status_label.setText(message or ("transfer complete" if success else "transfer failed"))
        self.status_label.setProperty("state", "success" if success else "error")

    def cancel(self) -> None:
        """Abort a running transfer."""
        if not self.running:
            return
        self.running = False
        self.log_view.log("Cancel", "cancelled by the operator", "warning")
        self.progress_view.set_busy(False)
        self.transfer_cancelled.emit()

    # -- internals ------------------------------------------------------------
    def _on_file_changed(self, path: str) -> None:
        """Parse the selected file and pre-fill the address and the size."""
        if not path:
            self.memory = MemoryMap()
            self.layout_view.clear()
            self.status_label.setText("select a firmware file")
            return
        try:
            segments = parse_firmware_file(path)
        except Exception as exc:  # noqa: BLE001 - report any parser failure
            self.status_label.setText(f"could not parse the file: {exc}")
            self.status_label.setProperty("state", "error")
            return
        self.memory = MemoryMap()
        self.memory.extend(segments)
        self.layout_view.set_memory(self.memory)
        self.address_field.setText(f"{self.memory.start_address:X}")
        self.size_field.setText(str(self.memory.total_size))
        self.status_label.setText(
            f"{len(self.memory.segments)} segment(s), {human_size(self.memory.total_size)}"
        )
        self.status_label.setProperty("state", "")

    @staticmethod
    def _int(text: str, fallback: int = 0) -> int:
        """Parse a decimal integer, falling back to *fallback*."""
        try:
            return int(text.strip())
        except ValueError:
            return fallback

    @staticmethod
    def _hex(text: str, fallback: int = 0) -> int:
        """Parse a hexadecimal address, falling back to *fallback*."""
        try:
            return int(text.strip().lower().removeprefix("0x"), 16)
        except ValueError:
            return fallback

    def _on_reject(self) -> None:
        """Cancel a running transfer, then close the dialog."""
        self.cancel()
        self.reject()
