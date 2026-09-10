"""Settings panel with one tab per configuration section."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.configuration_manager import ConfigurationManager, get_config

from ...dpi_scaler import DPIScaler
from ...widgets.responsive_widget import ResponsiveWidget
from ...widgets.scalable_button import ScalableButton
from ...widgets.scalable_label import HeadingLabel
from ...widgets.tab_widget_enhanced import EnhancedTabWidget
from ...styles.layout_helpers import tune_form


class SettingsMainPanel(ResponsiveWidget):
    """Edits the application configuration.

    Every control is bound to a dotted configuration path, so adding a setting
    only requires one line in the corresponding ``_build_*`` method.

    Args:
        parent: Parent widget.
        scaler: Shared DPI scaler.
        config: Configuration manager to read from and write to.
    """

    #: Emitted with ``{path: value}`` when the operator applies the settings.
    settings_applied = Signal(dict)
    #: Emitted when the operator restores the defaults.
    defaults_restored = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        scaler: DPIScaler | None = None,
        config: ConfigurationManager | None = None,
    ) -> None:
        """Build every settings tab from the configuration."""
        super().__init__(parent, scaler)
        self.config = config or get_config()
        self.editors: dict[str, QWidget] = {}

        self.tabs = EnhancedTabWidget(self, self.scaler, level="sub")
        self.tabs.add_panel(self._scrollable(self._build_general()), "General", "settings")
        self.tabs.add_panel(self._scrollable(self._build_protocols()), "Protocols", "connect")
        self.tabs.add_panel(self._scrollable(self._build_diagnostics()), "Diagnostics", "ecu")
        self.tabs.add_panel(self._scrollable(self._build_display()), "Display", "theme")
        self.tabs.add_panel(self._scrollable(self._build_logging()), "Logging", "log")
        self.tabs.add_panel(self._scrollable(self._build_plugins()), "Plugins", "plugin")

        self.apply_button = ScalableButton("Apply", "success", self, self.scaler, accent=True)
        self.apply_button.clicked.connect(self.apply)
        self.reset_button = ScalableButton("Restore defaults", "refresh", self, self.scaler)
        self.reset_button.clicked.connect(self.restore_defaults)
        self.save_button = ScalableButton("Save to disk", "save", self, self.scaler)
        self.save_button.clicked.connect(self.save)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(self.spacing(8), self.spacing(8), self.spacing(8), self.spacing(8))
        layout.setSpacing(self.spacing(8))
        from ...widgets.breadcrumb_widget import BreadcrumbWidget

        self.breadcrumb = BreadcrumbWidget(self, self.scaler)
        self.breadcrumb.set_path("Settings", self.tabs.current_title())
        self.tabs.tab_title_activated.connect(
            lambda title: self.breadcrumb.set_path("Settings", title)
        )
        layout.addWidget(self.breadcrumb)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(buttons)

# -- navigation ------------------------------------------------------------
    def sections(self) -> list[str]:
        """Return every section title in tab bar order."""
        return self.tabs.titles()

    def show_view(self, title: str) -> bool:
        """Activate the section tab called *title*."""
        return self.tabs.select_by_title(title)

    def set_compact(self, compact: bool) -> None:
        """Collapse the section tabs to icons on narrow screens."""
        self.tabs.set_compact(compact)

    # -- builders ------------------------------------------------------------
    def _scrollable(self, widget: QWidget) -> QScrollArea:
        """Wrap *widget* into a scroll area."""
        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setWidget(widget)
        return area

    def _page(self, title: str) -> tuple[QWidget, QFormLayout]:
        """Return a page widget with a form layout inside a group box."""
        page = QWidget(self)
        outer = QVBoxLayout(page)
        box = QGroupBox(title, page)
        form = QFormLayout(box)
        tune_form(form, self.scaler)
        form.setSpacing(self.spacing(8))
        outer.addWidget(box)
        outer.addStretch(1)
        return page, form

    def _bind_bool(self, form: QFormLayout, label: str, path: str) -> None:
        """Add a checkbox bound to *path*."""
        widget = QCheckBox(self)
        widget.setChecked(bool(self.config.get(path, False)))
        form.addRow(label, widget)
        self.editors[path] = widget

    def _bind_int(self, form: QFormLayout, label: str, path: str, minimum: int, maximum: int,
                  suffix: str = "") -> None:
        """Add a spin box bound to *path*."""
        widget = QSpinBox(self)
        widget.setRange(minimum, maximum)
        widget.setValue(int(self.config.get(path, minimum)))
        if suffix:
            widget.setSuffix(suffix)
        form.addRow(label, widget)
        self.editors[path] = widget

    def _bind_text(self, form: QFormLayout, label: str, path: str) -> None:
        """Add a line edit bound to *path*."""
        widget = QLineEdit(str(self.config.get(path, "")), self)
        form.addRow(label, widget)
        self.editors[path] = widget

    def _bind_choice(self, form: QFormLayout, label: str, path: str, choices: list[str]) -> None:
        """Add a combo box bound to *path*."""
        widget = QComboBox(self)
        widget.addItems(choices)
        current = str(self.config.get(path, choices[0] if choices else ""))
        index = widget.findText(current)
        if index >= 0:
            widget.setCurrentIndex(index)
        form.addRow(label, widget)
        self.editors[path] = widget

    def _build_general(self) -> QWidget:
        """Build the general settings page."""
        page, form = self._page("Application")
        self._bind_bool(form, "Start in developer mode", "application.developer_mode")
        self._bind_bool(form, "Reconnect to the last VCI at startup", "application.auto_connect_last")
        self._bind_bool(form, "Check for updates", "application.check_updates")
        self._bind_text(form, "Test script directory", "paths.test_scripts")
        self._bind_text(form, "Firmware directory", "paths.firmware")
        self._bind_text(form, "Export directory", "paths.exports")
        return page

    def _build_protocols(self) -> QWidget:
        """Build the protocol timing page."""
        page, form = self._page("CAN and ISO-TP")
        self._bind_int(form, "CAN bitrate", "protocols.can.bitrate", 5000, 1_000_000, " bit/s")
        self._bind_bool(form, "Use 29-bit identifiers", "protocols.can.extended_id")
        self._bind_bool(form, "Pad CAN frames", "protocols.can.padding_enabled")
        self._bind_int(form, "ISO-TP block size", "protocols.isotp.block_size", 0, 255)
        self._bind_int(form, "ISO-TP STmin", "protocols.isotp.st_min_ms", 0, 127, " ms")
        self._bind_int(form, "N_Bs timeout", "protocols.isotp.n_bs_timeout_ms", 100, 10000, " ms")
        self._bind_int(form, "N_Cr timeout", "protocols.isotp.n_cr_timeout_ms", 100, 10000, " ms")
        self._bind_text(form, "DoIP host", "protocols.doip.host")
        self._bind_int(form, "DoIP port", "protocols.doip.port", 1, 65535)
        self._bind_int(form, "K-Line baudrate", "protocols.kline.baudrate", 1200, 115200, " baud")
        return page

    def _build_diagnostics(self) -> QWidget:
        """Build the diagnostic timing page."""
        page, form = self._page("Diagnostic timing")
        self._bind_int(form, "P2 client", "diagnostics.p2_client_ms", 50, 10000, " ms")
        self._bind_int(form, "P2* client", "diagnostics.p2_star_client_ms", 500, 60000, " ms")
        self._bind_int(form, "S3 client", "diagnostics.s3_client_ms", 500, 30000, " ms")
        self._bind_int(form, "Maximum pending responses", "diagnostics.max_pending_responses", 1, 100)
        self._bind_bool(form, "Retry on busyRepeatRequest", "diagnostics.retry_on_busy")
        self._bind_int(form, "Maximum retries", "diagnostics.max_retries", 0, 10)
        self._bind_bool(form, "Tester present enabled", "diagnostics.tester_present_enabled")
        self._bind_int(form, "Tester present interval", "diagnostics.tester_present_interval_ms",
                       200, 10000, " ms")
        self._bind_bool(form, "Validate session requirements",
                        "diagnostics.validate_session_requirements")
        return page

    def _build_display(self) -> QWidget:
        """Build the display preferences page."""
        page, form = self._page("Appearance")
        self._bind_choice(form, "Theme", "ui.theme", ["dark", "light", "high_contrast"])
        self._bind_text(form, "Accent colour", "ui.accent_color")
        self._bind_text(form, "Font family", "ui.font_family")
        self._bind_text(form, "Monospace family", "ui.monospace_family")
        self._bind_int(form, "Base font size", "ui.base_font_pt", 8, 24, " pt")
        self._bind_bool(form, "Remember window geometry", "ui.remember_geometry")
        self._bind_bool(form, "Start maximised", "ui.start_maximized")
        self._bind_bool(form, "Show splash screen", "ui.show_splash")
        self._bind_bool(form, "Enable animations", "ui.animations_enabled")
        self._bind_int(form, "Toast timeout", "ui.toast_timeout_ms", 1000, 20000, " ms")
        return page

    def _build_logging(self) -> QWidget:
        """Build the logging configuration page."""
        page, form = self._page("Logging")
        self._bind_choice(form, "Level", "logging.level",
                          ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"])
        self._bind_bool(form, "Write a log file", "logging.log_to_file")
        self._bind_bool(form, "Write to the database", "logging.log_to_database")
        self._bind_text(form, "Log directory", "logging.directory")
        self._bind_int(form, "Maximum file size", "logging.max_file_size_mb", 1, 500, " MB")
        self._bind_int(form, "Backup files", "logging.backup_count", 0, 50)
        self._bind_int(form, "Retention", "logging.retention_days", 1, 365, " days")
        self._bind_bool(form, "Hide tester present traffic", "logging.hide_tester_present")
        return page

    def _build_plugins(self) -> QWidget:
        """Build the plugin management page."""
        page, form = self._page("Plugins")
        self._bind_bool(form, "Load plugins at startup", "plugins.enabled")
        self._bind_text(form, "Plugin directories (comma separated)", "plugins.directories")
        return page

    # -- API -----------------------------------------------------------------
    def values(self) -> dict[str, Any]:
        """Return ``{configuration path: value}`` for every editor."""
        result: dict[str, Any] = {}
        for path, widget in self.editors.items():
            if isinstance(widget, QCheckBox):
                result[path] = widget.isChecked()
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                result[path] = widget.value()
            elif isinstance(widget, QComboBox):
                result[path] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                result[path] = widget.text()
        return result

    def apply(self) -> dict[str, Any]:
        """Write every editor value into the configuration and emit it."""
        values = self.values()
        self.config.update(values)
        self.settings_applied.emit(values)
        return values

    def save(self) -> None:
        """Apply the settings and persist them to disk."""
        self.apply()
        self.config.save()

    def restore_defaults(self) -> None:
        """Reload the shipped defaults into the editors."""
        self.config.reset_to_defaults()
        for path, widget in self.editors.items():
            value = self.config.get(path)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(type(widget.value())(value or 0))
            elif isinstance(widget, QComboBox):
                index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value or ""))
        self.defaults_restored.emit()


__all__ = ["SettingsMainPanel"]
