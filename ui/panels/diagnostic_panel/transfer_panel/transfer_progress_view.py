"""Progress view for an ongoing firmware transfer.

Wraps the generic :class:`~ui.widgets.progress_widget.ProgressWidget` with the
information specific to a flash session: the current phase (request download,
transfer data, transfer exit, verification), the block counters and the CRC of
the transferred image.

Example:
    >>> from ui.panels.diagnostic_panel.transfer_panel.transfer_progress_view import (
    ...     PHASES, phase_index, format_speed)
    >>> PHASES[0]
    'Preparing'
    >>> phase_index("transfer")
    2
    >>> format_speed(2048.0)
    '2.0 KB/s'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from src.core.enums.transfer_enums import TransferState
from src.core.models.file_transfer_model import TransferProgress
from src.utils.file_utils import human_size

from ....dpi_scaler import DPIScaler
from ....widgets.led_indicator import LedIndicator
from ....widgets.progress_widget import ProgressWidget
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_label import HeadingLabel, MonoLabel

__all__ = [
    "PHASES",
    "TransferProgressView",
    "format_speed",
    "phase_index",
    "state_to_led",
]

#: The ordered phases of a flash session.
PHASES: tuple[str, ...] = (
    "Preparing",
    "Request download",
    "Transferring data",
    "Transfer exit",
    "Verifying",
    "Done",
)

#: Keyword to phase index mapping used by :func:`phase_index`.
_PHASE_KEYWORDS: dict[str, int] = {
    "prepare": 0,
    "preparing": 0,
    "request": 1,
    "download": 1,
    "transfer": 2,
    "data": 2,
    "exit": 3,
    "verify": 4,
    "verifying": 4,
    "done": 5,
    "complete": 5,
}


def phase_index(name: str) -> int:
    """Return the index in :data:`PHASES` implied by *name*.

    Args:
        name: A free-form phase description, matched case insensitively.

    Returns:
        The phase index, or ``0`` when nothing matches.

    Example:
        >>> phase_index("Verifying CRC")
        4
        >>> phase_index("unknown")
        0
    """
    lowered = name.lower()
    for keyword, index in _PHASE_KEYWORDS.items():
        if keyword in lowered:
            return index
    return 0


def format_speed(bytes_per_second: float) -> str:
    """Return the transfer speed as a human readable string.

    Example:
        >>> format_speed(0.0)
        '-'
    """
    return f"{human_size(bytes_per_second)}/s" if bytes_per_second > 0 else "-"


def state_to_led(state: TransferState) -> str:
    """Return the LED state matching the transfer *state*.

    Example:
        >>> state_to_led(TransferState.IDLE)
        'idle'
    """
    return {
        TransferState.IDLE: "idle",
        TransferState.COMPLETED: "pass",
        TransferState.FAILED: "error",
        TransferState.CANCELLED: "warning",
    }.get(state, "running")


class TransferProgressView(ResponsiveWidget):
    """Shows the phase, the progress bar and the transfer statistics.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        progress_widget: The embedded generic progress widget.
        progress: The last :class:`TransferProgress` that was displayed.
    """

    #: Re-emitted when the operator presses cancel.
    cancel_requested = Signal()
    #: Re-emitted with the paused flag when the operator presses pause.
    pause_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the phase row, the progress widget and the statistics grid."""
        super().__init__(parent, scaler)
        self.progress = TransferProgress()

        self.led = LedIndicator("idle", 14, self, self.scaler)
        self.phase_label = QLabel(PHASES[0], self)
        self.phase_label.setProperty("role", "heading")
        self.file_label = QLabel("-", self)
        self.file_label.setProperty("role", "secondary")

        self.progress_widget = ProgressWidget(self, self.scaler, show_cancel=True)
        self.progress_widget.cancel_requested.connect(self.cancel_requested.emit)
        self.progress_widget.pause_toggled.connect(self.pause_toggled.emit)

        self.bytes_label = QLabel("-", self)
        self.blocks_label = QLabel("-", self)
        self.speed_label = QLabel("-", self)
        self.crc_label = MonoLabel("-", self, self.scaler)
        for label in (self.bytes_label, self.blocks_label, self.speed_label):
            label.setProperty("role", "secondary")

        stats = QGridLayout()
        stats.setHorizontalSpacing(self.spacing(12))
        stats.setVerticalSpacing(self.spacing(4))
        stats.addWidget(self._caption("Bytes"), 0, 0)
        stats.addWidget(self.bytes_label, 1, 0)
        stats.addWidget(self._caption("Blocks"), 0, 1)
        stats.addWidget(self.blocks_label, 1, 1)
        stats.addWidget(self._caption("Speed"), 0, 2)
        stats.addWidget(self.speed_label, 1, 2)
        stats.addWidget(self._caption("CRC32"), 0, 3)
        stats.addWidget(self.crc_label, 1, 3)

        header = QGridLayout()
        header.addWidget(self.led, 0, 0)
        header.addWidget(self.phase_label, 0, 1)
        header.addWidget(self.file_label, 0, 2)
        header.setColumnStretch(2, 1)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(HeadingLabel("Transfer progress", 3, self, self.scaler))
        layout.addLayout(header)
        layout.addWidget(self.progress_widget)
        layout.addLayout(stats)

    def _caption(self, text: str) -> QLabel:
        """Return a small secondary caption label."""
        label = QLabel(text, self)
        label.setProperty("role", "secondary")
        return label

    # -- API -----------------------------------------------------------------
    def update_progress(self, progress: TransferProgress) -> None:
        """Refresh every field from *progress*."""
        self.progress = progress
        self.progress_widget.update_progress(progress)
        self.led.set_state(state_to_led(progress.state))
        self.file_label.setText(progress.current_file or "-")
        self.bytes_label.setText(
            f"{human_size(progress.bytes_done)} / {human_size(progress.bytes_total)}"
        )
        self.blocks_label.setText(
            f"{progress.blocks_done}/{progress.blocks_total}" if progress.blocks_total else "-"
        )
        self.speed_label.setText(format_speed(progress.speed_bps))
        if progress.message:
            self.set_phase(progress.message)

    def set_phase(self, name: str) -> int:
        """Display the phase *name* and return its index in :data:`PHASES`."""
        index = phase_index(name)
        self.phase_label.setText(f"{index + 1}/{len(PHASES)}  {PHASES[index]}")
        self.phase_label.setToolTip(name)
        return index

    def set_crc(self, crc: int | None) -> None:
        """Display the CRC32 of the transferred image."""
        self.crc_label.setText("-" if crc is None else f"0x{crc:08X}")

    def set_busy(self, busy: bool) -> None:
        """Enable or disable the pause and cancel buttons."""
        self.progress_widget.set_busy(busy)

    def reset(self) -> None:
        """Return the view to its idle state."""
        self.progress = TransferProgress()
        self.progress_widget.reset()
        self.led.set_state("idle")
        self.phase_label.setText(PHASES[0])
        for label in (self.file_label, self.bytes_label, self.blocks_label, self.speed_label):
            label.setText("-")
        self.crc_label.setText("-")

    def percent(self) -> float:
        """Return the completion of the displayed transfer."""
        return self.progress.percent
