"""VCI connection status indicator for the status bar."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.core.enums.protocol_enums import ConnectionState

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole
from .led_indicator import LedIndicator
from .responsive_widget import ResponsiveWidget


class ConnectionStatusWidget(ResponsiveWidget):
    """Compact widget showing the VCI, protocol and connection state.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted when the user clicks the widget.
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the indicator row."""
        super().__init__(parent, scaler)
        self.state = ConnectionState.DISCONNECTED
        self.led = LedIndicator("disconnected", 12, self, self.scaler)
        self.text_label = QLabel("Disconnected", self)
        self.detail_label = QLabel("", self)
        self.detail_label.setProperty("role", "secondary")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), 0, self.spacing(8), 0)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(self.led)
        layout.addWidget(self.text_label)
        layout.addWidget(self.detail_label)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_font(FontRole.STATUS)
        self.set_accessible("Connection status", "Click to open the connection details")

    # -- state ---------------------------------------------------------------
    def set_state(
        self,
        state: ConnectionState | str,
        vci: str = "",
        protocol: str = "",
        bitrate: int = 0,
    ) -> None:
        """Update the indicator with a new connection state."""
        self.state = ConnectionState(state) if not isinstance(state, ConnectionState) else state
        mapping = {
            ConnectionState.CONNECTED: ("connected", "Connected"),
            ConnectionState.CONNECTING: ("running", "Connecting..."),
            ConnectionState.DISCONNECTING: ("running", "Disconnecting..."),
            ConnectionState.DISCONNECTED: ("disconnected", "Disconnected"),
            ConnectionState.ERROR: ("fail", "Connection error"),
        }
        led_state, text = mapping.get(self.state, ("idle", self.state.value.title()))
        self.led.set_state(led_state)
        self.text_label.setText(text)
        details = [part for part in (vci, protocol, f"{bitrate // 1000}k" if bitrate else "") if part]
        self.detail_label.setText(" | ".join(details))
        self.setToolTip(f"{text}\n" + "\n".join(details))

    def set_error(self, message: str) -> None:
        """Show the error state with *message* as the tooltip."""
        self.set_state(ConnectionState.ERROR)
        self.detail_label.setText(message[:60])
        self.setToolTip(message)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802 - Qt naming
        """Emit :attr:`clicked` on a left click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


__all__ = ["ConnectionStatusWidget"]
