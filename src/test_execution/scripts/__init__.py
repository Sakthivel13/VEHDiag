"""Test script infrastructure."""
from __future__ import annotations

from .base_test_script import SCRIPT_TEMPLATE, BaseTestScript, normalise_result
from .script_api import AssertionFailure, DiagnosticAPI, ScriptContext
from .script_validator import ScriptValidator, ValidationReport

__all__ = [
    "AssertionFailure",
    "BaseTestScript",
    "DiagnosticAPI",
    "SCRIPT_TEMPLATE",
    "ScriptContext",
    "ScriptValidator",
    "ValidationReport",
    "normalise_result",
]
