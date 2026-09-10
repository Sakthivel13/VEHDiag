"""Shared layout rhythm helpers.

A professional interface is mostly consistency: the same gap between a label
and its editor, the same margin inside every card, the same alignment for
every form. These helpers centralise those decisions so a panel never has to
invent its own spacing.

All values are expressed in design pixels and scaled through the shared
:class:`~ui.dpi_scaler.DPIScaler`.

Example:
    >>> from ui.styles.layout_helpers import FORM_LABEL_GAP, FORM_ROW_GAP
    >>> FORM_LABEL_GAP, FORM_ROW_GAP
    (12, 8)
"""
from __future__ import annotations

from typing import Any

__all__ = [
    "CARD_MARGIN",
    "FORM_LABEL_GAP",
    "FORM_ROW_GAP",
    "SECTION_GAP",
    "TOOLBAR_GAP",
    "tune_form",
    "tune_layout",
]

#: Horizontal gap between a form label and its editor.
FORM_LABEL_GAP = 12

#: Vertical gap between two form rows.
FORM_ROW_GAP = 8

#: Gap between two sibling sections of a panel.
SECTION_GAP = 8

#: Gap between the buttons of a toolbar row.
TOOLBAR_GAP = 6

#: Margin inside a card or group box.
CARD_MARGIN = 12


def tune_form(form: Any, scaler: Any) -> Any:
    """Apply the shared form rhythm to *form*.

    Labels are right aligned against their editors, fields expand with the
    panel and rows never wrap, which keeps the caption and the control on the
    same visual line at every DPI.

    Args:
        form: The :class:`QFormLayout` to configure.
        scaler: The shared DPI scaler.

    Returns:
        The same *form*, so calls can be chained.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFormLayout

    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
    form.setHorizontalSpacing(scaler.spacing(FORM_LABEL_GAP))
    form.setVerticalSpacing(scaler.spacing(FORM_ROW_GAP))
    margin = scaler.spacing(6)
    form.setContentsMargins(margin, scaler.spacing(8), margin, margin)
    return form


def tune_layout(layout: Any, scaler: Any, margin: int = SECTION_GAP) -> Any:
    """Apply the shared section rhythm to a box layout.

    Args:
        layout: The :class:`QVBoxLayout` or :class:`QHBoxLayout` to configure.
        scaler: The shared DPI scaler.
        margin: Outer margin in design pixels.

    Returns:
        The same *layout*, so calls can be chained.
    """
    gap = scaler.spacing(margin)
    layout.setContentsMargins(gap, gap, gap, gap)
    layout.setSpacing(scaler.spacing(SECTION_GAP))
    return layout
