"""File selection widget with validation and drag and drop."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from ..dpi_scaler import DPIScaler
from .responsive_widget import ResponsiveWidget


class FileBrowserWidget(ResponsiveWidget):
    """A read-only path field with browse, clear and validity indicator.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        caption: Dialog caption.
        name_filter: Qt file dialog filter, e.g. ``"Python files (*.py)"``.
        directory_mode: Select a directory instead of a file.
    """

    #: Emitted with the selected path (empty when cleared).
    path_changed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        caption: str = "Select a file",
        name_filter: str = "All files (*)",
        directory_mode: bool = False,
    ) -> None:
        """Build the path row."""
        super().__init__(parent, scaler)
        self.caption = caption
        self.name_filter = name_filter
        self.directory_mode = directory_mode
        self.last_directory = str(Path.home())

        self.field = QLineEdit(self)
        self.field.setReadOnly(True)
        self.field.setPlaceholderText("no file selected")
        self.status = QLabel("", self)
        self.status.setFixedWidth(self.px(18))
        self.browse_button = QPushButton("Browse", self)
        self.browse_button.clicked.connect(self.browse)
        self.clear_button = QPushButton("x", self)
        self.clear_button.setFixedWidth(self.px(28))
        self.clear_button.clicked.connect(self.clear)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(4))
        layout.addWidget(self.field, 1)
        layout.addWidget(self.status)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.clear_button)
        self.setAcceptDrops(True)

    # -- API -----------------------------------------------------------------
    def path(self) -> str:
        """Return the selected path."""
        return self.field.text()

    def set_path(self, path: str | Path) -> None:
        """Set the selected path and refresh the validity indicator."""
        text = str(path)
        self.field.setText(text)
        self.field.setToolTip(text)
        self._update_status()
        if text:
            self.last_directory = str(Path(text).expanduser().parent)
        self.path_changed.emit(text)

    def clear(self) -> None:
        """Clear the selection."""
        self.field.clear()
        self.status.setText("")
        self.path_changed.emit("")

    def is_valid(self) -> bool:
        """Return ``True`` when the selected path exists."""
        text = self.path()
        if not text:
            return False
        candidate = Path(text).expanduser()
        return candidate.is_dir() if self.directory_mode else candidate.is_file()

    def browse(self) -> str:
        """Open the file dialog and return the chosen path."""
        if self.directory_mode:
            chosen = QFileDialog.getExistingDirectory(self, self.caption, self.last_directory)
        else:
            chosen, _ = QFileDialog.getOpenFileName(
                self, self.caption, self.last_directory, self.name_filter
            )
        if chosen:
            self.set_path(chosen)
        return chosen

    # -- drag and drop ----------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt naming
        """Accept dragged files."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt naming
        """Take the first dropped file as the selection."""
        urls = event.mimeData().urls()
        if urls:
            self.set_path(urls[0].toLocalFile())
            event.acceptProposedAction()

    def _update_status(self) -> None:
        """Show a tick or a cross depending on the path validity."""
        if not self.path():
            self.status.setText("")
            return
        valid = self.is_valid()
        self.status.setText("OK" if valid else "!")
        self.status.setStyleSheet(
            f"color:{'#22C55E' if valid else '#EF4444'};font-weight:600;"
        )
        self.status.setToolTip("File found" if valid else "File not found")


__all__ = ["FileBrowserWidget"]
