"""Validated hexadecimal input field."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import QLineEdit, QMenu, QWidget

from src.utils.byte_utils import bytes_to_hex, clean_hex, hex_to_bytes

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole

_logger = logging.getLogger(__name__)


class HexInputField(QLineEdit):
    """A line edit accepting only hexadecimal data.

    Features:

    * rejects every character that is not a hex digit,
    * auto-formats the text with a space after each byte,
    * cleans pasted text,
    * validates a configurable byte count and reflects it through the
      ``valid`` QSS property,
    * offers a context menu to copy the value as hex, decimal or binary.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        min_bytes: Minimum number of bytes for the value to be valid.
        max_bytes: Maximum number of bytes accepted (``0`` = unlimited).
        placeholder: Placeholder text.
    """

    #: Emitted with the parsed bytes whenever the content changes.
    bytes_changed = Signal(bytes)
    #: Emitted with the validity flag whenever it changes.
    validity_changed = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        min_bytes: int = 0,
        max_bytes: int = 0,
        placeholder: str = "e.g. 22 F1 90",
    ) -> None:
        """Create the field."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.min_bytes = min_bytes
        self.max_bytes = max_bytes
        self._valid = True
        self._formatting = False

        self.setPlaceholderText(placeholder)
        self.setProperty("role", "mono")
        self.setClearButtonEnabled(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.textChanged.connect(self._on_text_changed)
        self._apply_font()

    # -- value access -------------------------------------------------------
    def value(self) -> bytes:
        """Return the parsed byte value of the field."""
        try:
            return hex_to_bytes(self.text())
        except ValueError:
            return b""

    def set_value(self, data: bytes) -> None:
        """Set the field content from raw *data*."""
        self.setText(bytes_to_hex(data))

    def byte_count(self) -> int:
        """Return the number of bytes currently entered."""
        return len(self.value())

    @property
    def is_valid(self) -> bool:
        """Return ``True`` when the content satisfies the length bounds."""
        return self._valid

    def clear_value(self) -> None:
        """Empty the field."""
        self.clear()

    # -- input handling --------------------------------------------------------
    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt naming
        """Filter out characters that are not hexadecimal."""
        text = event.text()
        if text and text not in " " and not text.isspace():
            if text.upper() not in "0123456789ABCDEF" and not event.matches(QKeySequence.StandardKey.Paste):
                control_keys = (
                    Qt.Key.Key_Backspace,
                    Qt.Key.Key_Delete,
                    Qt.Key.Key_Left,
                    Qt.Key.Key_Right,
                    Qt.Key.Key_Home,
                    Qt.Key.Key_End,
                    Qt.Key.Key_Tab,
                )
                if event.key() not in control_keys and not (
                    event.modifiers() & Qt.KeyboardModifier.ControlModifier
                ):
                    return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source: Any) -> None:  # noqa: N802 - Qt naming
        """Clean pasted text before inserting it."""
        if source.hasText():
            self.insert(clean_hex(source.text()).upper())
            return
        super().insertFromMimeData(source)

    def _on_text_changed(self, text: str) -> None:
        """Reformat the text, validate it and emit the signals."""
        if self._formatting:
            return
        cleaned = clean_hex(text).upper()
        if self.max_bytes:
            cleaned = cleaned[: self.max_bytes * 2]
        formatted = " ".join(cleaned[i : i + 2] for i in range(0, len(cleaned), 2))
        if formatted != text:
            self._formatting = True
            position = self.cursorPosition() + (len(formatted) - len(text))
            self.setText(formatted)
            self.setCursorPosition(max(0, min(position, len(formatted))))
            self._formatting = False

        data = hex_to_bytes(formatted)
        valid = True
        if self.min_bytes and len(data) < self.min_bytes:
            valid = False
        if self.max_bytes and len(data) > self.max_bytes:
            valid = False
        if valid != self._valid:
            self._valid = valid
            self.setProperty("valid", "true" if valid else "false")
            style = self.style()
            if style is not None:
                style.unpolish(self)
                style.polish(self)
            self.validity_changed.emit(valid)
        self.setToolTip(f"{len(data)} byte(s)")
        self.bytes_changed.emit(data)

    # -- context menu ------------------------------------------------------------
    def _show_context_menu(self, position: Any) -> None:
        """Show the copy-as context menu."""
        menu = QMenu(self)
        data = self.value()
        menu.addAction(self._copy_action("Copy as hex", bytes_to_hex(data)))
        menu.addAction(
            self._copy_action("Copy as decimal", str(int.from_bytes(data, "big")) if data else "0")
        )
        menu.addAction(
            self._copy_action("Copy as binary", " ".join(f"{b:08b}" for b in data))
        )
        menu.addAction(
            self._copy_action(
                "Copy as ASCII", "".join(chr(b) if 32 <= b < 127 else "." for b in data)
            )
        )
        menu.addSeparator()
        paste = QAction("Paste (cleaned)", self)
        paste.triggered.connect(
            lambda: self.setText(clean_hex(QGuiApplication.clipboard().text()).upper())
        )
        menu.addAction(paste)
        clear = QAction("Clear", self)
        clear.triggered.connect(self.clear)
        menu.addAction(clear)
        menu.exec(self.mapToGlobal(position))

    def _copy_action(self, label: str, value: str) -> QAction:
        """Return an action copying *value* to the clipboard."""
        action = QAction(label, self)
        action.triggered.connect(lambda: QGuiApplication.clipboard().setText(value))
        return action

    def _apply_font(self) -> None:
        """Apply the monospace font used for hexadecimal data."""
        from ..font_manager import FontManager

        font = FontManager(self.scaler).qfont(FontRole.MONOSPACE)
        if font is not None:
            self.setFont(font)


__all__ = ["HexInputField"]
