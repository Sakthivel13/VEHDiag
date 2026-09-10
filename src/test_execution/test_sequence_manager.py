"""Loading, saving and reordering of developer-mode test sequences."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.enums.sid_enums import ServiceID
from ..core.models.test_sequence_model import ExecutionMode, TestSequence, TestStep
from ..utils.file_utils import load_yaml, save_yaml

_logger = logging.getLogger(__name__)

#: Services offered by default in the developer mode grid, in a sensible order.
DEFAULT_SERVICES: tuple[tuple[int, str, str], ...] = (
    (0x10, "Session Control", "10 03"),
    (0x22, "Read DID", "22 F1 90"),
    (0x19, "Read DTC", "19 02 FF"),
    (0x14, "Clear DTC", "14 FF FF FF"),
    (0x27, "Security Access", "27 01"),
    (0x31, "Routine Control", "31 01 FF 00"),
    (0x2E, "Write DID", "2E F1 98 00"),
    (0x2F, "I/O Control", "2F F1 A0 03 00"),
    (0x34, "Request Download", "34 00 44 08 00 00 00 00 00 10 00"),
    (0x3E, "Tester Present", "3E 00"),
    (0x11, "ECU Reset", "11 01"),
)


@dataclass(slots=True)
class SequenceInfo:
    """Metadata about a stored sequence file."""

    path: Path
    name: str
    steps: int

    @property
    def label(self) -> str:
        """Return the text shown in the recent sequences menu."""
        return f"{self.name} ({self.steps} steps)"


class TestSequenceManager:
    """Create, persist and reorder test sequences.

    Example:
        >>> manager = TestSequenceManager()
        >>> sequence = manager.create_default()
        >>> len(sequence.steps) == len(DEFAULT_SERVICES)
        True
        >>> sequence.steps[0].name
        'Session Control'
        >>> manager.move(sequence, 0, 2)
        >>> sequence.steps[2].name
        'Session Control'
    """

    def __init__(self, profile_dir: str | Path | None = None) -> None:
        """Create the manager.

        Args:
            profile_dir: Directory used by :meth:`list_profiles`.
        """
        self.profile_dir = Path(profile_dir).expanduser() if profile_dir else None
        self.recent: list[Path] = []

    # -- creation -----------------------------------------------------------
    def create_default(self, name: str = "Default sequence") -> TestSequence:
        """Return a sequence pre-filled with the standard services."""
        from ..utils.byte_utils import hex_to_bytes

        sequence = TestSequence(name=name)
        for order, (sid, label, payload) in enumerate(DEFAULT_SERVICES, start=1):
            sequence.steps.append(
                TestStep(
                    service_id=sid,
                    name=label,
                    payload=hex_to_bytes(payload),
                    mode=ExecutionMode.PAYLOAD,
                    enabled=sid not in (0x2E, 0x34, 0x11),
                    order=order,
                )
            )
        return sequence

    def create_empty(self, name: str = "New sequence") -> TestSequence:
        """Return an empty sequence."""
        return TestSequence(name=name)

    def add_step(
        self,
        sequence: TestSequence,
        service_id: int,
        name: str = "",
        payload: bytes = b"",
        script_path: str = "",
    ) -> TestStep:
        """Append a new step to *sequence* and return it."""
        service = ServiceID.from_byte(service_id)
        step = TestStep(
            service_id=service_id,
            name=name or (service.pretty_name if service else f"Service 0x{service_id:02X}"),
            payload=payload or bytes([service_id]),
            script_path=script_path,
            mode=ExecutionMode.SCRIPT if script_path else ExecutionMode.PAYLOAD,
        )
        sequence.steps.append(step)
        sequence.reorder()
        return step

    def duplicate_step(self, sequence: TestSequence, index: int) -> TestStep:
        """Insert a copy of the step at *index* right after it.

        Raises:
            IndexError: The index is out of range.
        """
        import copy

        original = sequence.steps[index]
        clone = copy.deepcopy(original)
        clone.name = f"{original.name} (copy)"
        sequence.steps.insert(index + 1, clone)
        sequence.reorder()
        return clone

    def remove_step(self, sequence: TestSequence, index: int) -> None:
        """Remove the step at *index* and renumber the sequence."""
        if 0 <= index < len(sequence.steps):
            del sequence.steps[index]
            sequence.reorder()

    def move(self, sequence: TestSequence, from_index: int, to_index: int) -> None:
        """Move a step, used by the drag and drop editor.

        Raises:
            IndexError: The source index is out of range.
        """
        sequence.move(from_index, to_index)

    # -- persistence ----------------------------------------------------------
    def save(self, sequence: TestSequence, path: str | Path) -> Path:
        """Write *sequence* to a YAML file."""
        target = Path(path).expanduser()
        save_yaml(target, sequence.as_config())
        self._remember(target)
        _logger.info("saved test sequence to %s", target)
        return target

    def load(self, path: str | Path) -> TestSequence:
        """Read a sequence from a YAML file.

        Raises:
            FileNotFoundError: The file does not exist.
        """
        source = Path(path).expanduser()
        data = load_yaml(source, default=None)
        if data is None:
            raise FileNotFoundError(f"test sequence not found: {source}")
        sequence = TestSequence.from_config(data)
        self._remember(source)
        _logger.info("loaded test sequence %s with %d steps", sequence.name, len(sequence.steps))
        return sequence

    def export_config(self, sequence: TestSequence) -> dict[str, Any]:
        """Return the YAML serialisable representation of *sequence*."""
        return sequence.as_config()

    def import_config(self, data: dict[str, Any]) -> TestSequence:
        """Build a sequence from a serialised representation."""
        return TestSequence.from_config(data)

    def list_profiles(self) -> list[SequenceInfo]:
        """Return the sequences stored in :attr:`profile_dir`."""
        if self.profile_dir is None or not self.profile_dir.is_dir():
            return []
        infos: list[SequenceInfo] = []
        for path in sorted(self.profile_dir.glob("*.yaml")):
            data = load_yaml(path, default={}) or {}
            infos.append(
                SequenceInfo(
                    path=path,
                    name=str(data.get("name", path.stem)),
                    steps=len(data.get("test_sequence", [])),
                )
            )
        return infos

    def _remember(self, path: Path) -> None:
        """Insert *path* at the front of the recent list."""
        self.recent = [p for p in self.recent if p != path]
        self.recent.insert(0, path)
        del self.recent[10:]


__all__ = ["TestSequenceManager", "SequenceInfo", "DEFAULT_SERVICES"]
