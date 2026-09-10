"""Collection and aggregation of test results."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.models.test_sequence_model import TestResult, TestStatus
from ..utils.file_utils import atomic_write_text, ensure_dir

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ResultSummary:
    """Aggregated counters of one execution run."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    cancelled: int = 0
    duration_ms: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def success_rate(self) -> float:
        """Return the percentage of executed steps that passed."""
        executed = self.passed + self.failed + self.errors
        return (self.passed / executed * 100.0) if executed else 0.0

    @property
    def successful(self) -> bool:
        """Return ``True`` when nothing failed and nothing errored."""
        return self.failed == 0 and self.errors == 0 and self.total > 0

    def as_text(self) -> str:
        """Return the summary bar text of the developer panel."""
        return (
            f"Total {self.total} | Passed {self.passed} | Failed {self.failed} | "
            f"Errors {self.errors} | Skipped {self.skipped} | "
            f"{self.duration_ms / 1000.0:.2f} s"
        )


class TestResultCollector:
    """Stores results, aggregates them and exports reports.

    Example:
        >>> from src.core.models.test_sequence_model import TestStep, TestResult, TestStatus
        >>> collector = TestResultCollector()
        >>> collector.add(TestResult(TestStep(0x22, "Read DID"), TestStatus.PASS, 12.5))
        >>> collector.summary().passed
        1
    """

    def __init__(self) -> None:
        """Create an empty collector."""
        self.results: list[TestResult] = []
        self.started_at: float = 0.0
        self.finished_at: float = 0.0

    # -- collection ---------------------------------------------------------
    def start(self) -> None:
        """Mark the beginning of a run and clear previous results."""
        self.results.clear()
        self.started_at = time.time()
        self.finished_at = 0.0

    def add(self, result: TestResult) -> None:
        """Append one result."""
        self.results.append(result)

    def finish(self) -> ResultSummary:
        """Mark the end of the run and return the summary."""
        self.finished_at = time.time()
        return self.summary()

    def clear(self) -> None:
        """Remove every stored result."""
        self.results.clear()
        self.started_at = self.finished_at = 0.0

    # -- aggregation ----------------------------------------------------------
    def summary(self) -> ResultSummary:
        """Return the aggregated counters of the stored results."""
        summary = ResultSummary(
            total=len(self.results),
            started_at=self.started_at,
            finished_at=self.finished_at or time.time(),
        )
        for result in self.results:
            if result.status is TestStatus.PASS:
                summary.passed += 1
            elif result.status is TestStatus.FAIL:
                summary.failed += 1
            elif result.status is TestStatus.ERROR:
                summary.errors += 1
            elif result.status is TestStatus.SKIPPED:
                summary.skipped += 1
            elif result.status is TestStatus.CANCELLED:
                summary.cancelled += 1
            summary.duration_ms += result.duration_ms
        return summary

    def failures(self) -> list[TestResult]:
        """Return only the failed and errored results."""
        return [r for r in self.results if r.status in (TestStatus.FAIL, TestStatus.ERROR)]

    def rows(self) -> list[dict[str, Any]]:
        """Return the rows displayed by the results table."""
        return [result.as_row() for result in self.results]

    # -- export -----------------------------------------------------------------
    def to_json(self, path: str | Path) -> Path:
        """Write the results as structured JSON."""
        payload = {
            "summary": {
                "total": self.summary().total,
                "passed": self.summary().passed,
                "failed": self.summary().failed,
                "errors": self.summary().errors,
                "skipped": self.summary().skipped,
                "duration_ms": round(self.summary().duration_ms, 2),
            },
            "results": self.rows(),
        }
        return atomic_write_text(path, json.dumps(payload, indent=2, default=str))

    def to_csv(self, path: str | Path) -> Path:
        """Write the results as CSV."""
        import csv
        import io

        rows = self.rows()
        buffer = io.StringIO()
        if rows:
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return atomic_write_text(path, buffer.getvalue())

    def to_html(self, path: str | Path, title: str = "Test report") -> Path:
        """Write a styled HTML report."""
        import html as html_module

        summary = self.summary()
        colours = {
            "PASS": "#22C55E",
            "FAIL": "#EF4444",
            "ERROR": "#DC2626",
            "SKIPPED": "#94A3B8",
            "CANCELLED": "#F59E0B",
        }
        rows = []
        for result in self.results:
            colour = colours.get(result.status.value, "#F8FAFC")
            row = result.as_row()
            cells = "".join(
                f"<td>{html_module.escape(str(row[key]))}</td>"
                for key in ("order", "service", "name", "file", "duration_ms", "request", "response")
            )
            rows.append(
                f'<tr><td style="color:{colour};font-weight:600">{result.status.value}</td>{cells}</tr>'
            )
        document = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{html_module.escape(title)}</title>
<style>
 body{{background:#1E1E2E;color:#F8FAFC;font-family:Roboto,sans-serif;padding:24px}}
 table{{border-collapse:collapse;width:100%;font-size:13px}}
 th{{background:#282840;text-align:left;padding:8px}}
 td{{border-bottom:1px solid #374151;padding:6px 8px}}
 .summary{{background:#282840;padding:12px;border-radius:8px;margin-bottom:16px}}
</style></head><body>
<h1>{html_module.escape(title)}</h1>
<div class="summary">{html_module.escape(summary.as_text())}</div>
<table><thead><tr><th>Status</th><th>#</th><th>Service</th><th>Name</th><th>File</th>
<th>Duration (ms)</th><th>Request</th><th>Response</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
</body></html>
"""
        return atomic_write_text(path, document)

    def __len__(self) -> int:  # noqa: D105 - trivial
        return len(self.results)


__all__ = ["TestResultCollector", "ResultSummary"]
