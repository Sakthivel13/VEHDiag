"""LED style status indicator."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import state_color
from .responsive_widget import ResponsiveWidget


class LedIndicator(ResponsiveWidget):
    """A small round status light with an optional pulsing animation.

    Args:
        state: Initial semantic state (``idle``, ``running``, ``pass`` ...).
        size: Diameter in design pixels.
        parent: Parent widget.
        scaler: Shared DPI scaler.

    Example:
        >>> # led = LedIndicator("running")
        >>> # led.set_state("pass")
        >>> None
    """

    def __init__(
        self,
        state: str = "idle",
        size: int = 14,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
    ) -> None:
        """Create the indicator in the given state."""
        super().__init__(parent, scaler)
        self._state = state
        self._base_size = size
        self._pulse = 0.0
        self._pulse_up = True
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._advance_pulse)
        self.setFixedSize(self.sizeHint())
        self.setObjectName("LedIndicator")
        self.set_accessible("Status indicator", f"Current state: {state}")

    # -- state ---------------------------------------------------------------
    @property
    def state(self) -> str:
        """Return the current semantic state."""
        return self._state

    def set_state(self, state: str, animate: bool | None = None) -> None:
        """Change the state and optionally start or stop the pulse."""
        self._state = state
        should_animate = animate if animate is not None else state in ("running", "connecting")
        if should_animate and not self._timer.isActive():
            self._timer.start()
        elif not should_animate and self._timer.isActive():
            self._timer.stop()
            self._pulse = 0.0
        self.setToolTip(state.replace("_", " ").title())
        self.set_accessible("Status indicator", f"Current state: {state}")
        self.update()

    @property
    def color(self) -> str:
        """Return the colour matching the current state."""
        return state_color(self._state, self.color_palette)

    # -- painting -------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        """Return the scaled preferred size."""
        edge = self.px(self._base_size)
        return QSize(edge, edge)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        """Return the smallest usable size."""
        return self.sizeHint()

    def paintEvent(self, event: Any) -> None:  # noqa: N802 - Qt naming
        """Draw the LED as a radial gradient with a soft glow."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rectangle = self.rect().adjusted(1, 1, -1, -1)
        base = QColor(self.color)
        glow = QColor(base)
        glow.setAlphaF(0.35 + 0.35 * self._pulse)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(self.rect())

        gradient = QRadialGradient(
            rectangle.center().x() - rectangle.width() * 0.2,
            rectangle.center().y() - rectangle.height() * 0.2,
            rectangle.width(),
        )
        gradient.setColorAt(0.0, base.lighter(150))
        gradient.setColorAt(1.0, base.darker(140))
        painter.setBrush(gradient)
        painter.drawEllipse(rectangle)
        painter.end()

    def on_scale_changed(self, scaler: DPIScaler) -> None:
        """Resize the indicator after a DPI change."""
        self.setFixedSize(self.sizeHint())

    def _advance_pulse(self) -> None:
        """Advance the pulse animation by one step."""
        step = 0.12
        self._pulse += step if self._pulse_up else -step
        if self._pulse >= 1.0:
            self._pulse, self._pulse_up = 1.0, False
        elif self._pulse <= 0.0:
            self._pulse, self._pulse_up = 0.0, True
        self.update()


__all__ = ["LedIndicator"]
