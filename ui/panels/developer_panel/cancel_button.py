"""*Cancel* button aborting a running test sequence.

The specification requires that a cancellation takes effect within 500 ms, so
the button switches to a "cancelling" state immediately, arms a watchdog and
warns the operator when the runner does not stop in time.

Example:
    >>> from ui.panels.developer_panel.cancel_button import (
    ...     CANCEL_SHORTCUT, CANCEL_TIMEOUT_MS, caption_for)
    >>> CANCEL_SHORTCUT
    'Esc'
    >>> CANCEL_TIMEOUT_MS
    500
    >>> caption_for(False)
    'Cancel'
    >>> caption_for(True)
    'Cancelling...'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

from ...dpi_scaler import DPIScaler
from ...widgets.scalable_button import ScalableButton

__all__ = ["CANCEL_SHORTCUT", "CANCEL_TIMEOUT_MS", "CancelButton", "caption_for"]

#: Keyboard shortcut cancelling the run.
CANCEL_SHORTCUT = "Esc"

#: Maximum time the runner may take to honour the cancellation.
CANCEL_TIMEOUT_MS = 500


def caption_for(cancelling: bool) -> str:
    """Return the button caption for the given cancellation state.

    Example:
        >>> caption_for(cancelling=True)
        'Cancelling...'
    """
    return "Cancelling..." if cancelling else "Cancel"


class CancelButton(ScalableButton):
    """Aborts the running step or sequence.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        with_shortcut: Install the Escape shortcut on the parent window.
        timeout_ms: Watchdog delay before :attr:`cancel_timed_out` fires.

    Attributes:
        cancelling: ``True`` between the click and the runner acknowledgement.
    """

    #: Emitted when the operator asks to cancel.
    cancel_requested = Signal()
    #: Emitted when the runner did not stop within the watchdog delay.
    cancel_timed_out = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        with_shortcut: bool = False,
        timeout_ms: int = CANCEL_TIMEOUT_MS,
    ) -> None:
        """Build the button, the watchdog and the optional shortcut."""
        super().__init__(caption_for(False), "cancel", parent, scaler, danger=True)
        self.cancelling = False
        self.timeout_ms = timeout_ms
        self.setEnabled(False)
        self.setToolTip(f"Cancel the running test ({CANCEL_SHORTCUT})")
        self.clicked.connect(self.request_cancel)

        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_timeout)

        self._shortcut: QShortcut | None = None
        if with_shortcut and parent is not None:
            self._shortcut = QShortcut(QKeySequence(CANCEL_SHORTCUT), parent)
            self._shortcut.activated.connect(self.request_cancel)

    # -- API -----------------------------------------------------------------
    def set_running(self, running: bool) -> None:
        """Enable the button while a test is running."""
        self.setEnabled(running)
        if not running:
            self.acknowledge()

    def request_cancel(self) -> bool:
        """Emit :attr:`cancel_requested` and arm the watchdog.

        Returns:
            ``True`` when the request was emitted, ``False`` when the button
            was disabled or a cancellation is already in flight.
        """
        if not self.isEnabled() or self.cancelling:
            return False
        self.cancelling = True
        self.setText(caption_for(True))
        self.setEnabled(False)
        self._watchdog.start(self.timeout_ms)
        self.cancel_requested.emit()
        return True

    def acknowledge(self) -> None:
        """Record that the runner has stopped and reset the button."""
        self._watchdog.stop()
        self.cancelling = False
        self.setText(caption_for(False))
        self.setToolTip(f"Cancel the running test ({CANCEL_SHORTCUT})")
        self.setEnabled(False)

    def is_cancelling(self) -> bool:
        """Return ``True`` while a cancellation is in flight."""
        return self.cancelling

    # -- internals ------------------------------------------------------------
    def _on_timeout(self) -> None:
        """Warn that the runner missed the cancellation deadline."""
        if not self.cancelling:
            return
        self.setToolTip(
            f"The runner did not stop within {self.timeout_ms} ms; "
            "it will be forced to stop"
        )
        self.cancel_timed_out.emit()
