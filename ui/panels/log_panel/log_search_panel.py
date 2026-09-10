"""Incremental search across the communication log.

The specification requires a search over 100 000 entries in under 100 ms, so
the search runs over the in-memory entry list with a pre-lowered haystack and
returns match indexes rather than copies of the entries.

Example:
    >>> from ui.panels.log_panel.log_search_panel import (
    ...     SearchOptions, find_matches, haystack_of, next_index)
    >>> from src.core.models.log_entry_model import LogEntry
    >>> entries = [LogEntry(message="hello"), LogEntry(message="world"),
    ...            LogEntry(message="hello again")]
    >>> find_matches(entries, "hello")
    [0, 2]
    >>> find_matches(entries, "HELLO", SearchOptions(case_sensitive=True))
    []
    >>> find_matches(entries, "h.llo", SearchOptions(regex=True))
    [0, 2]
    >>> next_index([0, 2], 0, forward=True)
    2
    >>> next_index([0, 2], 2, forward=True)
    0
    >>> "hello" in haystack_of(entries[0])
    True
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Sequence

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QWidget

from src.core.models.log_entry_model import LogEntry

from ...dpi_scaler import DPIScaler
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton

__all__ = [
    "LogSearchPanel",
    "SearchOptions",
    "find_matches",
    "haystack_of",
    "next_index",
]


@dataclass(frozen=True, slots=True)
class SearchOptions:
    """Options controlling a search run.

    Attributes:
        case_sensitive: Compare the needle case sensitively.
        regex: Interpret the needle as a regular expression.
        whole_word: Require the needle to match a whole word.
    """

    case_sensitive: bool = False
    regex: bool = False
    whole_word: bool = False


def haystack_of(entry: LogEntry) -> str:
    """Return the concatenated searchable text of *entry*.

    Example:
        >>> from src.core.models.log_entry_model import LogEntry
        >>> haystack_of(LogEntry(message="x", can_id="7E0")).strip().split()[0]
        'x'
    """
    return " ".join(
        (
            entry.message,
            entry.hex_data,
            entry.decoded_service,
            entry.decoded_detail,
            entry.can_id,
            entry.protocol,
            entry.direction,
        )
    )


def find_matches(
    entries: Sequence[LogEntry], needle: str, options: SearchOptions | None = None
) -> list[int]:
    """Return the indexes of the entries matching *needle*.

    Args:
        entries: The entries to search.
        needle: The search text or regular expression.
        options: Search options; the defaults are case insensitive substring.

    Returns:
        The matching indexes in ascending order; an empty list when *needle*
        is empty or the regular expression is invalid.

    Example:
        >>> find_matches([], "x")
        []
    """
    opts = options or SearchOptions()
    text = needle.strip()
    if not text:
        return []
    if opts.regex or opts.whole_word:
        pattern = text if opts.regex else re.escape(text)
        if opts.whole_word:
            pattern = rf"\b{pattern}\b"
        flags = 0 if opts.case_sensitive else re.IGNORECASE
        try:
            expression = re.compile(pattern, flags)
        except re.error:
            return []
        return [
            index for index, entry in enumerate(entries) if expression.search(haystack_of(entry))
        ]
    if opts.case_sensitive:
        return [index for index, entry in enumerate(entries) if text in haystack_of(entry)]
    lowered = text.lower()
    return [
        index for index, entry in enumerate(entries) if lowered in haystack_of(entry).lower()
    ]


def next_index(matches: Sequence[int], current: int, forward: bool = True) -> int:
    """Return the match following (or preceding) *current*, wrapping around.

    Args:
        matches: The match indexes in ascending order.
        current: The currently highlighted row index.
        forward: Search forwards when true, backwards otherwise.

    Returns:
        The next match index, or ``-1`` when there is no match at all.

    Example:
        >>> next_index([], 0)
        -1
        >>> next_index([5, 9], 7, forward=False)
        5
    """
    if not matches:
        return -1
    if forward:
        for index in matches:
            if index > current:
                return index
        return matches[0]
    for index in reversed(matches):
        if index < current:
            return index
    return matches[-1]


class LogSearchPanel(ResponsiveWidget):
    """Debounced search bar with match navigation for the log table.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        debounce_ms: Delay before the search runs after the last keystroke.

    Attributes:
        matches: The indexes of the entries matching the current needle.
        current: The index of the currently highlighted match.
    """

    #: Emitted with ``(row_index, match_number, match_total)`` on navigation.
    match_selected = Signal(int, int, int)
    #: Emitted with the match indexes after every search run.
    matches_changed = Signal(list)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        debounce_ms: int = 150,
    ) -> None:
        """Build the search row and the debounce timer."""
        super().__init__(parent, scaler)
        self.entries: Sequence[LogEntry] = []
        self.matches: list[int] = []
        self.current = -1
        self.last_duration_ms = 0.0

        self.field = QLineEdit(self)
        self.field.setPlaceholderText("Search the log...")
        self.field.setClearButtonEnabled(True)
        self.field.textChanged.connect(self._on_text_changed)
        self.field.returnPressed.connect(self.find_next)

        self.case_box = QCheckBox("Aa", self)
        self.case_box.setToolTip("Case sensitive")
        self.case_box.toggled.connect(lambda _c: self.search())
        self.regex_box = QCheckBox("Regex", self)
        self.regex_box.toggled.connect(lambda _c: self.search())
        self.word_box = QCheckBox("Word", self)
        self.word_box.setToolTip("Match whole words only")
        self.word_box.toggled.connect(lambda _c: self.search())

        self.previous_button = ScalableButton("Previous", "chevron_right", self, self.scaler)
        self.previous_button.clicked.connect(self.find_previous)
        self.next_button = ScalableButton("Next", "chevron_down", self, self.scaler)
        self.next_button.clicked.connect(self.find_next)

        self.status_label = QLabel("no search", self)
        self.status_label.setProperty("role", "secondary")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing(4))
        layout.addWidget(self.field, 3)
        layout.addWidget(self.case_box)
        layout.addWidget(self.regex_box)
        layout.addWidget(self.word_box)
        layout.addWidget(self.previous_button)
        layout.addWidget(self.next_button)
        layout.addWidget(self.status_label, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(0, debounce_ms))
        self._timer.timeout.connect(self.search)

    # -- API -----------------------------------------------------------------
    def set_entries(self, entries: Sequence[LogEntry]) -> None:
        """Replace the searched entries and re-run the search."""
        self.entries = entries
        self.search()

    def options(self) -> SearchOptions:
        """Return the options selected by the operator."""
        return SearchOptions(
            case_sensitive=self.case_box.isChecked(),
            regex=self.regex_box.isChecked(),
            whole_word=self.word_box.isChecked(),
        )

    def needle(self) -> str:
        """Return the text currently typed in the search field."""
        return self.field.text()

    def search(self) -> list[int]:
        """Run the search and return the match indexes."""
        started = time.perf_counter()
        self.matches = find_matches(self.entries, self.needle(), self.options())
        self.last_duration_ms = (time.perf_counter() - started) * 1000.0
        self.current = self.matches[0] if self.matches else -1
        self._refresh_status()
        self.matches_changed.emit(list(self.matches))
        if self.current >= 0:
            self.match_selected.emit(self.current, 1, len(self.matches))
        return self.matches

    def find_next(self) -> int:
        """Highlight the next match and return its row index."""
        return self._navigate(forward=True)

    def find_previous(self) -> int:
        """Highlight the previous match and return its row index."""
        return self._navigate(forward=False)

    def clear(self) -> None:
        """Clear the field and the matches."""
        self.field.clear()
        self.matches = []
        self.current = -1
        self._refresh_status()

    def match_count(self) -> int:
        """Return the number of matches of the current search."""
        return len(self.matches)

    # -- internals ------------------------------------------------------------
    def _navigate(self, forward: bool) -> int:
        """Move to the next or previous match."""
        target = next_index(self.matches, self.current, forward)
        if target < 0:
            return -1
        self.current = target
        position = self.matches.index(target) + 1
        self._refresh_status(position)
        self.match_selected.emit(target, position, len(self.matches))
        return target

    def _refresh_status(self, position: int = 0) -> None:
        """Refresh the ``n/m matches`` label."""
        if not self.needle():
            self.status_label.setText("no search")
            return
        if not self.matches:
            self.status_label.setText("no match")
            return
        current = position or (
            self.matches.index(self.current) + 1 if self.current in self.matches else 1
        )
        self.status_label.setText(
            f"{current}/{len(self.matches)} matches  ({self.last_duration_ms:.1f} ms)"
        )

    def _on_text_changed(self, _text: str) -> None:
        """Restart the debounce timer."""
        self._timer.start()
