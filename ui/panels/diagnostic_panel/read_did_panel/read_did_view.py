"""ReadDataByIdentifier (SID 0x22) panel."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.models.did_model import DIDRegistry, DIDValue

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.response_data_viewer import ResponseDataViewer
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel
from ....widgets.table_widget_enhanced import EnhancedTableWidget


class ReadDIDView(ResponsiveWidget):
    """UI for reading one or several data identifiers.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        registry: Known DID definitions used to fill the predefined list.
    """

    #: Emitted with the list of DIDs the operator wants to read.
    read_requested = Signal(list)
    #: Emitted with ``(enabled, interval_ms)`` for the continuous mode.
    continuous_toggled = Signal(bool, int)
    #: Emitted with the raw response bytes when the operator clicks *Analyse*.
    analyse_requested = Signal(bytes)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        registry: DIDRegistry | None = None,
    ) -> None:
        """Build the entry row, the DID list and the response view."""
        super().__init__(parent, scaler)
        self.registry = registry or DIDRegistry()

        self.did_field = HexInputField(self, self.scaler, min_bytes=2, max_bytes=2,
                                       placeholder="F190")
        self.predefined_box = QComboBox(self)
        self.predefined_box.addItem("Predefined DIDs...", 0)
        for definition in sorted(self.registry.definitions.values(), key=lambda d: d.did):
            self.predefined_box.addItem(definition.label, definition.did)
        self.predefined_box.activated.connect(self._on_predefined)

        self.add_button = ScalableButton("Add to list", "add", self, self.scaler)
        self.add_button.clicked.connect(self.add_current)
        self.read_button = ScalableButton("Read", "play", self, self.scaler, accent=True)
        self.read_button.clicked.connect(self._on_read_single)

        self.did_table = EnhancedTableWidget(["DID", "Name", "Value", "Raw", "Length"], self, self.scaler)
        self.read_selected_button = ScalableButton("Read selected", "play", self, self.scaler)
        self.read_selected_button.clicked.connect(self._on_read_selected)
        self.read_all_button = ScalableButton("Read all", "run_all", self, self.scaler)
        self.read_all_button.clicked.connect(self._on_read_all)
        self.clear_button = ScalableButton("Clear", "clear", self, self.scaler)
        self.clear_button.clicked.connect(self.did_table.clear_rows)

        self.continuous_box = QCheckBox("Continuous read", self)
        self.interval_box = QSpinBox(self)
        self.interval_box.setRange(100, 60000)
        self.interval_box.setSingleStep(100)
        self.interval_box.setValue(1000)
        self.interval_box.setSuffix(" ms")
        self.continuous_box.toggled.connect(self._on_continuous)

        self.response_view = ResponseDataViewer(self, self.scaler)
        self.analyse_button = ScalableButton("Analyse", "convert", self, self.scaler)
        self.analyse_button.clicked.connect(
            lambda: self.analyse_requested.emit(self.response_view.data())
        )

        entry_box = QGroupBox("Read data by identifier (SID 0x22)", self)
        entry_layout = QHBoxLayout(entry_box)
        entry_layout.setSpacing(self.spacing(6))
        entry_layout.addWidget(QLabel("DID:", self))
        entry_layout.addWidget(self.did_field)
        entry_layout.addWidget(self.predefined_box, 1)
        entry_layout.addWidget(self.add_button)
        entry_layout.addWidget(self.read_button)

        list_box = QGroupBox("DID read list", self)
        list_layout = QVBoxLayout(list_box)
        list_layout.setSpacing(self.spacing(6))
        list_layout.addWidget(self.did_table)
        buttons = QHBoxLayout()
        buttons.addWidget(self.read_selected_button)
        buttons.addWidget(self.read_all_button)
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        buttons.addWidget(self.continuous_box)
        buttons.addWidget(self.interval_box)
        list_layout.addLayout(buttons)

        response_box = QGroupBox("Response", self)
        response_layout = QVBoxLayout(response_box)
        response_layout.addWidget(self.response_view)
        response_layout.addWidget(self.analyse_button, 0, Qt.AlignmentFlag.AlignLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(10))
        layout.addWidget(HeadingLabel("Read data by identifier", 3, self, self.scaler))
        layout.addWidget(entry_box)
        layout.addWidget(list_box, 1)
        layout.addWidget(response_box, 1)

    # -- list management ----------------------------------------------------
    def current_did(self) -> int | None:
        """Return the DID entered in the field, or ``None``."""
        data = self.did_field.value()
        return int.from_bytes(data, "big") if len(data) == 2 else None

    def add_current(self) -> None:
        """Add the entered DID to the read list."""
        did = self.current_did()
        if did is None:
            return
        definition = self.registry.get(did)
        self.did_table.append_row(
            {
                "DID": f"{did:04X}",
                "Name": definition.name if definition else "",
                "Value": "",
                "Raw": "",
                "Length": "",
            }
        )

    def listed_dids(self) -> list[int]:
        """Return every DID currently in the read list."""
        result: list[int] = []
        for row in self.did_table.rows():
            try:
                result.append(int(str(row.get("DID", "")), 16))
            except ValueError:
                continue
        return result

    def selected_dids(self) -> list[int]:
        """Return the DIDs of the selected rows."""
        result: list[int] = []
        for row in self.did_table.selected_rows():
            try:
                result.append(int(str(row.get("DID", "")), 16))
            except ValueError:
                continue
        return result

    # -- results ---------------------------------------------------------------
    def show_values(self, values: list[DIDValue]) -> None:
        """Update the table and the response view with the read values.

        Identifiers that are not in the table yet are appended rather than
        dropped: reading a DID typed straight into the field never adds a row
        first, so the result used to disappear silently.
        """
        rows = self.did_table.rows()
        index_by_did: dict[int, int] = {}
        for index, row in enumerate(rows):
            try:
                index_by_did[int(str(row.get("DID", "")), 16)] = index
            except ValueError:
                continue

        for value in values:
            definition = self.registry.get(value.did)
            payload = {
                "DID": f"{value.did:04X}",
                "Name": value.name or (definition.name if definition else ""),
                "Value": str(value.parsed) if value.parsed is not None else value.ascii_value,
                "Raw": value.hex_value,
                "Length": str(len(value.raw)),
            }
            existing = index_by_did.get(value.did)
            if existing is None:
                rows.append(payload)
                index_by_did[value.did] = len(rows) - 1
            else:
                rows[existing].update(payload)

        self.did_table.set_rows(rows)
        if values:
            last = values[-1]
            self.response_view.set_data(
                last.raw,
                f"DID 0x{last.did:04X} {last.name}",
                {"Parsed": last.parsed, "ASCII": last.ascii_value, "Bytes": len(last.raw)},
            )

    def show_response(self, data: bytes, decoded: str = "") -> None:
        """Display a raw response in the response view."""
        self.response_view.set_data(data, decoded)

    def set_busy(self, busy: bool) -> None:
        """Disable the read buttons while a request is running."""
        for button in (self.read_button, self.read_selected_button, self.read_all_button):
            button.setEnabled(not busy)
        self.read_button.set_loading(busy)

    # -- events ----------------------------------------------------------------
    def _on_predefined(self, index: int) -> None:
        """Fill the DID field from the predefined list."""
        did = self.predefined_box.itemData(index)
        if did:
            self.did_field.set_value(int(did).to_bytes(2, "big"))

    def _on_read_single(self) -> None:
        """Request a read of the entered DID."""
        did = self.current_did()
        if did is not None:
            self.read_requested.emit([did])

    def _on_read_selected(self) -> None:
        """Request a read of the selected list entries."""
        dids = self.selected_dids() or self.listed_dids()
        if dids:
            self.read_requested.emit(dids)

    def _on_read_all(self) -> None:
        """Request a read of every listed DID."""
        dids = self.listed_dids()
        if dids:
            self.read_requested.emit(dids)

    def _on_continuous(self, checked: bool) -> None:
        """Emit the continuous read toggle."""
        self.continuous_toggled.emit(checked, self.interval_box.value())


__all__ = ["ReadDIDView"]
