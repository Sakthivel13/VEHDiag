"""Communication trace viewer with request/response pairing."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from src.core.models.log_entry_model import LogEntry
from src.logging_system.communication_logger import decode_uds

from ...dpi_scaler import DPIScaler
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_label import HeadingLabel
from ...widgets.table_widget_enhanced import EnhancedTableWidget


@dataclass(slots=True)
class Exchange:
    """One request/response pair extracted from the log."""

    request: LogEntry
    response: LogEntry | None = None
    pending_count: int = 0

    @property
    def response_time_ms(self) -> float:
        """Return the round trip time in milliseconds."""
        if self.response is None:
            return 0.0
        return (self.response.timestamp - self.request.timestamp) * 1000.0

    @property
    def service(self) -> str:
        """Return the decoded service name of the request."""
        return decode_uds(self.request.data)[0]

    @property
    def result(self) -> str:
        """Return a short description of the outcome."""
        if self.response is None:
            return "no response"
        name, detail = decode_uds(self.response.data)
        return f"{name} {detail}".strip()


class TraceViewerPanel(ResponsiveWidget):
    """Pairs requests with responses and shows the timing of each exchange.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the exchange table and the sequence diagram view."""
        super().__init__(parent, scaler)
        self.exchanges: list[Exchange] = []

        self.table = EnhancedTableWidget(
            ["#", "Time", "Service", "Request", "Response", "Result", "Time (ms)"],
            self,
            self.scaler,
        )
        self.diagram = QPlainTextEdit(self)
        self.diagram.setReadOnly(True)
        self.diagram.setProperty("role", "mono")
        self.statistics_label = QLabel("No exchanges", self)
        self.statistics_label.setProperty("role", "secondary")

        table_box = QGroupBox("Request / response pairs", self)
        table_layout = QVBoxLayout(table_box)
        table_layout.addWidget(self.table)
        table_layout.addWidget(self.statistics_label)

        diagram_box = QGroupBox("Sequence diagram", self)
        diagram_layout = QVBoxLayout(diagram_box)
        diagram_layout.addWidget(self.diagram)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(8))
        layout.addWidget(HeadingLabel("Communication trace", 3, self, self.scaler))
        layout.addWidget(table_box, 2)
        layout.addWidget(diagram_box, 1)

    # -- analysis ------------------------------------------------------------
    def analyse(self, entries: list[LogEntry]) -> list[Exchange]:
        """Pair the TX and RX entries of *entries* into exchanges."""
        self.exchanges = []
        pending: Exchange | None = None
        for entry in entries:
            if not entry.data:
                continue
            if entry.direction == "TX":
                if pending is not None:
                    self.exchanges.append(pending)
                pending = Exchange(request=entry)
            elif pending is not None:
                if len(entry.data) >= 3 and entry.data[0] == 0x7F and entry.data[2] == 0x78:
                    pending.pending_count += 1
                    continue
                pending.response = entry
                self.exchanges.append(pending)
                pending = None
        if pending is not None:
            self.exchanges.append(pending)
        self._render()
        return self.exchanges

    def _render(self) -> None:
        """Fill the table, the diagram and the statistics line."""
        rows: list[dict[str, Any]] = []
        for index, exchange in enumerate(self.exchanges, start=1):
            rows.append(
                {
                    "#": index,
                    "Time": exchange.request.formatted_time(False),
                    "Service": exchange.service,
                    "Request": exchange.request.hex_data,
                    "Response": exchange.response.hex_data if exchange.response else "-",
                    "Result": exchange.result,
                    "Time (ms)": f"{exchange.response_time_ms:.1f}",
                }
            )
        self.table.set_rows(rows)

        lines = ["Tester              ECU", "  |                  |"]
        for exchange in self.exchanges[-40:]:
            lines.append(f"  |  --- {exchange.request.hex_data[:20]:<20} -->  |")
            for _ in range(exchange.pending_count):
                lines.append("  |  <-- 7F .. 78 (pending)   |")
            if exchange.response is not None:
                lines.append(
                    f"  |  <-- {exchange.response.hex_data[:20]:<20} ---  |"
                    f"  ({exchange.response_time_ms:.1f} ms)"
                )
            else:
                lines.append("  |      (timeout)            |")
        self.diagram.setPlainText("\n".join(lines))

        times = [e.response_time_ms for e in self.exchanges if e.response is not None]
        if times:
            self.statistics_label.setText(
                f"{len(self.exchanges)} exchanges | average {sum(times) / len(times):.1f} ms | "
                f"max {max(times):.1f} ms | {sum(1 for e in self.exchanges if e.response is None)} timeouts"
            )
        else:
            self.statistics_label.setText(f"{len(self.exchanges)} exchanges | no responses")


__all__ = ["TraceViewerPanel", "Exchange"]
