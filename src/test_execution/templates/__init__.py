"""Ready-made test script templates.

Each module defines a ``TestScript`` class the developer mode can execute
directly; copy one and adapt it to a specific ECU.
"""
from __future__ import annotations

from pathlib import Path

#: Directory holding the template files.
TEMPLATE_DIR = Path(__file__).resolve().parent

#: Human readable names of the bundled templates.
TEMPLATES: dict[str, str] = {
    "session_control_template.py": "Change the diagnostic session",
    "read_did_template.py": "Read data identifiers",
    "read_dtc_template.py": "Read the fault memory",
    "clear_dtc_template.py": "Clear the fault memory",
    "security_access_template.py": "Unlock a security level",
    "flash_template.py": "Complete flash sequence",
    "custom_template.py": "Blank starting point",
}


def template_path(name: str) -> Path:
    """Return the path of a bundled template.

    Example:
        >>> template_path("custom_template.py").name
        'custom_template.py'
    """
    return TEMPLATE_DIR / name


def available_templates() -> list[tuple[str, str, Path]]:
    """Return ``(file name, description, path)`` for every template."""
    return [
        (name, description, TEMPLATE_DIR / name)
        for name, description in TEMPLATES.items()
        if (TEMPLATE_DIR / name).is_file()
    ]


__all__ = ["TEMPLATE_DIR", "TEMPLATES", "template_path", "available_templates"]
