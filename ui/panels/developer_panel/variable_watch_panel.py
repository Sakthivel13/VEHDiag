"""Watch panel for the variables published by a running test script.

Scripts store values with :meth:`DiagnosticAPI.set_variable`; this panel shows
them live, keeps a short history per variable and highlights the ones that
changed since the previous refresh.

Example:
    >>> from ui.panels.developer_panel.variable_watch_panel import (
    ...     WatchedVariable, format_value, type_name)
    >>> format_value(b"\\x01\\x02")
    '01 02'
    >>> format_value(True)
    'True'
    >>> format_value(3.14159)
    '3.14159'
    >>> type_name(b"")
    'bytes'
    >>> v = WatchedVariable("vin")
    >>> v.update("WBA")
    True
    >>> v.update("WBA")
    False
    >>> v.changes
    1
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Iterable, Mapping

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...dpi_scaler import DPIScaler
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.scalable_label import HeadingLabel
from ...widgets.table_widget_enhanced import EnhancedTableWidget
from ...styles.semantic_colors import semantic

__all__ = [
    "COLUMNS",
    "VariableWatchPanel",
    "WatchedVariable",
    "format_value",
    "type_name",
]

#: Column titles of the watch table.
COLUMNS: list[str] = ["Name", "Value", "Type", "Changes", "Updated"]

#: Number of past values kept per variable.
HISTORY_DEPTH = 32

#: Colour used to highlight a variable that just changed.
CHANGED_COLOR = semantic("running")


def format_value(value: Any) -> str:
    """Return the display rendering of *value*.

    Bytes are shown as spaced uppercase hex, everything else uses ``str``.

    Example:
        >>> format_value(None)
        'None'
        >>> format_value([1, 2])
        '[1, 2]'
    """
    if isinstance(value, (bytes, bytearray)):
        return " ".join(f"{b:02X}" for b in value)
    return str(value)


def type_name(value: Any) -> str:
    """Return the short type name of *value*.

    Example:
        >>> type_name(1)
        'int'
    """
    return type(value).__name__


@dataclass(slots=True)
class WatchedVariable:
    """One variable with its current value and its history.

    Attributes:
        name: The variable name.
        value: The current value.
        changes: How many times the value changed.
        updated_at: Monotonic timestamp of the last change.
        history: The last :data:`HISTORY_DEPTH` values.
    """

    name: str
    value: Any = None
    changes: int = 0
    updated_at: float = 0.0
    history: Deque[Any] = field(default_factory=lambda: deque(maxlen=HISTORY_DEPTH))

    def update(self, value: Any) -> bool:
        """Record *value*.

        Returns:
            ``True`` when the value actually changed.

        Example:
            >>> WatchedVariable("x").update(1)
            True
        """
        if self.changes and value == self.value:
            return False
        self.value = value
        self.changes += 1
        self.updated_at = time.monotonic()
        self.history.append(value)
        return True

    def as_row(self, now: float = 0.0) -> dict[str, Any]:
        """Return the table row describing the variable."""
        age = max(0.0, (now or time.monotonic()) - self.updated_at)
        return {
            "Name": self.name,
            "Value": format_value(self.value),
            "Type": type_name(self.value),
            "Changes": str(self.changes),
            "Updated": f"{age:.1f} s ago" if self.updated_at else "-",
            "_color": CHANGED_COLOR if age < 1.0 else "",
        }


class VariableWatchPanel(ResponsiveWidget):
    """Live table of the variables published by the running script.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        refresh_ms: Interval of the automatic table refresh.

    Attributes:
        variables: ``{name: WatchedVariable}`` in insertion order.
        table: The watch table.
    """

    #: Emitted with ``(name, value)`` whenever a variable changes.
    variable_changed = Signal(str, object)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        refresh_ms: int = 500,
    ) -> None:
        """Build the table, the toolbar and the refresh timer."""
        super().__init__(parent, scaler)
        self.variables: dict[str, WatchedVariable] = {}

        self.table = EnhancedTableWidget(COLUMNS, self, self.scaler)
        self.count_label = QLabel("no variable watched", self)
        self.count_label.setProperty("role", "secondary")

        self.clear_button = ScalableButton("Clear", "clear", self, self.scaler)
        self.clear_button.clicked.connect(self.clear)
        self.export_button = ScalableButton("Export", "export", self, self.scaler)
        self.export_button.clicked.connect(lambda: self.table.export_csv("variables.csv"))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(4))
        toolbar.addWidget(self.count_label, 1)
        toolbar.addWidget(self.clear_button)
        toolbar.addWidget(self.export_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(HeadingLabel("Variable watch", 3, self, self.scaler))
        layout.addWidget(self.table, 1)
        layout.addLayout(toolbar)

        self._timer = QTimer(self)
        self._timer.setInterval(max(100, refresh_ms))
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    # -- API -----------------------------------------------------------------
    def set_variable(self, name: str, value: Any) -> bool:
        """Record *value* for the variable *name*.

        Returns:
            ``True`` when the value changed.
        """
        variable = self.variables.get(name)
        if variable is None:
            variable = WatchedVariable(name)
            self.variables[name] = variable
        changed = variable.update(value)
        if changed:
            self.variable_changed.emit(name, value)
            self.refresh()
        return changed

    def update_from(self, values: Mapping[str, Any]) -> int:
        """Record every entry of *values* and return how many changed."""
        return sum(1 for name, value in values.items() if self.set_variable(name, value))

    def get(self, name: str, default: Any = None) -> Any:
        """Return the current value of *name*."""
        variable = self.variables.get(name)
        return variable.value if variable is not None else default

    def history(self, name: str) -> list[Any]:
        """Return the recorded history of *name*, oldest first."""
        variable = self.variables.get(name)
        return list(variable.history) if variable is not None else []

    def remove(self, name: str) -> bool:
        """Stop watching *name*."""
        removed = self.variables.pop(name, None) is not None
        if removed:
            self.refresh()
        return removed

    def clear(self) -> None:
        """Forget every variable."""
        self.variables.clear()
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the table from the current values."""
        now = time.monotonic()
        self.table.set_rows(
            [variable.as_row(now) for variable in self.variables.values()], color_key="_color"
        )
        self.count_label.setText(
            f"{len(self.variables)} variable(s) watched"
            if self.variables
            else "no variable watched"
        )

    def set_auto_refresh(self, active: bool) -> None:
        """Start or stop the automatic refresh timer."""
        self._timer.start() if active else self._timer.stop()
