"""Interactive response slicing widget with a visual byte map."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.enums.data_format_enums import DataFormat
from src.data_processing.response_slicer import (
    SLICE_COLORS,
    ResponseSlicer,
    SliceDefinition,
    SliceProfile,
)

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole
from .responsive_widget import ResponsiveWidget

#: Formats offered in the per-slice conversion drop-down.
SLICE_FORMATS: tuple[DataFormat, ...] = (
    DataFormat.HEX,
    DataFormat.ASCII,
    DataFormat.DEC_UNSIGNED,
    DataFormat.DEC_SIGNED,
    DataFormat.BIN,
    DataFormat.BCD,
    DataFormat.FLOAT32,
    DataFormat.PHYSICAL,
)


class DataSlicerWidget(ResponsiveWidget):
    """Define named slices over a response and see the converted values.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with ``{name: value}`` whenever the slices are recomputed.
    slices_changed = Signal(dict)
    #: Emitted with ``(SliceDefinition | None, raw bytes)`` when the operator
    #: selects a slice row, so a converter can work on that field alone.
    slice_selected = Signal(object, bytes)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the byte map and the slice table."""
        super().__init__(parent, scaler)
        self.slicer = ResponseSlicer()
        self.profile = SliceProfile("Untitled")
        self._data = b""

        self.byte_map = QTableWidget(2, 0, self)
        self.byte_map.setVerticalHeaderLabels(["Byte", "Slice"])
        self.byte_map.horizontalHeader().setVisible(True)
        self.byte_map.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        # Two rows plus the header plus the frame: a flat 90 px clipped the
        # "Slice" row on every DPI above 1.0, hiding the slice assignment.
        self.byte_map.verticalHeader().setDefaultSectionSize(self.px(24))
        self.byte_map.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Fixed
        )
        self.byte_map.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.byte_map.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._size_byte_map()
        self.byte_map.itemSelectionChanged.connect(self._on_map_selection)

        self.slice_table = QTableWidget(0, 6, self)
        self.slice_table.setHorizontalHeaderLabels(
            ["Name", "Start", "Length", "Format", "Value", ""]
        )
        self.slice_table.verticalHeader().setVisible(False)
        header = self.slice_table.horizontalHeader()
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        # The format column hosts a combo box; without a real width it is
        # sized from the header text and the popup overflows into "Value".
        self.slice_table.setColumnWidth(0, self.px(140))
        self.slice_table.setColumnWidth(1, self.px(60))
        self.slice_table.setColumnWidth(2, self.px(70))
        self.slice_table.setColumnWidth(3, self.px(130))
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.slice_table.setColumnWidth(5, self.px(34))
        self.slice_table.itemChanged.connect(self._on_table_edited)
        self.slice_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.slice_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.slice_table.itemSelectionChanged.connect(self._on_slice_selected)

        self.add_button = QPushButton("+ Add slice", self)
        self.add_button.clicked.connect(self.add_slice)
        self.auto_button = QPushButton("Auto detect", self)
        self.auto_button.clicked.connect(self.auto_detect)
        self.clear_button = QPushButton("Clear", self)
        self.clear_button.clicked.connect(self.clear_slices)
        self.status_label = QLabel("No data", self)
        self.status_label.setProperty("role", "secondary")

        buttons = QHBoxLayout()
        buttons.setSpacing(self.spacing(6))
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.auto_button)
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        buttons.addWidget(self.status_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(QLabel("Response bytes (select to create a slice):", self))
        layout.addWidget(self.byte_map)
        layout.addLayout(buttons)
        layout.addWidget(self.slice_table, 1)
        self._apply_mono_font()

    # -- data ----------------------------------------------------------------
    def set_data(self, data: bytes) -> None:
        """Load the response *data* to be sliced."""
        self._data = bytes(data)
        self._render_byte_map()
        self.refresh()
        self.status_label.setText(f"{len(self._data)} byte(s)")

    def data(self) -> bytes:
        """Return the loaded response bytes."""
        return self._data

    def load_profile(self, profile: SliceProfile) -> None:
        """Replace the slice definitions with *profile*."""
        self.profile = profile
        self.refresh()

    def current_profile(self) -> SliceProfile:
        """Return the current slice profile."""
        return self.profile

    def values(self) -> dict[str, Any]:
        """Return ``{slice name: value}`` for the loaded data."""
        return self.slicer.apply_dict(self._data, self.profile)

    # -- slice management -------------------------------------------------------
    def add_slice(self, start: int = 0, length: int = 1, name: str = "") -> SliceDefinition:
        """Append a new slice definition and refresh the table."""
        definition = SliceDefinition(
            name=name or f"Slice {len(self.profile) + 1}", start=start, length=length
        )
        self.profile.add(definition)
        self.refresh()
        return definition

    def remove_slice(self, index: int) -> None:
        """Remove the slice at *index*."""
        self.profile.remove(index)
        self.refresh()

    def clear_slices(self) -> None:
        """Remove every slice definition."""
        self.profile.slices.clear()
        self.refresh()

    def auto_detect(self) -> None:
        """Create a naive SID/DID/data profile for the loaded response."""
        self.profile = ResponseSlicer.auto_profile(self._data, self.profile.name)
        self.refresh()

    # -- rendering -------------------------------------------------------------
    def refresh(self) -> None:
        """Recompute every slice and repaint the table and the byte map."""
        results = self.slicer.apply(self._data, self.profile)
        self.slice_table.blockSignals(True)
        self.slice_table.setRowCount(len(results))
        for row, result in enumerate(results):
            definition = result.definition
            self.slice_table.setItem(row, 0, QTableWidgetItem(definition.name))
            self.slice_table.setItem(row, 1, QTableWidgetItem(str(definition.start)))
            self.slice_table.setItem(row, 2, QTableWidgetItem(str(definition.length)))

            box = QComboBox(self.slice_table)
            # SizeAdjustPolicy defaults to AdjustToContents, which lets the
            # widest entry ("ASCII text") push the editor past its cell and
            # over the Value column.
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(8)
            for fmt in SLICE_FORMATS:
                box.addItem(fmt.display_name, fmt.value)
            position = box.findData(definition.data_format.value)
            box.setCurrentIndex(max(0, position))
            box.currentIndexChanged.connect(
                lambda _index, r=row, widget=box: self._on_format_changed(r, widget)
            )
            self.slice_table.setCellWidget(row, 3, box)

            value_item = QTableWidgetItem(result.display)
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if definition.color:
                value_item.setForeground(QColor(definition.color))
            self.slice_table.setItem(row, 4, value_item)

            remove = QPushButton("x", self)
            remove.setFlat(True)
            remove.clicked.connect(lambda _=False, r=row: self.remove_slice(r))
            self.slice_table.setCellWidget(row, 5, remove)
        self.slice_table.blockSignals(False)
        self._colorise_byte_map()
        self.slices_changed.emit({r.name: r.value for r in results})

    def _size_byte_map(self) -> None:
        """Fix the byte map to exactly its two rows plus header and scrollbar.

        A hardcoded maximum height clipped the "Slice" row as soon as the DPI
        scale or the font grew, which hid the slice assignment - the whole
        point of the map.
        """
        head = self.byte_map.horizontalHeader()
        # The theme pads header sections, so the laid-out height exceeds the
        # size hint reported before the first show. Take whichever is larger,
        # otherwise the second ("Slice") row is clipped away.
        header = max(head.height(), head.sizeHint().height())
        rows = self.byte_map.verticalHeader().defaultSectionSize() * 2
        # The horizontal scrollbar is always reserved: a long response makes
        # it appear, and reclaiming that space later would clip the rows.
        bar = self.byte_map.horizontalScrollBar().sizeHint().height()
        frame = 2 * self.byte_map.frameWidth()
        self.byte_map.setFixedHeight(rows + header + bar + frame + self.px(6))

    def showEvent(self, event: Any) -> None:  # noqa: N802 - Qt naming
        """Re-measure the byte map once the theme has been applied."""
        super().showEvent(event)
        self._size_byte_map()

    def _render_byte_map(self) -> None:
        """Fill the byte map with the loaded data."""
        self.byte_map.setColumnCount(len(self._data))
        self.byte_map.setHorizontalHeaderLabels([str(i) for i in range(len(self._data))])
        for index, byte in enumerate(self._data):
            item = QTableWidgetItem(f"{byte:02X}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.byte_map.setItem(0, index, item)
            self.byte_map.setItem(1, index, QTableWidgetItem(""))
            self.byte_map.setColumnWidth(index, self.px(34))
        self._size_byte_map()

    def _colorise_byte_map(self) -> None:
        """Colour the byte map cells according to the slice assignments."""
        mapping = ResponseSlicer.byte_map(self._data, self.profile)
        for entry in mapping:
            index = int(entry["index"])
            label = self.byte_map.item(1, index)
            if label is None:
                continue
            label.setText(str(entry["slice"])[:6])
            colour = str(entry["color"])
            if colour:
                label.setForeground(QColor(colour))
                top = self.byte_map.item(0, index)
                if top is not None:
                    top.setForeground(QColor(colour))

    # -- events ----------------------------------------------------------------
    def _on_map_selection(self) -> None:
        """Create a slice from the selected byte range."""
        columns = sorted({item.column() for item in self.byte_map.selectedItems()})
        if len(columns) < 1:
            return
        start, length = columns[0], columns[-1] - columns[0] + 1
        if length >= 1 and self.byte_map.selectedItems():
            self.status_label.setText(f"selection: byte {start}..{columns[-1]} ({length} bytes)")

    def _on_table_edited(self, item: QTableWidgetItem) -> None:
        """Apply an edit of the name, start or length column."""
        row, column = item.row(), item.column()
        if row >= len(self.profile.slices):
            return
        definition = self.profile.slices[row]
        try:
            if column == 0:
                definition.name = item.text()
            elif column == 1:
                definition.start = max(0, int(item.text()))
            elif column == 2:
                definition.length = max(1, int(item.text()))
        except ValueError:
            pass
        self.refresh()

    def _on_format_changed(self, row: int, box: QComboBox) -> None:
        """Apply a conversion format change."""
        if row < len(self.profile.slices):
            self.profile.slices[row].data_format = DataFormat(box.currentData())
            self.refresh()

    def create_slice_from_selection(self) -> SliceDefinition | None:
        """Create a slice from the current byte map selection."""
        columns = sorted({item.column() for item in self.byte_map.selectedItems()})
        if not columns:
            return None
        return self.add_slice(columns[0], columns[-1] - columns[0] + 1)

    # -- selection --------------------------------------------------------------
    def selected_index(self) -> int:
        """Return the row index of the selected slice, or ``-1``."""
        rows = {item.row() for item in self.slice_table.selectedItems()}
        if not rows:
            return -1
        row = sorted(rows)[0]
        return row if 0 <= row < len(self.profile.slices) else -1

    def selected_slice(self) -> SliceDefinition | None:
        """Return the currently selected slice definition, if any."""
        index = self.selected_index()
        return self.profile.slices[index] if index >= 0 else None

    def selected_bytes(self) -> bytes:
        """Return the raw bytes covered by the selected slice."""
        definition = self.selected_slice()
        if definition is None:
            return b""
        return ResponseSlicer.slice_bytes(self._data, definition.start, definition.length)

    def select_slice(self, index: int) -> bool:
        """Select the slice at *index* programmatically."""
        if not 0 <= index < len(self.profile.slices):
            return False
        self.slice_table.selectRow(index)
        return True

    def _on_slice_selected(self) -> None:
        """Announce the selected slice and its raw bytes."""
        definition = self.selected_slice()
        self.slice_selected.emit(definition, self.selected_bytes())

    def _apply_mono_font(self) -> None:
        """Apply the monospace font to both tables."""
        from ..font_manager import FontManager

        font = FontManager(self.scaler).qfont(FontRole.MONOSPACE)
        if font is not None:
            self.byte_map.setFont(font)
            self.slice_table.setFont(font)


__all__ = ["DataSlicerWidget", "SLICE_FORMATS"]
