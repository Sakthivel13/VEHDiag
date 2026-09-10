"""Security level selector for SecurityAccess (SID 0x27).

ISO 14229 pairs an odd *requestSeed* sub-function with the following even
*sendKey* sub-function: level 0x01 requests the seed and 0x02 sends the key.
The helpers below implement that pairing and the range rules, so the panel and
the controller share one source of truth.

Example:
    >>> from ui.panels.diagnostic_panel.security_access_panel.security_level_selector import (
    ...     is_request_seed, send_key_level, validate_level, level_label)
    >>> is_request_seed(0x01)
    True
    >>> hex(send_key_level(0x03))
    '0x4'
    >>> validate_level(0x02)[1]
    '0x02 is a sendKey sub-function; select the odd requestSeed level'
    >>> level_label(0x01)
    'Level 1 (seed 0x01 / key 0x02)'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.responsive_widget import ResponsiveWidget

__all__ = [
    "STANDARD_LEVELS",
    "SecurityLevelSelector",
    "is_request_seed",
    "level_label",
    "request_seed_level",
    "send_key_level",
    "validate_level",
]

#: The requestSeed sub-functions offered by default.
STANDARD_LEVELS: tuple[int, ...] = (0x01, 0x03, 0x05, 0x07, 0x09, 0x0B)

#: Sentinel used by the *custom level* drop-down entry.
CUSTOM_ENTRY = -1


def is_request_seed(sub_function: int) -> bool:
    """Return ``True`` when *sub_function* requests a seed (odd value).

    Example:
        >>> is_request_seed(0x02)
        False
    """
    return bool(sub_function & 0x01)


def send_key_level(request_level: int) -> int:
    """Return the sendKey sub-function paired with *request_level*.

    Example:
        >>> hex(send_key_level(0x01))
        '0x2'
    """
    return (request_level | 0x01) + 1


def request_seed_level(send_level: int) -> int:
    """Return the requestSeed sub-function paired with *send_level*.

    Example:
        >>> hex(request_seed_level(0x04))
        '0x3'
    """
    return send_level - 1 if not send_level & 0x01 else send_level


def validate_level(sub_function: int) -> tuple[bool, str]:
    """Validate a requestSeed sub-function.

    Args:
        sub_function: The level the operator wants to unlock.

    Returns:
        ``(is_valid, reason)``; *reason* is empty when the value is accepted.

    Example:
        >>> validate_level(0x05)
        (True, '')
        >>> validate_level(0x00)[0]
        False
    """
    if not 0x00 < sub_function <= 0x7E:
        return False, "a security level is a sub-function in the range 0x01..0x7E"
    if not is_request_seed(sub_function):
        return (
            False,
            f"0x{sub_function:02X} is a sendKey sub-function; "
            "select the odd requestSeed level",
        )
    if sub_function in (0x7F,):
        return False, "0x7F is reserved by ISO 14229"
    return True, ""


def level_label(sub_function: int) -> str:
    """Return the drop-down label of the requestSeed *sub_function*.

    Example:
        >>> level_label(0x0B)
        'Level 6 (seed 0x0B / key 0x0C)'
    """
    ordinal = (sub_function + 1) // 2
    return (
        f"Level {ordinal} (seed 0x{sub_function:02X} / "
        f"key 0x{send_key_level(sub_function):02X})"
    )


class SecurityLevelSelector(ResponsiveWidget):
    """Drop-down choosing which security level is unlocked.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        levels: The requestSeed sub-functions to offer.
        allow_custom: Offer a free sub-function byte entry.

    Attributes:
        combo: The level drop-down.
        custom_field: One byte hex field shown for the custom entry.
    """

    #: Emitted with the selected requestSeed sub-function.
    level_changed = Signal(int)
    #: Emitted with ``(is_valid, reason)`` after every validation.
    validity_changed = Signal(bool, str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        levels: tuple[int, ...] = STANDARD_LEVELS,
        allow_custom: bool = True,
    ) -> None:
        """Build the drop-down, the custom field and the hint label."""
        super().__init__(parent, scaler)
        self.allow_custom = allow_custom

        self.combo = QComboBox(self)
        for level in levels:
            self.combo.addItem(level_label(level), level)
        if allow_custom:
            self.combo.addItem("Custom level...", CUSTOM_ENTRY)
        self.combo.currentIndexChanged.connect(self._on_changed)

        self.custom_field = HexInputField(
            self, self.scaler, min_bytes=1, max_bytes=1, placeholder="e.g. 11"
        )
        self.custom_field.setVisible(False)
        self.custom_field.bytes_changed.connect(lambda _d: self._emit_current())

        self.hint = QLabel("", self)
        self.hint.setProperty("role", "secondary")
        self.hint.setWordWrap(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(QLabel("Security level:", self))
        layout.addWidget(self.combo, 2)
        layout.addWidget(self.custom_field, 1)
        layout.addWidget(self.hint, 3)

        self._emit_current()

    # -- API -----------------------------------------------------------------
    def level(self) -> int:
        """Return the selected requestSeed sub-function."""
        data = self.combo.currentData()
        if data == CUSTOM_ENTRY:
            raw = self.custom_field.value()
            return raw[0] if raw else 0
        return int(data or 0)

    def key_level(self) -> int:
        """Return the sendKey sub-function paired with the selection."""
        return send_key_level(self.level())

    def set_level(self, sub_function: int) -> None:
        """Select *sub_function*, switching to the custom entry when needed."""
        index = self.combo.findData(sub_function)
        if index >= 0:
            self.combo.setCurrentIndex(index)
        elif self.allow_custom:
            self.combo.setCurrentIndex(self.combo.findData(CUSTOM_ENTRY))
            self.custom_field.set_value(bytes([sub_function & 0xFF]))
        self._emit_current()

    def is_valid(self) -> bool:
        """Return ``True`` when the selected level may be requested."""
        return validate_level(self.level())[0]

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable every child control."""
        self.combo.setEnabled(enabled)
        self.custom_field.setEnabled(enabled)

    # -- internals ------------------------------------------------------------
    def _on_changed(self, _index: int) -> None:
        """Show or hide the custom field and re-emit the selection."""
        self.custom_field.setVisible(self.combo.currentData() == CUSTOM_ENTRY)
        self._emit_current()

    def _emit_current(self) -> None:
        """Refresh the hint and emit the change signals."""
        level = self.level()
        valid, reason = validate_level(level)
        self.hint.setText(
            reason
            if not valid
            else f"requestSeed 0x{level:02X}, sendKey 0x{send_key_level(level):02X}"
        )
        self.validity_changed.emit(valid, reason)
        if valid:
            self.level_changed.emit(level)
