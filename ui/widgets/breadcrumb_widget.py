"""Breadcrumb showing the active navigation path.

The platform navigates with two rows of tabs: the workspace row of the main
window and the section row inside a workspace.  The breadcrumb turns that
implicit state into one readable line, exactly like the ``TVS Jupiter New >>
EMS-OBDII >> Conti2 Flashing`` header of the reference tester, so the operator
never has to look at two tab bars to know where he is.

Example:
    >>> # crumb = BreadcrumbWidget()
    >>> # crumb.set_path("Diagnostics", "Read DTC")
    >>> None
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole

#: Separator drawn between two breadcrumb segments.
SEPARATOR = "\u203a"


class BreadcrumbWidget(QWidget):
    """A single line ``Workspace › Section`` navigation indicator.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Attributes:
        segments: The path currently displayed, root first.
    """

    #: Emitted with the segment index the operator clicked.
    segment_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the breadcrumb line."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.segments: list[str] = []

        self.label = QLabel("", self)
        self.label.setObjectName("Breadcrumb")
        self.label.setProperty("role", "breadcrumb")
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.detail = QLabel("", self)
        self.detail.setProperty("role", "secondary")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            self.scaler.spacing(2), self.scaler.spacing(2),
            self.scaler.spacing(2), self.scaler.spacing(2),
        )
        layout.setSpacing(self.scaler.spacing(8))
        layout.addWidget(self.label, 1)
        layout.addWidget(self.detail, 0)

    # -- API -----------------------------------------------------------------
    def set_path(self, *segments: str) -> str:
        """Replace the displayed path and return the rendered text.

        Empty segments are dropped so ``set_path("Settings", "")`` renders a
        single crumb instead of a dangling separator.

        Args:
            *segments: Path segments, root first.

        Returns:
            The rendered breadcrumb string.
        """
        self.segments = [s for s in segments if s]
        text = f" {SEPARATOR} ".join(self.segments)
        self.label.setText(text)
        self.label.setToolTip(text)
        return text

    def set_detail(self, text: str) -> None:
        """Show a right aligned hint such as the connected ECU."""
        self.detail.setText(text)

    def text(self) -> str:
        """Return the rendered breadcrumb string."""
        return self.label.text()


__all__ = ["BreadcrumbWidget", "SEPARATOR"]
