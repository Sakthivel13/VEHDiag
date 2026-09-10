"""Mapping between UDS services and their test scripts.

Developer mode lets the operator attach a Python test script to each service of
the sequence. This module keeps that mapping, validates the scripts, persists
the mapping as YAML and offers a table view for editing it.

The YAML format is the one defined by the project specification::

    test_sequence:
      - service: "0x10"
        name: "Session Control"
        enabled: true
        test_file: "/path/to/session_test.py"
        payload: "10 03"
        order: 1

Example:
    >>> from ui.panels.developer_panel.test_file_mapper import (
    ...     TestFileMapping, suggested_filename, mapping_from_sequence)
    >>> suggested_filename(0x10, "Session Control")
    'test_10_session_control.py'
    >>> mapping = TestFileMapping()
    >>> mapping.assign(0x22, "/tmp/read_did.py")
    '/tmp/read_did.py'
    >>> mapping.script_for(0x22)
    '/tmp/read_did.py'
    >>> mapping.script_for(0x27) is None
    True
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.core.enums.sid_enums import SID_DESCRIPTIONS, ServiceID
from src.core.models.test_sequence_model import ExecutionMode, TestSequence, TestStep
from src.test_execution.scripts.script_validator import ScriptValidator

from ...dpi_scaler import DPIScaler
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.scalable_label import HeadingLabel
from ...widgets.table_widget_enhanced import EnhancedTableWidget
from ...styles.semantic_colors import semantic

__all__ = [
    "COLUMNS",
    "TestFileMapper",
    "TestFileMapping",
    "mapping_from_sequence",
    "suggested_filename",
]

#: Column titles of the mapping table.
COLUMNS: list[str] = ["Service", "Name", "Script", "Status"]


def suggested_filename(service_id: int, name: str = "") -> str:
    """Return the conventional script filename of a service.

    Args:
        service_id: The UDS service identifier.
        name: Optional service name used as the slug.

    Returns:
        A lowercase ``test_<sid>_<slug>.py`` filename.

    Example:
        >>> suggested_filename(0x27)
        'test_27.py'
        >>> suggested_filename(0x2E, "Write Data By ID")
        'test_2e_write_data_by_id.py'
    """
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"test_{service_id:02x}_{slug}.py" if slug else f"test_{service_id:02x}.py"


@dataclass(slots=True)
class TestFileMapping:
    """``{service_id: script_path}`` with YAML persistence.

    Attributes:
        scripts: The mapping itself.
        names: Optional display name per service identifier.
    """

    scripts: dict[int, str] = field(default_factory=dict)
    names: dict[int, str] = field(default_factory=dict)

    # -- editing -------------------------------------------------------------
    def assign(self, service_id: int, path: str | Path, name: str = "") -> str:
        """Attach *path* to *service_id* and return the stored path."""
        stored = str(Path(path).expanduser())
        self.scripts[service_id] = stored
        if name:
            self.names[service_id] = name
        return stored

    def unassign(self, service_id: int) -> bool:
        """Remove the script attached to *service_id*.

        Returns:
            ``True`` when a script was removed.
        """
        return self.scripts.pop(service_id, None) is not None

    def script_for(self, service_id: int) -> str | None:
        """Return the script attached to *service_id*, or ``None``."""
        return self.scripts.get(service_id)

    def clear(self) -> None:
        """Remove every mapping."""
        self.scripts.clear()

    # -- queries -------------------------------------------------------------
    def missing(self) -> list[int]:
        """Return the services whose script file does not exist.

        Example:
            >>> TestFileMapping({0x10: "/does/not/exist.py"}).missing()
            [16]
        """
        return [sid for sid, path in self.scripts.items() if not Path(path).is_file()]

    def service_name(self, service_id: int) -> str:
        """Return the display name of *service_id*."""
        if service_id in self.names:
            return self.names[service_id]
        return SID_DESCRIPTIONS.get(service_id, f"Service 0x{service_id:02X}")

    def rows(self) -> list[dict[str, Any]]:
        """Return the table rows describing the mapping."""
        rows: list[dict[str, Any]] = []
        for service_id in sorted(self.scripts):
            path = self.scripts[service_id]
            exists = Path(path).is_file()
            rows.append(
                {
                    "Service": f"0x{service_id:02X}",
                    "Name": self.service_name(service_id),
                    "Script": path,
                    "Status": "ok" if exists else "missing",
                    "_color": semantic("success") if exists else semantic("error"),
                }
            )
        return rows

    # -- persistence ---------------------------------------------------------
    def to_config(self) -> dict[str, Any]:
        """Return the YAML representation of the mapping.

        Example:
            >>> TestFileMapping({0x10: "a.py"}).to_config()["test_sequence"][0]["service"]
            '0x10'
        """
        return {
            "test_sequence": [
                {
                    "service": f"0x{service_id:02X}",
                    "name": self.service_name(service_id),
                    "enabled": True,
                    "test_file": self.scripts[service_id],
                    "payload": "",
                    "order": index + 1,
                }
                for index, service_id in enumerate(sorted(self.scripts))
            ]
        }

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "TestFileMapping":
        """Build a mapping from its YAML representation.

        Example:
            >>> cfg = {"test_sequence": [{"service": "0x10", "test_file": "a.py"}]}
            >>> TestFileMapping.from_config(cfg).script_for(0x10)
            'a.py'
        """
        mapping = cls()
        for entry in data.get("test_sequence", []) or []:
            service = entry.get("service", "0x00")
            service_id = int(str(service), 16) if isinstance(service, str) else int(service)
            path = entry.get("test_file") or ""
            if path:
                mapping.scripts[service_id] = str(path)
            if entry.get("name"):
                mapping.names[service_id] = str(entry["name"])
        return mapping

    def save(self, path: str | Path) -> Path:
        """Write the mapping to *path* as YAML and return the path."""
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(self.to_config(), sort_keys=False), encoding="utf-8"
        )
        return target

    @classmethod
    def load(cls, path: str | Path) -> "TestFileMapping":
        """Read a mapping from the YAML file at *path*."""
        data = yaml.safe_load(Path(path).expanduser().read_text(encoding="utf-8")) or {}
        return cls.from_config(data)

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.scripts)


def mapping_from_sequence(sequence: TestSequence) -> TestFileMapping:
    """Extract the script mapping of *sequence*.

    Example:
        >>> from src.core.models.test_sequence_model import TestSequence, TestStep
        >>> seq = TestSequence(steps=[TestStep(0x10, "Session", script_path="s.py")])
        >>> mapping_from_sequence(seq).script_for(0x10)
        's.py'
    """
    mapping = TestFileMapping()
    for step in sequence.steps:
        if step.script_path:
            mapping.assign(step.service_id, step.script_path, step.name)
    return mapping


class TestFileMapper(ResponsiveWidget):
    """Table editor for the service to test script mapping.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        mapping: The mapping to edit; a fresh one is created when omitted.

    Attributes:
        mapping: The mapping being edited.
        table: The mapping table.
    """

    #: Emitted with the mapping whenever it changes.
    mapping_changed = Signal(object)
    #: Emitted with ``(service_id, path)`` when a script is attached.
    script_assigned = Signal(int, str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        mapping: TestFileMapping | None = None,
    ) -> None:
        """Build the table and the toolbar."""
        super().__init__(parent, scaler)
        self.mapping = mapping or TestFileMapping()
        self.validator = ScriptValidator(strict=False)
        self.last_directory = str(Path.home())

        self.table = EnhancedTableWidget(COLUMNS, self, self.scaler)
        self.status_label = QLabel("no script mapped", self)
        self.status_label.setProperty("role", "secondary")

        self.assign_button = ScalableButton("Attach script", "add", self, self.scaler, accent=True)
        self.assign_button.clicked.connect(self.browse_for_selected)
        self.remove_button = ScalableButton("Detach", "remove", self, self.scaler)
        self.remove_button.clicked.connect(self.remove_selected)
        self.load_button = ScalableButton("Load YAML", "folder_open", self, self.scaler)
        self.load_button.clicked.connect(self.load_dialog)
        self.save_button = ScalableButton("Save YAML", "save", self, self.scaler)
        self.save_button.clicked.connect(self.save_dialog)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(4))
        toolbar.addWidget(self.assign_button)
        toolbar.addWidget(self.remove_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.load_button)
        toolbar.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(HeadingLabel("Test script mapping", 3, self, self.scaler))
        layout.addLayout(toolbar)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.status_label)

        self.refresh()

    # -- API -----------------------------------------------------------------
    def set_mapping(self, mapping: TestFileMapping) -> None:
        """Replace the edited mapping."""
        self.mapping = mapping
        self.refresh()

    def load_sequence(self, sequence: TestSequence) -> None:
        """Load the mapping contained in *sequence*."""
        self.set_mapping(mapping_from_sequence(sequence))

    def apply_to_sequence(self, sequence: TestSequence) -> int:
        """Write the mapping into *sequence*.

        Returns:
            The number of steps that were updated.
        """
        updated = 0
        for step in sequence.steps:
            path = self.mapping.script_for(step.service_id)
            if path and step.script_path != path:
                step.script_path = path
                step.mode = ExecutionMode.SCRIPT
                updated += 1
        return updated

    def assign(self, service_id: int, path: str | Path, name: str = "") -> str:
        """Attach *path* to *service_id* and refresh the table."""
        stored = self.mapping.assign(service_id, path, name)
        self.refresh()
        self.script_assigned.emit(service_id, stored)
        return stored

    def browse_for_selected(self) -> str:
        """Open the file dialog for the selected row."""
        service_id = self.selected_service()
        if service_id is None:
            return ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a test script", self.last_directory, "Python scripts (*.py)"
        )
        if path:
            self.last_directory = str(Path(path).parent)
            self.assign(service_id, path)
        return path

    def remove_selected(self) -> bool:
        """Detach the script of the selected row."""
        service_id = self.selected_service()
        if service_id is None:
            return False
        removed = self.mapping.unassign(service_id)
        self.refresh()
        return removed

    def selected_service(self) -> int | None:
        """Return the service identifier of the selected row, or ``None``."""
        rows = self.table.selected_rows()
        if not rows:
            return None
        return int(str(rows[0]["Service"]), 16)

    def load_dialog(self) -> Path | None:
        """Load a mapping from a YAML file chosen by the operator."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load the test mapping", self.last_directory, "YAML files (*.yaml *.yml)"
        )
        if not path:
            return None
        self.set_mapping(TestFileMapping.load(path))
        return Path(path)

    def save_dialog(self) -> Path | None:
        """Save the mapping to a YAML file chosen by the operator."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the test mapping", self.last_directory, "YAML files (*.yaml *.yml)"
        )
        if not path:
            return None
        return self.mapping.save(path)

    def refresh(self) -> None:
        """Rebuild the table and the status label."""
        self.table.set_rows(self.mapping.rows(), color_key="_color")
        missing = self.mapping.missing()
        if not self.mapping.scripts:
            self.status_label.setText("no script mapped")
        elif missing:
            self.status_label.setText(
                f"{len(self.mapping)} script(s) mapped, {len(missing)} missing on disk"
            )
        else:
            self.status_label.setText(f"{len(self.mapping)} script(s) mapped")
        self.mapping_changed.emit(self.mapping)
