"""Vector ASC (ASCII trace) writer."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable

from ..core.models.log_entry_model import LogEntry
from ..utils.file_utils import ensure_dir

_logger = logging.getLogger(__name__)


class ASCLogger:
    """Write CAN traffic in the Vector CANalyzer ASC format.

    Example:
        >>> import tempfile, pathlib
        >>> from src.core.models.log_entry_model import LogEntry
        >>> target = pathlib.Path(tempfile.mkdtemp()) / "trace.asc"
        >>> entry = LogEntry(direction="Tx", can_id="0x7E0", data=b"\\x02\\x10\\x03")
        >>> _ = ASCLogger(target).write_entries([entry])
        >>> "7E0" in target.read_text()
        True
    """

    def __init__(self, path: str | Path, channel: int = 1) -> None:
        """Store the destination path and the default channel number."""
        self.path = Path(path).expanduser()
        self.channel = channel
        ensure_dir(self.path.parent)

    def header(self, start_time: float | None = None) -> str:
        """Return the ASC file header."""
        moment = time.localtime(start_time or time.time())
        stamp = time.strftime("%a %b %d %I:%M:%S.000 %p %Y", moment)
        return f"date {stamp}\nbase hex  timestamps absolute\ninternal events logged\n"

    def format_entry(self, entry: LogEntry, start_time: float) -> str:
        """Return one ASC line for *entry*."""
        relative = max(0.0, entry.timestamp - start_time)
        identifier = entry.can_id.replace("0x", "").upper() or "0"
        direction = "Tx" if entry.direction.upper() == "TX" else "Rx"
        data = " ".join(f"{b:02X}" for b in entry.data)
        return (
            f"{relative:11.6f} {self.channel}  {identifier:<15} {direction}   d "
            f"{len(entry.data)} {data}\n"
        )

    def write_entries(self, entries: Iterable[LogEntry]) -> Path:
        """Write every entry that carries payload data."""
        items = [entry for entry in entries if entry.data]
        start = items[0].timestamp if items else time.time()
        with self.path.open("w", encoding="ascii") as handle:
            handle.write(self.header(start))
            for entry in items:
                handle.write(self.format_entry(entry, start))
        return self.path

    def append(self, entry: LogEntry, start_time: float | None = None) -> None:
        """Append a single entry to an existing ASC file."""
        new_file = not self.path.exists()
        with self.path.open("a", encoding="ascii") as handle:
            if new_file:
                handle.write(self.header(start_time))
            handle.write(self.format_entry(entry, start_time or entry.timestamp))


__all__ = ["ASCLogger"]
