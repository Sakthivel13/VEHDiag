"""Auto scaling label with ellipsis and tooltip support."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole


class ScalableLabel(QLabel):
    """A label that scales with the DPI and elides overflowing text.

    Args:
        text: Initial text.
        role: Semantic font role determining the size.
        parent: Parent widget.
        scaler: Shared DPI scaler.
        elide: Elide mode applied when the text does not fit.
    """

    def __init__(
        self,
        text: str = "",
        role: FontRole = FontRole.BODY,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        elide: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
    ) -> None:
        """Create the label and apply the font of *role*."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.role = role
        self.elide_mode = elide
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setProperty("role", "mono" if role is FontRole.MONOSPACE else "body")
        self.apply_role(role)
        self.setText(text)

    # -- text handling ------------------------------------------------------
    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        """Store the full text and display the elided version."""
        self._full_text = text
        self.setToolTip(text if self._needs_elide(text) else "")
        super().setText(self._elided(text))

    def full_text(self) -> str:
        """Return the untruncated text."""
        return self._full_text

    def apply_role(self, role: FontRole, bold: bool = False) -> None:
        """Apply the font of *role* to the label."""
        from ..font_manager import FontManager

        self.role = role
        font = FontManager(self.scaler).qfont(role, bold)
        if font is not None:
            self.setFont(font)

    def apply_scale(self, scaler: DPIScaler) -> None:
        """Re-apply the font after a DPI change."""
        self.scaler = scaler
        self.apply_role(self.role)
        self.setText(self._full_text)

    # -- Qt overrides ----------------------------------------------------------
    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt naming
        """Re-elide the text when the label is resized."""
        super().resizeEvent(event)
        super().setText(self._elided(self._full_text))

    def _elided(self, text: str) -> str:
        """Return *text* shortened to the available width."""
        if not text or self.width() <= 0:
            return text
        metrics = QFontMetrics(self.font())
        return metrics.elidedText(text, self.elide_mode, max(0, self.width() - self.scaler.px(4)))

    def _needs_elide(self, text: str) -> bool:
        """Return ``True`` when *text* does not fit into the label."""
        if not text or self.width() <= 0:
            return False
        return QFontMetrics(self.font()).horizontalAdvance(text) > self.width()


class HeadingLabel(ScalableLabel):
    """A bold heading label."""

    def __init__(
        self,
        text: str = "",
        level: int = 2,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
    ) -> None:
        """Create a heading of the requested *level* (1..3)."""
        role = {1: FontRole.HEADING_1, 2: FontRole.HEADING_2, 3: FontRole.HEADING_3}.get(
            level, FontRole.HEADING_2
        )
        super().__init__(text, role, parent, scaler)
        self.setProperty("role", "heading")
        self.apply_role(role, bold=True)


class MonoLabel(ScalableLabel):
    """A monospace label used for hexadecimal data."""

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
    ) -> None:
        """Create the label with the monospace font."""
        super().__init__(text, FontRole.MONOSPACE, parent, scaler)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)


__all__ = ["ScalableLabel", "HeadingLabel", "MonoLabel"]
