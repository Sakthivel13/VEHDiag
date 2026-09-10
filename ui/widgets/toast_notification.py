"""Toast notifications sliding in from the corner of the window."""
from __future__ import annotations

from enum import Enum
from typing import Any

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import DARK_PALETTE, ColorPalette, Duration


class ToastType(str, Enum):
    """Severity of a toast notification."""

    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"

    def color(self, palette: ColorPalette = DARK_PALETTE) -> str:
        """Return the accent colour of this severity."""
        return {
            ToastType.INFO: palette.info,
            ToastType.SUCCESS: palette.success,
            ToastType.WARNING: palette.warning,
            ToastType.ERROR: palette.error,
        }[self]

    @property
    def icon_name(self) -> str:
        """Return the bundled icon name for this severity."""
        return {
            ToastType.INFO: "info",
            ToastType.SUCCESS: "success",
            ToastType.WARNING: "warning",
            ToastType.ERROR: "error",
        }[self]


class Toast(QFrame):
    """A single notification card."""

    #: Emitted when the toast is dismissed.
    dismissed = Signal()

    def __init__(
        self,
        message: str,
        toast_type: ToastType = ToastType.INFO,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        timeout_ms: int = Duration.TOAST,
        title: str = "",
    ) -> None:
        """Build the toast card."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.toast_type = toast_type
        self.setObjectName("Toast")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        margin = self.scaler.px(10)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(self.scaler.px(8))

        accent = QFrame(self)
        accent.setFixedWidth(self.scaler.px(4))
        accent.setStyleSheet(f"background:{toast_type.color()};border-radius:{self.scaler.px(2)}px;")
        layout.addWidget(accent)

        text_container = QVBoxLayout()
        text_container.setSpacing(self.scaler.px(2))
        if title:
            heading = QLabel(title, self)
            heading.setStyleSheet(f"font-weight:600;color:{toast_type.color()};")
            text_container.addWidget(heading)
        self.label = QLabel(message, self)
        self.label.setWordWrap(True)
        text_container.addWidget(self.label)
        layout.addLayout(text_container, 1)

        self.close_button = QPushButton("x", self)
        self.close_button.setFixedSize(self.scaler.px(22), self.scaler.px(22))
        self.close_button.clicked.connect(self.dismiss)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)

        self.setMinimumWidth(self.scaler.px(280))
        self.setMaximumWidth(self.scaler.px(420))

        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, self.dismiss)

    def dismiss(self) -> None:
        """Hide and delete the toast."""
        self.dismissed.emit()
        self.hide()
        self.deleteLater()


class ToastManager:
    """Stacks toasts in the corner of a parent window.

    Args:
        parent: Window the toasts are shown on.
        scaler: Shared DPI scaler.
        corner: Corner to stack in (``top_right`` or ``bottom_right``).
        max_visible: Maximum number of simultaneously visible toasts.
    """

    def __init__(
        self,
        parent: QWidget,
        scaler: DPIScaler | None = None,
        corner: str = "bottom_right",
        max_visible: int = 4,
    ) -> None:
        """Create the manager bound to *parent*."""
        self.parent = parent
        self.scaler = scaler or DPIScaler()
        self.corner = corner
        self.max_visible = max_visible
        self._toasts: list[Toast] = []

    def show(
        self,
        message: str,
        toast_type: ToastType | str = ToastType.INFO,
        title: str = "",
        timeout_ms: int = Duration.TOAST,
    ) -> Toast:
        """Display a new toast and return it."""
        kind = ToastType(toast_type) if not isinstance(toast_type, ToastType) else toast_type
        toast = Toast(message, kind, self.parent, self.scaler, timeout_ms, title)
        toast.dismissed.connect(lambda: self._remove(toast))
        self._toasts.append(toast)
        while len(self._toasts) > self.max_visible:
            self._toasts[0].dismiss()
        toast.show()
        toast.adjustSize()
        self._reposition()
        self._animate_in(toast)
        return toast

    def info(self, message: str, title: str = "") -> Toast:
        """Show an informational toast."""
        return self.show(message, ToastType.INFO, title)

    def success(self, message: str, title: str = "") -> Toast:
        """Show a success toast."""
        return self.show(message, ToastType.SUCCESS, title)

    def warning(self, message: str, title: str = "") -> Toast:
        """Show a warning toast."""
        return self.show(message, ToastType.WARNING, title)

    def error(self, message: str, title: str = "") -> Toast:
        """Show an error toast."""
        return self.show(message, ToastType.ERROR, title, timeout_ms=8000)

    def clear(self) -> None:
        """Dismiss every visible toast."""
        for toast in list(self._toasts):
            toast.dismiss()

    def _remove(self, toast: Toast) -> None:
        """Forget a dismissed toast and restack the rest."""
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._reposition()

    def _reposition(self) -> None:
        """Stack the visible toasts in the configured corner."""
        margin = self.scaler.px(16)
        gap = self.scaler.px(8)
        offset = margin
        toasts = self._toasts if self.corner.startswith("bottom") else list(reversed(self._toasts))
        for toast in toasts:
            width, height = toast.width(), toast.height()
            x = self.parent.width() - width - margin
            y = (
                self.parent.height() - height - offset
                if self.corner.startswith("bottom")
                else offset
            )
            toast.move(x, y)
            offset += height + gap

    def _animate_in(self, toast: Toast) -> None:
        """Slide the toast in from the right edge."""
        end = toast.pos()
        start = QPoint(self.parent.width(), end.y())
        animation = QPropertyAnimation(toast, b"pos", toast)
        animation.setDuration(Duration.NORMAL)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


__all__ = ["Toast", "ToastManager", "ToastType"]
