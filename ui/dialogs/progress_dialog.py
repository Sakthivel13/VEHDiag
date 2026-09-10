"""Modal progress dialog wrapping the progress widget."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from src.core.models.file_transfer_model import TransferProgress

from ..dpi_scaler import DPIScaler
from ..widgets.progress_widget import ProgressWidget


class ProgressDialog(QDialog):
    """A modal dialog showing a long running operation.

    Args:
        title: Dialog title.
        parent: Parent widget.
        scaler: Shared DPI scaler.
        cancellable: Show the cancel button.
    """

    #: Emitted when the operator cancels the operation.
    cancelled = Signal()

    def __init__(
        self,
        title: str = "Working...",
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        cancellable: bool = True,
    ) -> None:
        """Build the dialog."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(self.scaler.px(460))
        self.progress = ProgressWidget(self, self.scaler, cancellable)
        self.progress.cancel_requested.connect(self._on_cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self.progress)

    def update_progress(self, progress: TransferProgress) -> None:
        """Refresh the embedded progress widget."""
        self.progress.update_progress(progress)

    def set_percent(self, percent: float, text: str = "") -> None:
        """Set the progress value directly."""
        self.progress.set_percent(percent, text)

    def set_indeterminate(self, active: bool, text: str = "Working...") -> None:
        """Switch to the indeterminate animation."""
        self.progress.set_indeterminate(active, text)

    def finish(self) -> None:
        """Close the dialog."""
        self.accept()

    def _on_cancel(self) -> None:
        """Emit :attr:`cancelled` and close the dialog."""
        self.cancelled.emit()
        self.reject()


__all__ = ["ProgressDialog"]
