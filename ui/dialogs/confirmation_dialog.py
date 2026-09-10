"""Reusable confirmation dialog."""
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

from ..dpi_scaler import DPIScaler


class ConfirmationDialog(QDialog):
    """Asks the operator to confirm a destructive action.

    Args:
        title: Dialog title.
        message: Question shown to the operator.
        warning: Additional warning line shown in the error colour.
        confirm_text: Caption of the confirm button.
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    def __init__(
        self,
        title: str,
        message: str,
        warning: str = "",
        confirm_text: str = "Confirm",
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
    ) -> None:
        """Build the dialog."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.setWindowTitle(title)
        self.setMinimumWidth(self.scaler.px(420))

        label = QLabel(message, self)
        label.setWordWrap(True)
        self.warning_label = QLabel(warning, self)
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color:#F59E0B;")
        self.warning_label.setVisible(bool(warning))
        self.remember_box = QCheckBox("Do not ask again", self)

        buttons = QDialogButtonBox(self)
        confirm = buttons.addButton(confirm_text, QDialogButtonBox.ButtonRole.AcceptRole)
        confirm.setProperty("danger", "true")
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.scaler.spacing(8))
        layout.addWidget(label)
        layout.addWidget(self.warning_label)
        layout.addWidget(self.remember_box)
        layout.addWidget(buttons)

    @property
    def remember(self) -> bool:
        """Return ``True`` when the operator ticked *do not ask again*."""
        return self.remember_box.isChecked()

    @classmethod
    def ask(
        cls,
        title: str,
        message: str,
        warning: str = "",
        confirm_text: str = "Confirm",
        parent: QWidget | None = None,
    ) -> bool:
        """Show the dialog and return ``True`` when the operator confirmed."""
        dialog = cls(title, message, warning, confirm_text, parent)
        return dialog.exec() == QDialog.DialogCode.Accepted


__all__ = ["ConfirmationDialog"]
