"""Transfer progress widget with speed, ETA and cancel support."""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QProgressBar, QPushButton, QWidget

from src.core.models.file_transfer_model import TransferProgress
from src.utils.file_utils import human_size

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole
from .responsive_widget import ResponsiveWidget


class ProgressWidget(ResponsiveWidget):
    """Shows a progress bar plus speed, ETA, elapsed time and block counters.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        show_cancel: Display the cancel button.
    """

    #: Emitted when the user presses the cancel button.
    cancel_requested = Signal()
    #: Emitted when the user presses the pause/resume button.
    pause_toggled = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        show_cancel: bool = True,
    ) -> None:
        """Build the progress bar and the statistics labels."""
        super().__init__(parent, scaler)
        self._paused = False

        self.bar = QProgressBar(self)
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(True)
        self.bar.setFormat("%p%")

        self.title_label = QLabel("Idle", self)
        self.speed_label = QLabel("-", self)
        self.eta_label = QLabel("-", self)
        self.elapsed_label = QLabel("-", self)
        self.blocks_label = QLabel("-", self)
        for label in (self.speed_label, self.eta_label, self.elapsed_label, self.blocks_label):
            label.setProperty("role", "secondary")

        self.pause_button = QPushButton("Pause", self)
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self._on_pause)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setProperty("danger", "true")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)

        layout = QGridLayout(self)
        gap = self.spacing(6)
        layout.setContentsMargins(gap, gap, gap, gap)
        layout.setHorizontalSpacing(self.spacing(12))
        layout.setVerticalSpacing(gap)
        layout.addWidget(self.title_label, 0, 0, 1, 4)
        layout.addWidget(self.bar, 1, 0, 1, 4)
        layout.addWidget(self._caption("Speed"), 2, 0)
        layout.addWidget(self.speed_label, 3, 0)
        layout.addWidget(self._caption("ETA"), 2, 1)
        layout.addWidget(self.eta_label, 3, 1)
        layout.addWidget(self._caption("Elapsed"), 2, 2)
        layout.addWidget(self.elapsed_label, 3, 2)
        layout.addWidget(self._caption("Blocks"), 2, 3)
        layout.addWidget(self.blocks_label, 3, 3)
        if show_cancel:
            layout.addWidget(self.pause_button, 4, 2)
            layout.addWidget(self.cancel_button, 4, 3)
        self.apply_font(FontRole.BODY_SMALL)

    def _caption(self, text: str) -> QLabel:
        """Return a small secondary caption label."""
        label = QLabel(text, self)
        label.setProperty("role", "secondary")
        return label

    # -- updates -------------------------------------------------------------
    def update_progress(self, progress: TransferProgress) -> None:
        """Refresh every field from a :class:`TransferProgress`."""
        self.bar.setValue(int(progress.percent))
        self.title_label.setText(
            f"{progress.state.value.title()}"
            + (f" - {progress.current_file}" if progress.current_file else "")
        )
        self.speed_label.setText(f"{human_size(progress.speed_bps)}/s")
        self.eta_label.setText(self._format_seconds(progress.eta_s))
        self.elapsed_label.setText(self._format_seconds(progress.elapsed_s))
        self.blocks_label.setText(
            f"{progress.blocks_done}/{progress.blocks_total}" if progress.blocks_total else "-"
        )
        self.bar.setFormat(
            f"%p%  ({human_size(progress.bytes_done)} / {human_size(progress.bytes_total)})"
        )

    def set_percent(self, percent: float, text: str = "") -> None:
        """Set the progress value directly."""
        self.bar.setValue(int(max(0.0, min(100.0, percent))))
        if text:
            self.title_label.setText(text)

    def set_indeterminate(self, active: bool, text: str = "Working...") -> None:
        """Switch the bar into the animated indeterminate mode."""
        self.bar.setRange(0, 0 if active else 100)
        if active:
            self.title_label.setText(text)

    def reset(self) -> None:
        """Return every field to its idle state."""
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.title_label.setText("Idle")
        for label in (self.speed_label, self.eta_label, self.elapsed_label, self.blocks_label):
            label.setText("-")
        self.pause_button.setChecked(False)

    def set_busy(self, busy: bool) -> None:
        """Enable or disable the pause and cancel buttons."""
        self.pause_button.setEnabled(busy)
        self.cancel_button.setEnabled(busy)

    def _on_pause(self, checked: bool) -> None:
        """Handle the pause toggle."""
        self._paused = checked
        self.pause_button.setText("Resume" if checked else "Pause")
        self.pause_toggled.emit(checked)

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        """Format a duration as ``1m 05s`` or ``12.3s``.

        Example:
            >>> ProgressWidget._format_seconds(65)
            '1m 05s'
            >>> ProgressWidget._format_seconds(12.34)
            '12.3s'
        """
        if seconds <= 0:
            return "-"
        if seconds >= 60:
            minutes, rest = divmod(int(seconds), 60)
            return f"{minutes}m {rest:02d}s"
        return f"{seconds:.1f}s"


__all__ = ["ProgressWidget"]
