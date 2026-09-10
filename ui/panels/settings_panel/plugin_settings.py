"""Plugin management settings page.

Lists the plugins discovered by :class:`~src.core.plugin_manager.PluginManager`,
lets the operator enable or disable them, add search directories and reload the
whole set without restarting the application.

Example:
    >>> from ui.panels.settings_panel.plugin_settings import (
    ...     COLUMNS, SETTINGS, parse_directories, plugin_row)
    >>> COLUMNS[0]
    'Plugin'
    >>> parse_directories(" ~/a , /opt/b ")
    ['~/a', '/opt/b']
    >>> parse_directories("")
    []
    >>> row = plugin_row({"name": "BMW", "version": "1.0", "identifier": "bmw"}, True)
    >>> row["Plugin"], row["Status"]
    ('BMW', 'loaded')
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.configuration_manager import ConfigurationManager
from src.core.plugin_manager import PluginManager

from ...dpi_scaler import DPIScaler
from ...widgets.scalable_button import ScalableButton
from ...widgets.table_widget_enhanced import EnhancedTableWidget
from .general_settings import SettingSpec, SettingsPage
from ...styles.semantic_colors import semantic

__all__ = [
    "COLUMNS",
    "PluginSettingsPage",
    "SETTINGS",
    "parse_directories",
    "paths",
    "plugin_row",
]

#: Column titles of the plugin table.
COLUMNS: list[str] = ["Plugin", "Version", "Identifier", "Status", "Description"]

#: Every setting shown on the plugin page.
SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec("plugins.enabled", "Load plugins at startup", "bool"),
    SettingSpec(
        "plugins.directories",
        "Plugin directories",
        tooltip="Comma separated list of directories scanned for plugins.",
    ),
    SettingSpec("plugins.allow_unsigned", "Allow unsigned plugins", "bool"),
    SettingSpec(
        "plugins.disabled",
        "Disabled plugins",
        tooltip="Comma separated list of plugin identifiers that must not load.",
    ),
)


def paths() -> list[str]:
    """Return every configuration path edited by this page.

    Example:
        >>> "plugins.enabled" in paths()
        True
    """
    return [spec.path for spec in SETTINGS]


def parse_directories(text: str) -> list[str]:
    """Split a comma separated directory list into its entries.

    Example:
        >>> parse_directories("a,,b")
        ['a', 'b']
    """
    return [part.strip() for part in text.split(",") if part.strip()]


def plugin_row(info: Mapping[str, Any], loaded: bool = True) -> dict[str, Any]:
    """Return the table row describing the plugin *info*.

    Args:
        info: The mapping returned by :meth:`PluginManager.describe`.
        loaded: Whether the plugin is currently loaded.

    Example:
        >>> plugin_row({"name": "X"}, False)["Status"]
        'disabled'
    """
    return {
        "Plugin": str(info.get("name", "unknown")),
        "Version": str(info.get("version", "-")),
        "Identifier": str(info.get("identifier", "-")),
        "Status": "loaded" if loaded else "disabled",
        "Description": str(info.get("description", "")),
        "_color": semantic("success") if loaded else semantic("muted"),
    }


class PluginSettingsPage(SettingsPage):
    """The plugin management page.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        config: Configuration manager backing the editors.
        manager: Plugin manager queried for the loaded plugins.

    Attributes:
        table: The discovered plugin table.
    """

    #: Emitted when the operator asks to reload every plugin.
    reload_requested = Signal()
    #: Emitted with the identifier when a plugin is enabled or disabled.
    plugin_toggled = Signal(str, bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        config: ConfigurationManager | None = None,
        manager: PluginManager | None = None,
    ) -> None:
        """Build the settings form plus the plugin table and its toolbar."""
        super().__init__(SETTINGS, "Plugins", parent, scaler, config)
        self.manager = manager

        self.table = EnhancedTableWidget(COLUMNS, self, self.scaler)
        self.status_label = QLabel("no plugin loaded", self)
        self.status_label.setProperty("role", "secondary")

        self.add_dir_button = ScalableButton("Add directory", "add", self, self.scaler)
        self.add_dir_button.clicked.connect(self.add_directory)
        self.reload_button = ScalableButton("Reload plugins", "refresh", self, self.scaler)
        self.reload_button.clicked.connect(self.reload_plugins)
        self.toggle_button = ScalableButton("Enable / disable", "plugin", self, self.scaler)
        self.toggle_button.clicked.connect(self.toggle_selected)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(self.spacing(4))
        toolbar.addWidget(self.add_dir_button)
        toolbar.addWidget(self.toggle_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.reload_button)

        container = QVBoxLayout()
        container.setSpacing(self.spacing(6))
        container.addLayout(toolbar)
        container.addWidget(self.table, 1)
        container.addWidget(self.status_label)
        holder = QWidget(self)
        holder.setLayout(container)

        layout = self.layout()
        if layout is not None:
            layout.addWidget(holder)

        self.refresh()

    # -- API -----------------------------------------------------------------
    def directories(self) -> list[str]:
        """Return the configured plugin search directories."""
        return parse_directories(str(self.values().get("plugins.directories", "")))

    def disabled_identifiers(self) -> list[str]:
        """Return the identifiers the operator has disabled."""
        return parse_directories(str(self.values().get("plugins.disabled", "")))

    def add_directory(self) -> str:
        """Ask for a directory and append it to the search path."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select a plugin directory", str(Path.home())
        )
        if not directory:
            return ""
        editor = self.editors["plugins.directories"]
        current = parse_directories(editor.text())
        if directory not in current:
            current.append(directory)
            editor.setText(", ".join(current))
        return directory

    def set_manager(self, manager: PluginManager) -> None:
        """Attach *manager* and refresh the table."""
        self.manager = manager
        self.refresh()

    def reload_plugins(self) -> int:
        """Reload every plugin through the manager.

        Returns:
            The number of plugins that are loaded afterwards.
        """
        self.reload_requested.emit()
        if self.manager is None:
            return 0
        self.manager.shutdown_all()
        loaded = self.manager.discover_and_load()
        self.refresh()
        return len(loaded)

    def toggle_selected(self) -> bool:
        """Enable or disable the plugin of the selected row."""
        rows = self.table.selected_rows()
        if not rows:
            return False
        identifier = str(rows[0]["Identifier"])
        disabled = self.disabled_identifiers()
        enabling = identifier in disabled
        if enabling:
            disabled.remove(identifier)
        else:
            disabled.append(identifier)
        self.editors["plugins.disabled"].setText(", ".join(disabled))
        self.plugin_toggled.emit(identifier, enabling)
        self.refresh()
        return enabling

    def refresh(self) -> None:
        """Rebuild the plugin table from the manager."""
        disabled = set(self.disabled_identifiers())
        infos: list[Mapping[str, Any]] = (
            list(self.manager.describe()) if self.manager is not None else []
        )
        self.table.set_rows(
            [
                plugin_row(info, str(info.get("identifier", "")) not in disabled)
                for info in infos
            ],
            color_key="_color",
        )
        self.status_label.setText(
            f"{len(infos)} plugin(s) discovered, {len(disabled)} disabled"
            if infos
            else "no plugin loaded"
        )
