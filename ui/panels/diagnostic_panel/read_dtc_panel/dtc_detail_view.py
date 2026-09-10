"""Detail pane for a single diagnostic trouble code.

Shows the decoded identity of the code (SAE rendering, category, failure type),
every status bit, the severity information and the list of snapshot and
extended data records that have been read so far.

Example:
    >>> from ui.panels.diagnostic_panel.read_dtc_panel.dtc_detail_view import (
    ...     category_name, describe_failure_type, identity_rows)
    >>> category_name(0xC07300)
    'Network'
    >>> describe_failure_type(0x00)
    'no sub-type information'
    >>> describe_failure_type(0x11)
    'circuit short to ground'
    >>> identity_rows.__name__
    'identity_rows'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.models.dtc_model import DTC, DTCExtendedRecord, DTCSnapshotRecord

from ....dpi_scaler import DPIScaler
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel, MonoLabel
from .dtc_status_display import DTCStatusDisplay
from ....styles.layout_helpers import tune_form

__all__ = [
    "DTCDetailView",
    "category_name",
    "describe_failure_type",
    "identity_rows",
]

#: Human readable name of each DTC category.
CATEGORY_NAMES: dict[str, str] = {
    "P": "Powertrain",
    "C": "Chassis",
    "B": "Body",
    "U": "Network",
}

#: Selected SAE J2012 failure type bytes.
FAILURE_TYPES: dict[int, str] = {
    0x00: "no sub-type information",
    0x11: "circuit short to ground",
    0x12: "circuit short to battery",
    0x13: "circuit open",
    0x16: "circuit voltage below threshold",
    0x17: "circuit voltage above threshold",
    0x1C: "circuit voltage out of range",
    0x21: "signal amplitude below threshold",
    0x22: "signal amplitude above threshold",
    0x29: "signal invalid",
    0x2F: "signal erratic",
    0x31: "no signal",
    0x38: "signal frequency incorrect",
    0x49: "internal electronic failure",
    0x62: "signal compare failure",
    0x64: "signal plausibility failure",
    0x81: "invalid serial data received",
    0x87: "missing message",
    0x88: "bus off",
}


def category_name(code: int) -> str:
    """Return the readable category of the DTC *code*.

    Example:
        >>> category_name(0x010000)
        'Powertrain'
    """
    letter = {0b00: "P", 0b01: "C", 0b10: "B", 0b11: "U"}[(code >> 22) & 0b11]
    return CATEGORY_NAMES[letter]


def describe_failure_type(failure_type: int) -> str:
    """Return the meaning of the DTC failure type byte.

    Example:
        >>> describe_failure_type(0xAB)
        'manufacturer specific (0xAB)'
    """
    return FAILURE_TYPES.get(
        failure_type & 0xFF, f"manufacturer specific (0x{failure_type & 0xFF:02X})"
    )


def identity_rows(dtc: DTC) -> list[tuple[str, str]]:
    """Return ``(caption, value)`` pairs describing *dtc*.

    Example:
        >>> from src.core.models.dtc_model import DTC
        >>> dict(identity_rows(DTC(code=0xC07300)))["Category"]
        'Network'
    """
    return [
        ("Code", dtc.display_code),
        ("Raw value", f"0x{dtc.code:06X}"),
        ("SAE code", dtc.sae_code),
        ("Category", category_name(dtc.code)),
        ("Failure type", f"0x{dtc.failure_type:02X} - {describe_failure_type(dtc.failure_type)}"),
        ("Description", dtc.name or "unknown"),
        ("Severity", "-" if dtc.severity is None else f"0x{dtc.severity:02X}"),
        (
            "Functional unit",
            "-" if dtc.functional_unit is None else f"0x{dtc.functional_unit:02X}",
        ),
    ]


class DTCDetailView(ResponsiveWidget):
    """Detail pane showing everything known about one DTC.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        dtc: The DTC currently displayed, if any.
        status_display: The eight status bit indicators.
    """

    #: Emitted with the DTC code when a snapshot read is requested.
    snapshot_requested = Signal(int)
    #: Emitted with the DTC code when an extended data read is requested.
    extended_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the identity form, the status display and the record lists."""
        super().__init__(parent, scaler)
        self.dtc: DTC | None = None

        self.title = HeadingLabel("No DTC selected", 3, self, self.scaler)
        self.fields: dict[str, QLabel] = {}

        identity_box = QGroupBox("Identity", self)
        self._form = QFormLayout(identity_box)
        self._form.setSpacing(self.spacing(6))
        for caption, _ in identity_rows(DTC(code=0)):
            label = MonoLabel("-", self, self.scaler)
            self.fields[caption] = label
            self._form.addRow(f"{caption}:", label)

        status_box = QGroupBox("Status bits", self)
        status_layout = QVBoxLayout(status_box)
        self.status_display = DTCStatusDisplay(self, self.scaler)
        status_layout.addWidget(self.status_display)

        self.snapshot_list = QListWidget(self)
        self.extended_list = QListWidget(self)
        self.snapshot_button = ScalableButton("Read snapshot", "search", self, self.scaler)
        self.snapshot_button.clicked.connect(self._request_snapshot)
        self.extended_button = ScalableButton("Read extended data", "search", self, self.scaler)
        self.extended_button.clicked.connect(self._request_extended)

        snapshot_box = QGroupBox("Snapshot records", self)
        snapshot_layout = QVBoxLayout(snapshot_box)
        snapshot_layout.addWidget(self.snapshot_list)
        snapshot_layout.addWidget(self.snapshot_button)

        extended_box = QGroupBox("Extended data records", self)
        extended_layout = QVBoxLayout(extended_box)
        extended_layout.addWidget(self.extended_list)
        extended_layout.addWidget(self.extended_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(8))
        layout.addWidget(self.title)
        layout.addWidget(identity_box)
        layout.addWidget(status_box)
        layout.addWidget(snapshot_box, 1)
        layout.addWidget(extended_box, 1)

        self.set_enabled(False)

    # -- API -----------------------------------------------------------------
    def set_dtc(self, dtc: DTC) -> None:
        """Display *dtc* in every section."""
        self.dtc = dtc
        self.title.setText(f"{dtc.display_code} - {dtc.name or 'unknown fault'}")
        for caption, value in identity_rows(dtc):
            self.fields[caption].setText(value)
        self.status_display.set_status(dtc.status)
        self._fill_snapshots(dtc.snapshots)
        self._fill_extended(dtc.extended_records)
        self.set_enabled(True)

    def clear(self) -> None:
        """Reset every section."""
        self.dtc = None
        self.title.setText("No DTC selected")
        for label in self.fields.values():
            label.setText("-")
        self.status_display.clear()
        self.snapshot_list.clear()
        self.extended_list.clear()
        self.set_enabled(False)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the two read buttons."""
        self.snapshot_button.setEnabled(enabled)
        self.extended_button.setEnabled(enabled)

    # -- internals ------------------------------------------------------------
    def _fill_snapshots(self, records: list[DTCSnapshotRecord]) -> None:
        """Fill the snapshot list from *records*."""
        self.snapshot_list.clear()
        for record in records:
            text = f"record 0x{record.record_number:02X}: {record.data.hex().upper() or '(empty)'}"
            item = QListWidgetItem(text, self.snapshot_list)
            if record.parsed:
                item.setToolTip(
                    "\n".join(f"{key}: {value}" for key, value in record.parsed.items())
                )
        if not records:
            QListWidgetItem("no snapshot read yet", self.snapshot_list)

    def _fill_extended(self, records: list[DTCExtendedRecord]) -> None:
        """Fill the extended data list from *records*."""
        self.extended_list.clear()
        for record in records:
            counter = record.occurrence_counter
            suffix = f"  (occurrences: {counter})" if counter is not None else ""
            QListWidgetItem(
                f"record 0x{record.record_number:02X}: "
                f"{record.data.hex().upper() or '(empty)'}{suffix}",
                self.extended_list,
            )
        if not records:
            QListWidgetItem("no extended data read yet", self.extended_list)

    def _request_snapshot(self) -> None:
        """Emit :attr:`snapshot_requested` for the displayed DTC."""
        if self.dtc is not None:
            self.snapshot_requested.emit(self.dtc.code)

    def _request_extended(self) -> None:
        """Emit :attr:`extended_requested` for the displayed DTC."""
        if self.dtc is not None:
            self.extended_requested.emit(self.dtc.code)
