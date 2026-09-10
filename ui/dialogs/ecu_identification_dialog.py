"""ECU identification dialog.

Reads the standard 0xF1xx identification identifiers, decodes the VIN and
presents everything as a copyable table. The reading itself is delegated to the
diagnostic controller: the dialog emits :attr:`read_requested` and is filled
through :meth:`set_identification`.

Example:
    >>> from ui.dialogs.ecu_identification_dialog import (
    ...     IDENTIFICATION_DIDS, decode_vin, is_valid_vin)
    >>> IDENTIFICATION_DIDS[0xF190]
    'VIN'
    >>> is_valid_vin("WBAZZZ0GM12345678")
    True
    >>> is_valid_vin("TOO-SHORT")
    False
    >>> decode_vin("WBAZZZ0GM12345678")["wmi"]
    'WBA'
    >>> decode_vin("bad")["wmi"]
    ''
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.models.did_model import DIDValue
from src.core.models.ecu_model import ECU, ECUIdentification

from ..dpi_scaler import DPIScaler
from ..widgets.scalable_button import ScalableButton
from ..widgets.scalable_label import HeadingLabel, MonoLabel
from ..widgets.table_widget_enhanced import EnhancedTableWidget

__all__ = [
    "COLUMNS",
    "ECUIdentificationDialog",
    "IDENTIFICATION_DIDS",
    "decode_vin",
    "is_valid_vin",
]

#: Identification identifiers read by the dialog, in display order.
IDENTIFICATION_DIDS: dict[int, str] = {
    0xF190: "VIN",
    0xF18C: "ECU serial number",
    0xF191: "Hardware number",
    0xF194: "Software number",
    0xF195: "Software version",
    0xF192: "Supplier hardware number",
    0xF193: "Supplier hardware version",
    0xF18A: "Supplier identifier",
    0xF18B: "Manufacturing date",
    0xF197: "System name",
    0xF186: "Active session",
}

#: Column titles of the identification table.
COLUMNS: list[str] = ["DID", "Name", "Value", "Hex", "Length"]

#: A VIN is 17 characters, excluding I, O and Q.
_VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def is_valid_vin(vin: str) -> bool:
    """Return ``True`` when *vin* is a well formed ISO 3779 VIN.

    Example:
        >>> is_valid_vin("")
        False
    """
    return bool(_VIN_PATTERN.match(vin.strip().upper()))


def decode_vin(vin: str) -> dict[str, str]:
    """Split *vin* into its three ISO 3779 sections.

    Args:
        vin: The vehicle identification number.

    Returns:
        A mapping with ``wmi`` (world manufacturer identifier), ``vds``
        (vehicle descriptor section), ``vis`` (vehicle indicator section),
        ``year_code`` and ``valid``. Every field is empty when *vin* is
        malformed.

    Example:
        >>> decode_vin("WBAZZZ0GM12345678")["vis"]
        'M12345678'
    """
    cleaned = vin.strip().upper()
    if not is_valid_vin(cleaned):
        return {"wmi": "", "vds": "", "vis": "", "year_code": "", "valid": "no"}
    return {
        "wmi": cleaned[0:3],
        "vds": cleaned[3:8],
        "vis": cleaned[8:17],
        "year_code": cleaned[9],
        "valid": "yes",
    }


class ECUIdentificationDialog(QDialog):
    """Shows the identification data read from the ECU.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        ecu: ECU whose identification is displayed on open.

    Attributes:
        table: The identifier table.
        identification: The identification currently displayed.
    """

    #: Emitted with the identifiers the dialog wants to read.
    read_requested = Signal(list)
    #: Emitted with the rendered report when the operator exports it.
    export_requested = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        ecu: ECU | None = None,
    ) -> None:
        """Build the summary block, the table and the toolbar."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.identification = ECUIdentification()
        self.values: list[DIDValue] = []
        self._vin = ""

        self.setWindowTitle("ECU identification")
        self.setModal(True)
        self.setMinimumSize(self.scaler.px(680), self.scaler.px(520))

        self.title = HeadingLabel("ECU identification", 2, self, self.scaler)
        self.vin_label = MonoLabel("-", self, self.scaler)
        self.wmi_label = QLabel("-", self)
        self.year_label = QLabel("-", self)
        self.validity_label = QLabel("-", self)
        for label in (self.wmi_label, self.year_label, self.validity_label):
            label.setProperty("role", "secondary")

        summary = QGroupBox("Vehicle", self)
        summary_layout = QHBoxLayout(summary)
        summary_layout.setSpacing(self.scaler.spacing(12))
        summary_layout.addWidget(QLabel("VIN:", self))
        summary_layout.addWidget(self.vin_label, 2)
        summary_layout.addWidget(QLabel("WMI:", self))
        summary_layout.addWidget(self.wmi_label)
        summary_layout.addWidget(QLabel("Year code:", self))
        summary_layout.addWidget(self.year_label)
        summary_layout.addWidget(QLabel("Valid:", self))
        summary_layout.addWidget(self.validity_label)

        self.table = EnhancedTableWidget(COLUMNS, self, self.scaler)
        self.status_label = QLabel("press Read to query the ECU", self)
        self.status_label.setProperty("role", "secondary")

        self.read_button = ScalableButton("Read", "refresh", self, self.scaler, accent=True)
        self.read_button.clicked.connect(self.read)
        self.copy_button = ScalableButton("Copy", "copy", self, self.scaler)
        self.copy_button.clicked.connect(lambda: self.table.copy_selection())
        self.export_button = ScalableButton("Export", "export", self, self.scaler)
        self.export_button.clicked.connect(lambda: self.export_requested.emit(self.as_text()))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.scaler.spacing(4))
        toolbar.addWidget(self.read_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.copy_button)
        toolbar.addWidget(self.export_button)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.buttons.rejected.connect(self.reject)
        self.buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.scaler.spacing(8))
        layout.addWidget(self.title)
        layout.addWidget(summary)
        layout.addLayout(toolbar)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.buttons)

        if ecu is not None:
            self.set_ecu(ecu)

    # -- API -----------------------------------------------------------------
    def read(self) -> list[int]:
        """Emit :attr:`read_requested` for every identification identifier."""
        dids = list(IDENTIFICATION_DIDS)
        self.status_label.setText(f"reading {len(dids)} identifiers...")
        self.read_requested.emit(dids)
        return dids

    def set_values(self, values: list[DIDValue]) -> None:
        """Fill the table from the readings *values*."""
        self.values = list(values)
        rows = []
        for value in self.values:
            rows.append(
                {
                    "DID": f"{value.did:04X}",
                    "Name": value.name or IDENTIFICATION_DIDS.get(value.did, ""),
                    "Value": value.ascii_value,
                    "Hex": value.hex_value,
                    "Length": str(len(value.raw)),
                }
            )
        self.table.set_rows(rows)
        vin = next(
            (v.ascii_value for v in self.values if v.did == 0xF190),
            self.identification.vin,
        )
        self._set_vin(vin)
        self.status_label.setText(f"{len(self.values)} identifier(s) read")

    def set_identification(self, identification: ECUIdentification) -> None:
        """Fill the table from an :class:`ECUIdentification`."""
        self.identification = identification
        rows = [
            {"DID": "-", "Name": name, "Value": value, "Hex": "", "Length": str(len(value))}
            for name, value in identification.as_dict().items()
            if value
        ]
        self.table.set_rows(rows)
        self._set_vin(identification.vin)
        self.status_label.setText(f"{len(rows)} field(s) available")

    def set_ecu(self, ecu: ECU) -> None:
        """Display the identification of *ecu*."""
        self.title.setText(f"ECU identification - {ecu.name}")
        self.set_identification(ecu.identification)

    def vin(self) -> str:
        """Return the VIN currently displayed.

        The label may elide long values, so the raw string recorded by
        :meth:`_set_vin` is returned instead of the label text.
        """
        return self._vin

    def as_text(self) -> str:
        """Return the identification as a plain text report."""
        lines = [self.title.text(), ""]
        lines += [f"{row['Name']}: {row['Value']}" for row in self.table.rows()]
        return "\n".join(lines)

    # -- internals ------------------------------------------------------------
    def _set_vin(self, vin: str) -> None:
        """Refresh the VIN summary block."""
        self._vin = vin.strip()
        decoded = decode_vin(self._vin)
        self.vin_label.setText(self._vin or "-")
        self.vin_label.setToolTip(self._vin)
        self.wmi_label.setText(decoded["wmi"] or "-")
        self.year_label.setText(decoded["year_code"] or "-")
        self.validity_label.setText(decoded["valid"])
        self.validity_label.setProperty(
            "state", "success" if decoded["valid"] == "yes" else "warning"
        )
