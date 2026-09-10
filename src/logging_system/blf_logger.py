"""Vector BLF (Binary Logging Format) writer.

BLF is a proprietary binary format; writing it correctly requires
:mod:`can.io.blf` from python-can. When the library is unavailable the logger
degrades to the ASC format and warns the caller.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from ..core.models.log_entry_model import LogEntry
from ..utils.file_utils import ensure_dir

_logger = logging.getLogger(__name__)


class BLFLogger:
    """Write CAN traffic in the Vector BLF format when python-can is present.

    Attributes:
        fell_back: ``True`` when the writer had to produce an ASC file instead.
    """

    def __init__(self, path: str | Path, channel: int = 1) -> None:
        """Store the destination path and channel number."""
        self.path = Path(path).expanduser()
        self.channel = channel
        self.fell_back = False
        ensure_dir(self.path.parent)

    @staticmethod
    def is_supported() -> bool:
        """Return ``True`` when python-can can write BLF files."""
        try:
            from can.io.blf import BLFWriter  # noqa: F401  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001
            return False
        return True

    def write_entries(self, entries: Iterable[LogEntry]) -> Path:
        """Write every entry carrying payload data.

        Returns:
            The path that was written; when BLF is unsupported the suffix is
            changed to ``.asc`` and :attr:`fell_back` is set.
        """
        items = [entry for entry in entries if entry.data]
        if not self.is_supported():
            self.fell_back = True
            _logger.warning("python-can BLF support unavailable; writing ASC instead")
            from .asc_logger import ASCLogger

            fallback = self.path.with_suffix(".asc")
            return ASCLogger(fallback, self.channel).write_entries(items)

        import can  # type: ignore[import-not-found]
        from can.io.blf import BLFWriter  # type: ignore[import-not-found]

        writer = BLFWriter(str(self.path), channel=self.channel)
        try:
            for entry in items:
                try:
                    arbitration_id = int(entry.can_id, 16) if entry.can_id else 0
                except ValueError:
                    arbitration_id = 0
                writer.on_message_received(
                    can.Message(
                        timestamp=entry.timestamp,
                        arbitration_id=arbitration_id,
                        data=entry.data,
                        is_extended_id=arbitration_id > 0x7FF,
                        is_rx=entry.direction.upper() == "RX",
                        channel=self.channel,
                    )
                )
        finally:
            writer.stop()
        return self.path


__all__ = ["BLFLogger"]
