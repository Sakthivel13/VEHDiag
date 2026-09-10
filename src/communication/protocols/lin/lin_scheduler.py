"""LIN schedule table execution."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator

from .lin_frame import LINFrame


@dataclass(slots=True)
class ScheduleEntry:
    """One slot of a LIN schedule table.

    Attributes:
        frame_id: Frame identifier transmitted in this slot.
        delay_ms: Nominal slot time in milliseconds.
        data: Data published by the master (empty for slave responses).
        label: Human readable slot name.
    """

    frame_id: int
    delay_ms: float = 10.0
    data: bytes = b""
    label: str = ""

    def to_frame(self, enhanced: bool = True) -> LINFrame:
        """Return the :class:`LINFrame` transmitted in this slot."""
        return LINFrame(self.frame_id, self.data, enhanced=enhanced)


@dataclass(slots=True)
class ScheduleTable:
    """An ordered list of :class:`ScheduleEntry` slots."""

    name: str = "default"
    entries: list[ScheduleEntry] = field(default_factory=list)

    @property
    def cycle_time_ms(self) -> float:
        """Return the total duration of one table pass."""
        return sum(entry.delay_ms for entry in self.entries)

    def __iter__(self) -> Iterator[ScheduleEntry]:  # noqa: D105 - trivial
        return iter(self.entries)

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.entries)


class LINScheduler:
    """Executes a :class:`ScheduleTable` on a background thread.

    Args:
        send_frame: Callable transmitting one :class:`LINFrame`.
        table: Schedule table to run.
    """

    def __init__(self, send_frame: Callable[[LINFrame], None], table: ScheduleTable | None = None) -> None:
        """Create the scheduler in the stopped state."""
        self.send_frame = send_frame
        self.table = table or ScheduleTable()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.cycles = 0

    @property
    def is_running(self) -> bool:
        """Return ``True`` while the schedule thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start executing the schedule table."""
        if self.is_running or not self.table.entries:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="lin-schedule", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        """Stop the schedule thread."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    def set_table(self, table: ScheduleTable) -> None:
        """Replace the schedule table, restarting if it was running."""
        running = self.is_running
        self.stop()
        self.table = table
        if running:
            self.start()

    def _run(self) -> None:
        """Thread body sending each slot in order, forever."""
        while not self._stop.is_set():
            for entry in self.table.entries:
                if self._stop.is_set():
                    return
                try:
                    self.send_frame(entry.to_frame())
                except Exception:  # noqa: BLE001 - keep the schedule running
                    pass
                time.sleep(entry.delay_ms / 1000.0)
            self.cycles += 1


__all__ = ["ScheduleEntry", "ScheduleTable", "LINScheduler"]
