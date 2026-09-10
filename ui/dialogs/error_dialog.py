"""Error dialog with expandable technical details."""
from __future__ import annotations

import traceback
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.exceptions import NegativeResponseError, VDPError

from ..dpi_scaler import DPIScaler


class ErrorDialog(QDialog):
    """Presents an error with a friendly message and the technical details.

    Args:
        title: Dialog title.
        message: Short, user facing description.
        details: Technical details shown when the operator expands the box.
        recovery: Suggested corrective action.
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    def __init__(
        self,
        title: str,
        message: str,
        details: str = "",
        recovery: str = "",
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
    ) -> None:
        """Build the dialog."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.details_text = details
        self.setWindowTitle(title)
        self.setMinimumWidth(self.scaler.px(520))

        heading = QLabel(message, self)
        heading.setWordWrap(True)
        heading.setProperty("role", "heading")

        self.recovery_label = QLabel(recovery, self)
        self.recovery_label.setWordWrap(True)
        self.recovery_label.setProperty("role", "secondary")
        self.recovery_label.setVisible(bool(recovery))

        self.details_view = QPlainTextEdit(details, self)
        self.details_view.setReadOnly(True)
        self.details_view.setProperty("role", "mono")
        self.details_view.setVisible(False)
        self.details_view.setMaximumHeight(self.scaler.px(200))

        self.toggle_button = QPushButton("Show technical details", self)
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self._on_toggle)
        self.toggle_button.setVisible(bool(details))

        self.copy_button = QPushButton("Copy error", self)
        self.copy_button.clicked.connect(self.copy)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        buttons.accepted.connect(self.accept)
        buttons.addButton(self.copy_button, QDialogButtonBox.ButtonRole.ActionRole)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.scaler.spacing(8))
        layout.addWidget(heading)
        layout.addWidget(self.recovery_label)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.details_view)
        layout.addWidget(buttons)

    def copy(self) -> str:
        """Copy the whole error description to the clipboard."""
        text = f"{self.windowTitle()}\n\n{self.details_text}"
        QGuiApplication.clipboard().setText(text)
        return text

    def _on_toggle(self, checked: bool) -> None:
        """Show or hide the technical details."""
        self.details_view.setVisible(checked)
        self.toggle_button.setText(
            "Hide technical details" if checked else "Show technical details"
        )
        self.adjustSize()

    @classmethod
    def from_exception(
        cls,
        error: BaseException,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
    ) -> "ErrorDialog":
        """Build a dialog describing *error*."""
        title = type(error).__name__
        message = str(error)
        recovery = ""
        details = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        if isinstance(error, NegativeResponseError):
            title = "The ECU rejected the request"
            recovery = error.recovery_hint
        elif isinstance(error, VDPError):
            title = type(error).__name__.replace("Error", " error")
            # ``str(VDPError)`` appends the whole details mapping, which is
            # right for a log line but turns the dialog headline into a wall
            # of text. The structured context is shown below instead.
            message = error.message
            if error.details:
                # A driver's "hint" is the one thing the operator can act on,
                # so it belongs in the always-visible recovery field rather
                # than buried in the collapsed details block.
                recovery = str(error.details.get("hint", "") or "")
                details = (
                    "\n".join(f"{k}: {v}" for k, v in error.details.items()) + "\n\n" + details
                )
        return cls(title, message, details, recovery, parent, scaler)


__all__ = ["ErrorDialog"]
