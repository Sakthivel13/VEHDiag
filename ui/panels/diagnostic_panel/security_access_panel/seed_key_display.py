"""Seed and key display for the SecurityAccess panel.

Shows the seed returned by the ECU, the key that was computed for it, the
algorithm that produced the key and the outcome of the exchange. It also
detects the "all zero seed" case, which means the ECU is already unlocked.

Example:
    >>> from ui.panels.diagnostic_panel.security_access_panel.seed_key_display import (
    ...     is_already_unlocked, format_bytes, exchange_summary)
    >>> is_already_unlocked(b"\\x00\\x00\\x00\\x00")
    True
    >>> is_already_unlocked(b"\\x11\\x22")
    False
    >>> format_bytes(b"\\xab\\xcd")
    'AB CD'
    >>> format_bytes(b"")
    '-'
    >>> exchange_summary(b"\\x11\\x22", b"\\xee\\xdd", "xor_complement")
    'seed 11 22 -> key EE DD (xor_complement)'
"""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from ....dpi_scaler import DPIScaler
from ....widgets.led_indicator import LedIndicator
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_label import MonoLabel

__all__ = [
    "SeedKeyDisplay",
    "exchange_summary",
    "format_bytes",
    "is_already_unlocked",
]


def is_already_unlocked(seed: bytes) -> bool:
    """Return ``True`` when *seed* is all zero, meaning the ECU is unlocked.

    Example:
        >>> is_already_unlocked(b"")
        False
    """
    return bool(seed) and not any(seed)


def format_bytes(data: bytes) -> str:
    """Return *data* as spaced uppercase hex, or ``"-"`` when empty.

    Example:
        >>> format_bytes(bytes(range(3)))
        '00 01 02'
    """
    return " ".join(f"{b:02X}" for b in data) if data else "-"


def exchange_summary(seed: bytes, key: bytes, algorithm: str = "") -> str:
    """Return a one line description of a seed/key exchange.

    Example:
        >>> exchange_summary(b"", b"")
        'no seed requested yet'
    """
    if not seed:
        return "no seed requested yet"
    suffix = f" ({algorithm})" if algorithm else ""
    if not key:
        return f"seed {format_bytes(seed)} - no key computed"
    return f"seed {format_bytes(seed)} -> key {format_bytes(key)}{suffix}"


class SeedKeyDisplay(ResponsiveWidget):
    """Displays the seed, the computed key and the unlock outcome.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        seed: The last seed received from the ECU.
        key: The last key that was computed or entered.
        unlocked: Whether the last exchange succeeded.
    """

    #: Emitted with the seed bytes whenever a new seed is shown.
    seed_received = Signal(bytes)
    #: Emitted with ``(unlocked, message)`` after :meth:`set_result`.
    result_changed = Signal(bool, str)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the seed, key and status rows."""
        super().__init__(parent, scaler)
        self.seed: bytes = b""
        self.key: bytes = b""
        self.algorithm: str = ""
        self.unlocked: bool = False
        self._requested_at: float = 0.0

        self.led = LedIndicator("idle", 14, self, self.scaler)
        self.state_label = QLabel("Locked", self)
        self.state_label.setProperty("role", "heading")

        self.seed_label = MonoLabel("-", self, self.scaler)
        self.key_label = MonoLabel("-", self, self.scaler)
        self.algorithm_label = QLabel("-", self)
        self.length_label = QLabel("-", self)
        self.duration_label = QLabel("-", self)
        self.message_label = QLabel("", self)
        self.message_label.setWordWrap(True)
        for label in (self.algorithm_label, self.length_label, self.duration_label):
            label.setProperty("role", "secondary")

        layout = QGridLayout(self)
        gap = self.spacing(6)
        layout.setContentsMargins(gap, gap, gap, gap)
        layout.setHorizontalSpacing(self.spacing(12))
        layout.setVerticalSpacing(gap)
        layout.addWidget(self.led, 0, 0)
        layout.addWidget(self.state_label, 0, 1, 1, 3)
        layout.addWidget(self._caption("Seed"), 1, 0)
        layout.addWidget(self.seed_label, 1, 1, 1, 3)
        layout.addWidget(self._caption("Key"), 2, 0)
        layout.addWidget(self.key_label, 2, 1, 1, 3)
        layout.addWidget(self._caption("Algorithm"), 3, 0)
        layout.addWidget(self.algorithm_label, 3, 1)
        layout.addWidget(self._caption("Length"), 3, 2)
        layout.addWidget(self.length_label, 3, 3)
        layout.addWidget(self._caption("Duration"), 4, 0)
        layout.addWidget(self.duration_label, 4, 1)
        layout.addWidget(self.message_label, 5, 0, 1, 4)

    def _caption(self, text: str) -> QLabel:
        """Return a small secondary caption label."""
        label = QLabel(text, self)
        label.setProperty("role", "secondary")
        return label

    # -- API -----------------------------------------------------------------
    def begin_request(self, level: int) -> None:
        """Mark the start of a seed request for *level*."""
        self._requested_at = time.monotonic()
        self.unlocked = False
        self.seed = b""
        self.key = b""
        self.led.set_state("running")
        self.state_label.setText(f"Requesting seed for level 0x{level:02X}...")
        self.seed_label.setText("-")
        self.key_label.setText("-")
        self.message_label.clear()

    def set_seed(self, seed: bytes) -> None:
        """Display the *seed* returned by the ECU."""
        self.seed = bytes(seed)
        self.seed_label.setText(format_bytes(self.seed))
        self.length_label.setText(f"{len(self.seed)} bytes")
        if is_already_unlocked(self.seed):
            self.set_result(True, "the ECU reported an all-zero seed: already unlocked")
        else:
            self.led.set_state("running")
            self.state_label.setText("Seed received")
        self.seed_received.emit(self.seed)

    def set_key(self, key: bytes, algorithm: str = "") -> None:
        """Display the *key* computed for the current seed."""
        self.key = bytes(key)
        self.algorithm = algorithm
        self.key_label.setText(format_bytes(self.key))
        self.algorithm_label.setText(algorithm or "-")
        self.state_label.setText("Key computed")

    def set_result(self, unlocked: bool, message: str = "") -> None:
        """Record the outcome of the exchange."""
        self.unlocked = unlocked
        self.led.set_state("pass" if unlocked else "error")
        self.state_label.setText("Unlocked" if unlocked else "Locked")
        self.message_label.setText(message)
        self.message_label.setProperty("state", "success" if unlocked else "error")
        if self._requested_at:
            self.duration_label.setText(
                f"{(time.monotonic() - self._requested_at) * 1000.0:.0f} ms"
            )
        self.result_changed.emit(unlocked, message)

    def clear(self) -> None:
        """Reset every field."""
        self.seed = b""
        self.key = b""
        self.algorithm = ""
        self.unlocked = False
        self._requested_at = 0.0
        self.led.set_state("idle")
        self.state_label.setText("Locked")
        for label in (
            self.seed_label,
            self.key_label,
            self.algorithm_label,
            self.length_label,
            self.duration_label,
        ):
            label.setText("-")
        self.message_label.clear()

    def summary(self) -> str:
        """Return the one line description of the current exchange."""
        return exchange_summary(self.seed, self.key, self.algorithm)
