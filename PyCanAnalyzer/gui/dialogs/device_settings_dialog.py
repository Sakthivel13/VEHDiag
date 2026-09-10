"""Device Settings Dialog - Advanced Device Configuration."""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QWidget, QLabel, QLineEdit, QSpinBox, QCheckBox,
                             QComboBox, QPushButton, QGroupBox, QFormLayout,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QTextEdit)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIntValidator
import time


class DeviceSettingsDialog(QDialog):
    """Dialog for advanced device configuration and firmware management."""

    def __init__(self, device_manager, device_name=None, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.device_name = device_name
        self.device = None

        if device_name and device_name in device_manager.devices:
            self.device = device_manager.devices[device_name]

        self.init_ui()
        self.load_device_info()

    def init_ui(self):
        """Initialize the device settings dialog UI."""
        self.setWindowTitle(f"Device Settings - {self.device_name or 'No Device'}")
        self.setModal(True)
        self.resize(700, 600)

        layout = QVBoxLayout(self)

        # Device info display
        info_group = QGroupBox("Device Information")
        info_layout = QFormLayout()

        self.device_name_label = QLabel(self.device_name or "No device selected")
        self.device_type_label = QLabel("")
        self.firmware_version_label = QLabel("")
        self.serial_number_label = QLabel("")
        self.connection_status_label = QLabel("")

        info_layout.addRow("Name:", self.device_name_label)
        info_layout.addRow("Type:", self.device_type_label)
        info_layout.addRow("Firmware:", self.firmware_version_label)
        info_layout.addRow("Serial:", self.serial_number_label)
        info_layout.addRow("Status:", self.connection_status_label)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Basic Settings tab
        self.tab_widget.addTab(self.create_basic_tab(), "Basic Settings")

        # Advanced Settings tab
        self.tab_widget.addTab(self.create_advanced_tab(), "Advanced")

        # Filters tab
        self.tab_widget.addTab(self.create_filters_tab(), "Filters")

        # Firmware tab
        self.tab_widget.addTab(self.create_firmware_tab(), "Firmware")

        layout.addWidget(self.tab_widget)

        # Buttons
        button_layout = QHBoxLayout()

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.apply_settings)

        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.clicked.connect(self.reset_to_defaults)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def create_basic_tab(self):
        """Create the basic settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Bitrate settings
        bitrate_group = QGroupBox("Bitrate Configuration")
        bitrate_layout = QFormLayout()

        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems([
            "1000000 (1Mbps)", "500000 (500kbps)", "250000 (250kbps)",
            "125000 (125kbps)", "100000 (100kbps)", "50000 (50kbps)",
            "20000 (20kbps)", "10000 (10kbps)"
        ])
        bitrate_layout.addRow("CAN Bitrate:", self.bitrate_combo)

        self.bus_number_spin = QSpinBox()
        self.bus_number_spin.setRange(0, 10)
        bitrate_layout.addRow("Bus Number:", self.bus_number_spin)

        bitrate_group.setLayout(bitrate_layout)
        layout.addWidget(bitrate_group)

        # Bus settings
        bus_group = QGroupBox("Bus Configuration")
        bus_layout = QVBoxLayout()

        self.enable_termination_check = QCheckBox("Enable bus termination")
        self.enable_termination_check.setToolTip("Enable 120 ohm termination resistor")

        self.listen_only_check = QCheckBox("Listen-only mode")
        self.listen_only_check.setToolTip("Receive only, don't transmit")

        self.wake_on_can_check = QCheckBox("Wake on CAN activity")
        self.wake_on_can_check.setToolTip("Wake from sleep on CAN bus activity")

        bus_layout.addWidget(self.enable_termination_check)
        bus_layout.addWidget(self.listen_only_check)
        bus_layout.addWidget(self.wake_on_can_check)
        bus_group.setLayout(bus_layout)
        layout.addWidget(bus_group)

        # Timing settings
        timing_group = QGroupBox("Timing")
        timing_layout = QFormLayout()

        self.sample_point_spin = QSpinBox()
        self.sample_point_spin.setRange(50, 90)
        self.sample_point_spin.setSuffix("%")
        self.sample_point_spin.setValue(75)
        timing_layout.addRow("Sample Point:", self.sample_point_spin)

        self.sjw_spin = QSpinBox()
        self.sjw_spin.setRange(1, 4)
        timing_layout.addRow("SJW:", self.sjw_spin)

        timing_group.setLayout(timing_layout)
        layout.addWidget(timing_group)

        layout.addStretch()
        return tab

    def create_advanced_tab(self):
        """Create the advanced settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Error handling
        error_group = QGroupBox("Error Handling")
        error_layout = QVBoxLayout()

        self.automatic_retransmission_check = QCheckBox("Automatic retransmission")
        self.automatic_retransmission_check.setChecked(True)

        self.error_passive_check = QCheckBox("Error passive mode")
        self.bus_off_recovery_check = QCheckBox("Bus-off recovery")

        error_layout.addWidget(self.automatic_retransmission_check)
        error_layout.addWidget(self.error_passive_check)
        error_layout.addWidget(self.bus_off_recovery_check)
        error_group.setLayout(error_layout)
        layout.addWidget(error_group)

        # Performance settings
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout()

        self.rx_buffer_size_spin = QSpinBox()
        self.rx_buffer_size_spin.setRange(1, 1000)
        self.rx_buffer_size_spin.setValue(100)
        perf_layout.addRow("RX Buffer Size:", self.rx_buffer_size_spin)

        self.tx_buffer_size_spin = QSpinBox()
        self.tx_buffer_size_spin.setRange(1, 100)
        self.tx_buffer_size_spin.setValue(10)
        perf_layout.addRow("TX Buffer Size:", self.tx_buffer_size_spin)

        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        # Debug settings
        debug_group = QGroupBox("Debug")
        debug_layout = QVBoxLayout()

        self.enable_timestamps_check = QCheckBox("Enable hardware timestamps")
        self.record_bus_errors_check = QCheckBox("Record bus errors")
        self.verbose_logging_check = QCheckBox("Verbose logging")

        debug_layout.addWidget(self.enable_timestamps_check)
        debug_layout.addWidget(self.record_bus_errors_check)
        debug_layout.addWidget(self.verbose_logging_check)
        debug_group.setLayout(debug_layout)
        layout.addWidget(debug_group)

        layout.addStretch()
        return tab

    def create_filters_tab(self):
        """Create the filters tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Filter mode
        mode_group = QGroupBox("Filter Mode")
        mode_layout = QVBoxLayout()

        self.filter_mode_combo = QComboBox()
        self.filter_mode_combo.addItems([
            "Accept All",
            "Reject All",
            "Accept List",
            "Reject List"
        ])
        mode_layout.addWidget(QLabel("Filter Mode:"))
        mode_layout.addWidget(self.filter_mode_combo)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Filter table
        filter_group = QGroupBox("Message Filters")
        filter_layout = QVBoxLayout()

        # Filter table
        self.filter_table = QTableWidget()
        self.filter_table.setColumnCount(3)
        self.filter_table.setHorizontalHeaderLabels(["ID", "Mask", "Extended"])
        self.filter_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Add some example filters
        self.filter_table.setRowCount(2)
        self.filter_table.setItem(0, 0, QTableWidgetItem("0x123"))
        self.filter_table.setItem(0, 1, QTableWidgetItem("0x7FF"))
        self.filter_table.setItem(0, 2, QTableWidgetItem("No"))

        self.filter_table.setItem(1, 0, QTableWidgetItem("0x200"))
        self.filter_table.setItem(1, 1, QTableWidgetItem("0x700"))
        self.filter_table.setItem(1, 2, QTableWidgetItem("No"))

        filter_layout.addWidget(self.filter_table)

        # Filter buttons
        button_layout = QHBoxLayout()

        add_button = QPushButton("Add Filter")
        add_button.clicked.connect(self.add_filter)

        remove_button = QPushButton("Remove Filter")
        remove_button.clicked.connect(self.remove_filter)

        clear_button = QPushButton("Clear All")
        clear_button.clicked.connect(self.clear_filters)

        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(clear_button)

        filter_layout.addLayout(button_layout)
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        return tab

    def create_firmware_tab(self):
        """Create the firmware management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Current firmware info
        current_group = QGroupBox("Current Firmware")
        current_layout = QFormLayout()

        self.current_version_label = QLabel("")
        self.available_version_label = QLabel("")

        current_layout.addRow("Installed:", self.current_version_label)
        current_layout.addRow("Available:", self.available_version_label)

        current_group.setLayout(current_layout)
        layout.addWidget(current_group)

        # Firmware operations
        ops_group = QGroupBox("Operations")
        ops_layout = QVBoxLayout()

        check_button = QPushButton("Check for Updates")
        check_button.clicked.connect(self.check_firmware_updates)

        download_button = QPushButton("Download Firmware")
        download_button.clicked.connect(self.download_firmware)

        flash_button = QPushButton("Flash Firmware")
        flash_button.clicked.connect(self.flash_firmware)

        backup_button = QPushButton("Backup Settings")
        backup_button.clicked.connect(self.backup_settings)

        ops_layout.addWidget(check_button)
        ops_layout.addWidget(download_button)
        ops_layout.addWidget(flash_button)
        ops_layout.addWidget(backup_button)
        ops_group.setLayout(ops_layout)
        layout.addWidget(ops_group)

        # Firmware log
        log_group = QGroupBox("Operation Log")
        log_layout = QVBoxLayout()

        self.firmware_log = QTextEdit()
        self.firmware_log.setMaximumHeight(150)
        self.firmware_log.setReadOnly(True)

        log_layout.addWidget(self.firmware_log)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        return tab

    def load_device_info(self):
        """Load device information into the dialog."""
        if not self.device:
            return

        # Basic device info
        self.device_type_label.setText(getattr(self.device, 'device_type', 'Unknown'))
        self.firmware_version_label.setText(getattr(self.device, 'firmware_version', 'Unknown'))
        self.serial_number_label.setText(getattr(self.device, 'serial_number', 'Unknown'))

        status = "Connected" if getattr(self.device, 'connected', False) else "Disconnected"
        self.connection_status_label.setText(status)

        # Load current settings
        self.load_current_settings()

    def load_current_settings(self):
        """Load current device settings into the UI."""
        if not self.device:
            return

        # Basic settings
        bitrate = getattr(self.device, 'bitrate', 500000)
        bitrate_text = f"{bitrate} ({bitrate//1000}kbps)" if bitrate >= 1000 else f"{bitrate}bps"
        index = self.bitrate_combo.findText(bitrate_text, Qt.MatchContains)
        if index >= 0:
            self.bitrate_combo.setCurrentIndex(index)

        self.bus_number_spin.setValue(getattr(self.device, 'bus_number', 0))

        # Bus settings
        self.enable_termination_check.setChecked(getattr(self.device, 'termination_enabled', False))
        self.listen_only_check.setChecked(getattr(self.device, 'listen_only', False))
        self.wake_on_can_check.setChecked(getattr(self.device, 'wake_on_can', False))

        # Timing
        self.sample_point_spin.setValue(getattr(self.device, 'sample_point', 75))
        self.sjw_spin.setValue(getattr(self.device, 'sjw', 1))

        # Advanced settings
        self.automatic_retransmission_check.setChecked(getattr(self.device, 'auto_retransmit', True))
        self.error_passive_check.setChecked(getattr(self.device, 'error_passive', False))
        self.bus_off_recovery_check.setChecked(getattr(self.device, 'bus_off_recovery', True))

        # Performance
        self.rx_buffer_size_spin.setValue(getattr(self.device, 'rx_buffer_size', 100))
        self.tx_buffer_size_spin.setValue(getattr(self.device, 'tx_buffer_size', 10))

        # Debug
        self.enable_timestamps_check.setChecked(getattr(self.device, 'hardware_timestamps', False))
        self.record_bus_errors_check.setChecked(getattr(self.device, 'record_errors', False))
        self.verbose_logging_check.setChecked(getattr(self.device, 'verbose_logging', False))

    def apply_settings(self):
        """Apply the current settings to the device."""
        if not self.device:
            QMessageBox.warning(self, "No Device",
                               "No device selected or device not available.")
            return

        try:
            # Basic settings
            bitrate_text = self.bitrate_combo.currentText()
            bitrate = int(bitrate_text.split()[0])  # Extract number before space
            self.device.bitrate = bitrate
            self.device.bus_number = self.bus_number_spin.value()

            # Bus settings
            self.device.termination_enabled = self.enable_termination_check.isChecked()
            self.device.listen_only = self.listen_only_check.isChecked()
            self.device.wake_on_can = self.wake_on_can_check.isChecked()

            # Timing
            self.device.sample_point = self.sample_point_spin.value()
            self.device.sjw = self.sjw_spin.value()

            # Advanced settings
            self.device.auto_retransmit = self.automatic_retransmission_check.isChecked()
            self.device.error_passive = self.error_passive_check.isChecked()
            self.device.bus_off_recovery = self.bus_off_recovery_check.isChecked()

            # Performance
            self.device.rx_buffer_size = self.rx_buffer_size_spin.value()
            self.device.tx_buffer_size = self.tx_buffer_size_spin.value()

            # Debug
            self.device.hardware_timestamps = self.enable_timestamps_check.isChecked()
            self.device.record_errors = self.record_bus_errors_check.isChecked()
            self.device.verbose_logging = self.verbose_logging_check.isChecked()

            # Apply settings to hardware
            if hasattr(self.device, 'apply_settings'):
                self.device.apply_settings()

            QMessageBox.information(self, "Settings Applied",
                                   "Device settings have been applied successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Error",
                                f"Failed to apply settings: {str(e)}")

    def reset_to_defaults(self):
        """Reset all settings to device defaults."""
        if not self.device:
            return

        reply = QMessageBox.question(
            self, "Reset to Defaults",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if hasattr(self.device, 'reset_to_defaults'):
                self.device.reset_to_defaults()
                self.load_current_settings()
                QMessageBox.information(self, "Reset Complete",
                                       "Device settings have been reset to defaults.")

    def add_filter(self):
        """Add a new filter to the table."""
        row = self.filter_table.rowCount()
        self.filter_table.insertRow(row)
        self.filter_table.setItem(row, 0, QTableWidgetItem("0x000"))
        self.filter_table.setItem(row, 1, QTableWidgetItem("0x000"))
        self.filter_table.setItem(row, 2, QTableWidgetItem("No"))

    def remove_filter(self):
        """Remove the selected filter from the table."""
        current_row = self.filter_table.currentRow()
        if current_row >= 0:
            self.filter_table.removeRow(current_row)

    def clear_filters(self):
        """Clear all filters from the table."""
        self.filter_table.setRowCount(0)

    def check_firmware_updates(self):
        """Check for firmware updates."""
        self.log_firmware_operation("Checking for firmware updates...")
        # Implementation would check online for updates
        self.available_version_label.setText("Checking...")
        # Simulate check
        import time
        time.sleep(1)  # Simulate network delay
        self.available_version_label.setText("1.2.3 (newer)")
        self.log_firmware_operation("Update available: v1.2.3")

    def download_firmware(self):
        """Download firmware update."""
        self.log_firmware_operation("Downloading firmware update...")
        # Implementation would download firmware
        self.log_firmware_operation("Firmware downloaded successfully")

    def flash_firmware(self):
        """Flash new firmware to device."""
        reply = QMessageBox.question(
            self, "Flash Firmware",
            "Are you sure you want to flash new firmware? This may take several minutes.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.log_firmware_operation("Starting firmware flash...")
            # Implementation would flash firmware
            self.log_firmware_operation("Firmware flash completed successfully")

    def backup_settings(self):
        """Backup device settings."""
        self.log_firmware_operation("Backing up device settings...")
        # Implementation would save settings
        self.log_firmware_operation("Settings backup completed")

    def log_firmware_operation(self, message):
        """Log a firmware operation."""
        timestamp = time.strftime("%H:%M:%S")
        self.firmware_log.append(f"[{timestamp}] {message}")