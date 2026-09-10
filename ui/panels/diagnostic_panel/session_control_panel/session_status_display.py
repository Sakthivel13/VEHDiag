"""Live display of the active session, the S3 timer and the security state.

The widget renders the state held by
:class:`~src.core.models.session_model.SessionState` and is refreshed either by
the diagnostic controller or by its own one second timer.

Example:
    >>> from ui.panels.diagnostic_panel.session_control_panel.session_status_display import (
    ...     format_remaining, timer_state)
    >>> format_remaining(4000.0)
    '4.0 s'
    >>> timer_state(4000.0, 4000.0)
    'ok'
    >>> timer_state(800.0, 4000.0)
    'warning'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QProgressBar, QWidget

from src.core.enums.session_enums import SecurityState
from src.core.models.session_model import SessionState

from ....dpi_scaler import DPIScaler
from ....widgets.led_indicator import LedIndicator
from ....widgets.responsive_widget import ResponsiveWidget

__all__ = ["SessionStatusDisplay", "format_remaining", "timer_state"]

#: Fraction of S3 below which the timer is shown as a warning.
WARNING_FRACTION = 0.25

#: Fraction of S3 below which the timer is shown as an error.
CRITICAL_FRACTION = 0.10


def format_remaining(milliseconds: float) -> str:
    """Return a human readable rendering of the S3 countdown.

    Args:
        milliseconds: Time left before the session falls back to default.

    Example:
        >>> format_remaining(0)
        'expired'
        >>> format_remaining(1500.0)
        '1.5 s'
    """
    if milliseconds <= 0:
        return "expired"
    if milliseconds < 1000:
        return f"{int(milliseconds)} ms"
    return f"{milliseconds / 1000.0:.1f} s"


def timer_state(remaining_ms: float, total_ms: float) -> str:
    """Classify the countdown into ``ok``, ``warning``, ``error`` or ``idle``.

    Args:
        remaining_ms: Time left in milliseconds.
        total_ms: The configured S3 client time.

    Example:
        >>> timer_state(0.0, 4000.0)
        'error'
        >>> timer_state(1000.0, 0.0)
        'idle'
    """
    if total_ms <= 0:
        return "idle"
    fraction = max(0.0, remaining_ms) / total_ms
    if fraction <= CRITICAL_FRACTION:
        return "error"
    if fraction <= WARNING_FRACTION:
        return "warning"
    return "ok"


class SessionStatusDisplay(ResponsiveWidget):
    """Shows the active session, the negotiated timing and the S3 countdown.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        auto_tick: Start an internal timer that refreshes the countdown.

    Attributes:
        led: Indicator reflecting the session and security state.
        state: The last :class:`SessionState` handed to :meth:`update_state`.
    """

    #: Emitted when the S3 countdown reaches zero.
    session_expired = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        auto_tick: bool = True,
    ) -> None:
        """Build the label grid and start the optional refresh timer."""
        super().__init__(parent, scaler)
        self.state = SessionState()
        self._expired_emitted = False

        self.led = LedIndicator("idle", 14, self, self.scaler)
        self.session_label = QLabel("Default session (0x01)", self)
        self.session_label.setProperty("role", "heading")
        self.security_label = QLabel("Locked", self)
        self.p2_label = QLabel("-", self)
        self.p2_star_label = QLabel("-", self)
        self.s3_label = QLabel("-", self)
        self.keepalive_label = QLabel("not required", self)
        for label in (self.p2_label, self.p2_star_label, self.s3_label, self.keepalive_label):
            label.setProperty("role", "secondary")

        self.countdown = QProgressBar(self)
        self.countdown.setRange(0, 1000)
        self.countdown.setValue(0)
        self.countdown.setTextVisible(True)
        self.countdown.setFormat("S3: %v ms")

        layout = QGridLayout(self)
        gap = self.spacing(6)
        layout.setContentsMargins(gap, gap, gap, gap)
        layout.setHorizontalSpacing(self.spacing(12))
        layout.setVerticalSpacing(gap)
        layout.addWidget(self.led, 0, 0)
        layout.addWidget(self.session_label, 0, 1, 1, 3)
        layout.addWidget(self._caption("Security"), 1, 0, 1, 2)
        layout.addWidget(self.security_label, 2, 0, 1, 2)
        layout.addWidget(self._caption("P2 server"), 1, 2)
        layout.addWidget(self.p2_label, 2, 2)
        layout.addWidget(self._caption("P2* server"), 1, 3)
        layout.addWidget(self.p2_star_label, 2, 3)
        layout.addWidget(self._caption("S3 client"), 3, 0)
        layout.addWidget(self.s3_label, 4, 0)
        layout.addWidget(self._caption("Tester present"), 3, 1)
        layout.addWidget(self.keepalive_label, 4, 1)
        layout.addWidget(self.countdown, 5, 0, 1, 4)

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._tick)
        if auto_tick:
            self._timer.start()

    def _caption(self, text: str) -> QLabel:
        """Return a small secondary caption label."""
        label = QLabel(text, self)
        label.setProperty("role", "secondary")
        return label

    # -- API -----------------------------------------------------------------
    def update_state(self, state: SessionState) -> None:
        """Refresh every field from *state*."""
        self.state = state
        self._expired_emitted = False
        self.session_label.setText(f"{state.session_label} (0x{state.active_session:02X})")
        self.security_label.setText(
            "Unlocked (level 0x%02X)" % state.unlocked_level
            if state.security_state is SecurityState.UNLOCKED and state.unlocked_level is not None
            else state.security_state.value.title()
        )
        self.p2_label.setText(f"{state.timing.p2_server_ms:.0f} ms")
        self.p2_star_label.setText(f"{state.timing.p2_star_server_ms:.0f} ms")
        self.s3_label.setText(f"{state.timing.s3_client_ms:.0f} ms")
        self.keepalive_label.setText(
            "required" if state.requires_tester_present else "not required"
        )
        self.countdown.setRange(0, int(state.timing.s3_client_ms) or 1)
        self.countdown.setVisible(state.requires_tester_present)
        self.led.set_state(
            "pass" if state.security_state is SecurityState.UNLOCKED
            else "running" if state.requires_tester_present
            else "idle"
        )
        self._tick()

    def remaining_ms(self) -> float:
        """Return the time left before the S3 timer expires."""
        return self.state.s3_remaining_ms if self.state.requires_tester_present else 0.0

    def set_auto_tick(self, active: bool) -> None:
        """Start or stop the internal refresh timer."""
        self._timer.start() if active else self._timer.stop()

    # -- internals ------------------------------------------------------------
    def _tick(self) -> None:
        """Refresh the countdown bar and emit :attr:`session_expired`."""
        if not self.state.requires_tester_present:
            return
        remaining = max(0.0, self.state.s3_remaining_ms)
        total = self.state.timing.s3_client_ms
        self.countdown.setValue(int(remaining))
        self.countdown.setFormat(f"S3: {format_remaining(remaining)}")
        self.countdown.setProperty("state", timer_state(remaining, total))
        style = self.countdown.style()
        if style is not None:
            style.unpolish(self.countdown)
            style.polish(self.countdown)
        if remaining <= 0 and not self._expired_emitted:
            self._expired_emitted = True
            self.led.set_state("error")
            self.session_expired.emit()
