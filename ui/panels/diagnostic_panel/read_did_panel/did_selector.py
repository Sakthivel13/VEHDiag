"""Searchable data identifier selector.

The widget combines a filter box with a list of the DIDs known to a
:class:`~src.core.models.did_model.DIDRegistry` and a free hexadecimal field so
that unknown identifiers can still be requested.

Example:
    >>> from ui.panels.diagnostic_panel.read_did_panel.did_selector import parse_did_text
    >>> parse_did_text("F190")
    [61840]
    >>> parse_did_text("F190, 0xF18C  F187")
    [61840, 61836, 61831]
    >>> parse_did_text("nonsense")
    []
"""
from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.models.did_model import DIDDefinition, DIDRegistry

from ....dpi_scaler import DPIScaler
from ....widgets.hex_input_field import HexInputField
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.search_filter_widget import SearchFilterWidget

__all__ = ["DIDSelector", "parse_did_text"]

#: Matches one hexadecimal identifier with an optional ``0x`` prefix.
_DID_PATTERN = re.compile(r"(?:0[xX])?([0-9a-fA-F]{1,4})")


def parse_did_text(text: str) -> list[int]:
    """Parse a free-form list of data identifiers.

    Separators may be commas, semicolons or any whitespace. Values are accepted
    with or without a ``0x`` prefix.

    Args:
        text: The text typed by the operator.

    Returns:
        The parsed identifiers in the order they appeared, without duplicates.

    Example:
        >>> parse_did_text("F190;F190")
        [61840]
    """
    result: list[int] = []
    for token in re.split(r"[\s,;]+", text.strip()):
        if not token:
            continue
        match = _DID_PATTERN.fullmatch(token)
        if match is None:
            continue
        value = int(match.group(1), 16)
        if value not in result:
            result.append(value)
    return result


class DIDSelector(ResponsiveWidget):
    """Lets the operator pick one or several data identifiers.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        registry: The registry holding the known DID definitions.

    Attributes:
        list_widget: Multi-selection list of the known identifiers.
        custom_field: Hex field for identifiers not present in the registry.
    """

    #: Emitted with the list of selected identifiers whenever it changes.
    selection_changed = Signal(list)
    #: Emitted with the selected identifiers when the operator double clicks.
    did_activated = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        registry: DIDRegistry | None = None,
    ) -> None:
        """Build the search box, the list and the custom identifier field."""
        super().__init__(parent, scaler)
        self.registry = registry or DIDRegistry()

        self.search = SearchFilterWidget(self, self.scaler, placeholder="Filter DIDs...")
        self.search.search_changed.connect(self.apply_filter)

        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)

        self.custom_field = HexInputField(
            self, self.scaler, min_bytes=2, max_bytes=2, placeholder="e.g. F1 90"
        )
        self.custom_field.bytes_changed.connect(lambda _d: self._on_selection_changed())
        self.add_button = ScalableButton("Add", "add", self, self.scaler)
        self.add_button.clicked.connect(self.add_custom)

        self.count_label = QLabel("0 selected", self)
        self.count_label.setProperty("role", "secondary")

        custom_row = QHBoxLayout()
        custom_row.setSpacing(self.spacing(4))
        custom_row.addWidget(QLabel("Custom DID:", self))
        custom_row.addWidget(self.custom_field, 1)
        custom_row.addWidget(self.add_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(self.search)
        layout.addWidget(self.list_widget, 1)
        layout.addLayout(custom_row)
        layout.addWidget(self.count_label)

        self.reload()

    # -- content -------------------------------------------------------------
    def reload(self) -> None:
        """Rebuild the list from the registry, keeping the current selection."""
        selected = set(self.selected_dids())
        self.list_widget.clear()
        for definition in self._definitions():
            item = QListWidgetItem(definition.label, self.list_widget)
            item.setData(Qt.ItemDataRole.UserRole, definition.did)
            item.setToolTip(definition.description or definition.name)
            if definition.did in selected:
                item.setSelected(True)
        self._on_selection_changed()

    def set_registry(self, registry: DIDRegistry) -> None:
        """Replace the registry and reload the list."""
        self.registry = registry
        self.reload()

    def apply_filter(self, text: str) -> int:
        """Hide every entry that does not match *text*.

        Args:
            text: Case insensitive substring matched against the label.

        Returns:
            The number of visible rows.
        """
        needle = text.strip().lower()
        visible = 0
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            match = not needle or needle in item.text().lower()
            item.setHidden(not match)
            visible += int(match)
        return visible

    # -- selection -----------------------------------------------------------
    def selected_dids(self) -> list[int]:
        """Return the identifiers currently selected in the list."""
        return [
            int(item.data(Qt.ItemDataRole.UserRole))
            for item in self.list_widget.selectedItems()
        ]

    def requested_dids(self) -> list[int]:
        """Return the list selection plus the custom field value."""
        result = self.selected_dids()
        raw = self.custom_field.value()
        if len(raw) == 2:
            value = int.from_bytes(raw, "big")
            if value not in result:
                result.append(value)
        return result

    def select(self, dids: list[int]) -> None:
        """Select every identifier of *dids* in the list."""
        wanted = set(dids)
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            item.setSelected(int(item.data(Qt.ItemDataRole.UserRole)) in wanted)

    def clear_selection(self) -> None:
        """Deselect every entry and clear the custom field."""
        self.list_widget.clearSelection()
        self.custom_field.clear_value()

    def add_custom(self) -> int | None:
        """Add the custom field value to the registry and select it.

        Returns:
            The added identifier, or ``None`` when the field is incomplete.
        """
        raw = self.custom_field.value()
        if len(raw) != 2:
            return None
        did = int.from_bytes(raw, "big")
        if self.registry.get(did) is None:
            self.registry.add(DIDDefinition(did=did, name=f"Custom {did:04X}"))
        self.reload()
        self.select([*self.selected_dids(), did])
        self.custom_field.clear_value()
        return did

    # -- internals ------------------------------------------------------------
    def _definitions(self) -> list[DIDDefinition]:
        """Return the registry content ordered by identifier."""
        return sorted(self.registry.definitions.values(), key=lambda d: d.did)

    def _on_selection_changed(self) -> None:
        """Refresh the counter and emit :attr:`selection_changed`."""
        dids = self.requested_dids()
        self.count_label.setText(f"{len(dids)} selected")
        self.selection_changed.emit(dids)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        """Emit :attr:`did_activated` for the double clicked entry."""
        self.did_activated.emit(int(item.data(Qt.ItemDataRole.UserRole)))
