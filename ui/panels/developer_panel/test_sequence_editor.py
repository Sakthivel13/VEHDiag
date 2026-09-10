"""Drag and drop editor for the developer mode test sequence."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from src.core.models.test_sequence_model import TestResult, TestSequence, TestStatus, TestStep

from ...dpi_scaler import DPIScaler
from ...widgets.responsive_widget import ResponsiveWidget
from .service_grid_widget import ServiceGridWidget

#: MIME type used to identify an internal card drag.
DRAG_MIME = "application/x-vdp-service-grid"


class TestSequenceEditor(ResponsiveWidget):
    """A scrollable, reorderable list of :class:`ServiceGridWidget` cards.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    #: Emitted with the step the operator wants to run.
    run_requested = Signal(object)
    #: Emitted whenever the order or the content of the sequence changes.
    sequence_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the scrollable card container."""
        super().__init__(parent, scaler)
        self.sequence = TestSequence()
        self.cards: list[ServiceGridWidget] = []

        self.container = QWidget(self)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(self.spacing(8))
        self.container_layout.addStretch(1)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)
        self.setAcceptDrops(True)
        self._drag_index = -1

    # -- content -------------------------------------------------------------
    def load_sequence(self, sequence: TestSequence) -> None:
        """Rebuild the editor from *sequence*."""
        self.sequence = sequence
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()
        for step in sequence.steps:
            self._add_card(step)
        self._renumber()

    def add_step(self, step: TestStep) -> ServiceGridWidget:
        """Append a step and return the created card."""
        self.sequence.steps.append(step)
        card = self._add_card(step)
        self._renumber()
        self.sequence_changed.emit(self.sequence)
        return card

    def remove_step(self, step: TestStep) -> None:
        """Remove *step* and its card."""
        for index, card in enumerate(self.cards):
            if card.step is step:
                card.setParent(None)
                card.deleteLater()
                del self.cards[index]
                break
        if step in self.sequence.steps:
            self.sequence.steps.remove(step)
        self._renumber()
        self.sequence_changed.emit(self.sequence)

    def move_card(self, from_index: int, to_index: int) -> None:
        """Move a card and its step to another position."""
        if not 0 <= from_index < len(self.cards):
            return
        to_index = max(0, min(to_index, len(self.cards) - 1))
        if from_index == to_index:
            return
        card = self.cards.pop(from_index)
        self.cards.insert(to_index, card)
        self.sequence.move(from_index, to_index)
        self.container_layout.removeWidget(card)
        self.container_layout.insertWidget(to_index, card)
        self._renumber()
        self.sequence_changed.emit(self.sequence)

    def _add_card(self, step: TestStep) -> ServiceGridWidget:
        """Create and wire a card for *step*."""
        card = ServiceGridWidget(step, self.container, self.scaler)
        card.run_requested.connect(self.run_requested.emit)
        card.remove_requested.connect(self.remove_step)
        card.step_changed.connect(lambda _s: self.sequence_changed.emit(self.sequence))
        card.drag_handle.mousePressEvent = lambda event, c=card: self._start_drag(event, c)
        self.container_layout.insertWidget(self.container_layout.count() - 1, card)
        self.cards.append(card)
        return card

    def _renumber(self) -> None:
        """Refresh the sequence numbers on every card."""
        self.sequence.reorder()
        for index, card in enumerate(self.cards, start=1):
            card.set_order(index)

    # -- results ---------------------------------------------------------------
    def card_for(self, step: TestStep) -> ServiceGridWidget | None:
        """Return the card representing *step*."""
        for card in self.cards:
            if card.step is step:
                return card
        return None

    def apply_result(self, result: TestResult) -> None:
        """Update the card matching the result."""
        card = self.card_for(result.step)
        if card is not None:
            card.apply_result(result)

    def mark_running(self, step: TestStep) -> None:
        """Mark the card of *step* as running."""
        card = self.card_for(step)
        if card is not None:
            card.set_running(True)

    def reset_status(self) -> None:
        """Set every card back to the idle state."""
        for card in self.cards:
            card.set_status(TestStatus.IDLE)
            card.set_running(False)

    def collapse_all(self, collapsed: bool = True) -> None:
        """Collapse or expand every card."""
        for card in self.cards:
            card.collapse_button.setChecked(not collapsed)

    # -- drag and drop ----------------------------------------------------------
    def _start_drag(self, event: Any, card: ServiceGridWidget) -> None:
        """Begin dragging *card* when the handle is pressed."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_index = self.cards.index(card)
        card.set_property_and_refresh("dragging", "true")
        drag = QDrag(card)
        mime = QMimeData()
        mime.setData(DRAG_MIME, str(self._drag_index).encode())
        drag.setMimeData(mime)
        pixmap = QPixmap(card.size())
        card.render(pixmap)
        drag.setPixmap(pixmap.scaledToWidth(self.px(280), Qt.TransformationMode.SmoothTransformation))
        drag.setHotSpot(QPoint(self.px(20), self.px(16)))
        drag.exec(Qt.DropAction.MoveAction)
        card.set_property_and_refresh("dragging", None)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt naming
        """Accept internal card drags."""
        if event.mimeData().hasFormat(DRAG_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802 - Qt naming
        """Keep accepting the drag while it moves over the editor."""
        if event.mimeData().hasFormat(DRAG_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt naming
        """Reorder the cards according to the drop position."""
        if not event.mimeData().hasFormat(DRAG_MIME):
            return
        source = int(bytes(event.mimeData().data(DRAG_MIME)).decode() or -1)
        target = self._index_at(event.position().toPoint())
        if source >= 0 and target >= 0:
            self.move_card(source, target)
        event.acceptProposedAction()

    def _index_at(self, position: QPoint) -> int:
        """Return the card index under *position*."""
        mapped = self.container.mapFrom(self, position)
        for index, card in enumerate(self.cards):
            if card.geometry().contains(mapped):
                return index
        return len(self.cards) - 1


__all__ = ["TestSequenceEditor", "DRAG_MIME"]
