"""*Run All* button driving a whole developer mode sequence.

The button reports how many steps will run, shows a progress caption while the
sequence executes and summarises the outcome when it finishes. F6 is the
shortcut required by the specification.

Example:
    >>> from ui.panels.developer_panel.run_all_button import (
    ...     RUN_ALL_SHORTCUT, idle_caption, progress_caption, summary_text)
    >>> RUN_ALL_SHORTCUT
    'F6'
    >>> idle_caption(0)
    'Run All'
    >>> idle_caption(4)
    'Run All (4)'
    >>> progress_caption(2, 5)
    'Running 2/5...'
    >>> summary_text(3, 1, 0)
    '3 passed, 1 failed'
    >>> summary_text(4, 0, 2)
    '4 passed, 2 skipped'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

from src.core.models.test_sequence_model import TestResult, TestSequence, TestStatus

from ...dpi_scaler import DPIScaler
from ...widgets.scalable_button import ScalableButton

__all__ = [
    "RUN_ALL_SHORTCUT",
    "RunAllButton",
    "idle_caption",
    "progress_caption",
    "summary_text",
]

#: Keyboard shortcut running the whole sequence.
RUN_ALL_SHORTCUT = "F6"


def idle_caption(step_count: int) -> str:
    """Return the caption shown while the sequence is not running.

    Example:
        >>> idle_caption(1)
        'Run All (1)'
    """
    return f"Run All ({step_count})" if step_count else "Run All"


def progress_caption(done: int, total: int) -> str:
    """Return the caption shown while the sequence runs.

    Example:
        >>> progress_caption(0, 0)
        'Running...'
    """
    return f"Running {done}/{total}..." if total else "Running..."


def summary_text(passed: int, failed: int, skipped: int = 0) -> str:
    """Return the one line summary of a finished sequence.

    Example:
        >>> summary_text(0, 0, 0)
        'nothing executed'
    """
    parts: list[str] = []
    if passed:
        parts.append(f"{passed} passed")
    if failed:
        parts.append(f"{failed} failed")
    if skipped:
        parts.append(f"{skipped} skipped")
    return ", ".join(parts) if parts else "nothing executed"


class RunAllButton(ScalableButton):
    """Starts the execution of an entire test sequence.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        with_shortcut: Install the F6 shortcut on the parent window.

    Attributes:
        sequence: The sequence bound to the button.
        running: Whether the sequence is currently executing.
    """

    #: Emitted with the sequence when the operator starts the run.
    run_all_requested = Signal(object)
    #: Emitted with the summary text when the run finishes.
    finished = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        with_shortcut: bool = False,
    ) -> None:
        """Build the button and optionally install the shortcut."""
        super().__init__(idle_caption(0), "run_all", parent, scaler, accent=True)
        self.sequence: TestSequence | None = None
        self.running = False
        self.setToolTip(f"Run every enabled step ({RUN_ALL_SHORTCUT})")
        self.clicked.connect(self._on_clicked)
        self._shortcut: QShortcut | None = None
        if with_shortcut and parent is not None:
            self._shortcut = QShortcut(QKeySequence(RUN_ALL_SHORTCUT), parent)
            self._shortcut.activated.connect(self._on_clicked)

    # -- API -----------------------------------------------------------------
    def set_sequence(self, sequence: TestSequence) -> None:
        """Bind the button to *sequence* and refresh the caption."""
        self.sequence = sequence
        self.setText(idle_caption(len(sequence.enabled_steps)))
        self.setEnabled(bool(sequence.enabled_steps) and not self.running)

    def start(self, total: int = 0) -> None:
        """Switch the button into the running state."""
        self.running = True
        self.set_loading(True)
        self.setText(progress_caption(0, total or self._total()))

    def set_progress(self, done: int, total: int = 0) -> None:
        """Update the progress caption."""
        self.setText(progress_caption(done, total or self._total()))

    def finish(self, results: list[TestResult]) -> str:
        """Leave the running state and summarise *results*.

        Returns:
            The summary text that is also emitted through :attr:`finished`.
        """
        self.running = False
        self.set_loading(False)
        passed = sum(1 for r in results if r.status is TestStatus.PASS)
        failed = sum(1 for r in results if r.status is TestStatus.FAIL)
        skipped = sum(1 for r in results if r.status is TestStatus.SKIPPED)
        summary = summary_text(passed, failed, skipped)
        self.setText(idle_caption(self._total()))
        self.setToolTip(summary)
        self.setEnabled(bool(self._total()))
        self.finished.emit(summary)
        return summary

    def cancel(self) -> None:
        """Leave the running state without a summary."""
        self.running = False
        self.set_loading(False)
        self.setText(idle_caption(self._total()))
        self.setEnabled(bool(self._total()))

    def set_available(self, enabled: bool, reason: str = "") -> None:
        """Enable or disable the button with an explanatory tooltip."""
        self.setEnabled(enabled and not self.running and bool(self._total()))
        self.setToolTip(
            reason if not enabled and reason else f"Run every enabled step ({RUN_ALL_SHORTCUT})"
        )

    # -- internals ------------------------------------------------------------
    def _total(self) -> int:
        """Return the number of enabled steps of the bound sequence."""
        return len(self.sequence.enabled_steps) if self.sequence else 0

    def _on_clicked(self) -> None:
        """Emit :attr:`run_all_requested` for the bound sequence."""
        if self.sequence is not None and not self.running:
            self.run_all_requested.emit(self.sequence)
