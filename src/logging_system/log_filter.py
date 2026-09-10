"""Log filtering predicates."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..core.models.log_entry_model import LogCategory, LogEntry, LogLevel


@dataclass(slots=True)
class LogFilter:
    """A combinable set of filter criteria (AND semantics).

    Attributes:
        min_level: Minimum severity an entry must have.
        categories: Accepted categories; empty means all.
        directions: Accepted directions (``TX``/``RX``); empty means all.
        protocols: Accepted protocol names; empty means all.
        id_from: Lowest accepted numeric identifier.
        id_to: Highest accepted numeric identifier.
        contains: Substring that must appear in the rendered entry.
        regex: Regular expression the rendered entry must match.
        data_pattern: Hex byte pattern the payload must contain.
        time_from: Earliest accepted timestamp.
        time_to: Latest accepted timestamp.
        services: Accepted decoded service names.
        hide_tester_present: Drop TesterPresent traffic.
        case_sensitive: Make :attr:`contains` case sensitive.
    """

    min_level: LogLevel = LogLevel.TRACE
    categories: set[LogCategory] = field(default_factory=set)
    directions: set[str] = field(default_factory=set)
    protocols: set[str] = field(default_factory=set)
    id_from: int | None = None
    id_to: int | None = None
    contains: str = ""
    regex: str = ""
    data_pattern: str = ""
    time_from: float | None = None
    time_to: float | None = None
    services: set[str] = field(default_factory=set)
    hide_tester_present: bool = False
    case_sensitive: bool = False

    def matches(self, entry: LogEntry) -> bool:
        """Return ``True`` when *entry* satisfies every active criterion."""
        if entry.level < self.min_level:
            return False
        if self.categories and entry.category not in self.categories:
            return False
        if self.directions and entry.direction not in self.directions:
            return False
        if self.protocols and entry.protocol not in self.protocols:
            return False
        if self.time_from is not None and entry.timestamp < self.time_from:
            return False
        if self.time_to is not None and entry.timestamp > self.time_to:
            return False
        if self.hide_tester_present and self._is_tester_present(entry):
            return False
        if (self.id_from is not None or self.id_to is not None) and not self._id_in_range(entry):
            return False
        if self.data_pattern and not self._data_matches(entry):
            return False
        if self.services and entry.decoded_service not in self.services:
            return False
        if self.contains and not self._text_matches(entry):
            return False
        if self.regex and not re.search(self.regex, self._searchable(entry), re.IGNORECASE):
            return False
        return True

    def apply(self, entries: list[LogEntry]) -> list[LogEntry]:
        """Return the subset of *entries* matching the filter."""
        return [entry for entry in entries if self.matches(entry)]

    def is_active(self) -> bool:
        """Return ``True`` when at least one criterion is set."""
        return bool(
            self.min_level > LogLevel.TRACE
            or self.categories
            or self.directions
            or self.protocols
            or self.id_from is not None
            or self.id_to is not None
            or self.contains
            or self.regex
            or self.data_pattern
            or self.services
            or self.hide_tester_present
            or self.time_from
            or self.time_to
        )

    def reset(self) -> None:
        """Clear every criterion."""
        self.min_level = LogLevel.TRACE
        self.categories.clear()
        self.directions.clear()
        self.protocols.clear()
        self.services.clear()
        self.id_from = self.id_to = None
        self.contains = self.regex = self.data_pattern = ""
        self.time_from = self.time_to = None
        self.hide_tester_present = False

    def to_dict(self) -> dict[str, Any]:
        """Return the YAML serialisable representation of the filter."""
        return {
            "min_level": self.min_level.name,
            "categories": sorted(c.value for c in self.categories),
            "directions": sorted(self.directions),
            "protocols": sorted(self.protocols),
            "id_from": self.id_from,
            "id_to": self.id_to,
            "contains": self.contains,
            "regex": self.regex,
            "data_pattern": self.data_pattern,
            "hide_tester_present": self.hide_tester_present,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogFilter":
        """Build a filter from its serialised representation."""
        return cls(
            min_level=LogLevel.parse(data.get("min_level", "TRACE")),
            categories={LogCategory(c) for c in data.get("categories", [])},
            directions=set(data.get("directions", [])),
            protocols=set(data.get("protocols", [])),
            id_from=data.get("id_from"),
            id_to=data.get("id_to"),
            contains=str(data.get("contains", "")),
            regex=str(data.get("regex", "")),
            data_pattern=str(data.get("data_pattern", "")),
            hide_tester_present=bool(data.get("hide_tester_present", False)),
        )

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _is_tester_present(entry: LogEntry) -> bool:
        """Return ``True`` for TesterPresent traffic."""
        if entry.data and entry.data[0] in (0x02, 0x3E):
            payload = entry.data[1:] if entry.data[0] == 0x02 else entry.data
            if payload and payload[0] in (0x3E, 0x7E):
                return True
        return "TesterPresent" in entry.decoded_service

    def _id_in_range(self, entry: LogEntry) -> bool:
        """Return ``True`` when the numeric identifier is inside the range."""
        try:
            value = int(entry.can_id, 16) if entry.can_id else None
        except ValueError:
            return True
        if value is None:
            return False
        if self.id_from is not None and value < self.id_from:
            return False
        if self.id_to is not None and value > self.id_to:
            return False
        return True

    def _data_matches(self, entry: LogEntry) -> bool:
        """Return ``True`` when the payload contains the byte pattern."""
        pattern = self.data_pattern.replace(" ", "").upper()
        return pattern in entry.hex_data.replace(" ", "")

    def _text_matches(self, entry: LogEntry) -> bool:
        """Return ``True`` when the searchable text contains the substring."""
        haystack = self._searchable(entry)
        needle = self.contains
        if not self.case_sensitive:
            haystack, needle = haystack.lower(), needle.lower()
        return needle in haystack

    @staticmethod
    def _searchable(entry: LogEntry) -> str:
        """Return the concatenated text used for substring and regex search."""
        return " ".join(
            (
                entry.message,
                entry.hex_data,
                entry.decoded_service,
                entry.decoded_detail,
                entry.can_id,
                entry.protocol,
            )
        )


#: Ready made filters offered as quick actions in the log panel.
QUICK_FILTERS: dict[str, LogFilter] = {
    "Errors only": LogFilter(min_level=LogLevel.ERROR),
    "Warnings and above": LogFilter(min_level=LogLevel.WARNING),
    "Diagnostics only": LogFilter(categories={LogCategory.DIAG}),
    "Communication only": LogFilter(categories={LogCategory.COMM}),
    "Hide tester present": LogFilter(hide_tester_present=True),
    "Transmitted only": LogFilter(directions={"TX"}),
    "Received only": LogFilter(directions={"RX"}),
}


__all__ = ["LogFilter", "QUICK_FILTERS"]
