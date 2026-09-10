"""File system helpers."""
from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:  # pragma: no cover - PyYAML is a hard dependency but keep imports safe
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def ensure_dir(path: str | Path) -> Path:
    """Create *path* (and parents) if needed and return it."""
    directory = Path(path).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_text(path: str | Path, encoding: str = "utf-8") -> str:
    """Return the text content of *path*."""
    return Path(path).expanduser().read_text(encoding=encoding)


def read_bytes(path: str | Path) -> bytes:
    """Return the binary content of *path*."""
    return Path(path).expanduser().read_bytes()


def atomic_write_text(path: str | Path, content: str, encoding: str = "utf-8") -> Path:
    """Write *content* to *path* atomically via a temporary file."""
    target = Path(path).expanduser()
    ensure_dir(target.parent)
    with tempfile.NamedTemporaryFile(
        "w", encoding=encoding, dir=target.parent, delete=False
    ) as handle:
        handle.write(content)
        temp_name = handle.name
    shutil.move(temp_name, target)
    return target


def load_yaml(path: str | Path, default: Any = None) -> Any:
    """Load a YAML document, returning *default* when the file is absent."""
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return default
    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML is required to read YAML configuration")
    with file_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or default


def save_yaml(path: str | Path, data: Any) -> Path:
    """Serialise *data* to YAML at *path* atomically."""
    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML is required to write YAML configuration")
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return atomic_write_text(path, text)


def load_json(path: str | Path, default: Any = None) -> Any:
    """Load a JSON document, returning *default* when the file is absent."""
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return default
    return json.loads(file_path.read_text(encoding="utf-8"))


def save_json(path: str | Path, data: Any, indent: int = 2) -> Path:
    """Serialise *data* to JSON at *path* atomically."""
    return atomic_write_text(path, json.dumps(data, indent=indent, default=str))


def human_size(num_bytes: float) -> str:
    """Return a human readable size such as ``'1.4 MB'``.

    Example:
        >>> human_size(1536)
        '1.5 KB'
    """
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024.0 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def unique_path(path: str | Path) -> Path:
    """Return *path* or ``name (2).ext``-style variant if it already exists."""
    candidate = Path(path).expanduser()
    if not candidate.exists():
        return candidate
    stem, suffix, parent = candidate.stem, candidate.suffix, candidate.parent
    index = 2
    while True:
        alternative = parent / f"{stem} ({index}){suffix}"
        if not alternative.exists():
            return alternative
        index += 1


@contextmanager
def temporary_directory(prefix: str = "vdp_") -> Iterator[Path]:
    """Yield a temporary directory that is removed on exit."""
    directory = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def iter_files(root: str | Path, suffixes: tuple[str, ...] | None = None) -> Iterator[Path]:
    """Yield files under *root*, optionally filtered by suffix."""
    for path in sorted(Path(root).expanduser().rglob("*")):
        if not path.is_file():
            continue
        if suffixes and path.suffix.lower() not in suffixes:
            continue
        yield path


__all__ = [
    "ensure_dir",
    "read_text",
    "read_bytes",
    "atomic_write_text",
    "load_yaml",
    "save_yaml",
    "load_json",
    "save_json",
    "human_size",
    "unique_path",
    "temporary_directory",
    "iter_files",
]
