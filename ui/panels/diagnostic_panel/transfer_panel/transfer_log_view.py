"""Chronological log of a firmware transfer session.

Every step of a flash session — session change, security unlock, request
download, each transferred block, transfer exit and verification — is appended
here with a relative timestamp so the operator can see where time was spent and
which step failed.

Example:
    >>> from ui.panels.diagnostic_panel.transfer_panel.transfer_log_view import (
    ...     TransferLogEntry, format_delta, entry_row)
    >>> format_delta(0.0)
    '+0.000 s'
    >>> format_delta(1.25)
    '+1.250 s'
    >>> row = entry_row(TransferLogEntry(delta_s=0.5, step="RequestDownload", detail="0x8000"))
    >>> row["Time"], row["Step"], row["Result"]
    ('+0.500 s', 'RequestDownload', 'ok')
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ....dpi_scaler import DPIScaler
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel
from ....widgets.table_widget_enhanced import EnhancedTableWidget
from ....styles.semantic_colors import semantic

__all__ = [
    "COLUMNS",
    "TransferLogEntry",
    "TransferLogView",
    "entry_row",
    "format_delta",
]

#: Column titles of the transfer log table.
COLUMNS: list[str] = ["Time", "Step", "Detail", "Result", "Duration"]

#: Row colour per result.
RESULT_COLORS: dict[str, str] = {
    "ok": semantic("success"),
    "warning": semantic("warning"),
    "error": semantic("error"),
    "info": semantic("muted"),
}


def format_delta(seconds: float) -> str:
    """Return the relative timestamp rendering used by the log.

    Example:
        >>> format_delta(12.3456)
        '+12.346 s'
    """
    return f"+{seconds:.3f} s"


@dataclass(slots=True)
class TransferLogEntry:
    """One line of the transfer log.

    Attributes:
        delta_s: Seconds elapsed since the session started.
        step: Short name of the step, e.g. ``"TransferData"``.
        detail: Free-form detail such as an address or a block number.
        result: One of ``ok``, ``warning``, ``error`` or ``info``.
        duration_ms: How long the step took, in milliseconds.
    """

    delta_s: float = 0.0
    step: str = ""
    detail: str = ""
    result: str = "ok"
    duration_ms: float = 0.0

    def as_text(self) -> str:
        """Return the entry as one plain text line.

        Example:
            >>> TransferLogEntry(1.0, "Exit", "crc ok").as_text()
            '+1.000 s  Exit  crc ok  [ok]'
        """
        return f"{format_delta(self.delta_s)}  {self.step}  {self.detail}  [{self.result}]"


def entry_row(entry: TransferLogEntry) -> dict[str, Any]:
    """Return the table row describing *entry*.

    Example:
        >>> entry_row(TransferLogEntry(result="error"))["_color"]
        semantic("error")
    """
    return {
        "Time": format_delta(entry.delta_s),
        "Step": entry.step,
        "Detail": entry.detail,
        "Result": entry.result,
        "Duration": f"{entry.duration_ms:.1f} ms" if entry.duration_ms else "-",
        "_color": RESULT_COLORS.get(entry.result, RESULT_COLORS["info"]),
    }


class TransferLogView(ResponsiveWidget):
    """Table showing every step of the current flash session.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        max_entries: Number of entries kept before the oldest are dropped.

    Attributes:
        entries: The log entries in chronological order.
    """

    #: Emitted with the entry that was just appended.
    entry_added = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        max_entries: int = 5000,
    ) -> None:
        """Build the table and the toolbar."""
        super().__init__(parent, scaler)
        self.entries: list[TransferLogEntry] = []
        self.max_entries = max_entries
        self._started_at = 0.0

        self.table = EnhancedTableWidget(COLUMNS, self, self.scaler)
        self.count_label = QLabel("no step logged", self)
        self.count_label.setProperty("role", "secondary")

        self.clear_button = ScalableButton("Clear", "clear", self, self.scaler)
        self.clear_button.clicked.connect(self.clear)
        self.export_button = ScalableButton("Export", "export", self, self.scaler)
        self.export_button.clicked.connect(lambda: self.export_text("transfer_log.txt"))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(4))
        toolbar.addWidget(self.count_label, 1)
        toolbar.addWidget(self.clear_button)
        toolbar.addWidget(self.export_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(HeadingLabel("Transfer log", 3, self, self.scaler))
        layout.addWidget(self.table, 1)
        layout.addLayout(toolbar)

    # -- API -----------------------------------------------------------------
    def start_session(self) -> None:
        """Clear the log and reset the relative time base."""
        self.clear()
        self._started_at = time.monotonic()

    def log(
        self,
        step: str,
        detail: str = "",
        result: str = "ok",
        duration_ms: float = 0.0,
    ) -> TransferLogEntry:
        """Append one step to the log.

        Args:
            step: Short name of the step.
            detail: Free-form detail.
            result: One of ``ok``, ``warning``, ``error`` or ``info``.
            duration_ms: Duration of the step in milliseconds.

        Returns:
            The entry that was appended.
        """
        if not self._started_at:
            self._started_at = time.monotonic()
        entry = TransferLogEntry(
            delta_s=time.monotonic() - self._started_at,
            step=step,
            detail=detail,
            result=result,
            duration_ms=duration_ms,
        )
        return self.add_entry(entry)

    def add_entry(self, entry: TransferLogEntry) -> TransferLogEntry:
        """Append a prepared *entry* to the log."""
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            del self.entries[: len(self.entries) - self.max_entries]
            self.table.set_rows([entry_row(item) for item in self.entries], color_key="_color")
        else:
            self.table.append_row(entry_row(entry))
        self.table.scrollToBottom()
        self._refresh_count()
        self.entry_added.emit(entry)
        return entry

    def add_entries(self, entries: Iterable[TransferLogEntry]) -> int:
        """Append every entry of *entries* and return how many were added."""
        return sum(1 for entry in entries if self.add_entry(entry))

    def clear(self) -> None:
        """Empty the log."""
        self.entries.clear()
        self.table.clear_rows()
        self._refresh_count()

    def error_count(self) -> int:
        """Return the number of entries whose result is ``error``."""
        return sum(1 for entry in self.entries if entry.result == "error")

    def as_text(self) -> str:
        """Return the whole log as plain text."""
        return "\n".join(entry.as_text() for entry in self.entries)

    def export_text(self, path: str | Path) -> Path:
        """Write the log to *path* as plain text and return the path."""
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.as_text() + "\n", encoding="utf-8")
        return target

    def export_csv(self, path: str | Path) -> Path:
        """Write the log to *path* as CSV and return the path."""
        return self.table.export_csv(path)

    # -- internals ------------------------------------------------------------
    def _refresh_count(self) -> None:
        """Refresh the counter label."""
        if not self.entries:
            self.count_label.setText("no step logged")
            return
        errors = self.error_count()
        suffix = f", {errors} error(s)" if errors else ""
        self.count_label.setText(f"{len(self.entries)} step(s){suffix}")
