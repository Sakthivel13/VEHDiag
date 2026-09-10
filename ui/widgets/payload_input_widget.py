"""Combined SID, sub-function and payload entry widget."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from src.core.enums.sid_enums import ServiceID
from src.utils.byte_utils import bytes_to_hex, hex_to_bytes

from ..dpi_scaler import DPIScaler
from .hex_input_field import HexInputField
from .responsive_widget import ResponsiveWidget

#: Frequently used payloads offered in the history drop-down.
COMMON_PAYLOADS: tuple[str, ...] = (
    "10 01",
    "10 03",
    "10 02",
    "11 01",
    "14 FF FF FF",
    "19 02 FF",
    "19 01 FF",
    "22 F1 90",
    "22 F1 8C",
    "27 01",
    "31 01 FF 00",
    "3E 00",
    "3E 80",
)


class PayloadInputWidget(ResponsiveWidget):
    """Lets the operator compose a complete UDS request.

    The widget combines a service drop-down with a validated hexadecimal field
    and a history of recently used payloads.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        show_service_selector: Display the service drop-down.
    """

    #: Emitted with the composed payload whenever it changes.
    payload_changed = Signal(bytes)
    #: Emitted when the user presses Return in the payload field.
    submitted = Signal(bytes)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        show_service_selector: bool = True,
    ) -> None:
        """Build the service selector, the hex field and the history box."""
        super().__init__(parent, scaler)
        self.history: list[str] = []

        self.service_box = QComboBox(self)
        self.service_box.addItem("Custom", 0)
        for service in ServiceID:
            self.service_box.addItem(f"0x{int(service):02X} {service.pretty_name}", int(service))
        self.service_box.currentIndexChanged.connect(self._on_service_selected)
        self.service_box.setVisible(show_service_selector)

        self.field = HexInputField(self, self.scaler, min_bytes=1, placeholder="e.g. 22 F1 90")
        self.field.bytes_changed.connect(self._on_payload_changed)
        self.field.returnPressed.connect(lambda: self.submitted.emit(self.payload()))

        self.history_box = QComboBox(self)
        self.history_box.setEditable(False)
        self.history_box.addItem("Recent / common...")
        self.history_box.addItems(list(COMMON_PAYLOADS))
        self.history_box.activated.connect(self._on_history_selected)

        self.info_label = QLabel("0 bytes", self)
        self.info_label.setProperty("role", "secondary")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(6))
        if show_service_selector:
            layout.addWidget(QLabel("Service:", self))
            layout.addWidget(self.service_box, 2)
        layout.addWidget(QLabel("Payload:", self))
        layout.addWidget(self.field, 3)
        layout.addWidget(self.history_box, 1)
        layout.addWidget(self.info_label)

    # -- value access -------------------------------------------------------
    def payload(self) -> bytes:
        """Return the composed request bytes."""
        return self.field.value()

    def set_payload(self, payload: bytes | str) -> None:
        """Set the payload from bytes or a hex string."""
        data = payload if isinstance(payload, bytes) else hex_to_bytes(str(payload))
        self.field.set_value(data)

    def service_id(self) -> int | None:
        """Return the first byte of the payload, if any."""
        data = self.payload()
        return data[0] if data else None

    def remember(self, payload: bytes | None = None) -> None:
        """Add the current payload to the history drop-down."""
        text = bytes_to_hex(payload if payload is not None else self.payload())
        if not text or text in self.history:
            return
        self.history.insert(0, text)
        del self.history[20:]
        self.history_box.insertItem(1, text)

    def is_valid(self) -> bool:
        """Return ``True`` when the payload is non-empty and well formed."""
        return self.field.is_valid and bool(self.payload())

    # -- events ----------------------------------------------------------------
    def _on_service_selected(self, index: int) -> None:
        """Pre-fill the payload with the selected service identifier."""
        sid = self.service_box.itemData(index)
        if not sid:
            return
        current = self.payload()
        if not current or current[0] != sid:
            self.field.set_value(bytes([sid]))
        self.field.setFocus()

    def _on_history_selected(self, index: int) -> None:
        """Apply a payload chosen from the history."""
        if index <= 0:
            return
        self.set_payload(self.history_box.itemText(index))
        self.history_box.setCurrentIndex(0)

    def _on_payload_changed(self, data: bytes) -> None:
        """Update the byte counter and the service selector."""
        self.info_label.setText(f"{len(data)} byte(s)")
        if data:
            service = ServiceID.from_byte(data[0])
            if service is not None:
                position = self.service_box.findData(int(service))
                if position >= 0 and self.service_box.currentIndex() != position:
                    self.service_box.blockSignals(True)
                    self.service_box.setCurrentIndex(position)
                    self.service_box.blockSignals(False)
        self.payload_changed.emit(data)


__all__ = ["PayloadInputWidget", "COMMON_PAYLOADS"]
