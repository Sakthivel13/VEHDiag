"""Preferences Dialog - Application Settings."""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QWidget, QLabel, QLineEdit, QSpinBox, QCheckBox,
                             QComboBox, QPushButton, QGroupBox, QFormLayout,
                             QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import os


class PreferencesDialog(QDialog):
    """Dialog for configuring application preferences."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config.copy()  # Work with a copy
        self.original_config = config.copy()  # Keep original for comparison

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize the preferences dialog UI."""
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.resize(600, 500)

        layout = QVBoxLayout(self)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # General tab
        self.tab_widget.addTab(self.create_general_tab(), "General")

        # Display tab
        self.tab_widget.addTab(self.create_display_tab(), "Display")

        # Logging tab
        self.tab_widget.addTab(self.create_logging_tab(), "Logging")

        # Devices tab
        self.tab_widget.addTab(self.create_devices_tab(), "Devices")

        layout.addWidget(self.tab_widget)

        # Buttons
        button_layout = QHBoxLayout()

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)

        button_layout.addStretch()
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)

        layout.addLayout(button_layout)

    def create_general_tab(self):
        """Create the general settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Buffer settings
        buffer_group = QGroupBox("Frame Buffer")
        buffer_layout = QFormLayout()

        self.max_frames_spin = QSpinBox()
        self.max_frames_spin.setRange(1000, 1000000)
        self.max_frames_spin.setSingleStep(1000)
        buffer_layout.addRow("Maximum frames:", self.max_frames_spin)

        self.buffer_timeout_spin = QSpinBox()
        self.buffer_timeout_spin.setRange(0, 3600)
        self.buffer_timeout_spin.setSuffix(" seconds")
        buffer_layout.addRow("Buffer timeout:", self.buffer_timeout_spin)

        buffer_group.setLayout(buffer_layout)
        layout.addWidget(buffer_group)

        # Performance settings
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout()

        self.update_interval_spin = QSpinBox()
        self.update_interval_spin.setRange(10, 1000)
        self.update_interval_spin.setSingleStep(10)
        self.update_interval_spin.setSuffix(" ms")
        perf_layout.addRow("UI update interval:", self.update_interval_spin)

        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        # Auto-save settings
        autosave_group = QGroupBox("Auto-save")
        autosave_layout = QVBoxLayout()

        self.autosave_config_check = QCheckBox("Automatically save configuration on exit")
        self.autosave_config_check.setChecked(True)

        self.autosave_session_check = QCheckBox("Automatically save session on exit")

        autosave_layout.addWidget(self.autosave_config_check)
        autosave_layout.addWidget(self.autosave_session_check)
        autosave_group.setLayout(autosave_layout)
        layout.addWidget(autosave_group)

        layout.addStretch()
        return tab

    def create_display_tab(self):
        """Create the display settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Theme settings
        theme_group = QGroupBox("Appearance")
        theme_layout = QFormLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark"])
        theme_layout.addRow("Theme:", self.theme_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        theme_layout.addRow("Font size:", self.font_size_spin)

        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # Table settings
        table_group = QGroupBox("Frame Table")
        table_layout = QFormLayout()

        self.alternating_rows_check = QCheckBox("Alternating row colors")
        self.alternating_rows_check.setChecked(True)

        self.show_grid_check = QCheckBox("Show grid lines")

        self.auto_scroll_check = QCheckBox("Auto-scroll to bottom")
        self.auto_scroll_check.setChecked(True)

        table_layout.addRow(self.alternating_rows_check)
        table_layout.addRow(self.show_grid_check)
        table_layout.addRow(self.auto_scroll_check)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Graph settings
        graph_group = QGroupBox("Graphs")
        graph_layout = QFormLayout()

        self.graph_update_rate_spin = QSpinBox()
        self.graph_update_rate_spin.setRange(1, 100)
        self.graph_update_rate_spin.setSuffix(" Hz")
        graph_layout.addRow("Update rate:", self.graph_update_rate_spin)

        self.graph_buffer_size_spin = QSpinBox()
        self.graph_buffer_size_spin.setRange(100, 10000)
        self.graph_buffer_size_spin.setSingleStep(100)
        graph_layout.addRow("Buffer size:", self.graph_buffer_size_spin)

        graph_group.setLayout(graph_layout)
        layout.addWidget(graph_group)

        layout.addStretch()
        return tab

    def create_logging_tab(self):
        """Create the logging settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Default log settings
        default_group = QGroupBox("Default Settings")
        default_layout = QFormLayout()

        self.default_format_combo = QComboBox()
        self.default_format_combo.addItems(["CSV", "Parquet", "ASC", "BLF"])
        default_layout.addRow("Default format:", self.default_format_combo)

        self.default_directory_edit = QLineEdit()
        self.default_directory_edit.setPlaceholderText("Leave empty for current directory")

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_log_directory)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.default_directory_edit)
        dir_layout.addWidget(browse_button)
        default_layout.addRow("Default directory:", dir_layout)

        default_group.setLayout(default_layout)
        layout.addWidget(default_group)

        # Auto-logging settings
        autolog_group = QGroupBox("Auto-logging")
        autolog_layout = QVBoxLayout()

        self.autolog_on_connect_check = QCheckBox("Start logging when device connects")
        self.autolog_on_capture_check = QCheckBox("Start logging when capture begins")

        autolog_layout.addWidget(self.autolog_on_connect_check)
        autolog_layout.addWidget(self.autolog_on_capture_check)
        autolog_group.setLayout(autolog_layout)
        layout.addWidget(autolog_group)

        # Log rotation
        rotation_group = QGroupBox("Log Rotation")
        rotation_layout = QFormLayout()

        self.max_log_size_spin = QSpinBox()
        self.max_log_size_spin.setRange(1, 1000)
        self.max_log_size_spin.setSuffix(" MB")
        rotation_layout.addRow("Maximum size:", self.max_log_size_spin)

        self.max_log_files_spin = QSpinBox()
        self.max_log_files_spin.setRange(1, 100)
        rotation_layout.addRow("Maximum files:", self.max_log_files_spin)

        rotation_group.setLayout(rotation_layout)
        layout.addWidget(rotation_group)

        layout.addStretch()
        return tab

    def create_devices_tab(self):
        """Create the device settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Default device settings
        default_device_group = QGroupBox("Default Device Settings")
        default_device_layout = QFormLayout()

        self.default_bitrate_combo = QComboBox()
        self.default_bitrate_combo.addItems([
            "1000000", "500000", "250000", "125000", "100000", "50000", "20000"
        ])
        default_device_layout.addRow("Default bitrate:", self.default_bitrate_combo)

        self.default_bus_spin = QSpinBox()
        self.default_bus_spin.setRange(0, 10)
        default_device_layout.addRow("Default bus:", self.default_bus_spin)

        default_device_group.setLayout(default_device_layout)
        layout.addWidget(default_device_group)

        # Connection settings
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout()

        self.auto_reconnect_check = QCheckBox("Automatically reconnect on disconnection")
        self.auto_reconnect_check.setChecked(True)

        self.connection_timeout_spin = QSpinBox()
        self.connection_timeout_spin.setRange(1, 60)
        self.connection_timeout_spin.setSuffix(" seconds")
        self.connection_timeout_spin.setValue(10)

        timeout_layout = QFormLayout()
        timeout_layout.addRow("Connection timeout:", self.connection_timeout_spin)

        conn_layout.addWidget(self.auto_reconnect_check)
        conn_layout.addLayout(timeout_layout)
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # Hardware settings
        hw_group = QGroupBox("Hardware")
        hw_layout = QVBoxLayout()

        self.enable_termination_check = QCheckBox("Enable bus termination by default")
        self.verify_connection_check = QCheckBox("Verify connection after setup")
        self.verify_connection_check.setChecked(True)

        hw_layout.addWidget(self.enable_termination_check)
        hw_layout.addWidget(self.verify_connection_check)
        hw_group.setLayout(hw_layout)
        layout.addWidget(hw_group)

        layout.addStretch()
        return tab

    def browse_log_directory(self):
        """Open directory browser for log directory selection."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Default Log Directory",
            self.default_directory_edit.text() or ""
        )
        if directory:
            self.default_directory_edit.setText(directory)

    def load_settings(self):
        """Load current settings into the dialog."""
        # General settings
        self.max_frames_spin.setValue(self.config.get('max_frames', 10000))
        self.buffer_timeout_spin.setValue(self.config.get('buffer_timeout', 300))
        self.update_interval_spin.setValue(self.config.get('update_interval', 100))

        self.autosave_config_check.setChecked(self.config.get('autosave_config', True))
        self.autosave_session_check.setChecked(self.config.get('autosave_session', False))

        # Display settings
        self.theme_combo.setCurrentText(self.config.get('theme', 'System'))
        self.font_size_spin.setValue(self.config.get('font_size', 10))

        display = self.config.get('display', {})
        self.alternating_rows_check.setChecked(display.get('alternating_rows', True))
        self.show_grid_check.setChecked(display.get('show_grid', False))
        self.auto_scroll_check.setChecked(display.get('auto_scroll', True))

        graphs = self.config.get('graphs', {})
        self.graph_update_rate_spin.setValue(graphs.get('update_rate', 10))
        self.graph_buffer_size_spin.setValue(graphs.get('buffer_size', 1000))

        # Logging settings
        logging_config = self.config.get('logging', {})
        self.default_format_combo.setCurrentText(logging_config.get('default_format', 'CSV'))
        self.default_directory_edit.setText(logging_config.get('default_directory', ''))

        self.autolog_on_connect_check.setChecked(logging_config.get('autolog_on_connect', False))
        self.autolog_on_capture_check.setChecked(logging_config.get('autolog_on_capture', False))

        rotation = logging_config.get('rotation', {})
        self.max_log_size_spin.setValue(rotation.get('max_size_mb', 100))
        self.max_log_files_spin.setValue(rotation.get('max_files', 10))

        # Device settings
        devices = self.config.get('devices', {})
        self.default_bitrate_combo.setCurrentText(str(devices.get('default_bitrate', 500000)))
        self.default_bus_spin.setValue(devices.get('default_bus', 0))

        self.auto_reconnect_check.setChecked(devices.get('auto_reconnect', True))
        self.connection_timeout_spin.setValue(devices.get('connection_timeout', 10))

        self.enable_termination_check.setChecked(devices.get('enable_termination', False))
        self.verify_connection_check.setChecked(devices.get('verify_connection', True))

    def save_settings(self):
        """Save dialog settings to config."""
        # General settings
        self.config['max_frames'] = self.max_frames_spin.value()
        self.config['buffer_timeout'] = self.buffer_timeout_spin.value()
        self.config['update_interval'] = self.update_interval_spin.value()

        self.config['autosave_config'] = self.autosave_config_check.isChecked()
        self.config['autosave_session'] = self.autosave_session_check.isChecked()

        # Display settings
        self.config['theme'] = self.theme_combo.currentText()
        self.config['font_size'] = self.font_size_spin.value()

        if 'display' not in self.config:
            self.config['display'] = {}
        self.config['display']['alternating_rows'] = self.alternating_rows_check.isChecked()
        self.config['display']['show_grid'] = self.show_grid_check.isChecked()
        self.config['display']['auto_scroll'] = self.auto_scroll_check.isChecked()

        if 'graphs' not in self.config:
            self.config['graphs'] = {}
        self.config['graphs']['update_rate'] = self.graph_update_rate_spin.value()
        self.config['graphs']['buffer_size'] = self.graph_buffer_size_spin.value()

        # Logging settings
        if 'logging' not in self.config:
            self.config['logging'] = {}
        self.config['logging']['default_format'] = self.default_format_combo.currentText()
        self.config['logging']['default_directory'] = self.default_directory_edit.text()

        self.config['logging']['autolog_on_connect'] = self.autolog_on_connect_check.isChecked()
        self.config['logging']['autolog_on_capture'] = self.autolog_on_capture_check.isChecked()

        if 'rotation' not in self.config['logging']:
            self.config['logging']['rotation'] = {}
        self.config['logging']['rotation']['max_size_mb'] = self.max_log_size_spin.value()
        self.config['logging']['rotation']['max_files'] = self.max_log_files_spin.value()

        # Device settings
        if 'devices' not in self.config:
            self.config['devices'] = {}
        self.config['devices']['default_bitrate'] = int(self.default_bitrate_combo.currentText())
        self.config['devices']['default_bus'] = self.default_bus_spin.value()

        self.config['devices']['auto_reconnect'] = self.auto_reconnect_check.isChecked()
        self.config['devices']['connection_timeout'] = self.connection_timeout_spin.value()

        self.config['devices']['enable_termination'] = self.enable_termination_check.isChecked()
        self.config['devices']['verify_connection'] = self.verify_connection_check.isChecked()

    def apply_settings(self):
        """Apply the current settings."""
        self.save_settings()
        # Here you would typically save to file and notify the application
        QMessageBox.information(self, "Settings Applied",
                               "Settings have been applied successfully.")

    def accept(self):
        """Handle OK button - save and close."""
        self.save_settings()
        super().accept()

    def reject(self):
        """Handle Cancel button - restore original config."""
        self.config = self.original_config.copy()
        super().reject()

    def get_config(self):
        """Get the updated configuration.

        Returns:
            Updated configuration dictionary
        """
        return self.config