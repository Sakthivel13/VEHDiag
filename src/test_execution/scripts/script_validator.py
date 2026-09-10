"""Static validation of user supplied test scripts."""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

_logger = logging.getLogger(__name__)

#: Modules a test script may not import.
FORBIDDEN_IMPORTS: frozenset[str] = frozenset(
    {"os", "sys", "subprocess", "shutil", "socket", "ctypes", "importlib", "builtins"}
)

#: Callables that are refused outright.
FORBIDDEN_CALLS: frozenset[str] = frozenset({"eval", "exec", "compile", "__import__", "open"})

#: The class every script must define.
REQUIRED_CLASS = "TestScript"

#: The method every script must implement.
REQUIRED_METHOD = "execute"


@dataclass(slots=True)
class ValidationReport:
    """Result of validating one script."""

    path: str = ""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    class_name: str = ""
    methods: list[str] = field(default_factory=list)
    docstring: str = ""

    def add_error(self, message: str) -> None:
        """Record an error and mark the script invalid."""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Record a non fatal warning."""
        self.warnings.append(message)

    def summary(self) -> str:
        """Return a one line summary for the UI."""
        if self.valid:
            suffix = f" ({len(self.warnings)} warning(s))" if self.warnings else ""
            return f"script is valid{suffix}"
        return "invalid script: " + "; ".join(self.errors)


class ScriptValidator:
    """Parse a script with :mod:`ast` and check its structure and safety.

    Example:
        >>> import tempfile, pathlib
        >>> code = '''
        ... class TestScript:
        ...     def __init__(self, api): self.api = api
        ...     def execute(self): return "PASS"
        ... '''
        >>> path = pathlib.Path(tempfile.mkstemp(suffix=".py")[1])
        >>> _ = path.write_text(code)
        >>> ScriptValidator().validate(path).valid
        True
    """

    def __init__(self, strict: bool = True) -> None:
        """Create the validator.

        Args:
            strict: Treat forbidden imports and calls as errors rather than
                warnings.
        """
        self.strict = strict

    def validate_source(self, source: str, path: str = "<string>") -> ValidationReport:
        """Validate script *source* without importing it."""
        report = ValidationReport(path=path)
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            report.add_error(f"syntax error on line {exc.lineno}: {exc.msg}")
            return report

        script_class: ast.ClassDef | None = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == REQUIRED_CLASS:
                script_class = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self._check_import(node, report)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALLS:
                    message = f"call to {node.func.id}() is not allowed in a test script"
                    report.add_error(message) if self.strict else report.add_warning(message)

        if script_class is None:
            report.add_error(f"the script must define a class named {REQUIRED_CLASS}")
            return report

        report.class_name = script_class.name
        report.docstring = ast.get_docstring(script_class) or ""
        report.methods = [
            node.name for node in script_class.body if isinstance(node, ast.FunctionDef)
        ]
        if REQUIRED_METHOD not in report.methods:
            report.add_error(f"{REQUIRED_CLASS} must implement {REQUIRED_METHOD}()")
        if "__init__" not in report.methods:
            report.add_warning(f"{REQUIRED_CLASS} has no __init__(self, api) constructor")
        for optional in ("setup", "teardown"):
            if optional not in report.methods:
                report.add_warning(f"{REQUIRED_CLASS} has no {optional}() method")
        return report

    def validate(self, path: str | Path) -> ValidationReport:
        """Validate the script stored at *path*."""
        file_path = Path(path).expanduser()
        if not file_path.is_file():
            report = ValidationReport(path=str(file_path))
            report.add_error(f"file not found: {file_path}")
            return report
        if file_path.suffix != ".py":
            report = ValidationReport(path=str(file_path))
            report.add_error("test scripts must be Python files (.py)")
            return report
        return self.validate_source(
            file_path.read_text(encoding="utf-8", errors="replace"), str(file_path)
        )

    def _check_import(self, node: ast.Import | ast.ImportFrom, report: ValidationReport) -> None:
        """Flag imports of forbidden modules."""
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif node.module:
            names = [node.module.split(".")[0]]
        for name in names:
            if name in FORBIDDEN_IMPORTS:
                message = f"importing {name!r} is not allowed in a test script"
                report.add_error(message) if self.strict else report.add_warning(message)


__all__ = [
    "ScriptValidator",
    "ValidationReport",
    "FORBIDDEN_IMPORTS",
    "FORBIDDEN_CALLS",
    "REQUIRED_CLASS",
]
