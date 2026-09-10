"""Developer mode main panel."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.core.enums.sid_enums import ServiceID
from src.core.models.test_sequence_model import TestResult, TestSequence, TestStep
from src.test_execution.test_sequence_manager import TestSequenceManager

from ...dpi_scaler import DPIScaler
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import RunButton, ScalableButton
from ...widgets.scalable_label import HeadingLabel
from ...widgets.tab_widget_enhanced import EnhancedTabWidget
from .execution_status_panel import ExecutionStatusPanel
from .test_result_panel import TestResultPanel
from .test_sequence_editor import TestSequenceEditor


class DeveloperModePanel(ResponsiveWidget):
    """The complete developer mode workspace.

    It combines the drag and drop sequence editor, the live execution status
    and the results table, plus the toolbar to run, cancel and persist the
    sequence.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted when the operator asks to run the whole sequence.
    run_all_requested = Signal()
    #: Emitted with a single step the operator wants to run.
    run_step_requested = Signal(object)
    #: Emitted when the operator cancels the execution.
    cancel_requested = Signal()
    #: Emitted with the sequence whenever it changes.
    sequence_changed = Signal(object)
    #: Emitted with the path of a script written by the code generator.
    script_generated = Signal(str)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the toolbar, the editor, the status and the results."""
        super().__init__(parent, scaler)
        self.manager = TestSequenceManager()

        self.run_all_button = RunButton(self, self.scaler, "Run all")
        self.run_all_button.run_requested.connect(self.run_all_requested.emit)
        self.run_all_button.cancel_requested.connect(self.cancel_requested.emit)
        self.add_button = ScalableButton("Add service", "add", self, self.scaler)
        self.add_button.clicked.connect(self.add_service)
        self.service_box = QComboBox(self)
        for service in ServiceID:
            self.service_box.addItem(f"0x{int(service):02X} {service.pretty_name}", int(service))
        self.load_button = ScalableButton("Load", "folder_open", self, self.scaler)
        self.load_button.clicked.connect(self.load_sequence_dialog)
        self.save_button = ScalableButton("Save", "save", self, self.scaler)
        self.save_button.clicked.connect(self.save_sequence_dialog)
        self.clear_results_button = ScalableButton("Clear results", "clear", self, self.scaler)
        self.collapse_box = QCheckBox("Collapse cards", self)
        self.stop_on_failure_box = QCheckBox("Stop on failure", self)

        self.editor = TestSequenceEditor(self, self.scaler)
        self.editor.run_requested.connect(self.run_step_requested.emit)
        self.editor.sequence_changed.connect(self.sequence_changed.emit)
        self.collapse_box.toggled.connect(self.editor.collapse_all)

        self.status_panel = ExecutionStatusPanel(self, self.scaler)
        self.result_panel = TestResultPanel(self, self.scaler)
        self.clear_results_button.clicked.connect(self.result_panel.clear)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(6))
        toolbar.addWidget(self.run_all_button)
        toolbar.addWidget(self.service_box)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.load_button)
        toolbar.addWidget(self.save_button)
        toolbar.addWidget(self.clear_results_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.collapse_box)
        toolbar.addWidget(self.stop_on_failure_box)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.addWidget(self.editor)
        bottom = QWidget(self)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(self.spacing(6))
        bottom_layout.addWidget(self.status_panel)
        bottom_layout.addWidget(self.result_panel, 1)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        sequence_page = QWidget(self)
        sequence_layout = QVBoxLayout(sequence_page)
        sequence_layout.setContentsMargins(0, 0, 0, 0)
        sequence_layout.setSpacing(self.spacing(8))
        sequence_layout.addLayout(toolbar)
        sequence_layout.addWidget(splitter, 1)

        from .code_generator_panel import CodeGeneratorPanel
        from .script_editor_panel import ScriptEditorPanel

        self.code_generator = CodeGeneratorPanel(self, self.scaler)
        self.script_editor = ScriptEditorPanel(self, self.scaler)
        self.code_generator.open_editor_button.clicked.connect(self._send_to_editor)
        self.code_generator.script_generated.connect(self.script_generated.emit)

        self.tabs = EnhancedTabWidget(self, self.scaler, level="sub")
        self.tabs.add_panel(sequence_page, "Test sequence", "run_all")
        self.tabs.add_panel(self.code_generator, "Code generator", "developer")
        self.tabs.add_panel(self.script_editor, "Script editor", "file_hex")

        from ...widgets.breadcrumb_widget import BreadcrumbWidget

        self.breadcrumb = BreadcrumbWidget(self, self.scaler)
        self.breadcrumb.set_path("Developer mode", self.tabs.current_title())
        self.tabs.tab_title_activated.connect(
            lambda title: self.breadcrumb.set_path("Developer mode", title)
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.spacing(10), self.spacing(6), self.spacing(10), self.spacing(6)
        )
        layout.setSpacing(self.spacing(4))
        layout.addWidget(self.breadcrumb)
        layout.addWidget(self.tabs, 1)

        self.load_sequence(self.manager.create_default())


    # -- navigation ------------------------------------------------------------
    def sections(self) -> list[str]:
        """Return every section title in tab bar order."""
        return self.tabs.titles()

    def show_view(self, title: str) -> bool:
        """Activate the section tab called *title*."""
        return self.tabs.select_by_title(title)

    def set_compact(self, compact: bool) -> None:
        """Collapse the section tabs to icons on narrow screens."""
        self.tabs.set_compact(compact)

    def _send_to_editor(self) -> None:
        """Move the generated source into the script editor tab."""
        self.script_editor.set_source(self.code_generator.generated_code())
        self.script_editor.validate()
        self.tabs.select_by_title("Script editor")

    # -- sequence -------------------------------------------------------------
    def load_sequence(self, sequence: TestSequence) -> None:
        """Load *sequence* into the editor."""
        self.editor.load_sequence(sequence)
        self.stop_on_failure_box.setChecked(sequence.stop_on_failure)

    def sequence(self) -> TestSequence:
        """Return the sequence currently displayed."""
        self.editor.sequence.stop_on_failure = self.stop_on_failure_box.isChecked()
        return self.editor.sequence

    def add_service(self) -> TestStep:
        """Append a card for the service selected in the drop-down."""
        service_id = int(self.service_box.currentData())
        step = self.manager.add_step(self.editor.sequence, service_id)
        self.editor.load_sequence(self.editor.sequence)
        return step

    def load_sequence_dialog(self) -> Path | None:
        """Ask for a YAML file and load the sequence from it."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load test sequence", str(Path.home()), "YAML files (*.yaml *.yml)"
        )
        if not path:
            return None
        self.load_sequence(self.manager.load(path))
        return Path(path)

    def save_sequence_dialog(self) -> Path | None:
        """Ask for a destination and save the current sequence."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save test sequence",
            str(Path.home() / "test_sequence.yaml"),
            "YAML files (*.yaml *.yml)",
        )
        if not path:
            return None
        return self.manager.save(self.sequence(), path)

    # -- execution feedback ------------------------------------------------------
    def execution_started(self, total_steps: int) -> None:
        """Prepare the panel for a new run."""
        self.run_all_button.set_running(True)
        self.editor.reset_status()
        self.result_panel.clear()
        self.status_panel.start(total_steps)

    def step_started(self, step: TestStep) -> None:
        """Mark *step* as running."""
        self.editor.mark_running(step)
        self.status_panel.step_started(step)

    def step_completed(self, result: TestResult) -> None:
        """Record the result of a finished step."""
        self.editor.apply_result(result)
        self.status_panel.step_completed(result)
        self.result_panel.add_result(result)

    def execution_finished(self, summary: str = "") -> None:
        """Restore the panel after a run."""
        self.run_all_button.set_running(False)
        self.status_panel.finish(summary or self.result_panel.summary().as_text())
        self.result_panel.update_summary()

    def execution_cancelled(self) -> None:
        """Restore the panel after a cancelled run."""
        self.run_all_button.set_running(False)
        self.status_panel.cancelled()


__all__ = ["DeveloperModePanel"]
