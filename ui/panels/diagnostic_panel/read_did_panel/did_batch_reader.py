"""Batch reading helper for ReadDataByIdentifier.

ISO 14229 allows several identifiers in a single 0x22 request, but ECUs limit
the response length, so long lists have to be split into chunks. This module
computes those chunks, tracks the progress of a batch and formats the summary
shown under the results table.

Example:
    >>> from ui.panels.diagnostic_panel.read_did_panel.did_batch_reader import (
    ...     chunk_dids, estimate_response_size)
    >>> chunk_dids([1, 2, 3, 4, 5], 2)
    [[1, 2], [3, 4], [5]]
    >>> estimate_response_size([0xF190, 0xF18C], {0xF190: 17, 0xF18C: 10})
    32
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QSpinBox, QWidget

from src.core.models.did_model import DIDRegistry, DIDValue

from ....dpi_scaler import DPIScaler
from ....widgets.responsive_widget import ResponsiveWidget
from ....widgets.scalable_button import ScalableButton

__all__ = [
    "BatchProgress",
    "DIDBatchReader",
    "chunk_dids",
    "estimate_response_size",
]

#: Default maximum number of identifiers put into a single request.
DEFAULT_CHUNK_SIZE = 4

#: Bytes of overhead of a 0x22 response: SID echo plus the DID echo per item.
RESPONSE_OVERHEAD = 1
_DID_ECHO_SIZE = 2
_DEFAULT_ITEM_SIZE = 8


def chunk_dids(dids: Iterable[int], chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[list[int]]:
    """Split *dids* into request sized chunks.

    Args:
        dids: The identifiers to read.
        chunk_size: Maximum number of identifiers per request (at least one).

    Returns:
        A list of chunks preserving the original order.

    Example:
        >>> chunk_dids([], 3)
        []
        >>> chunk_dids([1, 2, 3], 0)
        [[1], [2], [3]]
    """
    items = list(dids)
    size = max(1, int(chunk_size))
    return [items[index : index + size] for index in range(0, len(items), size)]


def estimate_response_size(dids: Iterable[int], lengths: dict[int, int] | None = None) -> int:
    """Estimate the length of the positive response for *dids*.

    Args:
        dids: The identifiers of the request.
        lengths: Known payload length per identifier; unknown identifiers are
            assumed to carry eight bytes.

    Returns:
        The estimated response length in bytes, including the SID echo.

    Example:
        >>> estimate_response_size([0x1234])
        11
    """
    known = lengths or {}
    total = RESPONSE_OVERHEAD
    for did in dids:
        total += _DID_ECHO_SIZE + int(known.get(did, _DEFAULT_ITEM_SIZE))
    return total


@dataclass(slots=True)
class BatchProgress:
    """State of a running batch read.

    Attributes:
        chunks: The planned request chunks.
        index: Index of the chunk currently in flight.
        values: The readings collected so far.
        failures: ``{did: reason}`` for the identifiers that could not be read.
        started_at: Monotonic start time of the batch.
        finished_at: Monotonic completion time, ``0.0`` while running.
    """

    chunks: list[list[int]] = field(default_factory=list)
    index: int = 0
    values: list[DIDValue] = field(default_factory=list)
    failures: dict[int, str] = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def total(self) -> int:
        """Return the number of identifiers in the batch."""
        return sum(len(chunk) for chunk in self.chunks)

    @property
    def done(self) -> int:
        """Return the number of identifiers already answered."""
        return len(self.values) + len(self.failures)

    @property
    def percent(self) -> float:
        """Return the completion percentage in the range 0..100."""
        return 100.0 * self.done / self.total if self.total else 0.0

    @property
    def is_finished(self) -> bool:
        """Return ``True`` when every chunk has been processed."""
        return self.index >= len(self.chunks)

    @property
    def elapsed_s(self) -> float:
        """Return the elapsed time of the batch in seconds."""
        if not self.started_at:
            return 0.0
        return max(0.0, (self.finished_at or time.monotonic()) - self.started_at)

    def summary(self) -> str:
        """Return the one line summary shown under the results table.

        Example:
            >>> BatchProgress().summary()
            'no DIDs requested'
        """
        if not self.chunks:
            return "no DIDs requested"
        parts = [f"{len(self.values)}/{self.total} read"]
        if self.failures:
            parts.append(f"{len(self.failures)} failed")
        parts.append(f"{self.elapsed_s * 1000.0:.0f} ms")
        return ", ".join(parts)


class DIDBatchReader(ResponsiveWidget):
    """Controls chunking, repetition and progress of a batch DID read.

    The widget owns no transport: it emits :attr:`chunk_requested` and the
    diagnostic controller answers with :meth:`chunk_completed` or
    :meth:`chunk_failed`. This keeps the widget fully testable without an ECU.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        registry: Registry used to estimate the response sizes.
    """

    #: Emitted with the identifiers of the next request chunk.
    chunk_requested = Signal(list)
    #: Emitted with ``(done, total)`` after every answered chunk.
    progress_changed = Signal(int, int)
    #: Emitted with the collected :class:`DIDValue` list when the batch ends.
    batch_finished = Signal(list)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        registry: DIDRegistry | None = None,
    ) -> None:
        """Build the chunk-size, repeat and control row."""
        super().__init__(parent, scaler)
        self.registry = registry or DIDRegistry()
        self.progress = BatchProgress()
        self._pending: list[int] = []

        self.chunk_spin = QSpinBox(self)
        self.chunk_spin.setRange(1, 32)
        self.chunk_spin.setValue(DEFAULT_CHUNK_SIZE)
        self.chunk_spin.setToolTip("Maximum number of DIDs per 0x22 request")

        self.stop_on_error = QCheckBox("Stop on error", self)
        self.stop_on_error.setChecked(False)

        self.repeat_box = QCheckBox("Repeat", self)
        self.interval_spin = QSpinBox(self)
        self.interval_spin.setRange(50, 60000)
        self.interval_spin.setValue(1000)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setEnabled(False)
        self.repeat_box.toggled.connect(self.interval_spin.setEnabled)

        self.status_label = QLabel("idle", self)
        self.status_label.setProperty("role", "secondary")
        self.cancel_button = ScalableButton("Cancel", "cancel", self, self.scaler, danger=True)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(6))
        layout.addWidget(QLabel("DIDs per request:", self))
        layout.addWidget(self.chunk_spin)
        layout.addWidget(self.stop_on_error)
        layout.addWidget(self.repeat_box)
        layout.addWidget(self.interval_spin)
        layout.addStretch(1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.cancel_button)

        self._repeat_timer = QTimer(self)
        self._repeat_timer.timeout.connect(self._on_repeat)

    # -- batch control -------------------------------------------------------
    def start(self, dids: list[int]) -> BatchProgress:
        """Plan the chunks for *dids* and request the first one.

        Args:
            dids: The identifiers to read.

        Returns:
            The freshly created :class:`BatchProgress`.
        """
        self._pending = list(dids)
        self.progress = BatchProgress(
            chunks=chunk_dids(dids, self.chunk_spin.value()), started_at=time.monotonic()
        )
        self.cancel_button.setEnabled(bool(self.progress.chunks))
        self._request_next()
        return self.progress

    def chunk_completed(self, values: list[DIDValue]) -> None:
        """Record the readings of the chunk in flight and request the next one."""
        self.progress.values.extend(values)
        self.progress.index += 1
        self._after_chunk()

    def chunk_failed(self, reason: str) -> None:
        """Record that the chunk in flight failed with *reason*."""
        if self.progress.index < len(self.progress.chunks):
            for did in self.progress.chunks[self.progress.index]:
                self.progress.failures[did] = reason
        self.progress.index += 1
        if self.stop_on_error.isChecked():
            self.progress.index = len(self.progress.chunks)
        self._after_chunk()

    def cancel(self) -> None:
        """Abort the batch and stop the repetition timer."""
        self._repeat_timer.stop()
        self.progress.index = len(self.progress.chunks)
        self.progress.finished_at = time.monotonic()
        self.cancel_button.setEnabled(False)
        self.status_label.setText("cancelled")

    def estimated_size(self, dids: list[int]) -> int:
        """Return the estimated response size for *dids* using the registry."""
        lengths = {
            did: definition.length
            for did, definition in self.registry.definitions.items()
            if definition.length
        }
        return estimate_response_size(dids, lengths)

    # -- internals ------------------------------------------------------------
    def _request_next(self) -> None:
        """Emit :attr:`chunk_requested` for the chunk at the current index."""
        if self.progress.is_finished:
            self._finish()
            return
        self.status_label.setText(
            f"chunk {self.progress.index + 1}/{len(self.progress.chunks)}"
        )
        self.chunk_requested.emit(list(self.progress.chunks[self.progress.index]))

    def _after_chunk(self) -> None:
        """Publish the progress and continue with the next chunk."""
        self.progress_changed.emit(self.progress.done, self.progress.total)
        self._request_next()

    def _finish(self) -> None:
        """Close the batch, emit the results and arm the repetition timer."""
        self.progress.finished_at = time.monotonic()
        self.cancel_button.setEnabled(False)
        self.status_label.setText(self.progress.summary())
        self.batch_finished.emit(list(self.progress.values))
        if self.repeat_box.isChecked() and self._pending:
            self._repeat_timer.start(self.interval_spin.value())

    def _on_repeat(self) -> None:
        """Restart the batch when the repetition timer fires."""
        self._repeat_timer.stop()
        if self.repeat_box.isChecked() and self._pending:
            self.start(list(self._pending))
