"""Logging and trace settings page.

Controls the severity threshold, the sinks (file, SQLite database, ASC/BLF
trace), the rotation policy and the retention window applied by
:meth:`~src.logging_system.log_database.LogDatabase.prune`.

Example:
    >>> from ui.panels.settings_panel.logging_settings import (
    ...     LEVELS, SETTINGS, estimate_disk_usage, paths)
    >>> LEVELS[0]
    'TRACE'
    >>> "logging.retention_days" in paths()
    True
    >>> estimate_disk_usage(10, 3)
    '40 MB maximum (1 active + 3 rotated files)'
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from src.core.configuration_manager import ConfigurationManager
from src.core.models.log_entry_model import LogLevel

from ...dpi_scaler import DPIScaler
from .general_settings import SettingSpec, SettingsPage

__all__ = ["LEVELS", "LoggingSettingsPage", "SETTINGS", "estimate_disk_usage", "paths"]

#: Severity names offered by the level drop-down.
LEVELS: tuple[str, ...] = tuple(level.name for level in LogLevel)

#: Every setting shown on the logging page.
SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec("logging.level", "Minimum level", "choice", choices=LEVELS),
    SettingSpec("logging.log_to_file", "Write a log file", "bool"),
    SettingSpec("logging.log_to_database", "Write to the SQLite database", "bool"),
    SettingSpec("logging.log_to_console", "Echo to the console", "bool"),
    SettingSpec("logging.directory", "Log directory"),
    SettingSpec(
        "logging.max_file_size_mb", "Maximum file size", "int",
        minimum=1, maximum=500, suffix=" MB",
    ),
    SettingSpec("logging.backup_count", "Rotated files kept", "int", minimum=0, maximum=50),
    SettingSpec(
        "logging.retention_days", "Database retention", "int",
        minimum=1, maximum=365, suffix=" days",
    ),
    SettingSpec(
        "logging.max_entries", "Maximum stored entries", "int",
        minimum=0, maximum=10_000_000,
        tooltip="Oldest entries are pruned beyond this count; 0 disables the limit.",
    ),
    SettingSpec("logging.hide_tester_present", "Hide tester present traffic", "bool"),
    SettingSpec("logging.timestamp_absolute", "Show absolute timestamps", "bool"),
    SettingSpec("logging.autoscroll", "Auto-scroll the log viewer", "bool"),
    SettingSpec(
        "logging.buffer_size", "In-memory buffer", "int",
        minimum=1000, maximum=1_000_000, suffix=" entries",
    ),
)


def paths() -> list[str]:
    """Return every configuration path edited by this page.

    Example:
        >>> "logging.level" in paths()
        True
    """
    return [spec.path for spec in SETTINGS]


def estimate_disk_usage(max_file_size_mb: int, backup_count: int) -> str:
    """Return the worst case disk usage of the rotating file handler.

    Example:
        >>> estimate_disk_usage(5, 0)
        '5 MB maximum (1 active + 0 rotated files)'
    """
    total = max_file_size_mb * (backup_count + 1)
    return f"{total} MB maximum (1 active + {backup_count} rotated files)"


class LoggingSettingsPage(SettingsPage):
    """The logging settings page.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        config: Configuration manager backing the editors.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        config: ConfigurationManager | None = None,
    ) -> None:
        """Build the page from :data:`SETTINGS`."""
        super().__init__(SETTINGS, "Logging", parent, scaler, config)

    def disk_usage(self) -> str:
        """Return the estimated worst case disk usage of the current values."""
        values = self.values()
        return estimate_disk_usage(
            int(values.get("logging.max_file_size_mb", 0) or 0),
            int(values.get("logging.backup_count", 0) or 0),
        )
