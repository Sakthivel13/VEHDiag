"""Per-step *Run* button of the developer mode grid.

The button owns the run state of a single :class:`TestStep`: it shows a
spinner while the step executes, turns green or red once the result is known
and exposes the F5 shortcut.

Example:
    >>> from ui.panels.developer_panel.run_button_widget import (
    ...     caption_for, tooltip_for, RUN_SHORTCUT)
    >>> RUN_SHORTCUT
    'F5'
    >>> caption_for(False)
    'Run'
    >>> caption_for(True)
    'Running...'
    >>> tooltip_for(enabled=False, reason="Connect first")
    'Connect first'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

from src.core.models.test_sequence_model import TestResult, TestStatus, TestStep

from ...dpi_scaler import DPIScaler
from ...widgets.scalable_button import ScalableButton

__all__ = ["RUN_SHORTCUT", "RunButtonWidget", "caption_for", "tooltip_for"]

#: Keyboard shortcut running the selected step.
RUN_SHORTCUT = "F5"


def caption_for(running: bool) -> str:
    """Return the button caption for the given run state.

    Example:
        >>> caption_for(running=True)
        'Running...'
    """
    return "Running..." if running else "Run"


def tooltip_for(enabled: bool, reason: str = "") -> str:
    """Return the tooltip of the button.

    Args:
        enabled: Whether the button is usable.
        reason: Why the button is disabled.

    Example:
        >>> tooltip_for(True)
        'Run this step (F5)'
    """
    if enabled:
        return f"Run this step ({RUN_SHORTCUT})"
    return reason or "Not available"


class RunButtonWidget(ScalableButton):
    """Runs a single test step and reflects its outcome.

    Args:
        step: The step the button executes.
        parent: Parent widget.
        scaler: Shared DPI scaler.
        with_shortcut: Install the F5 shortcut on the parent window.

    Attributes:
        step: The step bound to the button.
        running: Whether the step is currently executing.
    """

    #: Emitted with the step when the operator presses the button.
    run_requested = Signal(object)

    def __init__(
        self,
        step: TestStep | None = None,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        with_shortcut: bool = False,
    ) -> None:
        """Build the button and optionally install the shortcut."""
        super().__init__(caption_for(False), "play", parent, scaler, accent=True)
        self.step = step
        self.running = False
        self.setToolTip(tooltip_for(True))
        self.clicked.connect(self._on_clicked)
        self._shortcut: QShortcut | None = None
        if with_shortcut and parent is not None:
            self._shortcut = QShortcut(QKeySequence(RUN_SHORTCUT), parent)
            self._shortcut.activated.connect(self._on_clicked)

    # -- API -----------------------------------------------------------------
    def set_step(self, step: TestStep) -> None:
        """Bind the button to *step*."""
        self.step = step
        self.setToolTip(
            f"Run {step.name or f'service 0x{step.service_id:02X}'} ({RUN_SHORTCUT})"
        )

    def set_running(self, running: bool) -> None:
        """Show or hide the loading spinner."""
        self.running = running
        self.setText(caption_for(running))
        self.set_loading(running)

    def set_available(self, enabled: bool, reason: str = "") -> None:
        """Enable or disable the button with an explanatory tooltip."""
        self.setEnabled(enabled and not self.running)
        self.setToolTip(tooltip_for(enabled, reason))

    def apply_result(self, result: TestResult) -> None:
        """Colour the button according to *result* and stop the spinner."""
        self.set_running(False)
        passed = result.status is TestStatus.PASS
        self.setProperty("danger", "true" if not passed else None)
        self.setProperty("accent", "true" if passed else None)
        self.setToolTip(f"{result.status.value}: {result.message or 'no message'}")
        self._repolish()

    def reset(self) -> None:
        """Return the button to its neutral state."""
        self.set_running(False)
        self.setProperty("danger", None)
        self.setProperty("accent", "true")
        self.setToolTip(tooltip_for(True))
        self._repolish()

    # -- internals ------------------------------------------------------------
    def _on_clicked(self) -> None:
        """Emit :attr:`run_requested` for the bound step."""
        if self.step is not None and not self.running:
            self.run_requested.emit(self.step)

    def _repolish(self) -> None:
        """Re-apply the stylesheet after a dynamic property change."""
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
