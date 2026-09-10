"""DTC group selector for ClearDiagnosticInformation (SID 0x14).

ISO 14229 clears either every stored code (``0xFFFFFF``) or one functional
group identified by the first value of its range. The groups are defined in
:data:`~src.diagnostics.services.dtc_services.dtc_parser.GROUPS`.

Example:
    >>> from ui.panels.diagnostic_panel.clear_dtc_panel.dtc_group_selector import (
    ...     group_choices, group_label, mask_for)
    >>> [name for name, _ in group_choices()][0]
    'all'
    >>> hex(mask_for("chassis"))
    '0x400000'
    >>> group_label("all")
    'All DTCs (0xFFFFFF)'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from src.diagnostics.services.dtc_services.clear_dtc import CLEAR_ALL
from src.diagnostics.services.dtc_services.dtc_parser import GROUPS, group_mask, group_range

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.responsive_widget import ResponsiveWidget

__all__ = [
    "DTCGroupSelector",
    "GROUP_DESCRIPTIONS",
    "group_choices",
    "group_label",
    "mask_for",
]

#: Short explanation shown next to each group.
GROUP_DESCRIPTIONS: dict[str, str] = {
    "all": "Clear every stored diagnostic trouble code.",
    "powertrain": "Engine, transmission and emission related codes (P).",
    "chassis": "Braking, steering and suspension codes (C).",
    "body": "Comfort, lighting and restraint codes (B).",
    "network": "Communication and bus related codes (U).",
}

#: Sentinel used by the *custom mask* drop-down entry.
CUSTOM_ENTRY = "custom"


def mask_for(name: str) -> int:
    """Return the 24-bit group mask sent with SID 0x14.

    Args:
        name: A key of :data:`GROUPS`, case insensitive.

    Returns:
        The mask value; ``0xFFFFFF`` for ``"all"``.

    Example:
        >>> hex(mask_for("ALL"))
        '0xffffff'
    """
    return group_mask(name)


def group_label(name: str) -> str:
    """Return the drop-down label of the group *name*.

    Example:
        >>> group_label("body")
        'Body (0x800000..0xBFFFFF)'
    """
    if name.strip().lower() == "all":
        return f"All DTCs (0x{CLEAR_ALL:06X})"
    low, high = group_range(name)
    return f"{name.title()} (0x{low:06X}..0x{high:06X})"


def group_choices() -> list[tuple[str, int]]:
    """Return ``(name, mask)`` for every known group.

    Example:
        >>> dict(group_choices())["network"]
        12582912
    """
    return [(name, mask_for(name)) for name in GROUPS]


class DTCGroupSelector(ResponsiveWidget):
    """Drop-down choosing which DTC group is cleared.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        allow_custom: Offer a free hexadecimal mask entry.

    Attributes:
        combo: The group drop-down.
        custom_field: Three byte hex field shown for the custom entry.
    """

    #: Emitted with the selected 24-bit group mask.
    group_changed = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        allow_custom: bool = True,
    ) -> None:
        """Build the drop-down, the custom field and the description label."""
        super().__init__(parent, scaler)
        self.allow_custom = allow_custom

        self.combo = QComboBox(self)
        for name, _mask in group_choices():
            self.combo.addItem(group_label(name), name)
        if allow_custom:
            self.combo.addItem("Custom mask...", CUSTOM_ENTRY)
        self.combo.currentIndexChanged.connect(self._on_changed)

        self.custom_field = HexInputField(
            self, self.scaler, min_bytes=3, max_bytes=3, placeholder="e.g. C0 00 00"
        )
        self.custom_field.setVisible(False)
        self.custom_field.bytes_changed.connect(lambda _d: self._emit_current())

        self.description = QLabel(GROUP_DESCRIPTIONS["all"], self)
        self.description.setProperty("role", "secondary")
        self.description.setWordWrap(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(QLabel("Group:", self))
        layout.addWidget(self.combo, 2)
        layout.addWidget(self.custom_field, 1)
        layout.addWidget(self.description, 3)

    # -- API -----------------------------------------------------------------
    def group_name(self) -> str:
        """Return the name of the selected group, or ``"custom"``."""
        return str(self.combo.currentData() or "all")

    def mask(self) -> int:
        """Return the 24-bit mask that will be sent."""
        name = self.group_name()
        if name == CUSTOM_ENTRY:
            raw = self.custom_field.value()
            return int.from_bytes(raw, "big") if len(raw) == 3 else CLEAR_ALL
        return mask_for(name)

    def set_group(self, name: str) -> bool:
        """Select the group *name*.

        Returns:
            ``True`` when the group exists in the drop-down.
        """
        index = self.combo.findData(name)
        if index < 0:
            return False
        self.combo.setCurrentIndex(index)
        return True

    def is_clear_all(self) -> bool:
        """Return ``True`` when every DTC will be cleared."""
        return self.mask() == CLEAR_ALL

    def is_valid(self) -> bool:
        """Return ``True`` when the selection can be sent."""
        if self.group_name() != CUSTOM_ENTRY:
            return True
        return len(self.custom_field.value()) == 3

    # -- internals ------------------------------------------------------------
    def _on_changed(self, _index: int) -> None:
        """Show or hide the custom field and refresh the description."""
        name = self.group_name()
        self.custom_field.setVisible(name == CUSTOM_ENTRY)
        self.description.setText(
            GROUP_DESCRIPTIONS.get(name, "Send an arbitrary 24-bit group mask.")
        )
        self._emit_current()

    def _emit_current(self) -> None:
        """Emit :attr:`group_changed` with the current mask."""
        self.group_changed.emit(self.mask())
