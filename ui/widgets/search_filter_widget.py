"""Search and filter input with debouncing and quick filters."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget

from src.logging_system.log_filter import QUICK_FILTERS, LogFilter

from ..dpi_scaler import DPIScaler
from .responsive_widget import ResponsiveWidget


class SearchFilterWidget(ResponsiveWidget):
    """A debounced search box combined with a quick filter selector.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        placeholder: Placeholder text of the search field.
        debounce_ms: Delay before the search signal is emitted.
    """

    #: Emitted with the search text after the debounce delay.
    search_changed = Signal(str)
    #: Emitted with the selected quick filter.
    filter_selected = Signal(object)
    #: Emitted when the user presses Return.
    search_submitted = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        placeholder: str = "Search...",
        debounce_ms: int = 200,
    ) -> None:
        """Build the search row."""
        super().__init__(parent, scaler)
        self.field = QLineEdit(self)
        self.field.setPlaceholderText(placeholder)
        self.field.setClearButtonEnabled(True)
        self.field.textChanged.connect(self._on_text_changed)
        self.field.returnPressed.connect(lambda: self.search_submitted.emit(self.field.text()))

        self.regex_box = QCheckBox("Regex", self)
        self.case_box = QCheckBox("Aa", self)
        self.case_box.setToolTip("Case sensitive search")

        self.quick_box = QComboBox(self)
        self.quick_box.addItem("No filter", "")
        for name in QUICK_FILTERS:
            self.quick_box.addItem(name, name)
        self.quick_box.currentIndexChanged.connect(self._on_quick_filter)

        self.previous_button = QPushButton("<", self)
        self.previous_button.setToolTip("Previous match")
        self.next_button = QPushButton(">", self)
        self.next_button.setToolTip("Next match")
        for button in (self.previous_button, self.next_button):
            button.setFixedWidth(self.px(28))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(4))
        layout.addWidget(self.field, 1)
        layout.addWidget(self.previous_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.regex_box)
        layout.addWidget(self.case_box)
        layout.addWidget(self.quick_box)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(lambda: self.search_changed.emit(self.field.text()))

    # -- API -----------------------------------------------------------------
    def text(self) -> str:
        """Return the current search text."""
        return self.field.text()

    def set_text(self, text: str) -> None:
        """Set the search text."""
        self.field.setText(text)

    def clear(self) -> None:
        """Empty the search field and reset the quick filter."""
        self.field.clear()
        self.quick_box.setCurrentIndex(0)

    def build_filter(self) -> LogFilter:
        """Return a :class:`LogFilter` describing the current inputs."""
        name = self.quick_box.currentData()
        base = QUICK_FILTERS.get(str(name)) if name else None
        result = LogFilter.from_dict(base.to_dict()) if base else LogFilter()
        if self.regex_box.isChecked():
            result.regex = self.field.text()
        else:
            result.contains = self.field.text()
        result.case_sensitive = self.case_box.isChecked()
        return result

    def _on_text_changed(self, _text: str) -> None:
        """Restart the debounce timer."""
        self._timer.start()

    def _on_quick_filter(self, index: int) -> None:
        """Emit the selected quick filter."""
        self.filter_selected.emit(self.build_filter())


__all__ = ["SearchFilterWidget"]
