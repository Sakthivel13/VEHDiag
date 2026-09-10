"""Sub-function selector for ReadDTCInformation (SID 0x19).

The selector drives which extra parameters the request needs: a status mask, a
severity mask, a three byte DTC, a record number or a memory selection byte.
The pure helpers below decide which fields must be visible and build the
request payload, so the whole request composition can be unit tested without a
running ``QApplication``.

Example:
    >>> from ui.panels.diagnostic_panel.read_dtc_panel.dtc_subfunction_selector import (
    ...     required_fields, build_request)
    >>> sorted(required_fields(0x02))
    ['status_mask']
    >>> build_request(0x02, status_mask=0xFF).hex().upper()
    '1902FF'
    >>> build_request(0x06, dtc=0xC07300, record_number=0x01).hex().upper()
    '1906C0730001'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from src.core.enums.sid_enums import ServiceID
from src.diagnostics.services.dtc_services.dtc_sub_functions import (
    SUB_FUNCTION_SPECS,
    SubFunctionSpec,
    describe_sub_function,
    selectable_sub_functions,
)

from ....dpi_scaler import DPIScaler
from ....widgets.responsive_widget import ResponsiveWidget

__all__ = ["DTCSubFunctionSelector", "build_request", "required_fields"]


def required_fields(sub_function: int) -> set[str]:
    """Return the names of the parameters *sub_function* requires.

    Args:
        sub_function: The 0x19 sub-function byte.

    Returns:
        A set with any of ``status_mask``, ``severity_mask``, ``dtc``,
        ``record_number`` and ``memory_selection``.

    Example:
        >>> sorted(required_fields(0x19))
        ['dtc', 'memory_selection', 'record_number']
    """
    spec: SubFunctionSpec = describe_sub_function(sub_function)
    fields: set[str] = set()
    if spec.needs_status_mask:
        fields.add("status_mask")
    if spec.needs_severity_mask:
        fields.add("severity_mask")
    if spec.needs_dtc:
        fields.add("dtc")
    if spec.needs_record_number:
        fields.add("record_number")
    if spec.needs_memory_selection:
        fields.add("memory_selection")
    return fields


def build_request(
    sub_function: int,
    status_mask: int = 0xFF,
    severity_mask: int = 0xFF,
    dtc: int = 0,
    record_number: int = 0xFF,
    memory_selection: int = 0x00,
) -> bytes:
    """Build the complete 0x19 request for *sub_function*.

    Only the parameters reported by :func:`required_fields` are appended, in
    the order defined by ISO 14229-1.

    Args:
        sub_function: The sub-function byte.
        status_mask: DTC status availability mask.
        severity_mask: DTC severity mask.
        dtc: A three byte DTC value.
        record_number: Snapshot or extended data record number.
        memory_selection: User defined memory selector.

    Returns:
        The request bytes, starting with SID 0x19.

    Example:
        >>> build_request(0x0A).hex().upper()
        '190A'
        >>> build_request(0x08, severity_mask=0x20, status_mask=0x08).hex().upper()
        '19082008'
    """
    fields = required_fields(sub_function)
    payload = bytearray([int(ServiceID.READ_DTC_INFORMATION), sub_function & 0xFF])
    if "memory_selection" in fields:
        payload.append(memory_selection & 0xFF)
    if "severity_mask" in fields:
        payload.append(severity_mask & 0xFF)
    if "dtc" in fields:
        payload.extend((dtc & 0xFFFFFF).to_bytes(3, "big"))
    if "status_mask" in fields:
        payload.append(status_mask & 0xFF)
    if "record_number" in fields:
        payload.append(record_number & 0xFF)
    return bytes(payload)


class DTCSubFunctionSelector(ResponsiveWidget):
    """Drop-down listing every supported ReadDTCInformation sub-function.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        default: Sub-function selected on construction.

    Attributes:
        combo: The sub-function drop-down.
    """

    #: Emitted with the newly selected sub-function.
    sub_function_changed = Signal(int)
    #: Emitted with the set of required parameter names after every change.
    fields_changed = Signal(set)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        default: int = 0x02,
    ) -> None:
        """Build the drop-down and the description label."""
        super().__init__(parent, scaler)

        self.combo = QComboBox(self)
        for spec in selectable_sub_functions():
            self.combo.addItem(f"{spec.hex_value} {spec.label}", spec.value)
        self.combo.currentIndexChanged.connect(self._on_changed)

        self.hint_label = QLabel("", self)
        self.hint_label.setProperty("role", "secondary")
        self.hint_label.setWordWrap(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(QLabel("Sub-function:", self))
        layout.addWidget(self.combo, 2)
        layout.addWidget(self.hint_label, 3)

        self.set_sub_function(default)

    # -- API -----------------------------------------------------------------
    def sub_function(self) -> int:
        """Return the currently selected sub-function byte."""
        return int(self.combo.currentData() or 0)

    def set_sub_function(self, value: int) -> bool:
        """Select *value*.

        Returns:
            ``True`` when the value exists in the drop-down.
        """
        index = self.combo.findData(value)
        if index < 0:
            return False
        self.combo.setCurrentIndex(index)
        self._on_changed(index)
        return True

    def spec(self) -> SubFunctionSpec:
        """Return the specification of the current selection."""
        return describe_sub_function(self.sub_function())

    def required_fields(self) -> set[str]:
        """Return the parameter names required by the current selection."""
        return required_fields(self.sub_function())

    def returns_list(self) -> bool:
        """Return ``True`` when the response carries a DTC list."""
        return self.spec().returns_list

    def returns_count(self) -> bool:
        """Return ``True`` when the response carries a DTC count."""
        return self.spec().returns_count

    def supported_sub_functions(self) -> list[int]:
        """Return every sub-function offered by the drop-down."""
        return sorted(SUB_FUNCTION_SPECS)

    # -- internals ------------------------------------------------------------
    def _on_changed(self, _index: int) -> None:
        """Refresh the hint label and emit the change signals."""
        fields = self.required_fields()
        self.hint_label.setText(
            "requires: " + ", ".join(sorted(fields)) if fields else "no extra parameters"
        )
        self.sub_function_changed.emit(self.sub_function())
        self.fields_changed.emit(fields)
