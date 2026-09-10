"""Abstract test runner interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models.test_sequence_model import TestResult, TestSequence, TestStatus, TestStep


class ITestRunner(ABC):
    """Contract implemented by the developer-mode execution engines."""

    @abstractmethod
    def load_sequence(self, sequence: TestSequence) -> None:
        """Load the sequence that :meth:`execute_all` will run."""

    @abstractmethod
    def load_script(self, path: str) -> Any:
        """Import a Python test script and return its ``TestScript`` class.

        Raises:
            FileError: The script is missing or fails structural validation.
        """

    @abstractmethod
    def execute_step(self, step: TestStep) -> TestResult:
        """Run a single *step* and return its result."""

    @abstractmethod
    def execute_all(self) -> list[TestResult]:
        """Run every enabled step of the loaded sequence in order."""

    @abstractmethod
    def cancel(self) -> None:
        """Request a graceful stop of the running execution."""

    @abstractmethod
    def get_status(self) -> TestStatus:
        """Return the status of the currently executing step."""

    @abstractmethod
    def get_results(self) -> list[TestResult]:
        """Return all results collected so far."""


__all__ = ["ITestRunner"]
