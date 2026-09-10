"""Configuration assets shipped with the platform.

This package contains no code; it exposes the directory that holds the YAML
documents and QSS themes so they can be located after installation.
"""
from __future__ import annotations

from pathlib import Path

#: Absolute path of the directory containing the shipped configuration files.
CONFIG_DIR = Path(__file__).resolve().parent

#: Sub-directory holding the VCI hardware profiles.
VCI_PROFILE_DIR = CONFIG_DIR / "vci_profiles"

#: Sub-directory holding the diagnostic session templates.
SESSION_TEMPLATE_DIR = CONFIG_DIR / "session_templates"

#: Sub-directory holding the QSS themes.
THEME_DIR = CONFIG_DIR / "themes"

__all__ = ["CONFIG_DIR", "VCI_PROFILE_DIR", "SESSION_TEMPLATE_DIR", "THEME_DIR"]
