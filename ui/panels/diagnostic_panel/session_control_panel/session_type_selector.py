"""Session type selector used by the DiagnosticSessionControl panel.

The widget offers every standard session from
:data:`~src.diagnostics.services.session_control.session_types.STANDARD_SESSIONS`
plus a *custom* entry that lets the operator type any sub-function byte, which
covers the manufacturer (0x40..0x5F) and supplier (0x60..0x7E) ranges.

Example:
    >>> from ui.panels.diagnostic_panel.session_control_panel.session_type_selector import (
    ...     session_choices, validate_sub_function)
    >>> session_choices()[0][0]
    1
    >>> validate_sub_function(0x03)
    (True, '')
    >>> validate_sub_function(0x00)[0]
    False
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from src.core.enums.session_enums import SessionType, session_name
from src.diagnostics.services.session_control.session_types import (
    STANDARD_SESSIONS,
    SessionDescriptor,
    describe_session,
    is_manufacturer_specific,
    is_supplier_specific,
)

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.responsive_widget import ResponsiveWidget

__all__ = ["SessionTypeSelector", "session_choices", "validate_sub_function"]

#: Sentinel data value used by the *custom* combo box entry.
CUSTOM_ENTRY = -1


def session_choices() -> list[tuple[int, str]]:
    """Return ``(sub_function, label)`` for every standard session.

    Example:
        >>> [value for value, _ in session_choices()]
        [1, 2, 3, 4]
    """
    return [(d.value, f"{d.hex_value} {d.label}") for d in STANDARD_SESSIONS]


def validate_sub_function(value: int) -> tuple[bool, str]:
    """Validate a session sub-function byte.

    Args:
        value: The sub-function the operator wants to send.

    Returns:
        ``(is_valid, reason)``; *reason* is empty when the value is accepted.

    Example:
        >>> validate_sub_function(0x4F)
        (True, '')
        >>> validate_sub_function(0x7F)[1]
        '0x7F is reserved by ISO 14229'
    """
    if not 0x00 <= value <= 0xFF:
        return False, "a sub-function is a single byte"
    if value == 0x00:
        return False, "0x00 is not a valid session"
    if value == 0x7F:
        return False, "0x7F is reserved by ISO 14229"
    if value in {int(s) for s in SessionType}:
        return True, ""
    if is_manufacturer_specific(value) or is_supplier_specific(value):
        return True, ""
    if 0x05 <= value <= 0x3F:
        return False, f"0x{value:02X} is in the ISO reserved range 0x05..0x3F"
    return True, ""


class SessionTypeSelector(ResponsiveWidget):
    """Drop-down plus custom byte field for choosing a diagnostic session.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        allow_custom: Offer the *custom sub-function* entry.

    Attributes:
        combo: The session drop-down.
        custom_field: Hex field shown when *custom* is selected.
    """

    #: Emitted with the selected sub-function whenever the selection changes.
    session_changed = Signal(int)
    #: Emitted with ``(is_valid, reason)`` after every validation.
    validity_changed = Signal(bool, str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        allow_custom: bool = True,
    ) -> None:
        """Build the drop-down and the custom sub-function field."""
        super().__init__(parent, scaler)
        self.allow_custom = allow_custom

        self.combo = QComboBox(self)
        for value, label in session_choices():
            self.combo.addItem(label, value)
        if allow_custom:
            self.combo.addItem("Custom sub-function...", CUSTOM_ENTRY)
        self.combo.currentIndexChanged.connect(self._on_index_changed)

        self.custom_field = HexInputField(
            self, self.scaler, min_bytes=1, max_bytes=1, placeholder="e.g. 4F"
        )
        self.custom_field.setVisible(False)
        self.custom_field.bytes_changed.connect(lambda _data: self._emit_current())

        self.description = QLabel("", self)
        self.description.setProperty("role", "secondary")
        self.description.setWordWrap(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(QLabel("Session:", self))
        layout.addWidget(self.combo, 2)
        layout.addWidget(self.custom_field, 1)
        layout.addWidget(self.description, 3)

        self.set_session(int(SessionType.EXTENDED_DIAGNOSTIC))

    # -- API -----------------------------------------------------------------
    def session(self) -> int:
        """Return the currently selected sub-function.

        Returns:
            The sub-function byte; ``0`` when the custom field is empty.
        """
        data = self.combo.currentData()
        if data == CUSTOM_ENTRY:
            raw = self.custom_field.value()
            return raw[0] if raw else 0
        return int(data or 0)

    def set_session(self, sub_function: int) -> None:
        """Select *sub_function*, switching to the custom entry when needed."""
        index = self.combo.findData(sub_function)
        if index >= 0:
            self.combo.setCurrentIndex(index)
        elif self.allow_custom:
            self.combo.setCurrentIndex(self.combo.findData(CUSTOM_ENTRY))
            self.custom_field.set_value(bytes([sub_function & 0xFF]))
        self._emit_current()

    def descriptor(self) -> SessionDescriptor:
        """Return the :class:`SessionDescriptor` of the current selection."""
        return describe_session(self.session())

    def is_valid(self) -> bool:
        """Return ``True`` when the current selection may be sent."""
        return validate_sub_function(self.session())[0]

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable every child control."""
        self.combo.setEnabled(enabled)
        self.custom_field.setEnabled(enabled)

    # -- internals ------------------------------------------------------------
    def _on_index_changed(self, _index: int) -> None:
        """Show or hide the custom field and re-emit the selection."""
        self.custom_field.setVisible(self.combo.currentData() == CUSTOM_ENTRY)
        self._emit_current()

    def _emit_current(self) -> None:
        """Refresh the description label and emit the current selection."""
        value = self.session()
        valid, reason = validate_sub_function(value)
        descriptor = describe_session(value)
        self.description.setText(reason if not valid else descriptor.description)
        self.description.setProperty("state", "error" if not valid else "")
        self.setToolTip(f"{session_name(value)} (0x{value:02X})")
        self.validity_changed.emit(valid, reason)
        if valid:
            self.session_changed.emit(value)
