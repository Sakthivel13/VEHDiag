"""Project save, load and export.

A project bundles everything an engineer needs for one vehicle or one ECU: the
connection profile, the developer mode sequence, the slice profiles, the DID
watch list and the recently used firmware files. Projects are plain YAML with
the ``.vdp`` suffix so they can be reviewed and committed.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..utils.file_utils import load_yaml, save_yaml
from .event_bus import EventBus, EventType, get_event_bus

_logger = logging.getLogger(__name__)

#: Suffix of a project file.
PROJECT_SUFFIX = ".vdp"

#: Version of the project file format.
FORMAT_VERSION = 1


@dataclass(slots=True)
class Project:
    """The content of one project file.

    Attributes:
        name: Display name of the project.
        description: Free-form description.
        vehicle: Vehicle identification (VIN, model, year).
        connection: Serialised connection profile.
        sequence: Serialised developer mode sequence.
        slice_profiles: Named response slicing profiles.
        watch_dids: Data identifiers of the monitor panel.
        firmware_files: Paths of the firmware files of the flash panel.
        settings: Project specific configuration overrides.
        created_at: Creation timestamp.
        modified_at: Last modification timestamp.
    """

    name: str = "Untitled project"
    description: str = ""
    vehicle: dict[str, str] = field(default_factory=dict)
    connection: dict[str, Any] = field(default_factory=dict)
    sequence: dict[str, Any] = field(default_factory=dict)
    slice_profiles: list[dict[str, Any]] = field(default_factory=list)
    watch_dids: list[int] = field(default_factory=list)
    firmware_files: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Return the YAML serialisable representation."""
        return {
            "format_version": FORMAT_VERSION,
            "name": self.name,
            "description": self.description,
            "vehicle": dict(self.vehicle),
            "connection": dict(self.connection),
            "sequence": dict(self.sequence),
            "slice_profiles": list(self.slice_profiles),
            "watch_dids": [f"{did:04X}" for did in self.watch_dids],
            "firmware_files": list(self.firmware_files),
            "settings": dict(self.settings),
            "created_at": self.created_at,
            "modified_at": time.time(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        """Build a project from its serialised representation."""
        watch: list[int] = []
        for entry in data.get("watch_dids", []):
            try:
                watch.append(int(str(entry), 16))
            except ValueError:
                continue
        return cls(
            name=str(data.get("name", "Untitled project")),
            description=str(data.get("description", "")),
            vehicle=dict(data.get("vehicle", {})),
            connection=dict(data.get("connection", {})),
            sequence=dict(data.get("sequence", {})),
            slice_profiles=list(data.get("slice_profiles", [])),
            watch_dids=watch,
            firmware_files=[str(path) for path in data.get("firmware_files", [])],
            settings=dict(data.get("settings", {})),
            created_at=float(data.get("created_at", time.time())),
            modified_at=float(data.get("modified_at", time.time())),
        )

    @property
    def summary(self) -> str:
        """Return a one line description for the recent projects menu."""
        vehicle = self.vehicle.get("vin") or self.vehicle.get("model") or ""
        steps = len(self.sequence.get("test_sequence", []))
        return f"{self.name}" + (f" ({vehicle})" if vehicle else "") + f" - {steps} test step(s)"


class ProjectManager:
    """Creates, loads, saves and exports projects.

    Args:
        event_bus: Bus used to announce file operations.

    Example:
        >>> import tempfile, pathlib
        >>> manager = ProjectManager()
        >>> project = manager.create("Demo")
        >>> path = manager.save(pathlib.Path(tempfile.mkdtemp()) / "demo.vdp")
        >>> manager.load(path).name
        'Demo'
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Create the manager with an empty project."""
        self.bus = event_bus or get_event_bus()
        self.project = Project()
        self.path: Path | None = None
        self.modified = False
        self.recent: list[Path] = []

    # -- lifecycle ----------------------------------------------------------
    def create(self, name: str = "Untitled project") -> Project:
        """Start a new empty project."""
        self.project = Project(name=name)
        self.path = None
        self.modified = False
        return self.project

    def load(self, path: str | Path) -> Project:
        """Read a project file.

        Raises:
            FileNotFoundError: The file does not exist.
        """
        source = Path(path).expanduser()
        data = load_yaml(source, default=None)
        if data is None:
            raise FileNotFoundError(f"project not found: {source}")
        self.project = Project.from_dict(data)
        self.path = source
        self.modified = False
        self._remember(source)
        self.bus.publish(EventType.FILE_LOADED, {"path": str(source), "kind": "project"},
                         "ProjectManager")
        _logger.info("loaded project %s", self.project.name)
        return self.project

    def save(self, path: str | Path | None = None) -> Path:
        """Write the project, using the previous path when none is given.

        Raises:
            ValueError: No path was supplied and the project was never saved.
        """
        target = Path(path).expanduser() if path else self.path
        if target is None:
            raise ValueError("the project has no path yet; supply one")
        if target.suffix != PROJECT_SUFFIX:
            target = target.with_suffix(PROJECT_SUFFIX)
        save_yaml(target, self.project.to_dict())
        self.path = target
        self.modified = False
        self._remember(target)
        self.bus.publish(EventType.FILE_SAVED, {"path": str(target), "kind": "project"},
                         "ProjectManager")
        _logger.info("saved project to %s", target)
        return target

    def mark_modified(self) -> None:
        """Record that the project differs from the file on disk."""
        self.modified = True
        self.project.modified_at = time.time()

    # -- content -------------------------------------------------------------
    def capture(
        self,
        connection: dict[str, Any] | None = None,
        sequence: dict[str, Any] | None = None,
        slice_profiles: list[dict[str, Any]] | None = None,
        watch_dids: list[int] | None = None,
        firmware_files: list[str] | None = None,
    ) -> Project:
        """Store the current application state into the project."""
        if connection is not None:
            self.project.connection = connection
        if sequence is not None:
            self.project.sequence = sequence
        if slice_profiles is not None:
            self.project.slice_profiles = slice_profiles
        if watch_dids is not None:
            self.project.watch_dids = list(watch_dids)
        if firmware_files is not None:
            self.project.firmware_files = list(firmware_files)
        self.mark_modified()
        return self.project

    def set_vehicle(self, vin: str = "", model: str = "", year: str = "") -> None:
        """Record the vehicle the project belongs to."""
        self.project.vehicle = {
            key: value for key, value in (("vin", vin), ("model", model), ("year", year)) if value
        }
        self.mark_modified()

    # -- export ---------------------------------------------------------------
    def export_report(self, path: str | Path, results: list[dict[str, Any]] | None = None) -> Path:
        """Write an HTML summary of the project and the last test results."""
        import html as html_module

        rows = "".join(
            "<tr>" + "".join(f"<td>{html_module.escape(str(v))}</td>" for v in row.values()) + "</tr>"
            for row in (results or [])
        )
        headers = (
            "".join(f"<th>{html_module.escape(k)}</th>" for k in results[0]) if results else ""
        )
        vehicle = "".join(
            f"<li><b>{html_module.escape(k)}</b>: {html_module.escape(v)}</li>"
            for k, v in self.project.vehicle.items()
        )
        document = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{html_module.escape(self.project.name)}</title>
<style>
 body{{background:#1E1E2E;color:#F8FAFC;font-family:Roboto,sans-serif;padding:24px}}
 table{{border-collapse:collapse;width:100%;font-size:13px}}
 th{{background:#282840;text-align:left;padding:8px}}
 td{{border-bottom:1px solid #374151;padding:6px 8px}}
</style></head><body>
<h1>{html_module.escape(self.project.name)}</h1>
<p>{html_module.escape(self.project.description)}</p>
<ul>{vehicle}</ul>
<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>
</body></html>
"""
        target = Path(path).expanduser().with_suffix(".html")
        target.write_text(document, encoding="utf-8")
        return target

    def _remember(self, path: Path) -> None:
        """Insert *path* at the front of the recent projects list."""
        self.recent = [entry for entry in self.recent if entry != path]
        self.recent.insert(0, path)
        del self.recent[10:]


__all__ = ["Project", "ProjectManager", "PROJECT_SUFFIX", "FORMAT_VERSION"]
