"""Multi-format response viewer showing hex, ASCII and parsed fields."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from src.utils.byte_utils import bytes_to_ascii, bytes_to_hex

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole
from .responsive_widget import ResponsiveWidget


class ResponseDataViewer(ResponsiveWidget):
    """Displays a response as hex, ASCII and decoded fields simultaneously.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        bytes_per_row: Number of bytes shown per hex row.
    """

    #: Emitted with ``(start, length)`` when the user selects bytes.
    selection_changed = Signal(int, int)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        bytes_per_row: int = 16,
    ) -> None:
        """Build the three views."""
        super().__init__(parent, scaler)
        self.bytes_per_row = bytes_per_row
        self._data = b""

        self.header = QLabel("No response", self)
        self.header.setProperty("role", "secondary")
        self.hex_view = QPlainTextEdit(self)
        self.hex_view.setReadOnly(True)
        self.hex_view.setProperty("role", "mono")
        self.hex_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.parsed_view = QPlainTextEdit(self)
        self.parsed_view.setReadOnly(True)
        self.parsed_view.setMaximumHeight(self.px(120))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(4))
        layout.addWidget(self.header)
        layout.addWidget(self.hex_view, 1)
        layout.addWidget(self.parsed_view)
        self._apply_mono_font()

    # -- content -------------------------------------------------------------
    def set_data(self, data: bytes, decoded: str = "", parsed: dict[str, Any] | None = None) -> None:
        """Display *data* with an optional decoded description."""
        self._data = bytes(data)
        self.header.setText(
            f"{len(self._data)} byte(s)" + (f" - {decoded}" if decoded else "")
        )
        self.hex_view.setPlainText(self._render_dump())
        self.parsed_view.setPlainText(self._render_parsed(parsed))

    def data(self) -> bytes:
        """Return the displayed bytes."""
        return self._data

    def clear(self) -> None:
        """Remove the displayed response."""
        self._data = b""
        self.header.setText("No response")
        self.hex_view.clear()
        self.parsed_view.clear()

    # -- rendering -------------------------------------------------------------
    def _render_dump(self) -> str:
        """Return the offset/hex/ASCII dump of the data."""
        if not self._data:
            return ""
        width = self.bytes_per_row
        index_row = "      " + " ".join(f"{i:02d}" for i in range(width))
        lines = [index_row, "      " + "-" * (width * 3 - 1)]
        for offset in range(0, len(self._data), width):
            chunk = self._data[offset : offset + width]
            hex_part = bytes_to_hex(chunk).ljust(width * 3 - 1)
            lines.append(f"{offset:04X}  {hex_part}  {bytes_to_ascii(chunk)}")
        return "\n".join(lines)

    def _render_parsed(self, parsed: dict[str, Any] | None) -> str:
        """Return the parsed field list."""
        if not parsed:
            if not self._data:
                return ""
            return (
                f"ASCII : {bytes_to_ascii(self._data)}\n"
                f"UInt  : {int.from_bytes(self._data[:8], 'big')}\n"
                f"Length: {len(self._data)} bytes"
            )
        width = max((len(key) for key in parsed), default=0)
        return "\n".join(f"{key.ljust(width)} : {value}" for key, value in parsed.items())

    def _apply_mono_font(self) -> None:
        """Apply the monospace font to both text views."""
        from ..font_manager import FontManager

        font = FontManager(self.scaler).qfont(FontRole.MONOSPACE)
        if font is not None:
            self.hex_view.setFont(font)
            self.parsed_view.setFont(font)


__all__ = ["ResponseDataViewer"]
