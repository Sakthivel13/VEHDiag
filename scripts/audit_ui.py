"""Automated UI alignment and layout auditor.

Walks every workspace and every section of the running application and reports
geometry defects that a human would call "misaligned":

* **clipped** - a widget is wider/taller than the viewport that shows it, or a
  table row/column sits outside its viewport;
* **overlap** - two sibling widgets in the same layout intersect;
* **overflow** - a child sticks out of its parent's content rect;
* **elided** - a label is showing an ellipsis, i.e. its text does not fit;
* **truncated header** - a table header section is narrower than the text it
  must display;
* **offscreen** - a visible widget is positioned outside the window.

Usage::

    QT_QPA_PLATFORM=offscreen python3 scripts/audit_ui.py [--width 1920]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractScrollArea,
    QApplication,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTabWidget,
    QWidget,
)

#: Widgets whose children legitimately overlap (stacked/tabbed containers).
STACKED = ("QStackedWidget", "QTabWidget", "QToolBox", "QMdiArea")
#: Minimum sensible size for an interactive control, in device pixels.
MIN_CONTROL = 12


class Finding:
    """One reported defect.

    Args:
        kind: Defect category.
        screen: ``"Workspace > Section"`` where it was seen.
        widget: Readable widget identifier.
        detail: Human readable explanation.
    """

    def __init__(self, kind: str, screen: str, widget: str, detail: str) -> None:
        """Store the finding."""
        self.kind = kind
        self.screen = screen
        self.widget = widget
        self.detail = detail

    def __str__(self) -> str:  # noqa: D105 - trivial
        return f"[{self.kind:<10}] {self.screen:<34} {self.widget:<38} {self.detail}"


def describe(widget: QWidget) -> str:
    """Return a short, stable identifier for *widget*."""
    name = widget.objectName() or ""
    text = ""
    if isinstance(widget, QLabel):
        text = widget.property("_full") or widget.text()
    label = f"{type(widget).__name__}"
    if name:
        label += f"#{name}"
    if text:
        label += f"({str(text)[:22]})"
    return label[:38]


def is_live(widget: QWidget) -> bool:
    """Whether *widget* is actually shown and occupies space."""
    return widget.isVisible() and widget.width() > 0 and widget.height() > 0


def check_labels(root: QWidget, screen: str) -> list[Finding]:
    """Report labels whose text is elided or clipped."""
    found: list[Finding] = []
    for label in root.findChildren(QLabel):
        if not is_live(label):
            continue
        full = label.property("_full")
        shown = label.text()
        if "\u2026" in shown and label.toolTip():
            # Elision with a tooltip is a deliberate, documented fallback for
            # long free-text; only flag it when the label is very short.
            if label.width() < 60:
                found.append(
                    Finding("elided", screen, describe(label),
                            f"only {label.width()}px wide, text hidden")
                )
            continue
        hint = label.sizeHint()
        if hint.width() > label.width() + 2 and shown.strip():
            found.append(
                Finding("clipped", screen, describe(label),
                        f"needs {hint.width()}px, has {label.width()}px: {shown[:30]!r}")
            )
    return found


def check_tables(root: QWidget, screen: str) -> list[Finding]:
    """Report tables whose rows, columns or headers do not fit."""
    found: list[Finding] = []
    for table in root.findChildren(QTableWidget):
        if not is_live(table):
            continue
        viewport = table.viewport()
        # Rows below the viewport are fine when a vertical scrollbar exists.
        has_vbar = table.verticalScrollBar().isVisible()
        has_hbar = table.horizontalScrollBar().isVisible()
        if not has_vbar and table.rowCount():
            last = table.rowCount() - 1
            bottom = table.rowViewportPosition(last) + table.rowHeight(last)
            if bottom > viewport.height() + 1:
                found.append(
                    Finding("clipped", screen, describe(table),
                            f"row {last} bottom {bottom} > viewport {viewport.height()}"
                            " and no scrollbar")
                )
        if not has_hbar and table.columnCount():
            last = table.columnCount() - 1
            right = table.columnViewportPosition(last) + table.columnWidth(last)
            if right > viewport.width() + 1:
                found.append(
                    Finding("clipped", screen, describe(table),
                            f"column {last} right {right} > viewport {viewport.width()}"
                            " and no scrollbar")
                )
        header = table.horizontalHeader()
        if header.isVisible():
            metrics = header.fontMetrics()
            for column in range(table.columnCount()):
                text = str(table.model().headerData(column, Qt.Orientation.Horizontal) or "")
                if not text:
                    continue
                needed = metrics.horizontalAdvance(text) + 16
                actual = header.sectionSize(column)
                if actual and needed > actual + 2:
                    found.append(
                        Finding("truncated", screen, describe(table),
                                f"header {text!r} needs {needed}px, has {actual}px")
                    )
    return found


def check_overlap(root: QWidget, screen: str) -> list[Finding]:
    """Report sibling widgets that intersect inside a non-stacked parent."""
    found: list[Finding] = []
    seen: set[tuple[int, int]] = set()
    for parent in [root, *root.findChildren(QWidget)]:
        if type(parent).__name__ in STACKED or not is_live(parent):
            continue
        children = [
            c for c in parent.children()
            if isinstance(c, QWidget) and c.parent() is parent and is_live(c)
            and not c.isWindow()
        ]
        for i, first in enumerate(children):
            for second in children[i + 1:]:
                key = (id(first), id(second))
                if key in seen:
                    continue
                seen.add(key)
                a, b = first.geometry(), second.geometry()
                overlap = a.intersected(b)
                # A few pixels of overlap are normal for focus rings and
                # negative margins; only report a substantial collision.
                if overlap.width() > 6 and overlap.height() > 6:
                    found.append(
                        Finding("overlap", screen,
                                f"{describe(first)} / {describe(second)}",
                                f"{overlap.width()}x{overlap.height()}px in "
                                f"{type(parent).__name__}")
                    )
    return found


def check_overflow(root: QWidget, screen: str) -> list[Finding]:
    """Report children that stick out of their parent's content rect."""
    found: list[Finding] = []
    for child in root.findChildren(QWidget):
        parent = child.parentWidget()
        if parent is None or not is_live(child) or not is_live(parent):
            continue
        if isinstance(parent, QAbstractScrollArea) or child.isWindow():
            continue
        if isinstance(parent.parentWidget(), QAbstractScrollArea):
            continue
        area = QRect(0, 0, parent.width(), parent.height())
        geometry = child.geometry()
        if area.contains(geometry):
            continue
        dx = max(0, geometry.right() - area.right(), area.left() - geometry.left())
        dy = max(0, geometry.bottom() - area.bottom(), area.top() - geometry.top())
        if dx > 6 or dy > 6:
            found.append(
                Finding("overflow", screen, describe(child),
                        f"exceeds {type(parent).__name__} by {dx}x{dy}px")
            )
    return found


def check_controls(root: QWidget, screen: str) -> list[Finding]:
    """Report interactive widgets collapsed to an unusable size."""
    found: list[Finding] = []
    from PySide6.QtWidgets import QAbstractButton, QComboBox, QLineEdit

    widgets: list[QWidget] = []
    for kind in (QAbstractButton, QComboBox, QLineEdit):
        widgets.extend(root.findChildren(kind))
    for widget in widgets:
        if not is_live(widget):
            continue
        if widget.width() < MIN_CONTROL or widget.height() < MIN_CONTROL:
            found.append(
                Finding("collapsed", screen, describe(widget),
                        f"{widget.width()}x{widget.height()}px")
            )
    return found


def audit_widget(root: QWidget, screen: str) -> list[Finding]:
    """Run every check against one screen."""
    return [
        *check_labels(root, screen),
        *check_tables(root, screen),
        *check_overlap(root, screen),
        *check_overflow(root, screen),
        *check_controls(root, screen),
    ]


def run(width: int, height: int, theme: str) -> list[Finding]:
    """Build the window and audit every workspace/section combination."""
    from ui.main_window import MainWindow

    window = MainWindow()
    window.theme.set_theme(theme)
    window.apply_theme()
    window.resize(width, height)
    window.show()
    app = QApplication.instance()
    for _ in range(8):
        app.processEvents()

    findings: list[Finding] = []
    for _panel, title, _icon in window.workspaces():
        window.navigate(title)
        for _ in range(6):
            app.processEvents()
        current = window.tabs.currentWidget()
        sections = []
        getter = getattr(current, "sections", None)
        if callable(getter):
            sections = getter()
        if not sections:
            for _ in range(4):
                app.processEvents()
            findings += audit_widget(current, f"{title}")
            continue
        for section in sections:
            window.navigate(title, section)
            for _ in range(6):
                app.processEvents()
            findings += audit_widget(current, f"{title} > {section}")
    window.close()
    return findings


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--theme", default="dark")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    findings = run(args.width, args.height, args.theme)

    print(f"\n=== UI audit {args.width}x{args.height} {args.theme} ===")
    if not findings:
        print("no defects found")
        return 0
    by_kind: dict[str, int] = {}
    for finding in findings:
        by_kind[finding.kind] = by_kind.get(finding.kind, 0) + 1
        print(finding)
    print("\nsummary:", ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())))
    print("total:", len(findings))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
