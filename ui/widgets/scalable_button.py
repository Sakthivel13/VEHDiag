"""Auto scaling button with icon, loading state and accent styling."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QPushButton, QWidget

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole


class ScalableButton(QPushButton):
    """A DPI aware button supporting an icon, an accent style and a spinner.

    Args:
        text: Button caption.
        icon_name: Name of a bundled SVG icon.
        parent: Parent widget.
        scaler: Shared DPI scaler.
        accent: Render the button with the accent colour.
        danger: Render the button with the error colour.
        icon_only: Hide the caption and show only the icon.
    """

    #: Emitted when the loading state changes.
    loading_changed = Signal(bool)

    #: Frames of the textual spinner shown while loading.
    SPINNER_FRAMES = ("|", "/", "-", "\\")

    def __init__(
        self,
        text: str = "",
        icon_name: str = "",
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        accent: bool = False,
        danger: bool = False,
        icon_only: bool = False,
    ) -> None:
        """Create the button and apply the requested styling."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.icon_name = icon_name
        self._caption = text
        self._loading = False
        self._frame = 0
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._advance_spinner)

        if accent:
            self.setProperty("accent", "true")
        if danger:
            self.setProperty("danger", "true")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_icon_only(icon_only)
        self.apply_scale(self.scaler)
        if icon_name:
            self.set_icon(icon_name)
        self.setText("" if icon_only else text)

    # -- appearance ---------------------------------------------------------
    def set_icon(self, name: str, color: str | None = None) -> None:
        """Set the SVG icon shown on the button."""
        from ..icon_manager import IconManager

        self.icon_name = name
        icon = IconManager(self.scaler, color or self.color_hint()).icon(name)
        if icon is not None:
            self.setIcon(icon)
            self.setIconSize(QSize(self.scaler.icon(18), self.scaler.icon(18)))

    def color_hint(self) -> str:
        """Return the icon colour matching the button style and theme.

        A filled button needs the foreground that contrasts with its fill; a
        plain button follows the theme's primary text colour, which is dark on
        the light theme and light on the dark one.
        """
        from ..styles.semantic_colors import active_palette

        palette = active_palette()
        if self.property("accent") == "true":
            return palette.on(palette.primary)
        if self.property("danger") == "true":
            return palette.on(palette.error)
        return palette.text_primary

    def set_icon_only(self, icon_only: bool) -> None:
        """Show only the icon (used in compact layouts)."""
        self._icon_only = icon_only
        if icon_only:
            super().setText("")
            self.setToolTip(self._caption)
            edge = self.scaler.px(34)
            self.setFixedSize(edge, edge)
        else:
            self.setMinimumHeight(self.scaler.px(30))
            self.setMaximumWidth(16777215)
            super().setText(self._caption)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        """Store the caption and honour the icon-only mode."""
        self._caption = text
        if getattr(self, "_icon_only", False):
            self.setToolTip(text)
            super().setText("")
        else:
            super().setText(text)

    def apply_scale(self, scaler: DPIScaler) -> None:
        """Re-apply the font and sizes after a DPI change."""
        from ..font_manager import FontManager

        self.scaler = scaler
        font = FontManager(scaler).qfont(FontRole.BUTTON)
        if font is not None:
            self.setFont(font)
        self.setMinimumHeight(scaler.px(30))
        if self.icon_name:
            self.set_icon(self.icon_name)

    # -- loading state ---------------------------------------------------------
    @property
    def loading(self) -> bool:
        """Return ``True`` while the button shows the spinner."""
        return self._loading

    def set_loading(self, loading: bool) -> None:
        """Enable or disable the loading state."""
        if loading == self._loading:
            return
        self._loading = loading
        self.setEnabled(not loading)
        if loading:
            self._timer.start()
        else:
            self._timer.stop()
            super().setText("" if getattr(self, "_icon_only", False) else self._caption)
        self.loading_changed.emit(loading)

    def _advance_spinner(self) -> None:
        """Show the next spinner frame."""
        self._frame = (self._frame + 1) % len(self.SPINNER_FRAMES)
        frame = self.SPINNER_FRAMES[self._frame]
        super().setText(frame if getattr(self, "_icon_only", False) else f"{frame} {self._caption}")


class RunButton(ScalableButton):
    """A play/stop toggle button used by the developer panel."""

    #: Emitted when the user asks to start execution.
    run_requested = Signal()
    #: Emitted when the user asks to cancel execution.
    cancel_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        label: str = "Run",
    ) -> None:
        """Create the button in the idle (run) state."""
        super().__init__(label, "play", parent, scaler, accent=True)
        self._running = False
        self._idle_label = label
        self.clicked.connect(self._on_clicked)

    @property
    def running(self) -> bool:
        """Return ``True`` while the button is in the cancel state."""
        return self._running

    def set_running(self, running: bool) -> None:
        """Switch between the run and the cancel appearance."""
        self._running = running
        self.setText("Cancel" if running else self._idle_label)
        self.set_icon("cancel" if running else "play")
        self.setProperty("danger", "true" if running else None)
        self.setProperty("accent", None if running else "true")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def _on_clicked(self) -> None:
        """Emit the matching signal for the current state."""
        if self._running:
            self.cancel_requested.emit()
        else:
            self.run_requested.emit()


__all__ = ["ScalableButton", "RunButton"]
