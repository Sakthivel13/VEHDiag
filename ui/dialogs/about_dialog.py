"""About dialog."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.utils.platform_utils import system_info

from ..dpi_scaler import DPIScaler
from ..styles.style_constants import FontRole

#: Application version shown in the dialog.
VERSION = "0.1.0"


class AboutDialog(QDialog):
    """Shows the version, the environment and the licence.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
    """

    def __init__(self, parent: QWidget | None = None, scaler: DPIScaler | None = None) -> None:
        """Build the dialog."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.setWindowTitle("About the Vehicle Diagnostics Platform")
        self.setMinimumWidth(self.scaler.px(520))

        title = QLabel("Vehicle Diagnostics Platform", self)
        title.setProperty("role", "heading")
        subtitle = QLabel(f"Version {VERSION}", self)
        subtitle.setProperty("role", "secondary")

        tabs = QTabWidget(self)
        tabs.addTab(self._text_page(self._about_text()), "About")
        tabs.addTab(self._text_page(self._environment_text()), "Environment")
        tabs.addTab(self._text_page(self._license_text()), "Licence")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.scaler.spacing(8))
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(tabs, 1)
        layout.addWidget(buttons)

    def _text_page(self, text: str) -> QPlainTextEdit:
        """Return a read-only text page."""
        view = QPlainTextEdit(text, self)
        view.setReadOnly(True)
        view.setProperty("role", "mono")
        return view

    def _about_text(self) -> str:
        """Return the feature summary."""
        return (
            "A professional, cross-platform vehicle diagnostics platform.\n\n"
            "Protocols : CAN, CAN FD, K-Line (ISO 9141 / KWP2000), LIN, FlexRay,\n"
            "            DoIP (ISO 13400) and SAE J1939\n"
            "Diagnostics: full UDS (ISO 14229) service set with ISO-TP transport\n"
            "Hardware  : PEAK PCAN, Vector, Kvaser, IntrepidCS, SocketCAN and a\n"
            "            built-in virtual VCI with an ECU simulator\n"
            "Tooling   : developer mode with scripted test sequences, response\n"
            "            slicing, multi-format conversion and flash programming\n"
        )

    def _environment_text(self) -> str:
        """Return the runtime environment description."""
        info = system_info()
        try:
            from PySide6 import __version__ as pyside_version
            from PySide6.QtCore import qVersion

            info["PySide6"] = pyside_version
            info["Qt"] = qVersion()
        except Exception:  # noqa: BLE001 - best effort
            pass
        width = max(len(key) for key in info)
        return "\n".join(f"{key.ljust(width)} : {value}" for key, value in info.items())

    def _license_text(self) -> str:
        """Return the licence text."""
        return (
            "MIT License\n\n"
            "Copyright (c) 2026 Vehicle Diagnostics Platform Team\n\n"
            "Permission is hereby granted, free of charge, to any person obtaining a\n"
            "copy of this software and associated documentation files (the \"Software\"),\n"
            "to deal in the Software without restriction, including without limitation\n"
            "the rights to use, copy, modify, merge, publish, distribute, sublicense,\n"
            "and/or sell copies of the Software.\n\n"
            "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND."
        )


__all__ = ["AboutDialog", "VERSION"]
