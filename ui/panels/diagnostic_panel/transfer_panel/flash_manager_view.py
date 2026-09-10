"""Flash and data transfer panel."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.models.file_transfer_model import TransferProgress

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.progress_widget import ProgressWidget
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel
from ....widgets.table_widget_enhanced import EnhancedTableWidget

#: Steps of the standard flash sequence shown in the progress list.
FLASH_STEPS: tuple[str, ...] = (
    "1. Extended session (0x10 0x03)",
    "2. Disable DTC setting (0x85 0x02)",
    "3. Disable communication (0x28 0x03)",
    "4. Programming session (0x10 0x02)",
    "5. Security unlock (0x27)",
    "6. Request download (0x34)",
    "7. Transfer data (0x36)",
    "8. Transfer exit (0x37)",
    "9. Check dependencies (0x31)",
    "10. ECU reset (0x11 0x01)",
)


class FlashManagerView(ResponsiveWidget):
    """UI for selecting firmware files and running a flash sequence.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the list of file paths when the transfer starts.
    transfer_requested = Signal(list)
    #: Emitted when the operator cancels the transfer.
    cancel_requested = Signal()
    #: Emitted with the pause state.
    pause_requested = Signal(bool)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the file table, the settings and the progress views."""
        super().__init__(parent, scaler)
        self.files: list[Path] = []

        self.file_table = EnhancedTableWidget(
            ["#", "File", "Type", "Address", "Size", "Status"], self, self.scaler
        )
        self.add_button = ScalableButton("Add file", "folder_open", self, self.scaler)
        self.add_button.clicked.connect(self.add_files)
        self.remove_button = ScalableButton("Remove", "remove", self, self.scaler)
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button = ScalableButton("Clear all", "clear", self, self.scaler)
        self.clear_button.clicked.connect(self.clear_files)

        self.compression_box = QComboBox(self)
        self.compression_box.addItems(["None", "Manufacturer 1", "Manufacturer 2"])
        self.encryption_box = QComboBox(self)
        self.encryption_box.addItems(["None", "Manufacturer 1", "Manufacturer 2"])
        self.block_size_box = QComboBox(self)
        self.block_size_box.addItems(["Auto (from ECU)", "256", "512", "1024", "2048", "4096"])
        self.address_field = HexInputField(self, self.scaler, max_bytes=4,
                                           placeholder="08 00 00 00")
        self.verify_readback = QCheckBox("Verify by read-back", self)
        self.verify_checksum = QCheckBox("Verify checksum", self)
        self.verify_checksum.setChecked(True)

        self.sequence_table = EnhancedTableWidget(["Step", "State"], self, self.scaler)
        self.sequence_table.set_rows([{"Step": step, "State": "pending"} for step in FLASH_STEPS])
        self.sequence_table.setMaximumHeight(self.px(200))

        self.progress = ProgressWidget(self, self.scaler)
        self.progress.cancel_requested.connect(self.cancel_requested.emit)
        self.progress.pause_toggled.connect(self.pause_requested.emit)
        self.start_button = ScalableButton("Start transfer", "flash", self, self.scaler, accent=True)
        self.start_button.clicked.connect(self._on_start)

        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setProperty("role", "mono")
        self.log_view.setMaximumHeight(self.px(140))

        files_box = QGroupBox("Files to transfer", self)
        files_layout = QVBoxLayout(files_box)
        files_layout.addWidget(self.file_table)
        file_buttons = QHBoxLayout()
        file_buttons.addWidget(self.add_button)
        file_buttons.addWidget(self.remove_button)
        file_buttons.addWidget(self.clear_button)
        file_buttons.addStretch(1)
        files_layout.addLayout(file_buttons)

        settings_box = QGroupBox("Transfer settings", self)
        settings = QGridLayout(settings_box)
        settings.setSpacing(self.spacing(8))
        settings.addWidget(QLabel("Compression:", self), 0, 0)
        settings.addWidget(self.compression_box, 0, 1)
        settings.addWidget(QLabel("Encryption:", self), 0, 2)
        settings.addWidget(self.encryption_box, 0, 3)
        settings.addWidget(QLabel("Block size:", self), 1, 0)
        settings.addWidget(self.block_size_box, 1, 1)
        settings.addWidget(QLabel("Base address:", self), 1, 2)
        settings.addWidget(self.address_field, 1, 3)
        settings.addWidget(self.verify_readback, 2, 1)
        settings.addWidget(self.verify_checksum, 2, 2)

        sequence_box = QGroupBox("Transfer sequence", self)
        sequence_layout = QVBoxLayout(sequence_box)
        sequence_layout.addWidget(self.sequence_table)
        sequence_layout.addWidget(self.progress)
        sequence_layout.addWidget(self.start_button, 0, Qt.AlignmentFlag.AlignLeft)
        sequence_layout.addWidget(self.log_view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Flash / data transfer", 3, self, self.scaler))
        layout.addWidget(files_box, 1)
        layout.addWidget(settings_box)
        layout.addWidget(sequence_box, 1)

    # -- file management ----------------------------------------------------
    def add_files(self) -> list[Path]:
        """Open the file dialog and add the selected firmware files."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select firmware files",
            str(Path.home()),
            "Firmware files (*.hex *.ihex *.mot *.s19 *.s28 *.s37 *.srec *.bin *.elf);;All files (*)",
        )
        for path in paths:
            self.add_file(Path(path))
        return [Path(p) for p in paths]

    def add_file(self, path: Path) -> None:
        """Add one file to the transfer list."""
        from src.data_processing.file_parsers.file_merger import FileMerger

        info = FileMerger.describe_file(path)
        self.files.append(path)
        self.file_table.append_row(
            {
                "#": len(self.files),
                "File": info["name"],
                "Type": info["type"],
                "Address": info["address"],
                "Size": info["size"],
                "Status": info["error"] or "ready",
            }
        )

    def remove_selected(self) -> None:
        """Remove the selected rows from the transfer list."""
        for row in self.file_table.selected_rows():
            index = int(row.get("#", 0)) - 1
            if 0 <= index < len(self.files):
                del self.files[index]
        self._rebuild_table()

    def clear_files(self) -> None:
        """Empty the transfer list."""
        self.files.clear()
        self.file_table.clear_rows()

    def _rebuild_table(self) -> None:
        """Rebuild the file table after a removal."""
        paths = list(self.files)
        self.files.clear()
        self.file_table.clear_rows()
        for path in paths:
            self.add_file(path)

    # -- progress -------------------------------------------------------------
    def update_progress(self, progress: TransferProgress) -> None:
        """Refresh the progress widget."""
        self.progress.update_progress(progress)

    def set_step_state(self, index: int, state: str) -> None:
        """Update the state column of one sequence step."""
        rows = self.sequence_table.rows()
        if 0 <= index < len(rows):
            rows[index]["State"] = state
            self.sequence_table.set_rows(rows)

    def reset_steps(self) -> None:
        """Set every sequence step back to pending."""
        self.sequence_table.set_rows([{"Step": step, "State": "pending"} for step in FLASH_STEPS])

    def log(self, message: str) -> None:
        """Append a line to the transfer log."""
        self.log_view.appendPlainText(message)

    def set_busy(self, busy: bool) -> None:
        """Enable or disable the controls while a transfer runs."""
        self.start_button.set_loading(busy)
        self.progress.set_busy(busy)
        for widget in (self.add_button, self.remove_button, self.clear_button):
            widget.setEnabled(not busy)

    def base_address(self) -> int | None:
        """Return the base address entered for raw binary files."""
        data = self.address_field.value()
        return int.from_bytes(data, "big") if data else None

    def _on_start(self) -> None:
        """Emit the transfer request for the listed files."""
        if self.files:
            self.reset_steps()
            self.log_view.clear()
            self.transfer_requested.emit(list(self.files))


__all__ = ["FlashManagerView", "FLASH_STEPS"]
