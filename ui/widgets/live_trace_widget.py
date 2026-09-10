"""Compact live request/response trace strip.

This is the always-visible counterpart of
:class:`~ui.panels.log_panel.trace_viewer_panel.TraceViewerPanel`.  The full
trace viewer is an offline analysis tool: it takes a list of
:class:`~src.core.models.log_entry_model.LogEntry` objects and pairs them up
after the fact.  This widget instead grows one row at a time while the bus is
running, so the operator can slice a response and still watch the traffic that
produced it.

Rows are colour coded by outcome: a positive response is neutral, a negative
response (``7F``) is red, a still-pending ``NRC 0x78`` is amber and a request
without an answer is dimmed until it is resolved.

Example:
    >>> # trace = LiveTraceWidget()
    >>> # trace.add_frame("TX", bytes.fromhex("22F190"))
    >>> # trace.add_frame("RX", bytes.fromhex("62F19057"))
    >>> None
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.logging_system.communication_logger import decode_uds

from ..dpi_scaler import DPIScaler
from ..styles.semantic_colors import semantic
from .responsive_widget import ResponsiveWidget
from .scalable_button import ScalableButton
from .table_widget_enhanced import EnhancedTableWidget

#: Negative response service identifier.
NEGATIVE_RESPONSE = 0x7F
#: "Request correctly received, response pending" negative response code.
NRC_PENDING = 0x78
#: Columns of the trace strip.
COLUMNS: tuple[str, ...] = ("#", "Time", "Dir", "Service", "Data", "Result", "ms")


@dataclass(slots=True)
class TraceRow:
    """One line of the live trace.

    Attributes:
        index: 1-based row number.
        direction: ``"TX"`` or ``"RX"``.
        data: Raw payload bytes.
        timestamp: Unix timestamp when the frame was seen.
        request_ts: Timestamp of the request this row answers, if any.
        pending: Whether this row is a ``NRC 0x78`` pending notification.
    """

    index: int
    direction: str
    data: bytes
    timestamp: float = field(default_factory=time.time)
    request_ts: float = 0.0
    pending: bool = False

    @property
    def is_negative(self) -> bool:
        """Whether the payload is a negative response."""
        return len(self.data) >= 3 and self.data[0] == NEGATIVE_RESPONSE

    @property
    def elapsed_ms(self) -> float:
        """Round trip time against the matching request, in milliseconds."""
        if not self.request_ts:
            return 0.0
        return (self.timestamp - self.request_ts) * 1000.0


class LiveTraceWidget(ResponsiveWidget):
    """A scrolling, colour coded strip of the most recent UDS frames.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        capacity: Maximum number of rows kept before the oldest is dropped.

    Attributes:
        rows: The retained :class:`TraceRow` objects, oldest first.
    """

    #: Emitted with the payload of the row the operator double clicked.
    frame_activated = Signal(bytes)
    #: Emitted with the payload of every response added to the strip.
    response_received = Signal(bytes)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        capacity: int = 500,
    ) -> None:
        """Build the toolbar and the trace table."""
        super().__init__(parent, scaler)
        self.capacity = max(10, int(capacity))
        self.rows: list[TraceRow] = []
        self._paused = False
        self._counter = 0
        self._last_request_ts = 0.0

        self.table = EnhancedTableWidget(list(COLUMNS), self, self.scaler)
        self.table.setSortingEnabled(False)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self.table.setColumnWidth(0, self.px(50))
        self.table.setColumnWidth(1, self.px(90))
        self.table.setColumnWidth(2, self.px(50))
        self.table.setColumnWidth(3, self.px(210))
        self.table.setColumnWidth(5, self.px(230))
        self.table.setColumnWidth(6, self.px(60))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(4, header.ResizeMode.Stretch)
        # Roughly six rows: enough to see a request, its pending replies and
        # the final answer without stealing space from the analysis area.
        self.setMinimumHeight(self.px(170))

        self.pause_button = ScalableButton("Pause", "pause", self, self.scaler)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.clear_button = ScalableButton("Clear", "clear", self, self.scaler)
        self.clear_button.clicked.connect(self.clear)
        self.autoscroll_box = QCheckBox("Auto-scroll", self)
        self.autoscroll_box.setChecked(True)
        self.status_label = QLabel("0 frames", self)
        self.status_label.setProperty("role", "secondary")

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(6))
        toolbar.addWidget(QLabel("Live trace", self))
        toolbar.addWidget(self.pause_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addWidget(self.autoscroll_box)
        toolbar.addStretch(1)
        toolbar.addWidget(self.status_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(4))
        layout.addLayout(toolbar)
        layout.addWidget(self.table, 1)

    # -- ingestion -----------------------------------------------------------
    def add_frame(self, direction: str, data: bytes) -> TraceRow | None:
        """Append one frame to the strip.

        Args:
            direction: ``"TX"`` for a request, anything else for a response.
            data: Raw payload bytes.

        Returns:
            The created :class:`TraceRow`, or ``None`` when paused or empty.
        """
        payload = bytes(data)
        if self._paused or not payload:
            return None
        self._counter += 1
        is_tx = direction.upper() == "TX"
        pending = (
            not is_tx
            and len(payload) >= 3
            and payload[0] == NEGATIVE_RESPONSE
            and payload[2] == NRC_PENDING
        )
        row = TraceRow(
            index=self._counter,
            direction="TX" if is_tx else "RX",
            data=payload,
            request_ts=0.0 if is_tx else self._last_request_ts,
            pending=pending,
        )
        if is_tx:
            self._last_request_ts = row.timestamp
        self.rows.append(row)
        self.table.append_row(self._render(row))
        self._trim()
        self.status_label.setText(f"{len(self.rows)} frames")
        if self.autoscroll_box.isChecked():
            self.table.scrollToBottom()
        if not is_tx:
            self.response_received.emit(payload)
        return row

    def add_entry(self, entry: Any) -> TraceRow | None:
        """Append a :class:`LogEntry`-like object carrying ``direction``/``data``."""
        direction = getattr(entry, "direction", "")
        data = getattr(entry, "data", b"")
        if not direction or not data:
            return None
        return self.add_frame(direction, data)

    def _render(self, row: TraceRow) -> dict[str, Any]:
        """Return the table row mapping for *row*, including its colour."""
        service, detail = decode_uds(row.data)
        if row.pending:
            colour = semantic("warning")
            result = "pending (0x78)"
        elif row.is_negative:
            colour = semantic("error")
            result = detail or "negative"
        elif row.direction == "TX":
            colour = semantic("tx")
            result = ""
        else:
            colour = semantic("success")
            result = detail or "positive"
        return {
            "#": row.index,
            "Time": time.strftime("%H:%M:%S", time.localtime(row.timestamp)),
            "Dir": row.direction,
            "Service": service,
            "Data": row.data.hex(" ").upper(),
            "Result": result,
            "ms": f"{row.elapsed_ms:.1f}" if row.elapsed_ms else "",
            "_c": colour,
        }

    def _trim(self) -> None:
        """Drop the oldest rows once the capacity is exceeded."""
        excess = len(self.rows) - self.capacity
        if excess <= 0:
            return
        del self.rows[:excess]
        for _ in range(excess):
            self.table.removeRow(0)

    # -- actions -------------------------------------------------------------
    def clear(self) -> None:
        """Remove every row from the strip."""
        self.rows.clear()
        self._counter = 0
        self._last_request_ts = 0.0
        self.table.set_rows([])
        self.status_label.setText("0 frames")

    def set_paused(self, paused: bool) -> None:
        """Stop or resume appending new frames."""
        self._paused = bool(paused)
        self.pause_button.setText("Resume" if self._paused else "Pause")

    def is_paused(self) -> bool:
        """Return whether ingestion is currently paused."""
        return self._paused

    def last_response(self) -> bytes:
        """Return the payload of the most recent response, or ``b""``."""
        for row in reversed(self.rows):
            if row.direction == "RX" and not row.pending:
                return row.data
        return b""

    def _toggle_pause(self) -> None:
        """Flip the paused state from the toolbar button."""
        self.set_paused(not self._paused)

    def _on_double_click(self, item: Any) -> None:
        """Emit the payload of the double clicked row."""
        index = item.row()
        if 0 <= index < len(self.rows):
            self.frame_activated.emit(self.rows[index].data)


__all__ = ["LiveTraceWidget", "TraceRow", "COLUMNS", "NEGATIVE_RESPONSE", "NRC_PENDING"]
