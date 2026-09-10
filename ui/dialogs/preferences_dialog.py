"""Application preferences dialog.

A modal wrapper around the settings pages of
:mod:`ui.panels.settings_panel`, offering the usual OK / Cancel / Apply
semantics: changes are only written to the configuration when the operator
applies them, and Cancel restores the values captured on open.

Example:
    >>> from ui.dialogs.preferences_dialog import PAGES, changed_paths
    >>> [title for title, _ in PAGES][0]
    'General'
    >>> changed_paths({"ui.theme": "dark"}, {"ui.theme": "light"})
    ['ui.theme']
    >>> changed_paths({"a": 1}, {"a": 1})
    []
"""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.configuration_manager import ConfigurationManager, get_config

from ..dpi_scaler import DPIScaler
from ..panels.settings_panel.display_settings import DisplaySettingsPage
from ..panels.settings_panel.general_settings import GeneralSettingsPage
from ..panels.settings_panel.logging_settings import LoggingSettingsPage
from ..panels.settings_panel.plugin_settings import PluginSettingsPage
from ..panels.settings_panel.protocol_settings import ProtocolSettingsPage

__all__ = ["PAGES", "PreferencesDialog", "changed_paths"]

#: The pages of the dialog as ``(title, page class)`` pairs.
PAGES: tuple[tuple[str, type], ...] = (
    ("General", GeneralSettingsPage),
    ("Protocols", ProtocolSettingsPage),
    ("Display", DisplaySettingsPage),
    ("Logging", LoggingSettingsPage),
    ("Plugins", PluginSettingsPage),
)


def changed_paths(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    """Return the configuration paths whose value differs.

    Args:
        before: Values captured when the dialog opened.
        after: Values currently held by the editors.

    Returns:
        The differing paths, sorted alphabetically.

    Example:
        >>> changed_paths({"a": 1, "b": 2}, {"a": 9, "b": 2})
        ['a']
    """
    return sorted(path for path, value in after.items() if before.get(path) != value)


class PreferencesDialog(QDialog):
    """Modal preferences dialog with a category list and stacked pages.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        config: Configuration manager backing every page.

    Attributes:
        pages: ``{title: page}`` for every category.
        applied: The values written by the last :meth:`apply` call.
    """

    #: Emitted with ``{path: value}`` after the settings were applied.
    settings_applied = Signal(dict)
    #: Emitted with the new theme name when the theme changed.
    theme_changed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        config: ConfigurationManager | None = None,
    ) -> None:
        """Build the category list, the stacked pages and the button box."""
        super().__init__(parent)
        self.scaler = scaler or DPIScaler()
        self.config = config or get_config()
        self.applied: dict[str, Any] = {}

        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.setMinimumSize(self.scaler.px(760), self.scaler.px(560))

        self.categories = QListWidget(self)
        self.categories.setMaximumWidth(self.scaler.px(180))
        self.stack = QStackedWidget(self)
        self.pages: dict[str, Any] = {}

        for title, page_class in PAGES:
            page = page_class(self, self.scaler, self.config)
            self.pages[title] = page
            self.categories.addItem(title)
            self.stack.addWidget(page)
        self.categories.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.categories.setCurrentRow(0)

        self._initial = self.values()

        self.status_label = QLabel("no change", self)
        self.status_label.setProperty("role", "secondary")

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.RestoreDefaults,
            self,
        )
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self._on_reject)
        apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        if apply_button is not None:
            apply_button.clicked.connect(self.apply)
        restore_button = self.buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        if restore_button is not None:
            restore_button.clicked.connect(self.restore_defaults)

        body = QHBoxLayout()
        body.setSpacing(self.scaler.spacing(8))
        body.addWidget(self.categories)
        body.addWidget(self.stack, 1)

        layout = QVBoxLayout(self)
        layout.setSpacing(self.scaler.spacing(8))
        layout.addLayout(body, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.buttons)

    # -- API -----------------------------------------------------------------
    def values(self) -> dict[str, Any]:
        """Return ``{path: value}`` across every page."""
        result: dict[str, Any] = {}
        for page in self.pages.values():
            result.update(page.values())
        return result

    def pending_changes(self) -> list[str]:
        """Return the paths that differ from the values captured on open."""
        return changed_paths(self._initial, self.values())

    def show_page(self, title: str) -> bool:
        """Activate the category *title*.

        Returns:
            ``True`` when the category exists.
        """
        items = self.categories.findItems(title, Qt.MatchFlag.MatchExactly)
        if not items:
            return False
        self.categories.setCurrentRow(self.categories.row(items[0]))
        return True

    def apply(self) -> dict[str, Any]:
        """Write every page value into the configuration."""
        changes = self.pending_changes()
        values = self.values()
        self.config.update(values)
        self.applied = values
        self._initial = dict(values)
        self.status_label.setText(
            f"{len(changes)} setting(s) applied" if changes else "no change"
        )
        self.settings_applied.emit(values)
        if "ui.theme" in changes:
            self.theme_changed.emit(str(values.get("ui.theme", "dark")))
        return values

    def restore_defaults(self) -> None:
        """Reload the shipped defaults into every page."""
        self.config.reset_to_defaults()
        for page in self.pages.values():
            page.reload()
        self.status_label.setText("defaults restored - press Apply to keep them")

    def save(self) -> None:
        """Apply the settings and write them to disk."""
        self.apply()
        self.config.save()

    # -- internals ------------------------------------------------------------
    def _on_accept(self) -> None:
        """Apply, persist and close the dialog."""
        self.save()
        self.accept()

    def _on_reject(self) -> None:
        """Discard the pending edits and close the dialog."""
        for page in self.pages.values():
            page.reload()
        self.reject()
