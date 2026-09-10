"""Full filter editor for the communication log.

Where :class:`~ui.widgets.search_filter_widget.SearchFilterWidget` is the quick
one-line filter above the log table, this panel exposes every criterion of
:class:`~src.logging_system.log_filter.LogFilter`: severity, category,
direction, protocol, identifier range, payload pattern and the tester-present
suppression. Filters can be saved to and loaded from YAML.

Example:
    >>> from ui.panels.log_panel.log_filter_panel import (
    ...     LEVEL_NAMES, parse_id, describe_filter)
    >>> LEVEL_NAMES[0]
    'TRACE'
    >>> parse_id("0x7E0")
    2016
    >>> parse_id("7E0")
    2016
    >>> parse_id("")
    >>> from src.logging_system.log_filter import LogFilter
    >>> describe_filter(LogFilter())
    'no filter active'
    >>> describe_filter(LogFilter(hide_tester_present=True))
    'tester present hidden'
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.models.log_entry_model import LogCategory, LogLevel
from src.logging_system.log_filter import QUICK_FILTERS, LogFilter

from ...dpi_scaler import DPIScaler
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.scalable_label import HeadingLabel
from ...styles.layout_helpers import tune_form

__all__ = [
    "DIRECTIONS",
    "LEVEL_NAMES",
    "LogFilterPanel",
    "PROTOCOLS",
    "describe_filter",
    "parse_id",
]

#: Severity names offered by the level drop-down.
LEVEL_NAMES: list[str] = [level.name for level in LogLevel]

#: Directions offered as checkboxes.
DIRECTIONS: tuple[str, ...] = ("TX", "RX")

#: Protocol names offered as checkboxes.
PROTOCOLS: tuple[str, ...] = ("CAN", "CANFD", "DOIP", "KLINE", "LIN", "FLEXRAY", "J1939")


def parse_id(text: str) -> int | None:
    """Parse a CAN identifier written with or without the ``0x`` prefix.

    Args:
        text: The text typed by the operator.

    Returns:
        The parsed value, or ``None`` when *text* is empty or invalid.

    Example:
        >>> parse_id("zzz") is None
        True
    """
    cleaned = text.strip().lower().removeprefix("0x")
    if not cleaned:
        return None
    try:
        return int(cleaned, 16)
    except ValueError:
        return None


def describe_filter(log_filter: LogFilter) -> str:
    """Return a one line description of the active criteria.

    Example:
        >>> describe_filter(LogFilter(min_level=LogLevel.ERROR))
        'level >= ERROR'
    """
    parts: list[str] = []
    if log_filter.min_level > LogLevel.TRACE:
        parts.append(f"level >= {log_filter.min_level.name}")
    if log_filter.categories:
        parts.append("categories: " + ", ".join(sorted(c.value for c in log_filter.categories)))
    if log_filter.directions:
        parts.append("directions: " + ", ".join(sorted(log_filter.directions)))
    if log_filter.protocols:
        parts.append("protocols: " + ", ".join(sorted(log_filter.protocols)))
    if log_filter.id_from is not None or log_filter.id_to is not None:
        low = "*" if log_filter.id_from is None else f"0x{log_filter.id_from:X}"
        high = "*" if log_filter.id_to is None else f"0x{log_filter.id_to:X}"
        parts.append(f"id {low}..{high}")
    if log_filter.contains:
        parts.append(f"contains '{log_filter.contains}'")
    if log_filter.regex:
        parts.append(f"regex /{log_filter.regex}/")
    if log_filter.data_pattern:
        parts.append(f"payload {log_filter.data_pattern}")
    if log_filter.hide_tester_present:
        parts.append("tester present hidden")
    return ", ".join(parts) if parts else "no filter active"


class LogFilterPanel(ResponsiveWidget):
    """Editor exposing every criterion of a :class:`LogFilter`.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        level_box: Minimum severity drop-down.
        category_boxes: One checkbox per :class:`LogCategory`.
    """

    #: Emitted with the built filter whenever a criterion changes.
    filter_changed = Signal(object)
    #: Emitted when the operator resets the filter.
    filter_reset = Signal()

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build every criterion editor."""
        super().__init__(parent, scaler)
        self._updating = False

        self.level_box = QComboBox(self)
        self.level_box.addItems(LEVEL_NAMES)
        self.level_box.currentIndexChanged.connect(self._emit)

        self.category_boxes: dict[LogCategory, QCheckBox] = {}
        category_layout = QGridLayout()
        for index, category in enumerate(LogCategory):
            box = QCheckBox(category.value, self)
            box.toggled.connect(self._emit)
            self.category_boxes[category] = box
            category_layout.addWidget(box, index // 3, index % 3)

        self.direction_boxes: dict[str, QCheckBox] = {}
        direction_row = QHBoxLayout()
        for direction in DIRECTIONS:
            box = QCheckBox(direction, self)
            box.toggled.connect(self._emit)
            self.direction_boxes[direction] = box
            direction_row.addWidget(box)
        direction_row.addStretch(1)

        self.protocol_boxes: dict[str, QCheckBox] = {}
        protocol_layout = QGridLayout()
        for index, protocol in enumerate(PROTOCOLS):
            box = QCheckBox(protocol, self)
            box.toggled.connect(self._emit)
            self.protocol_boxes[protocol] = box
            protocol_layout.addWidget(box, index // 4, index % 4)

        self.id_from_field = QLineEdit(self)
        self.id_from_field.setPlaceholderText("0x700")
        self.id_to_field = QLineEdit(self)
        self.id_to_field.setPlaceholderText("0x7FF")
        self.contains_field = QLineEdit(self)
        self.contains_field.setPlaceholderText("substring")
        self.regex_field = QLineEdit(self)
        self.regex_field.setPlaceholderText("regular expression")
        self.payload_field = QLineEdit(self)
        self.payload_field.setPlaceholderText("hex pattern, e.g. 62F190")
        for field in (
            self.id_from_field,
            self.id_to_field,
            self.contains_field,
            self.regex_field,
            self.payload_field,
        ):
            field.textChanged.connect(self._emit)

        self.hide_tp_box = QCheckBox("Hide tester present traffic", self)
        self.hide_tp_box.toggled.connect(self._emit)
        self.case_box = QCheckBox("Case sensitive", self)
        self.case_box.toggled.connect(self._emit)

        self.quick_box = QComboBox(self)
        self.quick_box.addItem("Quick filters...", "")
        for name in QUICK_FILTERS:
            self.quick_box.addItem(name, name)
        self.quick_box.activated.connect(self._on_quick)

        self.summary_label = QLabel(describe_filter(LogFilter()), self)
        self.summary_label.setProperty("role", "secondary")
        self.summary_label.setWordWrap(True)

        self.reset_button = ScalableButton("Reset", "refresh", self, self.scaler)
        self.reset_button.clicked.connect(self.reset)
        self.load_button = ScalableButton("Load", "folder_open", self, self.scaler)
        self.load_button.clicked.connect(self.load_dialog)
        self.save_button = ScalableButton("Save", "save", self, self.scaler)
        self.save_button.clicked.connect(self.save_dialog)

        severity_box = QGroupBox("Severity and category", self)
        severity_form = QFormLayout(severity_box)
        tune_form(severity_form, self.scaler)
        severity_form.addRow("Minimum level:", self.level_box)
        severity_form.addRow("Categories:", self._wrap(category_layout))

        traffic_box = QGroupBox("Traffic", self)
        traffic_form = QFormLayout(traffic_box)
        tune_form(traffic_form, self.scaler)
        traffic_form.addRow("Directions:", self._wrap(direction_row))
        traffic_form.addRow("Protocols:", self._wrap(protocol_layout))
        traffic_form.addRow("Identifier from:", self.id_from_field)
        traffic_form.addRow("Identifier to:", self.id_to_field)

        text_box = QGroupBox("Content", self)
        text_form = QFormLayout(text_box)
        tune_form(text_form, self.scaler)
        text_form.addRow("Contains:", self.contains_field)
        text_form.addRow("Regex:", self.regex_field)
        text_form.addRow("Payload pattern:", self.payload_field)
        text_form.addRow("", self.case_box)
        text_form.addRow("", self.hide_tp_box)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(4))
        toolbar.addWidget(self.quick_box, 1)
        toolbar.addStretch(1)
        toolbar.addWidget(self.reset_button)
        toolbar.addWidget(self.load_button)
        toolbar.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(8))
        layout.addWidget(HeadingLabel("Log filter", 3, self, self.scaler))
        layout.addLayout(toolbar)
        layout.addWidget(severity_box)
        layout.addWidget(traffic_box)
        layout.addWidget(text_box)
        layout.addWidget(self.summary_label)
        layout.addStretch(1)

    def _wrap(self, inner: Any) -> QWidget:
        """Return a plain widget hosting the layout *inner*."""
        holder = QWidget(self)
        holder.setLayout(inner)
        return holder

    # -- API -----------------------------------------------------------------
    def build_filter(self) -> LogFilter:
        """Return the :class:`LogFilter` described by the current editors."""
        return LogFilter(
            min_level=LogLevel.parse(self.level_box.currentText()),
            categories={
                category for category, box in self.category_boxes.items() if box.isChecked()
            },
            directions={
                direction for direction, box in self.direction_boxes.items() if box.isChecked()
            },
            protocols={
                protocol for protocol, box in self.protocol_boxes.items() if box.isChecked()
            },
            id_from=parse_id(self.id_from_field.text()),
            id_to=parse_id(self.id_to_field.text()),
            contains=self.contains_field.text(),
            regex=self.regex_field.text(),
            data_pattern=self.payload_field.text(),
            hide_tester_present=self.hide_tp_box.isChecked(),
            case_sensitive=self.case_box.isChecked(),
        )

    def apply_filter(self, log_filter: LogFilter) -> None:
        """Load *log_filter* into the editors."""
        self._updating = True
        try:
            index = self.level_box.findText(log_filter.min_level.name)
            if index >= 0:
                self.level_box.setCurrentIndex(index)
            for category, box in self.category_boxes.items():
                box.setChecked(category in log_filter.categories)
            for direction, box in self.direction_boxes.items():
                box.setChecked(direction in log_filter.directions)
            for protocol, box in self.protocol_boxes.items():
                box.setChecked(protocol in log_filter.protocols)
            self.id_from_field.setText(
                "" if log_filter.id_from is None else f"0x{log_filter.id_from:X}"
            )
            self.id_to_field.setText(
                "" if log_filter.id_to is None else f"0x{log_filter.id_to:X}"
            )
            self.contains_field.setText(log_filter.contains)
            self.regex_field.setText(log_filter.regex)
            self.payload_field.setText(log_filter.data_pattern)
            self.hide_tp_box.setChecked(log_filter.hide_tester_present)
            self.case_box.setChecked(log_filter.case_sensitive)
        finally:
            self._updating = False
        self._emit()

    def reset(self) -> None:
        """Clear every criterion."""
        self.apply_filter(LogFilter())
        self.filter_reset.emit()

    def save(self, path: str | Path) -> Path:
        """Write the current filter to *path* as YAML."""
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(self.build_filter().to_dict(), sort_keys=False), encoding="utf-8"
        )
        return target

    def load(self, path: str | Path) -> LogFilter:
        """Load a filter from the YAML file at *path*."""
        data = yaml.safe_load(Path(path).expanduser().read_text(encoding="utf-8")) or {}
        log_filter = LogFilter.from_dict(data)
        self.apply_filter(log_filter)
        return log_filter

    def save_dialog(self) -> Path | None:
        """Ask where to save the filter and write it."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the log filter", str(Path.home()), "YAML files (*.yaml *.yml)"
        )
        return self.save(path) if path else None

    def load_dialog(self) -> LogFilter | None:
        """Ask for a filter file and load it."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load a log filter", str(Path.home()), "YAML files (*.yaml *.yml)"
        )
        return self.load(path) if path else None

    # -- internals ------------------------------------------------------------
    def _emit(self, *_args: Any) -> None:
        """Refresh the summary and publish the built filter."""
        if self._updating:
            return
        log_filter = self.build_filter()
        self.summary_label.setText(describe_filter(log_filter))
        self.filter_changed.emit(log_filter)

    def _on_quick(self, index: int) -> None:
        """Apply the quick filter selected at *index*."""
        name = str(self.quick_box.itemData(index) or "")
        if name in QUICK_FILTERS:
            self.apply_filter(QUICK_FILTERS[name])
