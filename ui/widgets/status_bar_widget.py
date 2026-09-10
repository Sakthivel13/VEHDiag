"""Enhanced status bar with connection, session and counters."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

from src.core.enums.protocol_enums import ConnectionState

from ..dpi_scaler import DPIScaler
from .connection_status_widget import ConnectionStatusWidget
from .led_indicator import LedIndicator


class StatusBarWidget(QStatusBar):
    """The application status bar.

    Shows, from left to right: a transient message, the diagnostic session,
    the security state, the message counters and the connection indicator.

    Args:
        parent: Parent window.
        scaler: Shared DPI scaler.
    """

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the permanent status bar widgets."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()

        self.session_label = QLabel("Session: default", self)
        self.security_led = LedIndicator("locked", 10, self, self.scaler)
        self.security_label = QLabel("Locked", self)
        self.counter_label = QLabel("TX 0 / RX 0", self)
        self.breakpoint_label = QLabel("", self)
        self.breakpoint_label.setProperty("role", "secondary")
        self.connection = ConnectionStatusWidget(self, self.scaler)

        for widget in (
            self.breakpoint_label,
            self.session_label,
            self.security_led,
            self.security_label,
            self.counter_label,
            self.connection,
        ):
            self.addPermanentWidget(widget)
        self.setSizeGripEnabled(True)

    # -- updates -------------------------------------------------------------
    def set_message(self, text: str, timeout_ms: int = 4000) -> None:
        """Show a transient message on the left side."""
        self.showMessage(text, timeout_ms)

    def set_session(self, label: str) -> None:
        """Update the diagnostic session indicator."""
        self.session_label.setText(f"Session: {label}")

    def set_security(self, unlocked: bool, level: int | None = None) -> None:
        """Update the security state indicator."""
        self.security_led.set_state("unlocked" if unlocked else "locked")
        suffix = f" (0x{level:02X})" if unlocked and level is not None else ""
        self.security_label.setText(("Unlocked" if unlocked else "Locked") + suffix)

    def set_counters(self, tx: int, rx: int) -> None:
        """Update the transmitted/received message counters."""
        self.counter_label.setText(f"TX {tx} / RX {rx}")

    def set_connection(
        self,
        state: ConnectionState | str,
        vci: str = "",
        protocol: str = "",
        bitrate: int = 0,
    ) -> None:
        """Update the connection indicator."""
        self.connection.set_state(state, vci, protocol, bitrate)

    def set_breakpoint(self, name: str) -> None:
        """Show the active responsive breakpoint (useful while testing)."""
        self.breakpoint_label.setText(name)


__all__ = ["StatusBarWidget"]
