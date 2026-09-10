"""DBC database integration built on :mod:`cantools`."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ....core.exceptions import FileError, ParseError

_logger = logging.getLogger(__name__)


class CANDatabase:
    """Decode and encode CAN frames using a DBC/ARXML database.

    Example:
        >>> db = CANDatabase()
        >>> db.is_loaded
        False
    """

    def __init__(self, path: str | Path | None = None) -> None:
        """Create an empty database, optionally loading *path* immediately."""
        self._database: Any = None
        self.path: Path | None = None
        if path is not None:
            self.load(path)

    @property
    def is_loaded(self) -> bool:
        """Return ``True`` when a database file has been loaded."""
        return self._database is not None

    def load(self, path: str | Path) -> None:
        """Load a DBC, KCD, SYM or ARXML database.

        Raises:
            FileError: cantools is unavailable or the file is missing.
            ParseError: The database could not be parsed.
        """
        try:
            import cantools  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - declared dependency
            raise FileError("cantools is required to read CAN databases") from exc
        file_path = Path(path).expanduser()
        if not file_path.exists():
            raise FileError(f"CAN database not found: {file_path}")
        try:
            self._database = cantools.database.load_file(str(file_path))
        except Exception as exc:  # noqa: BLE001 - normalise parser errors
            raise ParseError(
                f"could not parse the CAN database {file_path}", {"cause": str(exc)}
            ) from exc
        self.path = file_path
        _logger.info("loaded CAN database %s with %d messages", file_path.name, len(self.messages))

    @property
    def messages(self) -> list[Any]:
        """Return every message definition in the database."""
        return list(getattr(self._database, "messages", []))

    def message_names(self) -> list[str]:
        """Return the names of all messages, sorted alphabetically."""
        return sorted(message.name for message in self.messages)

    def decode(self, arbitration_id: int, data: bytes) -> dict[str, Any]:
        """Decode a frame into named signal values.

        Returns:
            The decoded signals, or an empty mapping when the identifier is
            unknown to the database.
        """
        if not self.is_loaded:
            return {}
        try:
            return dict(self._database.decode_message(arbitration_id, data))
        except Exception:  # noqa: BLE001 - unknown ids are common on a live bus
            return {}

    def encode(self, message_name: str, signals: dict[str, Any]) -> tuple[int, bytes]:
        """Encode named signals into ``(arbitration_id, data)``.

        Raises:
            ParseError: The message or a signal name is unknown.
        """
        if not self.is_loaded:
            raise ParseError("no CAN database loaded")
        try:
            message = self._database.get_message_by_name(message_name)
            return int(message.frame_id), bytes(message.encode(signals))
        except Exception as exc:  # noqa: BLE001
            raise ParseError(
                f"could not encode the message {message_name!r}", {"cause": str(exc)}
            ) from exc

    def describe(self, arbitration_id: int) -> str:
        """Return the message name for *arbitration_id*, or an empty string."""
        if not self.is_loaded:
            return ""
        try:
            return str(self._database.get_message_by_frame_id(arbitration_id).name)
        except Exception:  # noqa: BLE001
            return ""

    def signal_names(self, message_name: str) -> list[str]:
        """Return the signal names of one message."""
        if not self.is_loaded:
            return []
        try:
            message = self._database.get_message_by_name(message_name)
        except Exception:  # noqa: BLE001
            return []
        return [signal.name for signal in message.signals]

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.messages)

    def __repr__(self) -> str:  # noqa: D105 - trivial
        name = self.path.name if self.path else "empty"
        return f"<CANDatabase {name} messages={len(self)}>"


__all__ = ["CANDatabase"]
