"""Dynamic loading of Python test scripts."""
from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from ..core.exceptions import FileError
from .scripts.script_validator import REQUIRED_CLASS, ScriptValidator, ValidationReport

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LoadedScript:
    """A successfully imported test script.

    Attributes:
        path: File the script was loaded from.
        module: The imported module object.
        script_class: The ``TestScript`` class found in the module.
        report: The structural validation report.
        mtime: Modification time at load time, used by the file watcher.
    """

    path: Path
    module: ModuleType
    script_class: type
    report: ValidationReport
    mtime: float = 0.0

    @property
    def name(self) -> str:
        """Return the display name of the script."""
        return str(getattr(self.script_class, "name", self.path.stem))

    @property
    def description(self) -> str:
        """Return the class docstring of the script."""
        return (self.script_class.__doc__ or "").strip()

    def instantiate(self, api: Any) -> Any:
        """Create an instance of the script class bound to *api*."""
        return self.script_class(api)

    def changed_on_disk(self) -> bool:
        """Return ``True`` when the file was modified since it was loaded."""
        try:
            return self.path.stat().st_mtime > self.mtime
        except OSError:
            return False


class TestScriptLoader:
    """Import test scripts, validate them and cache the result.

    Args:
        validator: Structural validator; a default one is created when omitted.
        strict: Refuse to load scripts that fail validation.

    Example:
        >>> import tempfile, pathlib
        >>> code = "class TestScript:\\n    def __init__(self, api): pass\\n    def execute(self): return 'PASS'\\n"
        >>> path = pathlib.Path(tempfile.mkstemp(suffix=".py")[1])
        >>> _ = path.write_text(code)
        >>> loaded = TestScriptLoader().load(path)
        >>> loaded.script_class.__name__
        'TestScript'
    """

    def __init__(self, validator: ScriptValidator | None = None, strict: bool = True) -> None:
        """Create the loader with an empty cache."""
        self.validator = validator or ScriptValidator(strict=False)
        self.strict = strict
        self._cache: dict[str, LoadedScript] = {}

    def load(self, path: str | Path, reload: bool = False) -> LoadedScript:
        """Import the script at *path*.

        Args:
            path: Python file to import.
            reload: Re-import even when the script is cached.

        Returns:
            The :class:`LoadedScript` record.

        Raises:
            FileError: The file is missing, invalid or has no ``TestScript``.
        """
        file_path = Path(path).expanduser().resolve()
        key = str(file_path)
        cached = self._cache.get(key)
        if cached is not None and not reload and not cached.changed_on_disk():
            return cached

        report = self.validator.validate(file_path)
        if not report.valid and self.strict:
            raise FileError(f"invalid test script: {report.summary()}", {"path": key})

        module_name = f"vdp_script_{file_path.stem}_{abs(hash(key)) & 0xFFFF:04x}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise FileError(f"could not import the test script {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - user supplied code
            sys.modules.pop(module_name, None)
            raise FileError(
                f"the test script raised during import: {exc}", {"path": key}
            ) from exc

        script_class = getattr(module, REQUIRED_CLASS, None)
        if script_class is None or not isinstance(script_class, type):
            sys.modules.pop(module_name, None)
            raise FileError(
                f"the script does not define a class named {REQUIRED_CLASS}", {"path": key}
            )

        loaded = LoadedScript(
            path=file_path,
            module=module,
            script_class=script_class,
            report=report,
            mtime=file_path.stat().st_mtime,
        )
        self._cache[key] = loaded
        _logger.info("loaded test script %s", file_path.name)
        return loaded

    def load_source(self, source: str, name: str = "inline") -> LoadedScript:
        """Import a script from a string (used by the inline editor).

        Raises:
            FileError: The source is invalid or has no ``TestScript`` class.
        """
        report = self.validator.validate_source(source, name)
        if not report.valid and self.strict:
            raise FileError(f"invalid test script: {report.summary()}")
        module = ModuleType(f"vdp_inline_{abs(hash(source)) & 0xFFFF:04x}")
        try:
            exec(compile(source, name, "exec"), module.__dict__)  # noqa: S102
        except Exception as exc:  # noqa: BLE001
            raise FileError(f"the inline script raised during import: {exc}") from exc
        script_class = getattr(module, REQUIRED_CLASS, None)
        if not isinstance(script_class, type):
            raise FileError(f"the inline script defines no {REQUIRED_CLASS} class")
        return LoadedScript(Path(name), module, script_class, report)

    def preview(self, path: str | Path, max_lines: int = 40) -> str:
        """Return the first lines of a script for the preview pane."""
        file_path = Path(path).expanduser()
        if not file_path.is_file():
            return ""
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        preview = "\n".join(lines[:max_lines])
        return preview + ("\n..." if len(lines) > max_lines else "")

    def discover(self, directory: str | Path) -> list[Path]:
        """Return every ``.py`` file under *directory*, sorted naturally."""
        from natsort import natsorted  # type: ignore[import-not-found]

        root = Path(directory).expanduser()
        if not root.is_dir():
            return []
        return [Path(p) for p in natsorted(str(p) for p in root.rglob("*.py"))]

    def invalidate(self, path: str | Path | None = None) -> None:
        """Drop one cached script, or the whole cache when *path* is ``None``."""
        if path is None:
            self._cache.clear()
            return
        self._cache.pop(str(Path(path).expanduser().resolve()), None)

    @property
    def cached(self) -> list[str]:
        """Return the paths of the currently cached scripts."""
        return sorted(self._cache)


__all__ = ["TestScriptLoader", "LoadedScript"]
