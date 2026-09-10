"""Code Generator panel for developer mode.

Lets the operator assemble a test from form inputs and a reference template,
previews the generated ``TestScript`` live with syntax highlighting, validates
it and saves it straight into the test script directory.

The heavy lifting lives in :mod:`src.test_execution.code_generator`, which is
pure Python; this module is only the Qt surface.

Example:
    >>> from ui.panels.developer_panel.code_generator_panel import STEP_FIELDS
    >>> "read_did" in STEP_FIELDS
    True
    >>> STEP_FIELDS["wait"]
    ('milliseconds',)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.core.enums.session_enums import SessionType
from src.test_execution.code_generator import (
    STEP_KINDS,
    GeneratedStep,
    GeneratorSpec,
    generate_script,
    generate_yaml_sequence,
    validate_spec,
)
from src.test_execution.scripts.script_validator import ScriptValidator
from src.test_execution.templates import TEMPLATES

from ...dpi_scaler import DPIScaler
from ...widgets.hex_input_field import HexInputField
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.scalable_label import HeadingLabel
from .script_editor_panel import PythonHighlighter
from ...styles.layout_helpers import tune_form

__all__ = ["STEP_FIELDS", "CodeGeneratorPanel"]

#: Which editors are relevant for each step kind.
STEP_FIELDS: dict[str, tuple[str, ...]] = {
    "session": ("session",),
    "security": ("level", "algorithm"),
    "read_did": ("did", "expect"),
    "write_did": ("did", "data"),
    "read_dtc": ("status_mask",),
    "clear_dtc": ("group",),
    "routine": ("routine_id", "sub_function", "data"),
    "io_control": ("did", "sub_function", "data"),
    "ecu_reset": ("reset_type",),
    "tester_present": (),
    "raw": ("data",),
    "wait": ("milliseconds",),
    "assert_nrc": ("nrc",),
}


class CodeGeneratorPanel(ResponsiveWidget):
    """Builds a runnable test script from form inputs.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        output_dir: Directory offered when saving the generated script.

    Attributes:
        steps: The steps assembled so far.
        preview: The live source preview.
    """

    #: Emitted with the path after the script was saved.
    script_generated = Signal(str)
    #: Emitted with the source whenever the preview is refreshed.
    preview_changed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        output_dir: str | Path | None = None,
    ) -> None:
        """Build the metadata form, the step editor and the preview."""
        super().__init__(parent, scaler)
        self.steps: list[GeneratedStep] = []
        self.output_dir = Path(output_dir) if output_dir else Path.home()
        self.validator = ScriptValidator(strict=False)

        # -- metadata --------------------------------------------------------
        self.name_field = QLineEdit("Read the VIN", self)
        self.description_field = QLineEdit("", self)
        self.description_field.setPlaceholderText("one line summary for the docstring")
        self.author_field = QLineEdit("", self)
        self.template_box = QComboBox(self)
        self.template_box.addItem("Blank (build from steps)", "")
        for filename, label in TEMPLATES.items():
            self.template_box.addItem(f"{label}", filename)
        self.template_box.currentIndexChanged.connect(self._on_template_selected)

        self.session_box = QComboBox(self)
        self.session_box.addItem("None", 0)
        for session in SessionType:
            self.session_box.addItem(
                f"0x{int(session):02X} {session.name.replace('_', ' ').title()}", int(session)
            )
        self.session_box.setCurrentIndex(3)
        self.security_spin = QSpinBox(self)
        self.security_spin.setRange(0, 0x7F)
        self.security_spin.setPrefix("0x")
        self.security_spin.setDisplayIntegerBase(16)

        self.logging_box = QCheckBox("Emit progress logging", self)
        self.logging_box.setChecked(True)
        self.docstring_box = QCheckBox("Emit docstrings", self)
        self.docstring_box.setChecked(True)
        self.teardown_box = QCheckBox("Return to the default session", self)
        self.teardown_box.setChecked(True)
        self.tester_box = QCheckBox("Keep the session alive", self)
        for widget in (
            self.name_field,
            self.description_field,
            self.author_field,
        ):
            widget.textChanged.connect(self.refresh)
        for widget in (self.session_box,):
            widget.currentIndexChanged.connect(self.refresh)
        self.security_spin.valueChanged.connect(self.refresh)
        for box in (self.logging_box, self.docstring_box, self.teardown_box, self.tester_box):
            box.toggled.connect(self.refresh)

        meta = QGroupBox("Test definition", self)
        meta_form = QFormLayout(meta)
        tune_form(meta_form, self.scaler)
        self._tune_form(meta_form)
        meta_form.addRow("Name:", self.name_field)
        meta_form.addRow("Description:", self.description_field)
        meta_form.addRow("Author:", self.author_field)
        meta_form.addRow("Reference template:", self.template_box)
        meta_form.addRow("Setup session:", self.session_box)
        meta_form.addRow("Setup security level:", self.security_spin)
        meta_form.addRow("", self.logging_box)
        meta_form.addRow("", self.docstring_box)
        meta_form.addRow("", self.teardown_box)
        meta_form.addRow("", self.tester_box)

        # -- step editor -----------------------------------------------------
        self.kind_box = QComboBox(self)
        for kind, label in STEP_KINDS:
            self.kind_box.addItem(label, kind)
        self.kind_box.currentIndexChanged.connect(self._on_kind_changed)

        self.did_field = HexInputField(self, self.scaler, max_bytes=2, placeholder="F1 90")
        self.did_field.set_value(b"\xf1\x90")
        self.data_field = HexInputField(self, self.scaler, placeholder="payload bytes")
        self.expect_field = HexInputField(self, self.scaler, placeholder="expected bytes")
        self.value_spin = QSpinBox(self)
        self.value_spin.setRange(0, 0xFFFFFF)
        self.value_spin.setPrefix("0x")
        self.value_spin.setDisplayIntegerBase(16)
        self.sub_spin = QSpinBox(self)
        self.sub_spin.setRange(0, 0xFF)
        self.sub_spin.setPrefix("0x")
        self.sub_spin.setDisplayIntegerBase(16)
        self.sub_spin.setValue(1)
        self.ms_spin = QSpinBox(self)
        self.ms_spin.setRange(0, 60_000)
        self.ms_spin.setSuffix(" ms")
        self.ms_spin.setValue(100)
        self.algorithm_field = QLineEdit("xor_complement", self)
        self.comment_field = QLineEdit("", self)
        self.comment_field.setPlaceholderText("optional comment")

        self.add_button = ScalableButton("Add step", "add", self, self.scaler, accent=True)
        self.add_button.clicked.connect(self.add_step)
        self.remove_button = ScalableButton("Remove", "remove", self, self.scaler)
        self.remove_button.clicked.connect(self.remove_selected)
        self.up_button = ScalableButton("Up", "chevron_right", self, self.scaler)
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        self.down_button = ScalableButton("Down", "chevron_down", self, self.scaler)
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        self.clear_button = ScalableButton("Clear", "clear", self, self.scaler, danger=True)
        self.clear_button.clicked.connect(self.clear_steps)

        self.step_list = QListWidget(self)
        self.step_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        step_box = QGroupBox("Steps", self)
        step_form = QFormLayout()
        tune_form(step_form, self.scaler)
        self._tune_form(step_form)
        step_form.addRow("Action:", self.kind_box)
        step_form.addRow("Identifier:", self.did_field)
        step_form.addRow("Value:", self.value_spin)
        step_form.addRow("Sub-function:", self.sub_spin)
        step_form.addRow("Data:", self.data_field)
        step_form.addRow("Expect:", self.expect_field)
        step_form.addRow("Algorithm:", self.algorithm_field)
        step_form.addRow("Delay:", self.ms_spin)
        step_form.addRow("Comment:", self.comment_field)
        self._step_form = step_form

        step_buttons = QHBoxLayout()
        step_buttons.setSpacing(self.spacing(4))
        for button in (
            self.add_button,
            self.remove_button,
            self.up_button,
            self.down_button,
        ):
            step_buttons.addWidget(button)
        step_buttons.addStretch(1)
        step_buttons.addWidget(self.clear_button)

        step_layout = QVBoxLayout(step_box)
        step_layout.setSpacing(self.spacing(6))
        step_layout.addLayout(step_form)
        step_layout.addLayout(step_buttons)
        step_layout.addWidget(self.step_list, 1)

        # -- preview ---------------------------------------------------------
        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._apply_mono_font()
        self.highlighter = PythonHighlighter(self.preview.document(), self.color_palette)

        self.status_label = QLabel("", self)
        self.status_label.setProperty("role", "secondary")
        self.status_label.setWordWrap(True)

        self.format_box = QComboBox(self)
        self.format_box.addItem("Python test script", "python")
        self.format_box.addItem("YAML test sequence", "yaml")
        self.format_box.currentIndexChanged.connect(self.refresh)

        self.copy_button = ScalableButton("Copy", "copy", self, self.scaler)
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.save_button = ScalableButton("Save as...", "save", self, self.scaler, accent=True)
        self.save_button.clicked.connect(self.save_dialog)
        self.open_editor_button = ScalableButton("Send to editor", "developer", self, self.scaler)

        preview_buttons = QHBoxLayout()
        preview_buttons.setSpacing(self.spacing(4))
        preview_buttons.addWidget(QLabel("Output:", self))
        preview_buttons.addWidget(self.format_box, 1)
        preview_buttons.addStretch(1)
        preview_buttons.addWidget(self.copy_button)
        preview_buttons.addWidget(self.open_editor_button)
        preview_buttons.addWidget(self.save_button)

        preview_box = QGroupBox("Generated code", self)
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setSpacing(self.spacing(6))
        preview_layout.addLayout(preview_buttons)
        preview_layout.addWidget(self.preview, 1)
        preview_layout.addWidget(self.status_label)

        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(self.spacing(8))
        left_layout.addWidget(meta)
        left_layout.addWidget(step_box, 1)

        # A scroll area guarantees the form never renders below its minimum
        # height; without it Qt silently overlaps the rows on short screens.
        left_scroll = QScrollArea(self)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setWidget(left)
        left_scroll.setMinimumWidth(self.scaler.px(360))

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(left_scroll)
        splitter.addWidget(preview_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(8))
        layout.addWidget(HeadingLabel("Code generator", 2, self, self.scaler))
        layout.addWidget(splitter, 1)

        self._on_kind_changed(0)
        self.refresh()

    def _tune_form(self, form: QFormLayout) -> None:
        """Apply the shared form rhythm to *form*.

        Rows get a comfortable vertical gap and labels are top-aligned so a
        wrapped editor never collides with its caption.
        """
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setHorizontalSpacing(self.spacing(12))
        form.setVerticalSpacing(self.spacing(8))
        form.setContentsMargins(
            self.spacing(4), self.spacing(6), self.spacing(4), self.spacing(4)
        )

    # -- step management -----------------------------------------------------
    def current_kind(self) -> str:
        """Return the step kind selected in the drop-down."""
        return str(self.kind_box.currentData())

    def build_step(self) -> GeneratedStep:
        """Return a :class:`GeneratedStep` from the current editors."""
        kind = self.current_kind()
        raw_did = self.did_field.value()
        step = GeneratedStep(kind=kind, comment=self.comment_field.text().strip())
        step.did = int.from_bytes(raw_did, "big") if raw_did else 0
        step.data = self.data_field.value()
        step.expect = self.expect_field.value()
        step.sub_function = self.sub_spin.value()
        step.milliseconds = self.ms_spin.value()
        step.algorithm = self.algorithm_field.text().strip() or "xor_complement"
        value = self.value_spin.value()
        if kind == "session":
            step.session = value or int(SessionType.EXTENDED_DIAGNOSTIC)
        elif kind == "security":
            step.level = value or 0x01
        elif kind == "read_dtc":
            step.status_mask = value or 0xFF
        elif kind == "clear_dtc":
            step.group = value or 0xFFFFFF
        elif kind == "routine":
            step.routine_id = value or 0x0203
        elif kind == "ecu_reset":
            step.reset_type = value or 0x01
        elif kind == "assert_nrc":
            step.nrc = value or 0x31
        return step

    def add_step(self) -> GeneratedStep:
        """Append the configured step to the list."""
        step = self.build_step()
        self.steps.append(step)
        QListWidgetItem(f"{len(self.steps)}. {step.label()}", self.step_list)
        self.refresh()
        return step

    def remove_selected(self) -> bool:
        """Remove the selected step."""
        row = self.step_list.currentRow()
        if not 0 <= row < len(self.steps):
            return False
        del self.steps[row]
        self._reload_list()
        self.refresh()
        return True

    def move_selected(self, offset: int) -> bool:
        """Move the selected step by *offset* positions."""
        row = self.step_list.currentRow()
        target = row + offset
        if not (0 <= row < len(self.steps) and 0 <= target < len(self.steps)):
            return False
        self.steps[row], self.steps[target] = self.steps[target], self.steps[row]
        self._reload_list()
        self.step_list.setCurrentRow(target)
        self.refresh()
        return True

    def clear_steps(self) -> None:
        """Remove every step."""
        self.steps.clear()
        self.step_list.clear()
        self.refresh()

    # -- generation ----------------------------------------------------------
    def spec(self) -> GeneratorSpec:
        """Return the :class:`GeneratorSpec` described by the form."""
        return GeneratorSpec(
            name=self.name_field.text().strip() or "Generated test",
            description=self.description_field.text().strip(),
            author=self.author_field.text().strip(),
            steps=list(self.steps),
            setup_session=int(self.session_box.currentData() or 0),
            setup_security=self.security_spin.value(),
            teardown_default_session=self.teardown_box.isChecked(),
            tester_present=self.tester_box.isChecked(),
            include_logging=self.logging_box.isChecked(),
            include_docstrings=self.docstring_box.isChecked(),
        )

    def generated_code(self) -> str:
        """Return the code in the selected output format."""
        spec = self.spec()
        if str(self.format_box.currentData()) == "yaml":
            return generate_yaml_sequence(spec)
        return generate_script(spec)

    def refresh(self) -> None:
        """Regenerate the preview and revalidate."""
        spec = self.spec()
        valid, problems = validate_spec(spec)
        code = self.generated_code()
        self.preview.setPlainText(code)
        if not valid:
            self.status_label.setText("; ".join(problems))
            self.status_label.setProperty("state", "warning")
        elif str(self.format_box.currentData()) == "python":
            report = self.validator.validate_source(code, spec.module_name())
            self.status_label.setText(
                f"{report.summary()}  -  {len(code.splitlines())} lines, "
                f"{len(spec.steps)} step(s)"
            )
            self.status_label.setProperty("state", "success" if report.valid else "error")
        else:
            self.status_label.setText(f"{len(spec.steps)} step(s) in the sequence")
            self.status_label.setProperty("state", "success")
        self._repolish(self.status_label)
        self.preview_changed.emit(code)

    def copy_to_clipboard(self) -> str:
        """Copy the generated code to the clipboard."""
        from PySide6.QtWidgets import QApplication

        code = self.generated_code()
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(code)
        return code

    def save(self, path: str | Path) -> Path:
        """Write the generated code to *path*."""
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.generated_code(), encoding="utf-8")
        self.script_generated.emit(str(target))
        self.status_label.setText(f"written to {target}")
        self.status_label.setProperty("state", "success")
        self._repolish(self.status_label)
        return target

    def save_dialog(self) -> Path | None:
        """Ask where to save the generated file and write it."""
        spec = self.spec()
        is_yaml = str(self.format_box.currentData()) == "yaml"
        suggested = self.output_dir / (
            f"{spec.module_name()[:-3]}.yaml" if is_yaml else spec.module_name()
        )
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save the generated file",
            str(suggested),
            "YAML files (*.yaml)" if is_yaml else "Python scripts (*.py)",
        )
        return self.save(selected) if selected else None

    # -- internals ------------------------------------------------------------
    def _reload_list(self) -> None:
        """Rebuild the step list widget from :attr:`steps`."""
        self.step_list.clear()
        for index, step in enumerate(self.steps, start=1):
            QListWidgetItem(f"{index}. {step.label()}", self.step_list)

    def _on_kind_changed(self, _index: int) -> None:
        """Show only the editors relevant for the selected step kind."""
        fields = STEP_FIELDS.get(self.current_kind(), ())
        mapping = {
            "did": self.did_field,
            "data": self.data_field,
            "expect": self.expect_field,
            "algorithm": self.algorithm_field,
            "milliseconds": self.ms_spin,
            "sub_function": self.sub_spin,
        }
        value_fields = {
            "session",
            "level",
            "status_mask",
            "group",
            "routine_id",
            "reset_type",
            "nrc",
        }
        for key, widget in mapping.items():
            self._set_row_visible(widget, key in fields)
        self._set_row_visible(self.value_spin, bool(value_fields & set(fields)))

    def _set_row_visible(self, widget: QWidget, visible: bool) -> None:
        """Show or hide *widget* together with its form label."""
        widget.setVisible(visible)
        label = self._step_form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _on_template_selected(self, _index: int) -> None:
        """Prefill the steps from the chosen reference template."""
        filename = str(self.template_box.currentData() or "")
        presets: dict[str, list[GeneratedStep]] = {
            "session_control_template.py": [GeneratedStep(kind="session", session=0x03)],
            "read_did_template.py": [
                GeneratedStep(kind="read_did", did=0xF190),
                GeneratedStep(kind="read_did", did=0xF18C),
            ],
            "read_dtc_template.py": [GeneratedStep(kind="read_dtc", status_mask=0xFF)],
            "clear_dtc_template.py": [
                GeneratedStep(kind="read_dtc"),
                GeneratedStep(kind="clear_dtc", group=0xFFFFFF),
                GeneratedStep(kind="read_dtc"),
            ],
            "security_access_template.py": [GeneratedStep(kind="security", level=0x01)],
            "flash_template.py": [
                GeneratedStep(kind="session", session=0x02),
                GeneratedStep(kind="security", level=0x11),
                GeneratedStep(kind="routine", routine_id=0xFF00, sub_function=0x01,
                              comment="erase memory"),
            ],
        }
        if filename in presets:
            self.steps = list(presets[filename])
            self._reload_list()
        self.refresh()

    def _apply_mono_font(self) -> None:
        """Apply the monospace font to the preview."""
        from ...font_manager import FontManager
        from ...styles.style_constants import FontRole

        font = FontManager(self.scaler).qfont(FontRole.MONOSPACE)
        if font is not None:
            self.preview.setFont(font)

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        """Re-apply the stylesheet after a dynamic property change."""
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
