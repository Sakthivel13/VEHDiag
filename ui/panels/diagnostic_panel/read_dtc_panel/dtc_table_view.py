"""Sortable, colour coded table of diagnostic trouble codes.

The table renders a :class:`~src.core.models.dtc_model.DTCReport` and colours
each row according to its severity (confirmed = red, pending = amber, clean =
green), which is the behaviour required by the design specification.

Example:
    >>> from ui.panels.diagnostic_panel.read_dtc_panel.dtc_table_view import (
    ...     COLUMNS, dtc_to_row)
    >>> COLUMNS[0]
    'Code'
    >>> from src.core.models.dtc_model import DTC, DTCStatus
    >>> row = dtc_to_row(DTC(code=0xC07300, status=DTCStatus(0x2F), name="Left sensor"))
    >>> row["Code"], row["Status"], row["Confirmed"]
    ('C0730', '0x2F', 'yes')
    >>> from ui.styles.semantic_colors import semantic
    >>> row["_color"] == semantic("confirmed")
    True
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from src.core.models.dtc_model import DTC, DTCReport

from ....dpi_scaler import DPIScaler
from ....widgets.table_widget_enhanced import EnhancedTableWidget
from .dtc_status_display import severity_of, status_colour

__all__ = ["COLUMNS", "DTCTableView", "dtc_to_row"]

#: Column titles of the DTC table.
COLUMNS: list[str] = [
    "Code",
    "Raw",
    "Description",
    "Status",
    "Confirmed",
    "Pending",
    "Severity",
    "Occurrences",
]


def dtc_to_row(dtc: DTC) -> dict[str, Any]:
    """Convert *dtc* into a row mapping understood by the table.

    Args:
        dtc: The trouble code to render.

    Returns:
        A mapping with one key per entry of :data:`COLUMNS` plus the private
        keys ``_color`` (row colour) and ``_dtc`` (the original object).

    Example:
        >>> from src.core.models.dtc_model import DTC
        >>> dtc_to_row(DTC(code=0x010000))["Raw"]
        '010000'
    """
    occurrences = (
        dtc.extended_records[0].occurrence_counter if dtc.extended_records else None
    )
    return {
        "Code": dtc.display_code,
        "Raw": dtc.code_hex,
        "Description": dtc.name,
        "Status": f"0x{dtc.status.value:02X}",
        "Confirmed": "yes" if dtc.status.confirmed else "no",
        "Pending": "yes" if dtc.status.pending else "no",
        "Severity": severity_of(dtc.status.value),
        "Occurrences": "-" if occurrences is None else str(occurrences),
        "_color": status_colour(dtc.status.value),
        "_dtc": dtc,
    }


class DTCTableView(EnhancedTableWidget):
    """Table showing every DTC of a report with severity colouring.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        report: The last :class:`DTCReport` handed to :meth:`set_report`.
    """

    #: Emitted with the DTC of the selected row.
    dtc_selected = Signal(object)
    #: Emitted with the DTC of the double clicked row.
    dtc_activated = Signal(object)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Create the table with the DTC columns."""
        super().__init__(COLUMNS, parent, scaler)
        self.report: DTCReport | None = None
        self._dtcs: list[DTC] = []
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.row_activated.connect(self._on_row_activated)

    # -- content -------------------------------------------------------------
    def set_report(self, report: DTCReport) -> int:
        """Replace the content with the DTCs of *report*.

        Returns:
            The number of rows that were inserted.
        """
        self.report = report
        return self.set_dtcs(list(report))

    def set_dtcs(self, dtcs: list[DTC]) -> int:
        """Replace the content with *dtcs*.

        Returns:
            The number of rows that were inserted.
        """
        self._dtcs = list(dtcs)
        self.set_rows([dtc_to_row(dtc) for dtc in self._dtcs], color_key="_color")
        self.resizeColumnsToContents()
        return len(self._dtcs)

    def add_dtc(self, dtc: DTC) -> int:
        """Append one DTC and return its row index."""
        self._dtcs.append(dtc)
        return self.append_row(dtc_to_row(dtc))

    def clear_dtcs(self) -> None:
        """Remove every row."""
        self._dtcs.clear()
        self.report = None
        self.clear_rows()

    def dtcs(self) -> list[DTC]:
        """Return the DTCs currently displayed."""
        return list(self._dtcs)

    # -- selection -----------------------------------------------------------
    def selected_dtc(self) -> DTC | None:
        """Return the DTC of the selected row, or ``None``."""
        rows = self.selectionModel().selectedRows() if self.selectionModel() else []
        if not rows:
            return None
        index = rows[0].row()
        return self._dtcs[index] if 0 <= index < len(self._dtcs) else None

    def select_code(self, code: int) -> bool:
        """Select the row holding the DTC *code*.

        Returns:
            ``True`` when the code was found.
        """
        for index, dtc in enumerate(self._dtcs):
            if dtc.code == code:
                self.selectRow(index)
                return True
        return False

    def counts(self) -> dict[str, int]:
        """Return the number of DTCs per severity class.

        Example:
            >>> # table.counts() -> {'confirmed': 2, 'pending': 1, 'clean': 0}
            >>> None
        """
        result = {"confirmed": 0, "pending": 0, "warning": 0, "clean": 0}
        for dtc in self._dtcs:
            result[severity_of(dtc.status.value)] += 1
        return result

    # -- internals ------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        """Emit :attr:`dtc_selected` for the newly selected row."""
        dtc = self.selected_dtc()
        if dtc is not None:
            self.dtc_selected.emit(dtc)

    def _on_row_activated(self, row: dict[str, Any]) -> None:
        """Emit :attr:`dtc_activated` for a double clicked row."""
        dtc = row.get("_dtc")
        if dtc is not None:
            self.dtc_activated.emit(dtc)
