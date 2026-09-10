"""Confirmation step guarding ClearDiagnosticInformation.

Clearing DTCs is destructive and irreversible, so the panel asks the operator
to confirm before the request is sent. This module contains the wording rules
and the modal dialog.

Example:
    >>> from ui.panels.diagnostic_panel.clear_dtc_panel.clear_confirmation import (
    ...     confirmation_text, requires_double_confirmation, warnings_for)
    >>> requires_double_confirmation(0xFFFFFF)
    True
    >>> requires_double_confirmation(0x400000)
    False
    >>> "12" in confirmation_text(0xFFFFFF, 12)
    True
    >>> warnings_for(0xFFFFFF, session=1)[0]
    'The default session may not allow clearing DTCs.'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.enums.session_enums import SessionType
from src.diagnostics.services.dtc_services.clear_dtc import CLEAR_ALL

from ....dpi_scaler import DPIScaler

__all__ = [
    "ClearConfirmationDialog",
    "confirmation_text",
    "requires_double_confirmation",
    "warnings_for",
]


def requires_double_confirmation(mask: int) -> bool:
    """Return ``True`` when the operator must tick an extra checkbox.

    Clearing every code is the only operation that needs the second step.

    Example:
        >>> requires_double_confirmation(0x000000)
        False
    """
    return mask == CLEAR_ALL


def confirmation_text(mask: int, known_count: int = -1) -> str:
    """Return the question shown in the dialog.

    Args:
        mask: The 24-bit group mask that will be sent.
        known_count: Number of DTCs currently known, or ``-1`` when unknown.

    Returns:
        A complete sentence ending with a question mark.

    Example:
        >>> confirmation_text(0x400000)
        'Clear the DTC group 0x400000 from the ECU memory?'
    """
    scope = "every stored DTC" if mask == CLEAR_ALL else f"the DTC group 0x{mask:06X}"
    if known_count >= 0:
        return (
            f"Clear {scope} from the ECU memory? "
            f"{known_count} code(s) are currently reported."
        )
    return f"Clear {scope} from the ECU memory?".replace("Clear every stored DTC", "Clear every stored DTC")


def warnings_for(mask: int, session: int = int(SessionType.EXTENDED_DIAGNOSTIC)) -> list[str]:
    """Return the warnings shown above the confirmation question.

    Args:
        mask: The group mask that will be sent.
        session: The currently active diagnostic session.

    Returns:
        Zero or more warning sentences.

    Example:
        >>> warnings_for(0x400000, session=3)
        ['Clearing DTCs also erases the stored freeze frames.']
    """
    messages: list[str] = []
    if session == int(SessionType.DEFAULT):
        messages.append("The default session may not allow clearing DTCs.")
    messages.append("Clearing DTCs also erases the stored freeze frames.")
    if mask == CLEAR_ALL:
        messages.append("This operation cannot be undone.")
    return messages


class ClearConfirmationDialog(QDialog):
    """Modal dialog asking the operator to confirm a clear operation.

    Args:
        mask: The group mask that will be sent.
        known_count: Number of DTCs currently reported, or ``-1``.
        session: The active diagnostic session.
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Example:
        >>> # dialog = ClearConfirmationDialog(0xFFFFFF, 3)
        >>> # dialog.exec() == QDialog.DialogCode.Accepted
        >>> None
    """

    def __init__(
        self,
        mask: int = CLEAR_ALL,
        known_count: int = -1,
        session: int = int(SessionType.EXTENDED_DIAGNOSTIC),
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
    ) -> None:
        """Build the warning list, the question and the confirmation buttons."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.mask = mask
        self.setWindowTitle("Confirm clearing DTCs")
        self.setModal(True)
        self.setMinimumWidth(self.scaler.px(460))

        question = QLabel(confirmation_text(mask, known_count), self)
        question.setWordWrap(True)
        question.setProperty("role", "heading")

        layout = QVBoxLayout(self)
        layout.setSpacing(self.scaler.spacing(8))
        layout.addWidget(question)
        for message in warnings_for(mask, session):
            warning = QLabel(f"\u2022 {message}", self)
            warning.setWordWrap(True)
            warning.setProperty("role", "secondary")
            layout.addWidget(warning)

        self.acknowledge = QCheckBox("I understand this cannot be undone", self)
        self.acknowledge.setVisible(requires_double_confirmation(mask))
        self.acknowledge.toggled.connect(self._update_ok_state)
        layout.addWidget(self.acknowledge)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("Clear DTCs")
            ok_button.setProperty("danger", "true")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._update_ok_state(self.acknowledge.isChecked())

    # -- API -----------------------------------------------------------------
    def is_confirmed(self) -> bool:
        """Return ``True`` when the dialog may be accepted."""
        return not requires_double_confirmation(self.mask) or self.acknowledge.isChecked()

    def _update_ok_state(self, _checked: bool) -> None:
        """Enable the OK button only when the acknowledgement is satisfied."""
        button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if button is not None:
            button.setEnabled(self.is_confirmed())
