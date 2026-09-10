"""Firmware file queue for the flash manager.

The panel lets the operator collect the files to be flashed, reorder them,
enable or disable individual entries and see the detected format together with
the address range each file covers.

Example:
    >>> from ui.panels.diagnostic_panel.transfer_panel.file_selector_panel import (
    ...     detect_type, file_row, name_filter)
    >>> detect_type("firmware.hex").value
    'INTEL_HEX'
    >>> detect_type("app.s19").value
    'SREC'
    >>> detect_type("blob.bin").value
    'BINARY'
    >>> "*.hex" in name_filter()
    True
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.core.enums.transfer_enums import FirmwareFileType
from src.core.models.file_transfer_model import MemorySegment, TransferFile
from src.utils.file_utils import human_size

from ....dpi_scaler import DPIScaler
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel
from ....widgets.table_widget_enhanced import EnhancedTableWidget

__all__ = [
    "COLUMNS",
    "EXTENSION_TYPES",
    "FileSelectorPanel",
    "detect_type",
    "file_row",
    "name_filter",
]

#: Column titles of the queue table.
COLUMNS: list[str] = ["#", "File", "Type", "Start", "End", "Size", "Enabled"]

#: Mapping of file suffix to firmware file type.
EXTENSION_TYPES: dict[str, FirmwareFileType] = {
    ".hex": FirmwareFileType.INTEL_HEX,
    ".ihex": FirmwareFileType.INTEL_HEX,
    ".ihx": FirmwareFileType.INTEL_HEX,
    ".s19": FirmwareFileType.SREC,
    ".s28": FirmwareFileType.SREC,
    ".s37": FirmwareFileType.SREC,
    ".srec": FirmwareFileType.SREC,
    ".mot": FirmwareFileType.SREC,
    ".bin": FirmwareFileType.BINARY,
    ".rom": FirmwareFileType.BINARY,
    ".elf": FirmwareFileType.ELF,
    ".axf": FirmwareFileType.ELF,
}


def detect_type(path: str | Path) -> FirmwareFileType:
    """Return the firmware file type implied by the suffix of *path*.

    Example:
        >>> detect_type("unknown.xyz").value
        'UNKNOWN'
    """
    return EXTENSION_TYPES.get(Path(path).suffix.lower(), FirmwareFileType.UNKNOWN)


def name_filter() -> str:
    """Return the Qt file dialog filter covering every supported format.

    Example:
        >>> name_filter().startswith("Firmware files")
        True
    """
    patterns = " ".join(f"*{suffix}" for suffix in sorted(EXTENSION_TYPES))
    return (
        f"Firmware files ({patterns});;"
        "Intel HEX (*.hex *.ihex *.ihx);;"
        "Motorola S-record (*.s19 *.s28 *.s37 *.srec *.mot);;"
        "Raw binary (*.bin *.rom);;"
        "ELF (*.elf *.axf);;"
        "All files (*)"
    )


def file_row(index: int, transfer_file: TransferFile) -> dict[str, Any]:
    """Return the table row describing *transfer_file*.

    Args:
        index: Zero based position in the queue.
        transfer_file: The queued file.

    Returns:
        A mapping with one key per entry of :data:`COLUMNS`.

    Example:
        >>> from pathlib import Path
        >>> from src.core.models.file_transfer_model import MemorySegment, TransferFile
        >>> f = TransferFile(Path("a.bin"), segments=[MemorySegment(0x8000, b"\\x00" * 16)])
        >>> row = file_row(0, f)
        >>> row["Start"], row["Size"], row["Enabled"]
        ('0x00008000', '16 B', 'yes')
    """
    segments = transfer_file.segments
    end = max((segment.end_address for segment in segments), default=0)
    return {
        "#": str(index + 1),
        "File": transfer_file.path.name,
        "Type": transfer_file.file_type.value,
        "Start": f"0x{transfer_file.start_address:08X}",
        "End": f"0x{end:08X}",
        "Size": human_size(transfer_file.total_size),
        "Enabled": "yes" if transfer_file.enabled else "no",
        "_path": str(transfer_file.path),
    }


class FileSelectorPanel(ResponsiveWidget):
    """Manages the ordered queue of firmware files to flash.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        files: The queued :class:`TransferFile` objects, in transfer order.
        table: The queue table.
    """

    #: Emitted with the queue whenever it changes.
    files_changed = Signal(list)
    #: Emitted with the file selected in the table.
    file_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the queue table and its toolbar."""
        super().__init__(parent, scaler)
        self.files: list[TransferFile] = []
        self.last_directory = str(Path.home())

        self.table = EnhancedTableWidget(COLUMNS, self, self.scaler)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        self.add_button = ScalableButton("Add files", "add", self, self.scaler, accent=True)
        self.add_button.clicked.connect(self.browse)
        self.remove_button = ScalableButton("Remove", "remove", self, self.scaler)
        self.remove_button.clicked.connect(self.remove_selected)
        self.up_button = ScalableButton("Up", "chevron_right", self, self.scaler)
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        self.down_button = ScalableButton("Down", "chevron_down", self, self.scaler)
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        self.toggle_button = ScalableButton("Enable/disable", "success", self, self.scaler)
        self.toggle_button.clicked.connect(self.toggle_selected)
        self.clear_button = ScalableButton("Clear", "clear", self, self.scaler, danger=True)
        self.clear_button.clicked.connect(self.clear)

        self.summary_label = QLabel("no file queued", self)
        self.summary_label.setProperty("role", "secondary")

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(4))
        for button in (
            self.add_button,
            self.remove_button,
            self.up_button,
            self.down_button,
            self.toggle_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(HeadingLabel("Firmware files", 3, self, self.scaler))
        layout.addLayout(toolbar)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.summary_label)

        self.setAcceptDrops(True)

    # -- queue management ----------------------------------------------------
    def add_path(self, path: str | Path) -> TransferFile | None:
        """Append *path* to the queue.

        Returns:
            The created :class:`TransferFile`, or ``None`` when the path is
            already queued.
        """
        resolved = Path(path).expanduser()
        if any(existing.path == resolved for existing in self.files):
            return None
        transfer_file = TransferFile(path=resolved, file_type=detect_type(resolved))
        self.files.append(transfer_file)
        self.last_directory = str(resolved.parent)
        self.refresh()
        return transfer_file

    def add_paths(self, paths: Iterable[str | Path]) -> int:
        """Append every path of *paths* and return how many were added."""
        added = sum(1 for path in paths if self.add_path(path) is not None)
        return added

    def set_segments(self, path: str | Path, segments: list[MemorySegment]) -> bool:
        """Attach the parsed *segments* to the queued file at *path*.

        Returns:
            ``True`` when the file was found.
        """
        resolved = Path(path).expanduser()
        for transfer_file in self.files:
            if transfer_file.path == resolved:
                transfer_file.segments = list(segments)
                self.refresh()
                return True
        return False

    def browse(self) -> int:
        """Open the file dialog and queue every chosen file."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select firmware files", self.last_directory, name_filter()
        )
        return self.add_paths(paths)

    def remove_selected(self) -> int:
        """Remove every selected row and return how many were removed."""
        indexes = sorted(self._selected_indexes(), reverse=True)
        for index in indexes:
            del self.files[index]
        self.refresh()
        return len(indexes)

    def move_selected(self, offset: int) -> bool:
        """Move the selected row by *offset* positions.

        Returns:
            ``True`` when the move was possible.
        """
        indexes = self._selected_indexes()
        if len(indexes) != 1:
            return False
        source = indexes[0]
        target = source + offset
        if not 0 <= target < len(self.files):
            return False
        self.files[source], self.files[target] = self.files[target], self.files[source]
        self.refresh()
        self.table.selectRow(target)
        return True

    def toggle_selected(self) -> int:
        """Toggle the enabled flag of every selected row."""
        indexes = self._selected_indexes()
        for index in indexes:
            self.files[index].enabled = not self.files[index].enabled
        self.refresh()
        return len(indexes)

    def clear(self) -> None:
        """Empty the queue."""
        self.files.clear()
        self.refresh()

    # -- queries -------------------------------------------------------------
    def enabled_files(self) -> list[TransferFile]:
        """Return the queued files that are enabled, in transfer order."""
        return [entry for entry in self.files if entry.enabled]

    def total_size(self) -> int:
        """Return the number of bytes that will be transferred."""
        return sum(entry.total_size for entry in self.enabled_files())

    def selected_file(self) -> TransferFile | None:
        """Return the file of the selected row, or ``None``."""
        indexes = self._selected_indexes()
        return self.files[indexes[0]] if indexes else None

    def refresh(self) -> None:
        """Rebuild the table and the summary label."""
        self.table.set_rows([file_row(i, f) for i, f in enumerate(self.files)])
        enabled = self.enabled_files()
        self.summary_label.setText(
            f"{len(enabled)}/{len(self.files)} file(s) enabled, "
            f"{human_size(self.total_size())} to transfer"
            if self.files
            else "no file queued"
        )
        self.files_changed.emit(list(self.files))

    # -- drag and drop ----------------------------------------------------------
    def dragEnterEvent(self, event: Any) -> None:  # noqa: N802 - Qt naming
        """Accept dragged files."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: Any) -> None:  # noqa: N802 - Qt naming
        """Queue every dropped file."""
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.add_paths(paths)
            event.acceptProposedAction()

    # -- internals ------------------------------------------------------------
    def _selected_indexes(self) -> list[int]:
        """Return the indexes of the selected rows."""
        model = self.table.selectionModel()
        if model is None:
            return []
        return sorted(index.row() for index in model.selectedRows())

    def _on_selection_changed(self) -> None:
        """Emit :attr:`file_selected` for the newly selected row."""
        selected = self.selected_file()
        if selected is not None:
            self.file_selected.emit(selected)
