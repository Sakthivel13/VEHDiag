"""Freeze frame (snapshot) viewer for a diagnostic trouble code.

A snapshot record returned by ReadDTCInformation sub-function 0x04 contains one
or more DIDs captured at the moment the fault was stored. This module decodes
that layout using a :class:`~src.core.models.did_model.DIDRegistry` and renders
the result as a table.

Example:
    >>> from ui.panels.diagnostic_panel.read_dtc_panel.dtc_freeze_frame_view import (
    ...     decode_snapshot, split_records)
    >>> payload = bytes.fromhex("F190" "1234" "F18C" "ABCD")
    >>> items = decode_snapshot(payload, {0xF190: 2, 0xF18C: 2})
    >>> [(f"{i['did']:04X}", i['hex']) for i in items]
    [('F190', '1234'), ('F18C', 'ABCD')]
    >>> split_records(b"")
    []
"""
from __future__ import annotations

from typing import Any, Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.core.models.dtc_model import DTC, DTCSnapshotRecord
from src.core.models.did_model import DIDRegistry

from ....dpi_scaler import DPIScaler
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.response_data_viewer import ResponseDataViewer
from ....widgets.scalable_label import HeadingLabel
from ....widgets.table_widget_enhanced import EnhancedTableWidget

__all__ = [
    "COLUMNS",
    "DTCFreezeFrameView",
    "decode_snapshot",
    "split_records",
]

#: Column titles of the freeze frame table.
COLUMNS: list[str] = ["DID", "Name", "Length", "Hex", "ASCII"]


def split_records(payload: bytes) -> list[DTCSnapshotRecord]:
    """Split a 0x19/0x04 payload into its snapshot records.

    The payload layout after the DTC and its status byte is
    ``recordNumber(1) numberOfIdentifiers(1) <identifier data>``. Because the
    total length of the identifier data is only known once the identifiers
    themselves are decoded, the remaining bytes are attached to the record and
    decoded later by :func:`decode_snapshot`.

    Args:
        payload: Response bytes after the DTC and its status byte.

    Returns:
        The records found in *payload*; an empty list when it is too short.

    Example:
        >>> records = split_records(bytes.fromhex("01" "01" "F1900141"))
        >>> records[0].record_number, records[0].data.hex().upper()
        (1, 'F1900141')
        >>> split_records(b"\\x01")
        []
    """
    if len(payload) < 2:
        return []
    return [DTCSnapshotRecord(record_number=payload[0], data=bytes(payload[2:]))]


def decode_snapshot(
    data: bytes, lengths: dict[int, int] | None = None, default_length: int = 1
) -> list[dict[str, Any]]:
    """Decode the ``DID + value`` sequence of a snapshot record.

    Two layouts are supported. When *lengths* knows the identifier, the value
    length is taken from it; otherwise the byte following the identifier is
    treated as an explicit length prefix.

    Args:
        data: The record payload.
        lengths: Known payload length per identifier.
        default_length: Length assumed when neither source gives one.

    Returns:
        One mapping per decoded item with the keys ``did``, ``raw``, ``hex``
        and ``ascii``.

    Example:
        >>> decode_snapshot(bytes.fromhex("F1900141"), {})[0]["ascii"]
        'A'
    """
    known = lengths or {}
    items: list[dict[str, Any]] = []
    index = 0
    while index + 2 <= len(data):
        did = int.from_bytes(data[index : index + 2], "big")
        index += 2
        if did in known:
            length = int(known[did])
        elif index < len(data):
            length = data[index]
            index += 1
        else:
            length = default_length
        raw = bytes(data[index : index + length])
        index += length
        items.append(
            {
                "did": did,
                "raw": raw,
                "hex": raw.hex().upper(),
                "ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in raw),
            }
        )
        if not raw:
            break
    return items


class DTCFreezeFrameView(ResponsiveWidget):
    """Shows the snapshot records captured with a DTC.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        registry: Registry used to resolve identifier names and lengths.

    Attributes:
        table: The decoded identifier table.
        record_box: Drop-down selecting which record is displayed.
    """

    #: Emitted with the raw record bytes when the operator asks for the slicer.
    analyse_requested = Signal(bytes)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        registry: DIDRegistry | None = None,
    ) -> None:
        """Build the record selector, the table and the raw viewer."""
        super().__init__(parent, scaler)
        self.registry = registry or DIDRegistry()
        self.records: list[DTCSnapshotRecord] = []

        self.title = HeadingLabel("Freeze frame", 3, self, self.scaler)
        self.record_box = QComboBox(self)
        self.record_box.currentIndexChanged.connect(self._on_record_selected)
        self.info_label = QLabel("no snapshot loaded", self)
        self.info_label.setProperty("role", "secondary")

        self.table = EnhancedTableWidget(COLUMNS, self, self.scaler)
        self.viewer = ResponseDataViewer(self, self.scaler)

        header = QHBoxLayout()
        header.setSpacing(self.spacing(6))
        header.addWidget(QLabel("Record:", self))
        header.addWidget(self.record_box, 1)
        header.addWidget(self.info_label, 2)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(self.title)
        layout.addLayout(header)
        layout.addWidget(self.table, 2)
        layout.addWidget(self.viewer, 1)

    # -- API -----------------------------------------------------------------
    def set_records(self, records: Iterable[DTCSnapshotRecord]) -> int:
        """Display *records* and select the first one.

        Returns:
            The number of records that were loaded.
        """
        self.records = list(records)
        self.record_box.blockSignals(True)
        self.record_box.clear()
        for record in self.records:
            self.record_box.addItem(
                f"0x{record.record_number:02X} ({len(record.data)} bytes)", record.record_number
            )
        self.record_box.blockSignals(False)
        if self.records:
            self.record_box.setCurrentIndex(0)
            self._on_record_selected(0)
        else:
            self.clear()
        return len(self.records)

    def set_dtc(self, dtc: DTC) -> int:
        """Display the snapshots attached to *dtc*."""
        self.title.setText(f"Freeze frame - {dtc.display_code}")
        return self.set_records(dtc.snapshots)

    def clear(self) -> None:
        """Remove every record."""
        self.records = []
        self.record_box.clear()
        self.table.clear_rows()
        self.viewer.clear()
        self.info_label.setText("no snapshot loaded")

    def current_record(self) -> DTCSnapshotRecord | None:
        """Return the record currently selected, or ``None``."""
        index = self.record_box.currentIndex()
        return self.records[index] if 0 <= index < len(self.records) else None

    def decoded_items(self) -> list[dict[str, Any]]:
        """Return the decoded identifiers of the selected record."""
        record = self.current_record()
        if record is None:
            return []
        return decode_snapshot(record.data, self._known_lengths())

    # -- internals ------------------------------------------------------------
    def _known_lengths(self) -> dict[int, int]:
        """Return ``{did: length}`` for every registry entry with a length."""
        return {
            did: definition.length
            for did, definition in self.registry.definitions.items()
            if definition.length
        }

    def _on_record_selected(self, index: int) -> None:
        """Decode and render the record at *index*."""
        if not 0 <= index < len(self.records):
            return
        record = self.records[index]
        items = decode_snapshot(record.data, self._known_lengths())
        rows = []
        for item in items:
            definition = self.registry.get(item["did"])
            rows.append(
                {
                    "DID": f"{item['did']:04X}",
                    "Name": definition.name if definition else "",
                    "Length": str(len(item["raw"])),
                    "Hex": item["hex"],
                    "ASCII": item["ascii"],
                }
            )
        self.table.set_rows(rows)
        self.info_label.setText(
            f"{len(items)} identifiers, {len(record.data)} bytes"
            if items
            else f"{len(record.data)} raw bytes"
        )
        self.viewer.set_data(record.data, decoded=f"snapshot 0x{record.record_number:02X}")
        self.analyse_requested.emit(record.data)
