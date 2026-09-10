"""Visualisation of the eight ISO 14229 DTC status bits.

The bit order is fixed by the specification and reproduced by
:data:`~src.core.models.dtc_model.DTC_STATUS_BITS`:

===  ==========================================
Bit  Meaning
===  ==========================================
0    testFailed
1    testFailedThisOperationCycle
2    pendingDTC
3    confirmedDTC
4    testNotCompletedSinceLastClear
5    testFailedSinceLastClear
6    testNotCompletedThisOperationCycle
7    warningIndicatorRequested
===  ==========================================

Example:
    >>> from ui.panels.diagnostic_panel.read_dtc_panel.dtc_status_display import (
    ...     bit_rows, severity_of)
    >>> [row["name"] for row in bit_rows(0x01)][:1]
    ['testFailed']
    >>> bit_rows(0x09)[3]["set"]
    True
    >>> severity_of(0x08)
    'confirmed'
    >>> severity_of(0x04)
    'pending'
    >>> severity_of(0x00)
    'clean'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from src.core.models.dtc_model import DTC_STATUS_BITS, DTCStatus
from src.diagnostics.services.dtc_services.dtc_status_mask import (
    BIT_ABBREVIATIONS,
    describe_status,
)

from ....dpi_scaler import DPIScaler
from ....styles.semantic_colors import semantic, severity_color
from ....widgets.led_indicator import LedIndicator
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_label import MonoLabel

__all__ = ["DTCStatusDisplay", "SEVERITY_NAMES", "bit_rows", "severity_of", "status_colour"]

#: Severity classes, resolved through the active theme at paint time.
SEVERITY_NAMES: tuple[str, ...] = ("confirmed", "pending", "warning", "clean")


def bit_rows(status: int) -> list[dict[str, Any]]:
    """Return one descriptor per status bit.

    Args:
        status: The raw status byte.

    Returns:
        A list of eight mappings with the keys ``bit``, ``name``,
        ``abbreviation`` and ``set``, ordered from bit 0 to bit 7.

    Example:
        >>> len(bit_rows(0xFF))
        8
        >>> bit_rows(0x80)[7]["abbreviation"] == BIT_ABBREVIATIONS[7]
        True
    """
    return [
        {
            "bit": bit,
            "name": name,
            "abbreviation": BIT_ABBREVIATIONS[bit],
            "set": bool(status & (1 << bit)),
        }
        for bit, name in DTC_STATUS_BITS.items()
    ]


def severity_of(status: int) -> str:
    """Classify *status* into ``confirmed``, ``pending``, ``warning`` or ``clean``.

    Example:
        >>> severity_of(0x80)
        'warning'
    """
    if status & 0x08:
        return "confirmed"
    if status & 0x04:
        return "pending"
    if status & 0x80:
        return "warning"
    return "clean"


def status_colour(status: int) -> str:
    """Return the colour used to render *status* in the active theme.

    The colour is resolved through :mod:`ui.styles.semantic_colors`, so a
    confirmed DTC stays legible when the operator switches to the light or the
    high contrast theme.

    Example:
        >>> from ui.styles.semantic_colors import semantic
        >>> status_colour(0x08) == semantic("confirmed")
        True
        >>> status_colour(0x00) == semantic("clean")
        True
    """
    return severity_color(severity_of(status))


class DTCStatusDisplay(ResponsiveWidget):
    """Renders a DTC status byte as eight labelled indicators.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        columns: Number of indicator columns in the grid.

    Attributes:
        leds: One :class:`LedIndicator` per bit, keyed by bit index.
    """

    #: Emitted with the status byte after every :meth:`set_status` call.
    status_changed = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        columns: int = 4,
    ) -> None:
        """Build the indicator grid."""
        super().__init__(parent, scaler)
        self._status = 0
        self.leds: dict[int, LedIndicator] = {}
        self.labels: dict[int, QLabel] = {}

        layout = QGridLayout(self)
        gap = self.spacing(4)
        layout.setContentsMargins(gap, gap, gap, gap)
        layout.setHorizontalSpacing(self.spacing(10))
        layout.setVerticalSpacing(gap)

        for bit, name in DTC_STATUS_BITS.items():
            led = LedIndicator("idle", 12, self, self.scaler)
            led.setToolTip(f"Bit {bit}: {name}")
            label = QLabel(BIT_ABBREVIATIONS[bit], self)
            label.setToolTip(f"Bit {bit}: {name}")
            label.setProperty("role", "secondary")
            self.leds[bit] = led
            self.labels[bit] = label
            row, column = divmod(bit, max(1, columns))
            layout.addWidget(led, row, column * 2)
            layout.addWidget(label, row, column * 2 + 1)

        self.summary_label = MonoLabel("0x00 []", self, self.scaler)
        layout.addWidget(self.summary_label, (8 // max(1, columns)) + 1, 0, 1, columns * 2)

    # -- API -----------------------------------------------------------------
    def status(self) -> int:
        """Return the status byte currently displayed."""
        return self._status

    def set_status(self, status: int | DTCStatus) -> None:
        """Display *status*, which may be a raw byte or a :class:`DTCStatus`."""
        value = int(status.value if isinstance(status, DTCStatus) else status) & 0xFF
        self._status = value
        for bit, led in self.leds.items():
            is_set = bool(value & (1 << bit))
            led.set_state("error" if is_set and bit in (0, 3) else "pass" if is_set else "idle")
            self.labels[bit].setProperty("state", "active" if is_set else "")
        self.summary_label.setText(describe_status(value))
        self.setToolTip(describe_status(value))
        self.status_changed.emit(value)

    def clear(self) -> None:
        """Reset every indicator."""
        self.set_status(0)

    def active_names(self) -> list[str]:
        """Return the names of the bits that are currently set.

        Example:
            >>> # display.set_status(0x09); display.active_names()
            >>> None
        """
        return [row["name"] for row in bit_rows(self._status) if row["set"]]

    def severity(self) -> str:
        """Return the severity class of the displayed status."""
        return severity_of(self._status)

    def colour(self) -> str:
        """Return the colour used for the displayed status."""
        return status_colour(self._status)
