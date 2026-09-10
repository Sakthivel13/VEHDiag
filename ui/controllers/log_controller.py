"""Log panel controller bridging the log manager and the viewer."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from src.core.models.log_entry_model import LogEntry
from src.logging_system.log_filter import LogFilter
from src.logging_system.log_manager import LogManager

_logger = logging.getLogger(__name__)


class LogController(QObject):
    """Streams log entries into the viewer and handles filtering and export.

    Entries are buffered and pushed in batches so a burst of bus traffic never
    stalls the UI thread.

    Args:
        panel: The log viewer panel.
        manager: The central log manager.
        window: The main window used for notifications.
        batch_interval_ms: How often buffered entries are flushed.
        live_trace: Optional :class:`~ui.widgets.live_trace_widget.LiveTraceWidget`
            fed with the communication entries of every batch.  Sharing the
            log controller's timer keeps the strip on the UI thread and means
            a burst of traffic is coalesced exactly once.
    """

    #: Emitted with the number of entries after each flush.
    entries_updated = Signal(int)

    def __init__(
        self,
        panel: Any,
        manager: LogManager,
        window: Any = None,
        batch_interval_ms: int = 120,
        live_trace: Any = None,
    ) -> None:
        """Subscribe to the log manager and wire the panel signals."""
        super().__init__()
        self.panel = panel
        self.manager = manager
        self.window = window
        self.live_trace = live_trace
        self.filter = LogFilter()
        self._pending: list[LogEntry] = []

        manager.add_listener(self._on_entry)
        panel.pause_toggled.connect(self.set_paused)
        panel.clear_requested.connect(self.clear)
        panel.export_requested.connect(self.export)
        panel.filter_changed.connect(self.set_filter)

        self._timer = QTimer(self)
        self._timer.setInterval(batch_interval_ms)
        self._timer.timeout.connect(self._flush)
        self._timer.start()

    # -- streaming ----------------------------------------------------------
    def _on_entry(self, entry: LogEntry) -> None:
        """Buffer an entry produced by the log manager."""
        self._pending.append(entry)

    def _flush(self) -> None:
        """Push the buffered entries into the viewer."""
        if not self._pending:
            return
        batch, self._pending = self._pending, []
        for entry in batch:
            if not self.filter.is_active() or self.filter.matches(entry):
                self.panel.add_entry(entry)
            # The live trace shows raw traffic and deliberately ignores the
            # log filter: hiding a frame there would misrepresent the bus.
            if self.live_trace is not None and entry.direction and entry.data:
                self.live_trace.add_entry(entry)
        self.entries_updated.emit(self.panel.viewer.entry_count())

    # -- actions ---------------------------------------------------------------
    def set_paused(self, paused: bool) -> None:
        """Pause or resume the log stream."""
        if paused:
            self.manager.pause()
        else:
            self.manager.resume()

    def clear(self) -> None:
        """Clear the viewer, the live trace and the in-memory buffer."""
        self._pending.clear()
        self.manager.clear()
        self.panel.clear()
        if self.live_trace is not None:
            self.live_trace.clear()

    def set_filter(self, log_filter: LogFilter) -> None:
        """Apply a new filter and repopulate the viewer."""
        self.filter = log_filter
        self.refresh()

    def refresh(self) -> None:
        """Re-apply the current filter to every buffered entry."""
        entries = self.manager.entries()
        if self.filter.is_active():
            entries = self.filter.apply(entries)
        self.panel.set_entries(entries)
        self.entries_updated.emit(len(entries))

    def export(self, path: str, fmt: str) -> Path | None:
        """Export the filtered entries to *path*."""
        try:
            target = self.manager.export(path, fmt)
        except Exception as exc:  # noqa: BLE001 - reported to the operator
            self._notify(f"Export failed: {exc}", "error")
            return None
        self._notify(f"Log exported to {target.name}", "success")
        return target

    def analyse_trace(self) -> None:
        """Feed the trace viewer with the current entries."""
        if self.window is None:
            return
        trace = getattr(self.window, "trace_panel", None)
        if trace is not None:
            trace.analyse(self.manager.entries())

    def _notify(self, message: str, level: str = "info") -> None:
        """Show a toast and a status bar message."""
        if self.window is None:
            return
        toasts = getattr(self.window, "toasts", None)
        if toasts is not None:
            getattr(toasts, level, toasts.info)(message)


__all__ = ["LogController"]
