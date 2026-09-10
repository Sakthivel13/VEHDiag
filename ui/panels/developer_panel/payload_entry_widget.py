"""Per-service payload editor used by the developer mode grid.

Each card of the service grid owns one of these widgets. It composes the
request from a service identifier plus the parameter bytes, validates the
length against a small table of well known services and offers a set of
templates for the most common requests.

Example:
    >>> from ui.panels.developer_panel.payload_entry_widget import (
    ...     TEMPLATES, compose, validate_payload)
    >>> compose(0x22, b"\\xf1\\x90").hex().upper()
    '22F190'
    >>> validate_payload(0x10, b"\\x03")
    (True, '')
    >>> validate_payload(0x10, b"")[1]
    'DiagnosticSessionControl needs 1 parameter byte'
    >>> TEMPLATES[0x22][0][0]
    'Read VIN'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from src.core.enums.sid_enums import SID_DESCRIPTIONS, ServiceID

from ...dpi_scaler import DPIScaler
from ...widgets.hex_input_field import HexInputField
from ...widgets.responsive_widget import ResponsiveWidget

__all__ = [
    "MIN_PARAMETER_BYTES",
    "PayloadEntryWidget",
    "TEMPLATES",
    "compose",
    "service_name",
    "validate_payload",
]

#: Minimum number of parameter bytes required by the common services.
MIN_PARAMETER_BYTES: dict[int, int] = {
    int(ServiceID.DIAGNOSTIC_SESSION_CONTROL): 1,
    int(ServiceID.ECU_RESET): 1,
    int(ServiceID.CLEAR_DIAGNOSTIC_INFORMATION): 3,
    int(ServiceID.READ_DTC_INFORMATION): 1,
    int(ServiceID.READ_DATA_BY_IDENTIFIER): 2,
    int(ServiceID.SECURITY_ACCESS): 1,
    int(ServiceID.COMMUNICATION_CONTROL): 2,
    int(ServiceID.WRITE_DATA_BY_IDENTIFIER): 3,
    int(ServiceID.INPUT_OUTPUT_CONTROL_BY_IDENTIFIER): 3,
    int(ServiceID.ROUTINE_CONTROL): 3,
    int(ServiceID.TESTER_PRESENT): 1,
    int(ServiceID.CONTROL_DTC_SETTING): 1,
}

#: Ready-made parameter bytes per service, as ``(label, hex)`` pairs.
TEMPLATES: dict[int, list[tuple[str, str]]] = {
    int(ServiceID.DIAGNOSTIC_SESSION_CONTROL): [
        ("Default session", "01"),
        ("Programming session", "02"),
        ("Extended session", "03"),
    ],
    int(ServiceID.ECU_RESET): [
        ("Hard reset", "01"),
        ("Key off/on reset", "02"),
        ("Soft reset", "03"),
    ],
    int(ServiceID.READ_DATA_BY_IDENTIFIER): [
        ("Read VIN", "F190"),
        ("Read ECU serial", "F18C"),
        ("Read software version", "F195"),
    ],
    int(ServiceID.READ_DTC_INFORMATION): [
        ("Report DTC by status mask", "02FF"),
        ("Report number of DTC", "01FF"),
        ("Report supported DTC", "0A"),
    ],
    int(ServiceID.CLEAR_DIAGNOSTIC_INFORMATION): [("Clear all DTCs", "FFFFFF")],
    int(ServiceID.SECURITY_ACCESS): [("Request seed level 1", "01")],
    int(ServiceID.TESTER_PRESENT): [("Suppress positive response", "80"), ("Normal", "00")],
    int(ServiceID.ROUTINE_CONTROL): [("Start routine 0x0203", "010203")],
}


def service_name(service_id: int) -> str:
    """Return the ISO name of *service_id*.

    Example:
        >>> service_name(0x22)
        'ReadDataByIdentifier'
        >>> service_name(0x99)
        'Service 0x99'
    """
    try:
        return "".join(part.capitalize() for part in ServiceID(service_id).name.split("_"))
    except ValueError:
        return f"Service 0x{service_id:02X}"


def compose(service_id: int, parameters: bytes) -> bytes:
    """Return the complete request for *service_id*.

    Example:
        >>> compose(0x3E, b"\\x00").hex().upper()
        '3E00'
    """
    return bytes([service_id & 0xFF]) + bytes(parameters)


def validate_payload(service_id: int, parameters: bytes) -> tuple[bool, str]:
    """Validate the parameter bytes of *service_id*.

    Args:
        service_id: The UDS service identifier.
        parameters: The bytes that follow the SID.

    Returns:
        ``(is_valid, reason)``; *reason* is empty when the payload is accepted.

    Example:
        >>> validate_payload(0x22, b"\\xf1")[0]
        False
        >>> validate_payload(0x99, b"")
        (True, '')
    """
    required = MIN_PARAMETER_BYTES.get(service_id)
    if required is None:
        return True, ""
    if len(parameters) >= required:
        return True, ""
    plural = "byte" if required == 1 else "bytes"
    return False, f"{service_name(service_id)} needs {required} parameter {plural}"


class PayloadEntryWidget(ResponsiveWidget):
    """Composes the request payload for one service of the grid.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        service_id: The service the widget builds a request for.

    Attributes:
        field: The validated hexadecimal parameter field.
        template_box: Drop-down offering the ready-made payloads.
    """

    #: Emitted with the complete request bytes whenever they change.
    payload_changed = Signal(bytes)
    #: Emitted with ``(is_valid, reason)`` after every validation.
    validity_changed = Signal(bool, str)
    #: Emitted with the request bytes when the operator presses Return.
    submitted = Signal(bytes)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        service_id: int = 0x22,
    ) -> None:
        """Build the SID label, the parameter field and the template box."""
        super().__init__(parent, scaler)
        self.service_id = service_id

        self.sid_label = QLabel(f"0x{service_id:02X}", self)
        self.sid_label.setProperty("role", "mono")
        self.sid_label.setToolTip(
            SID_DESCRIPTIONS.get(service_id, service_name(service_id))
        )

        self.field = HexInputField(self, self.scaler, placeholder="parameters, e.g. F1 90")
        self.field.bytes_changed.connect(self._on_changed)
        self.field.returnPressed.connect(lambda: self.submitted.emit(self.payload()))

        self.template_box = QComboBox(self)
        self.template_box.activated.connect(self._on_template)

        self.hint_label = QLabel("", self)
        self.hint_label.setProperty("role", "secondary")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(4))
        layout.addWidget(self.sid_label)
        layout.addWidget(self.field, 3)
        layout.addWidget(self.template_box, 2)
        layout.addWidget(self.hint_label, 2)

        self.set_service(service_id)

    # -- API -----------------------------------------------------------------
    def set_service(self, service_id: int) -> None:
        """Switch to *service_id* and reload the template list."""
        self.service_id = service_id
        self.sid_label.setText(f"0x{service_id:02X}")
        self.sid_label.setToolTip(
            SID_DESCRIPTIONS.get(service_id, service_name(service_id))
        )
        self.template_box.clear()
        templates = TEMPLATES.get(service_id, [])
        self.template_box.addItem("Templates...", "")
        for label, value in templates:
            self.template_box.addItem(label, value)
        self.template_box.setEnabled(bool(templates))
        self._on_changed(self.field.value())

    def parameters(self) -> bytes:
        """Return the parameter bytes typed by the operator."""
        return self.field.value()

    def payload(self) -> bytes:
        """Return the complete request including the SID."""
        return compose(self.service_id, self.parameters())

    def set_parameters(self, data: bytes | str) -> None:
        """Set the parameter bytes from raw bytes or a hex string."""
        raw = bytes.fromhex(str(data).replace(" ", "")) if isinstance(data, str) else bytes(data)
        self.field.set_value(raw)

    def set_payload(self, data: bytes) -> None:
        """Set the widget from a complete request, taking the SID from *data*."""
        if not data:
            self.field.clear_value()
            return
        self.set_service(data[0])
        self.field.set_value(bytes(data[1:]))

    def is_valid(self) -> bool:
        """Return ``True`` when the payload may be sent."""
        return validate_payload(self.service_id, self.parameters())[0]

    def clear(self) -> None:
        """Clear the parameter field."""
        self.field.clear_value()

    # -- internals ------------------------------------------------------------
    def _on_changed(self, _data: bytes) -> None:
        """Validate the payload and emit the change signals."""
        valid, reason = validate_payload(self.service_id, self.parameters())
        self.hint_label.setText(reason if not reason == "" else f"{len(self.payload())} bytes")
        self.hint_label.setProperty("state", "error" if not valid else "")
        self.validity_changed.emit(valid, reason)
        self.payload_changed.emit(self.payload())

    def _on_template(self, index: int) -> None:
        """Apply the template selected at *index*."""
        value = str(self.template_box.itemData(index) or "")
        if value:
            self.set_parameters(value)
