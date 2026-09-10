"""Embedded editor for developer mode test scripts.

The editor is intentionally small: a monospace text area with Python syntax
highlighting, a validation bar backed by
:class:`~src.test_execution.scripts.script_validator.ScriptValidator` and the
usual open/save/new actions. Scripts follow the template required by the
specification:

.. code-block:: python

    from src.test_execution.scripts.script_api import DiagnosticAPI

    class TestScript:
        def __init__(self, api: DiagnosticAPI):
            self.api = api
        def setup(self): ...
        def execute(self) -> TestResult: ...
        def teardown(self): ...

Example:
    >>> from ui.panels.developer_panel.script_editor_panel import (
    ...     KEYWORDS, default_template, line_of_offset)
    >>> "class TestScript" in default_template(0x22, "Read DID")
    True
    >>> "def execute" in default_template(0x22)
    True
    >>> line_of_offset("a\\nb\\nc", 3)
    2
    >>> "assert" in KEYWORDS
    True
"""
from __future__ import annotations

import keyword
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.enums.sid_enums import SID_DESCRIPTIONS
from src.test_execution.scripts.script_validator import ScriptValidator, ValidationReport

from ...dpi_scaler import DPIScaler
from ...styles.style_constants import DARK_PALETTE, FontRole
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.scalable_label import HeadingLabel

__all__ = [
    "KEYWORDS",
    "PythonHighlighter",
    "ScriptEditorPanel",
    "default_template",
    "line_of_offset",
]

#: Words highlighted as Python keywords.
KEYWORDS: frozenset[str] = frozenset(keyword.kwlist) | {"self", "api"}


def line_of_offset(text: str, offset: int) -> int:
    """Return the 1-based line number containing the character at *offset*.

    Example:
        >>> line_of_offset("abc", 0)
        1
        >>> line_of_offset("a\\nb", 2)
        2
    """
    return text[: max(0, offset)].count("\n") + 1


def default_template(service_id: int = 0x22, name: str = "") -> str:
    """Return the starting point of a new test script.

    Args:
        service_id: The service the script exercises.
        name: Optional human readable service name.

    Returns:
        A complete, valid script source.

    Example:
        >>> "Test script for" in default_template(0x10)
        True
    """
    label = name or SID_DESCRIPTIONS.get(service_id, f"Service 0x{service_id:02X}")
    return f'''"""Test script for {label} (0x{service_id:02X})."""
from src.test_execution.scripts.script_api import DiagnosticAPI


class TestScript:
    """Exercises {label}."""

    def __init__(self, api: DiagnosticAPI):
        """Store the diagnostic API handed in by the runner."""
        self.api = api

    def setup(self):
        """Prepare the ECU: switch the session, unlock security, ..."""
        self.api.change_session(0x03)

    def execute(self):
        """Send the request and assert the response."""
        self.api.log("sending 0x{service_id:02X}")
        self.api.send_request(bytes([0x{service_id:02X}]))
        self.api.assert_positive_response()
        return True

    def teardown(self):
        """Return the ECU to a safe state."""
        self.api.change_session(0x01)
'''


class PythonHighlighter(QSyntaxHighlighter):
    """Minimal Python syntax highlighter for the script editor.

    Args:
        document: The document to highlight.
        palette: Colour palette providing the accent colours.
    """

    def __init__(self, document: QTextDocument, palette: Any = DARK_PALETTE) -> None:
        """Build the highlighting rules."""
        super().__init__(document)
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(palette.primary))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        for word in sorted(KEYWORDS):
            self.rules.append(
                (QRegularExpression(rf"\b{word}\b"), keyword_format)
            )

        string_format = QTextCharFormat()
        string_format.setForeground(QColor(palette.success))
        self.rules.append((QRegularExpression(r"'[^']*'"), string_format))
        self.rules.append((QRegularExpression(r'"[^"]*"'), string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor(palette.secondary))
        self.rules.append((QRegularExpression(r"\b0[xX][0-9a-fA-F]+\b"), number_format))
        self.rules.append((QRegularExpression(r"\b\d+\b"), number_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(palette.text_secondary))
        comment_format.setFontItalic(True)
        self.rules.append((QRegularExpression(r"#[^\n]*"), comment_format))

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt naming
        """Apply every rule to one block of *text*."""
        for expression, char_format in self.rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), char_format)


class ScriptEditorPanel(ResponsiveWidget):
    """Edits, validates and saves a developer mode test script.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        validator: Validator used by :meth:`validate`.

    Attributes:
        editor: The plain text editor holding the source.
        path: The file the source was loaded from, if any.
    """

    #: Emitted with the path after a successful save.
    script_saved = Signal(str)
    #: Emitted with the validation report after every validation.
    validated = Signal(object)
    #: Emitted with the source when the operator asks to run the script.
    run_requested = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        validator: ScriptValidator | None = None,
    ) -> None:
        """Build the editor, the highlighter and the toolbar."""
        super().__init__(parent, scaler)
        self.validator = validator or ScriptValidator(strict=False)
        self.path: Path | None = None
        self.last_directory = str(Path.home())

        self.editor = QPlainTextEdit(self)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.setTabStopDistance(self.scaler.px(32))
        self.editor.setPlaceholderText("# write your test script here")
        self.editor.textChanged.connect(self._on_text_changed)
        self._apply_mono_font()
        self.highlighter = PythonHighlighter(self.editor.document(), self.color_palette)

        self.path_label = QLabel("untitled", self)
        self.path_label.setProperty("role", "secondary")
        self.status_label = QLabel("not validated", self)
        self.status_label.setProperty("role", "secondary")
        self.status_label.setWordWrap(True)

        self.new_button = ScalableButton("New", "add", self, self.scaler)
        self.new_button.clicked.connect(lambda: self.set_source(default_template()))
        self.open_button = ScalableButton("Open", "folder_open", self, self.scaler)
        self.open_button.clicked.connect(self.open_dialog)
        self.save_button = ScalableButton("Save", "save", self, self.scaler, accent=True)
        self.save_button.clicked.connect(self.save)
        self.validate_button = ScalableButton("Validate", "success", self, self.scaler)
        self.validate_button.clicked.connect(self.validate)
        self.run_button = ScalableButton("Run", "play", self, self.scaler)
        self.run_button.clicked.connect(lambda: self.run_requested.emit(self.source()))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(4))
        for button in (
            self.new_button,
            self.open_button,
            self.save_button,
            self.validate_button,
            self.run_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.path_label)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(HeadingLabel("Script editor", 3, self, self.scaler))
        layout.addLayout(toolbar)
        layout.addWidget(self.editor, 1)
        layout.addWidget(self.status_label)

    # -- content -------------------------------------------------------------
    def source(self) -> str:
        """Return the source currently in the editor."""
        return self.editor.toPlainText()

    def set_source(self, source: str, path: str | Path | None = None) -> None:
        """Replace the editor content with *source*."""
        self.editor.setPlainText(source)
        self.path = Path(path).expanduser() if path else None
        self.path_label.setText(str(self.path) if self.path else "untitled")

    def new_script(self, service_id: int = 0x22, name: str = "") -> None:
        """Load the default template for *service_id*."""
        self.set_source(default_template(service_id, name))

    def load(self, path: str | Path) -> Path:
        """Load the script at *path* into the editor."""
        resolved = Path(path).expanduser()
        self.set_source(resolved.read_text(encoding="utf-8"), resolved)
        self.last_directory = str(resolved.parent)
        self.validate()
        return resolved

    def save(self, path: str | Path | None = None) -> Path | None:
        """Write the editor content to *path* or to the current file."""
        target = Path(path).expanduser() if path else self.path
        if target is None:
            return self.save_dialog()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.source(), encoding="utf-8")
        self.path = target
        self.path_label.setText(str(target))
        self.script_saved.emit(str(target))
        return target

    def open_dialog(self) -> Path | None:
        """Ask for a file and load it."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open a test script", self.last_directory, "Python scripts (*.py)"
        )
        return self.load(path) if path else None

    def save_dialog(self) -> Path | None:
        """Ask where to save and write the file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the test script", self.last_directory, "Python scripts (*.py)"
        )
        return self.save(path) if path else None

    # -- validation ----------------------------------------------------------
    def validate(self) -> ValidationReport:
        """Validate the current source and update the status bar."""
        report = self.validator.validate_source(
            self.source(), str(self.path) if self.path else "<editor>"
        )
        self.status_label.setText(report.summary())
        self.status_label.setProperty(
            "state", "success" if report.valid else "error"
        )
        style = self.status_label.style()
        if style is not None:
            style.unpolish(self.status_label)
            style.polish(self.status_label)
        self.validated.emit(report)
        return report

    def is_valid(self) -> bool:
        """Return ``True`` when the current source passes validation."""
        return self.validator.validate_source(self.source()).valid

    def goto_line(self, line: int) -> None:
        """Move the cursor to the 1-based *line*."""
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        for _ in range(max(0, line - 1)):
            cursor.movePosition(cursor.MoveOperation.Down)
        self.editor.setTextCursor(cursor)

    # -- internals ------------------------------------------------------------
    def _apply_mono_font(self) -> None:
        """Apply the monospace font to the editor."""
        from ...font_manager import FontManager

        font = FontManager(self.scaler).qfont(FontRole.MONOSPACE)
        if font is not None:
            self.editor.setFont(font)

    def _on_text_changed(self) -> None:
        """Mark the status as stale after an edit."""
        self.status_label.setText("modified - press Validate")
        self.status_label.setProperty("state", "")
