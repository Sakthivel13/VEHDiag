"""Drag and drop editor for the ECU flashing sequence.

The operator builds the sequence by dragging steps from a categorised palette
into an ordered list, reorders them by dragging within the list, enables or
disables individual steps and picks the flash and security files. Validation
runs continuously so *Start flash* is only enabled when the sequence can
actually run.

Example:
    >>> from ui.panels.diagnostic_panel.transfer_panel.flash_sequence_editor import (
    ...     STEP_MIME, step_summary)
    >>> STEP_MIME
    'application/x-vdp-flash-step'
    >>> from src.diagnostics.flash_sequence import FlashStep, FlashStepKind
    >>> step_summary(FlashStep(kind=FlashStepKind.READ_VIN), 0)
    '1. Read VIN'
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.diagnostics.flash_sequence import (
    CATEGORY_ORDER,
    FlashSequence,
    FlashStep,
    FlashStepKind,
    StepStatus,
    palette_steps,
)

from ....dpi_scaler import DPIScaler
from ....styles.layout_helpers import tune_form
from ....styles.semantic_colors import semantic
from ....widgets.file_browser_widget import FileBrowserWidget
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton
from ....widgets.scalable_label import HeadingLabel

__all__ = ["STEP_MIME", "FlashSequenceEditor", "StepListWidget", "step_summary"]

#: MIME type carrying a step kind while it is dragged.
STEP_MIME = "application/x-vdp-flash-step"

#: Glyph shown for each execution state.
_STATUS_GLYPH: dict[StepStatus, str] = {
    StepStatus.PENDING: "\u25cb",
    StepStatus.RUNNING: "\u25b6",
    StepStatus.PASSED: "\u2713",
    StepStatus.FAILED: "\u2717",
    StepStatus.SKIPPED: "\u2013",
}


def step_summary(step: FlashStep, index: int) -> str:
    """Return the label shown for *step* at position *index*.

    Example:
        >>> from src.diagnostics.flash_sequence import FlashStep, FlashStepKind
        >>> step = FlashStep(kind=FlashStepKind.ERASE_MEMORY)
        >>> step_summary(step, 4)
        '5. Erase memory'
        >>> step.enabled = False
        >>> step_summary(step, 0)
        '1. Erase memory  (disabled)'
    """
    suffix = "" if step.enabled else "  (disabled)"
    return f"{index + 1}. {step.label}{suffix}"


class StepListWidget(QListWidget):
    """The ordered step list, accepting drops from the palette and itself.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the kind dropped in from the palette and the target row.
    step_dropped = Signal(object, int)
    #: Emitted with ``(from_row, to_row)`` when a step is reordered.
    step_moved = Signal(int, int)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Configure the list for internal and external drops."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setAlternatingRowColors(True)
        self.setSpacing(self.scaler.px(1))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt naming
        """Accept palette drags and internal moves."""
        if event.mimeData().hasFormat(STEP_MIME) or event.source() is self:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802 - Qt naming
        """Keep accepting while the pointer moves over the list."""
        if event.mimeData().hasFormat(STEP_MIME) or event.source() is self:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt naming
        """Insert a palette step or reorder an existing one."""
        row = self._row_at(event)
        if event.mimeData().hasFormat(STEP_MIME):
            raw = bytes(event.mimeData().data(STEP_MIME)).decode("utf-8")
            try:
                kind = FlashStepKind(raw)
            except ValueError:
                event.ignore()
                return
            event.acceptProposedAction()
            self.step_dropped.emit(kind, row)
            return
        if event.source() is self:
            source = self.currentRow()
            event.acceptProposedAction()
            if source >= 0 and source != row:
                self.step_moved.emit(source, min(row, self.count() - 1))
            return
        super().dropEvent(event)

    def _row_at(self, event: QDropEvent) -> int:
        """Return the row the drop position corresponds to."""
        position = event.position().toPoint()
        item = self.itemAt(position)
        if item is None:
            return self.count()
        row = self.row(item)
        rect = self.visualItemRect(item)
        return row + 1 if position.y() > rect.center().y() else row


class _PaletteTree(QTreeWidget):
    """The categorised palette the operator drags steps from."""

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Populate the tree from :func:`palette_steps`."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        groups = palette_steps()
        for category in CATEGORY_ORDER:
            kinds = groups.get(category)
            if not kinds:
                continue
            parent_item = QTreeWidgetItem(self, [category])
            parent_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = parent_item.font(0)
            font.setBold(True)
            parent_item.setFont(0, font)
            for kind in kinds:
                child = QTreeWidgetItem(parent_item, [kind.label])
                child.setData(0, Qt.ItemDataRole.UserRole, kind.value)
                child.setToolTip(0, kind.detail)
            parent_item.setExpanded(True)

    def startDrag(self, actions: Any) -> None:  # noqa: N802 - Qt naming
        """Carry the step kind in the drag payload."""
        item = self.currentItem()
        if item is None:
            return
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if not value:
            return
        payload = QMimeData()
        payload.setData(STEP_MIME, str(value).encode("utf-8"))
        payload.setText(item.text(0))
        drag = QDrag(self)
        drag.setMimeData(payload)
        drag.exec(Qt.DropAction.CopyAction)


class FlashSequenceEditor(ResponsiveWidget):
    """Builds and validates a flashing sequence.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        sequence: Sequence to edit; the default 13 steps when omitted.

    Attributes:
        sequence: The sequence being edited.
        step_list: The ordered step list.
    """

    #: Emitted with the sequence whenever it changes.
    sequence_changed = Signal(object)
    #: Emitted with the sequence when the operator presses *Start flash*.
    start_requested = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        sequence: FlashSequence | None = None,
    ) -> None:
        """Build the palette, the step list and the file selectors."""
        super().__init__(parent, scaler)
        self.sequence = sequence or FlashSequence.default()

        # -- files -----------------------------------------------------------
        self.flash_file = FileBrowserWidget(
            self,
            self.scaler,
            caption="Select the flash file",
            name_filter=(
                "Firmware (*.hex *.ihex *.ihx *.mot *.srec *.s19 *.s28 *.s37 *.bin *.raw "
                "*.elf *.axf);;Intel HEX (*.hex *.ihex *.ihx);;"
                "Motorola S-record (*.mot *.srec *.s19 *.s28 *.s37);;"
                "Raw binary (*.bin *.raw);;ELF (*.elf *.axf);;All files (*)"
            ),
        )
        self.flash_file.path_changed.connect(self._on_flash_file)
        self.security_file = FileBrowserWidget(
            self,
            self.scaler,
            caption="Select the seed-key implementation",
            name_filter="Seed-key (*.py *.dll *.so *.dylib);;All files (*)",
        )
        self.security_file.path_changed.connect(self._on_security_file)

        self.level_spin = QSpinBox(self)
        self.level_spin.setRange(0x01, 0x7F)
        self.level_spin.setPrefix("0x")
        self.level_spin.setDisplayIntegerBase(16)
        self.level_spin.setValue(self.sequence.security_level)
        self.level_spin.valueChanged.connect(self._on_options_changed)

        self.block_spin = QSpinBox(self)
        self.block_spin.setRange(0, 0xFFFF)
        self.block_spin.setSpecialValueText("ECU default")
        self.block_spin.setSuffix(" bytes")
        self.block_spin.setValue(self.sequence.block_size)
        self.block_spin.valueChanged.connect(self._on_options_changed)

        files_box = QGroupBox("Files and options", self)
        files_form = QFormLayout(files_box)
        tune_form(files_form, self.scaler)
        files_form.addRow("Flash file:", self.flash_file)
        files_form.addRow("Security file:", self.security_file)
        files_form.addRow("Security level:", self.level_spin)
        files_form.addRow("Block size:", self.block_spin)

        # -- palette ----------------------------------------------------------
        self.palette_tree = _PaletteTree(self, self.scaler)
        palette_box = QGroupBox("Available steps", self)
        palette_layout = QVBoxLayout(palette_box)
        hint = QLabel("Drag a step into the sequence", self)
        hint.setProperty("role", "secondary")
        palette_layout.addWidget(hint)
        palette_layout.addWidget(self.palette_tree, 1)

        # -- sequence ---------------------------------------------------------
        self.step_list = StepListWidget(self, self.scaler)
        self.step_list.step_dropped.connect(self._on_step_dropped)
        self.step_list.step_moved.connect(self._on_step_moved)
        self.step_list.itemSelectionChanged.connect(self._on_selection)
        self.step_list.itemDoubleClicked.connect(lambda _i: self.toggle_selected())

        self.up_button = ScalableButton("Up", "chevron_right", self, self.scaler)
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        self.down_button = ScalableButton("Down", "chevron_down", self, self.scaler)
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        self.toggle_button = ScalableButton("Enable / disable", "success", self, self.scaler)
        self.toggle_button.clicked.connect(self.toggle_selected)
        self.remove_button = ScalableButton("Remove", "remove", self, self.scaler)
        self.remove_button.clicked.connect(self.remove_selected)
        self.reset_button = ScalableButton("Restore default", "refresh", self, self.scaler)
        self.reset_button.clicked.connect(self.restore_default)
        self.load_button = ScalableButton("Load", "folder_open", self, self.scaler)
        self.load_button.clicked.connect(self.load_dialog)
        self.save_button = ScalableButton("Save", "save", self, self.scaler)
        self.save_button.clicked.connect(self.save_dialog)

        tools = QHBoxLayout()
        tools.setSpacing(self.spacing(4))
        for button in (self.up_button, self.down_button, self.toggle_button, self.remove_button):
            tools.addWidget(button)
        tools.addStretch(1)
        tools.addWidget(self.reset_button)
        tools.addWidget(self.load_button)
        tools.addWidget(self.save_button)

        sequence_box = QGroupBox("Flash sequence", self)
        sequence_layout = QVBoxLayout(sequence_box)
        sequence_layout.setSpacing(self.spacing(6))
        sequence_layout.addLayout(tools)
        sequence_layout.addWidget(self.step_list, 1)

        # -- status -----------------------------------------------------------
        self.status_label = QLabel("", self)
        self.status_label.setWordWrap(True)
        self.start_button = ScalableButton(
            "Start flash", "flash", self, self.scaler, accent=True
        )
        self.start_button.clicked.connect(self._on_start)

        footer = QHBoxLayout()
        footer.setSpacing(self.spacing(8))
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.start_button)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(palette_box)
        splitter.addWidget(sequence_box)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.spacing(8))
        layout.addWidget(HeadingLabel("Flashing sequence", 3, self, self.scaler))
        layout.addWidget(files_box)
        layout.addWidget(splitter, 1)
        layout.addLayout(footer)

        self.reload()

    # -- editing -------------------------------------------------------------
    def reload(self) -> None:
        """Rebuild the list widget from :attr:`sequence` and revalidate."""
        selected = self.step_list.currentRow()
        self.step_list.clear()
        for index, step in enumerate(self.sequence.steps):
            item = QListWidgetItem(
                f"{_STATUS_GLYPH[step.status]}  {step_summary(step, index)}", self.step_list
            )
            item.setToolTip(f"{step.kind.detail}\n{step.message}".strip())
            if not step.enabled:
                item.setForeground(_color("muted"))
            elif step.status is StepStatus.PASSED:
                item.setForeground(_color("success"))
            elif step.status is StepStatus.FAILED:
                item.setForeground(_color("error"))
            elif step.status is StepStatus.RUNNING:
                item.setForeground(_color("running"))
        if 0 <= selected < self.step_list.count():
            self.step_list.setCurrentRow(selected)
        self.validate()
        self.sequence_changed.emit(self.sequence)

    def move_selected(self, offset: int) -> bool:
        """Move the selected step by *offset* rows."""
        row = self.step_list.currentRow()
        if self.sequence.move(row, row + offset):
            self.reload()
            self.step_list.setCurrentRow(row + offset)
            return True
        return False

    def toggle_selected(self) -> bool:
        """Enable or disable the selected step."""
        row = self.step_list.currentRow()
        if not 0 <= row < len(self.sequence.steps):
            return False
        step = self.sequence.steps[row]
        step.enabled = not step.enabled
        self.reload()
        return step.enabled

    def remove_selected(self) -> bool:
        """Remove the selected step."""
        if self.sequence.remove(self.step_list.currentRow()):
            self.reload()
            return True
        return False

    def restore_default(self) -> None:
        """Replace the sequence with the 13 specification steps."""
        self.sequence = FlashSequence.default(
            flash_file=self.sequence.flash_file,
            security_file=self.sequence.security_file,
            security_level=self.sequence.security_level,
            security_algorithm=self.sequence.security_algorithm,
            block_size=self.sequence.block_size,
        )
        self.reload()

    # -- validation ----------------------------------------------------------
    def validate(self) -> list[str]:
        """Refresh the status line and the *Start flash* button."""
        problems = self.sequence.validate()
        enabled = len(self.sequence.enabled_steps)
        if problems:
            self.status_label.setText("  \u2022  ".join(problems))
            self.status_label.setProperty("state", "error")
        else:
            self.status_label.setText(f"{enabled} step(s) ready to run")
            self.status_label.setProperty("state", "success")
        self.start_button.setEnabled(not problems and enabled > 0)
        style = self.status_label.style()
        if style is not None:
            style.unpolish(self.status_label)
            style.polish(self.status_label)
        return problems

    # -- persistence ---------------------------------------------------------
    def save(self, path: str | Path) -> Path:
        """Write the sequence to *path* as YAML."""
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(self.sequence.as_dict(), sort_keys=False), encoding="utf-8"
        )
        return target

    def load(self, path: str | Path) -> FlashSequence:
        """Load a sequence from the YAML file at *path*."""
        data = yaml.safe_load(Path(path).expanduser().read_text(encoding="utf-8")) or {}
        self.sequence = FlashSequence.from_dict(data)
        if self.sequence.flash_file:
            self.flash_file.set_path(self.sequence.flash_file)
        if self.sequence.security_file:
            self.security_file.set_path(self.sequence.security_file)
        self.level_spin.setValue(self.sequence.security_level)
        self.block_spin.setValue(self.sequence.block_size)
        self.reload()
        return self.sequence

    def save_dialog(self) -> Path | None:
        """Ask where to save the sequence and write it."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the flash sequence", str(Path.home() / "flash_sequence.yaml"),
            "YAML files (*.yaml *.yml)",
        )
        return self.save(path) if path else None

    def load_dialog(self) -> FlashSequence | None:
        """Ask for a sequence file and load it."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load a flash sequence", str(Path.home()), "YAML files (*.yaml *.yml)"
        )
        return self.load(path) if path else None

    # -- live updates --------------------------------------------------------
    def apply_status(self, step: FlashStep) -> None:
        """Refresh the row of *step* after the runner changed its status."""
        self.reload()

    # -- internals ------------------------------------------------------------
    def _on_step_dropped(self, kind: FlashStepKind, row: int) -> None:
        """Insert a palette step at *row*."""
        self.sequence.add(kind, row)
        self.reload()
        self.step_list.setCurrentRow(min(row, self.step_list.count() - 1))

    def _on_step_moved(self, source: int, target: int) -> None:
        """Reorder after an internal drag."""
        if self.sequence.move(source, target):
            self.reload()
            self.step_list.setCurrentRow(target)

    def _on_selection(self) -> None:
        """Enable the row tools only when a row is selected."""
        has = 0 <= self.step_list.currentRow() < len(self.sequence.steps)
        for button in (
            self.up_button,
            self.down_button,
            self.toggle_button,
            self.remove_button,
        ):
            button.setEnabled(has)

    def _on_flash_file(self, path: str) -> None:
        """Record the chosen flash file."""
        self.sequence.flash_file = Path(path) if path else None
        self.validate()
        self.sequence_changed.emit(self.sequence)

    def _on_security_file(self, path: str) -> None:
        """Record the chosen seed-key file."""
        self.sequence.security_file = Path(path) if path else None
        self.validate()
        self.sequence_changed.emit(self.sequence)

    def _on_options_changed(self, _value: int) -> None:
        """Copy the spin box values into the sequence."""
        self.sequence.security_level = self.level_spin.value()
        self.sequence.block_size = self.block_spin.value()
        self.sequence_changed.emit(self.sequence)

    def _on_start(self) -> None:
        """Emit :attr:`start_requested` when the sequence is valid."""
        if self.validate():
            return
        self.start_requested.emit(self.sequence)


def _color(token: str) -> Any:
    """Return a :class:`QColor` for the semantic *token*."""
    from PySide6.QtGui import QColor

    return QColor(semantic(token))
