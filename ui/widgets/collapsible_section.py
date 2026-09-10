"""Collapsible panel with an animated expand/collapse transition."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import Duration, FontRole
from .responsive_widget import ResponsiveWidget


class CollapsibleSection(ResponsiveWidget):
    """A titled container the user can fold away.

    Args:
        title: Header caption.
        parent: Parent widget.
        scaler: Shared DPI scaler.
        expanded: Initial state.
        animated: Animate the transition.

    Example:
        >>> # section = CollapsibleSection("Protocol")
        >>> # section.set_content_layout(my_layout)
        >>> None
    """

    #: Emitted with the new expanded state whenever the section is toggled.
    toggled_state = Signal(bool)

    def __init__(
        self,
        title: str = "",
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        expanded: bool = True,
        animated: bool = True,
    ) -> None:
        """Build the header and the content container."""
        super().__init__(parent, scaler)
        self.animated = animated
        self._expanded = expanded

        self.toggle_button = QToolButton(self)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toggle_button.clicked.connect(self._on_toggled)

        self.header = QWidget(self)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(self.spacing(4))
        header_layout.addWidget(self.toggle_button, 1)

        self.content = QFrame(self)
        self.content.setObjectName("Card")
        self.content.setMaximumHeight(16777215 if expanded else 0)
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(4))
        layout.addWidget(self.header)
        layout.addWidget(self.content)

        self._animation = QPropertyAnimation(self.content, b"maximumHeight", self)
        self._animation.setDuration(Duration.NORMAL if animated else 0)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.apply_font(FontRole.LABEL, bold=True)

    # -- content -------------------------------------------------------------
    def set_content_layout(self, layout: Any) -> None:
        """Install *layout* as the content of the section."""
        existing = self.content.layout()
        if existing is not None:
            QWidget().setLayout(existing)
        self.content.setLayout(layout)
        if self._expanded:
            self.content.setMaximumHeight(16777215)

    def add_widget(self, widget: QWidget) -> None:
        """Append *widget* to the content, creating a layout if needed."""
        layout = self.content.layout()
        if layout is None:
            layout = QVBoxLayout()
            layout.setContentsMargins(
                self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8)
            )
            layout.setSpacing(self.spacing(6))
            self.content.setLayout(layout)
        layout.addWidget(widget)

    def set_title(self, title: str) -> None:
        """Change the header caption."""
        self.toggle_button.setText(title)

    # -- state ----------------------------------------------------------------
    @property
    def expanded(self) -> bool:
        """Return ``True`` when the content is visible."""
        return self._expanded

    def set_expanded(self, expanded: bool, animate: bool | None = None) -> None:
        """Expand or collapse the section."""
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        use_animation = self.animated if animate is None else animate
        target = self.content.sizeHint().height() if expanded else 0
        if use_animation:
            self._animation.stop()
            self._animation.setStartValue(self.content.maximumHeight())
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self.content.setMaximumHeight(16777215 if expanded else 0)
        self.toggled_state.emit(expanded)

    def toggle(self) -> bool:
        """Invert the current state and return the new one."""
        self.set_expanded(not self._expanded)
        return self._expanded

    def _on_toggled(self, checked: bool) -> None:
        """Handle a click on the header button."""
        self.set_expanded(checked)


__all__ = ["CollapsibleSection"]
