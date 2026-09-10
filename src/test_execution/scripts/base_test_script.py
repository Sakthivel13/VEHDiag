"""Base class and template for user written test scripts."""
from __future__ import annotations

import logging
from typing import Any

from ...core.models.test_sequence_model import TestStatus
from .script_api import DiagnosticAPI

_logger = logging.getLogger(__name__)

#: Template used by the "new script" action of the developer panel.
SCRIPT_TEMPLATE = '''"""Test script executed by the Vehicle Diagnostics Platform."""
from __future__ import annotations


class TestScript:
    """Describe what this test verifies."""

    #: Optional human readable name shown in the results table.
    name = "My test"

    def __init__(self, api):
        """Store the diagnostic API handed in by the runner."""
        self.api = api

    def setup(self):
        """Prepare the ECU (session, security, preconditions)."""
        self.api.change_session(0x03)

    def execute(self):
        """Run the test and return PASS or FAIL."""
        self.api.send_hex("22 F1 90")
        self.api.assert_positive_response()
        self.api.log(f"VIN: {self.api.get_last_response().raw[3:].decode('ascii', 'replace')}")
        return "PASS"

    def teardown(self):
        """Restore the ECU state."""
        self.api.change_session(0x01)
'''


class BaseTestScript:
    """Optional base class user scripts may inherit from.

    Inheriting is not mandatory: the loader accepts any class named
    ``TestScript`` that exposes ``execute``. Inheriting simply provides default
    ``setup``/``teardown`` implementations and a few helpers.
    """

    #: Human readable name shown in the results table.
    name: str = "Test script"
    #: Longer description shown in the script preview.
    description: str = ""
    #: Diagnostic session the script needs; ``None`` means "do not change".
    required_session: int | None = None
    #: Security level the script needs; ``None`` means "no unlock".
    required_security: int | None = None

    def __init__(self, api: DiagnosticAPI) -> None:
        """Store the diagnostic API."""
        self.api = api

    def setup(self) -> None:
        """Enter the required session and unlock security if requested."""
        if self.required_session is not None:
            self.api.change_session(self.required_session)
        if self.required_security is not None:
            self.api.security_unlock(self.required_security)

    def execute(self) -> Any:
        """Run the test; subclasses must override this method.

        Returns:
            ``"PASS"``, ``"FAIL"``, a :class:`TestStatus` or a boolean.
        """
        raise NotImplementedError("a test script must implement execute()")

    def teardown(self) -> None:
        """Clean up after the test; the default does nothing."""

    # -- helpers -------------------------------------------------------------
    def log(self, message: str) -> None:
        """Record a message in the script log."""
        self.api.log(message)

    @staticmethod
    def passed() -> TestStatus:
        """Return the PASS status."""
        return TestStatus.PASS

    @staticmethod
    def failed() -> TestStatus:
        """Return the FAIL status."""
        return TestStatus.FAIL


def normalise_result(value: Any) -> TestStatus:
    """Convert whatever a script returned into a :class:`TestStatus`.

    Example:
        >>> normalise_result(True).value
        'PASS'
        >>> normalise_result("fail").value
        'FAIL'
        >>> normalise_result(None).value
        'PASS'
    """
    if isinstance(value, TestStatus):
        return value
    if value is None or value is True:
        return TestStatus.PASS
    if value is False:
        return TestStatus.FAIL
    text = str(value).strip().upper()
    try:
        return TestStatus(text)
    except ValueError:
        return TestStatus.PASS if text in ("OK", "SUCCESS", "TRUE") else TestStatus.FAIL


__all__ = ["BaseTestScript", "SCRIPT_TEMPLATE", "normalise_result"]
