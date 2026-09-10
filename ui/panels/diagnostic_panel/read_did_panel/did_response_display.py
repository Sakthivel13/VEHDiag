"""Rendering of ReadDataByIdentifier responses.

The module owns two things: the pure functions that turn a
:class:`~src.core.models.did_model.DIDValue` into displayable text, and the
widget that shows the raw bytes, the ASCII rendering and the physical value
side by side.

Example:
    >>> from ui.panels.diagnostic_panel.read_did_panel.did_response_display import (
    ...     physical_value, render_ascii)
    >>> render_ascii(b"AB\\x00C")
    'AB.C'
    >>> physical_value(b"\\x01\\x2C", factor=0.1, offset=-40.0)
    -10.0
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from src.core.enums.data_format_enums import ByteOrder
from src.core.models.did_model import DIDDefinition, DIDValue

from ....dpi_scaler import DPIScaler
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.response_data_viewer import ResponseDataViewer
from ....widgets.scalable_label import MonoLabel

__all__ = [
    "DIDResponseDisplay",
    "physical_value",
    "render_ascii",
    "render_hex",
    "summarise",
]


def render_hex(data: bytes, group: int = 1) -> str:
    """Return *data* as uppercase hex, grouped every *group* bytes.

    Example:
        >>> render_hex(b"\\x01\\x02\\x03\\x04", 2)
        '0102 0304'
    """
    if group <= 1:
        return " ".join(f"{b:02X}" for b in data)
    chunks = [data[i : i + group] for i in range(0, len(data), group)]
    return " ".join(chunk.hex().upper() for chunk in chunks)


def render_ascii(data: bytes, placeholder: str = ".") -> str:
    """Return the printable ASCII rendering of *data*.

    Example:
        >>> render_ascii(b"\\xffVIN", "?")
        '?VIN'
    """
    return "".join(chr(b) if 32 <= b < 127 else placeholder for b in data)


def physical_value(
    raw: bytes,
    factor: float = 1.0,
    offset: float = 0.0,
    byte_order: ByteOrder = ByteOrder.BIG_ENDIAN,
    signed: bool = False,
) -> float | None:
    """Convert *raw* into its physical value.

    Args:
        raw: The payload bytes.
        factor: Multiplicative conversion factor.
        offset: Additive conversion offset.
        byte_order: Byte order used to build the integer.
        signed: Interpret the integer as two's complement.

    Returns:
        ``raw * factor + offset`` rounded to six decimals, or ``None`` when
        *raw* is empty or longer than eight bytes.

    Example:
        >>> physical_value(b"\\xff", signed=True)
        -1.0
        >>> physical_value(b"") is None
        True
    """
    if not raw or len(raw) > 8:
        return None
    order = "little" if byte_order is ByteOrder.LITTLE_ENDIAN else "big"
    number = int.from_bytes(raw, order, signed=signed)
    return round(number * factor + offset, 6)


def summarise(value: DIDValue) -> str:
    """Return a single line describing *value* for the status label.

    Example:
        >>> summarise(DIDValue(did=0xF190, raw=b"AB"))
        'F190: 2 bytes  4142  "AB"'
    """
    name = f" ({value.name})" if value.name else ""
    return (
        f"{value.did:04X}{name}: {len(value.raw)} bytes  "
        f"{value.raw.hex().upper()}  \"{render_ascii(value.raw)}\""
    )


class DIDResponseDisplay(ResponsiveWidget):
    """Shows one DID reading with its raw, ASCII and physical rendering.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        viewer: The hex-dump viewer showing the raw payload.
        value: The last :class:`DIDValue` handed to :meth:`set_value`.
    """

    #: Emitted with the raw payload when the operator asks for the slicer.
    analyse_requested = Signal(bytes)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the label grid and the hex dump viewer."""
        super().__init__(parent, scaler)
        self.value: DIDValue | None = None

        self.title_label = QLabel("No DID selected", self)
        self.title_label.setProperty("role", "heading")
        self.description_label = QLabel("", self)
        self.description_label.setProperty("role", "secondary")
        self.description_label.setWordWrap(True)

        self.hex_label = MonoLabel("-", self, self.scaler)
        self.ascii_label = MonoLabel("-", self, self.scaler)
        self.physical_label = QLabel("-", self)
        self.length_label = QLabel("-", self)
        self.viewer = ResponseDataViewer(self, self.scaler)

        layout = QGridLayout(self)
        gap = self.spacing(6)
        layout.setContentsMargins(gap, gap, gap, gap)
        layout.setHorizontalSpacing(self.spacing(12))
        layout.setVerticalSpacing(gap)
        layout.addWidget(self.title_label, 0, 0, 1, 4)
        layout.addWidget(self.description_label, 1, 0, 1, 4)
        layout.addWidget(self._caption("Hex"), 2, 0)
        layout.addWidget(self.hex_label, 3, 0, 1, 3)
        layout.addWidget(self._caption("Length"), 2, 3)
        layout.addWidget(self.length_label, 3, 3)
        layout.addWidget(self._caption("ASCII"), 4, 0)
        layout.addWidget(self.ascii_label, 5, 0, 1, 3)
        layout.addWidget(self._caption("Physical"), 4, 3)
        layout.addWidget(self.physical_label, 5, 3)
        layout.addWidget(self.viewer, 6, 0, 1, 4)
        layout.setRowStretch(6, 1)

    def _caption(self, text: str) -> QLabel:
        """Return a small secondary caption label."""
        label = QLabel(text, self)
        label.setProperty("role", "secondary")
        return label

    # -- API -----------------------------------------------------------------
    def set_value(self, value: DIDValue) -> None:
        """Render *value* in every field."""
        self.value = value
        definition: DIDDefinition | None = value.definition
        title = f"{value.did:04X}"
        if value.name:
            title += f" - {value.name}"
        self.title_label.setText(title)
        self.description_label.setText(definition.description if definition else "")
        self.hex_label.setText(render_hex(value.raw) or "-")
        self.ascii_label.setText(render_ascii(value.raw) or "-")
        self.length_label.setText(f"{len(value.raw)} bytes")
        self.physical_label.setText(self._physical_text(value))
        self.viewer.set_data(value.raw, decoded=summarise(value), parsed=value.as_row())

    def clear(self) -> None:
        """Reset every field to its empty state."""
        self.value = None
        self.title_label.setText("No DID selected")
        self.description_label.clear()
        for label in (self.hex_label, self.ascii_label, self.length_label, self.physical_label):
            label.setText("-")
        self.viewer.clear()

    def raw(self) -> bytes:
        """Return the payload currently displayed."""
        return self.value.raw if self.value else b""

    # -- internals ------------------------------------------------------------
    def _physical_text(self, value: DIDValue) -> str:
        """Return the physical value rendering including the unit."""
        definition = value.definition
        if definition is None:
            return "-"
        physical = physical_value(
            value.raw, definition.factor, definition.offset, definition.byte_order
        )
        if physical is None:
            return "-"
        unit = f" {definition.unit}" if definition.unit else ""
        return f"{physical:g}{unit}"
