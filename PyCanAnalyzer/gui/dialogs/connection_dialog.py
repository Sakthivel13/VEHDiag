"""Connection Dialog for CAN Interfaces."""
import platform
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QLineEdit, QPushButton, QGroupBox, QFormLayout, QMessageBox,
                             QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt
from devices.devices import DeviceManager, SocketCANDevice, PCANDevice, VectorDevice, VirtualCANDevice, KvaserDevice, GVRETDevice


class ConnectionDialog(QDialog):
    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.current_interface = None
        self.setWindowTitle("CAN Connection Settings")
        self.setModal(True)
        self.resize(500, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Interface selection
        interface_group = QGroupBox("Interface Selection")
        interface_layout = QVBoxLayout(interface_group)

        self.interface_combo = QComboBox()
        # Don't connect signal yet
        # self.interface_combo.currentTextChanged.connect(self.on_interface_changed)

        # Add interfaces based on platform
        system = platform.system().lower()
        if system == "linux":
            self.interface_combo.addItem("SocketCAN", "socketcan")
        elif system == "windows":
            # On Windows, SocketCAN doesn't work, so we skip it
            # Add a note about Windows limitations
            note_label = QLabel("Note: On Windows, SocketCAN is not available.\nUse PCAN, Vector, or Virtual CAN interfaces.")
            note_label.setStyleSheet("color: blue; font-style: italic;")
            interface_layout.addWidget(note_label)
        else:
            # Other systems might support SocketCAN
            self.interface_combo.addItem("SocketCAN", "socketcan")

        # These should work on all platforms with proper drivers
        self.interface_combo.addItem("PCAN", "pcan")
        self.interface_combo.addItem("Vector", "vector")
        self.interface_combo.addItem("Kvaser", "kvaser")
        self.interface_combo.addItem("Virtual CAN", "virtual")
        self.interface_combo.addItem("GVRET", "gvret")

        if self.interface_combo.count() == 0:
            QMessageBox.warning(self, "No Interfaces", "No compatible CAN interfaces found for this platform.")
            self.accept()
            return

        interface_layout.addWidget(QLabel("Interface Type:"))
        interface_layout.addWidget(self.interface_combo)

        layout.addWidget(interface_group)

        # Connection settings
        self.settings_group = QGroupBox("Connection Settings")
        self.settings_layout = QFormLayout(self.settings_group)

        # Create all possible setting widgets with default values
        self.socketcan_channel = QLineEdit("can0")
        self.socketcan_channel.setPlaceholderText("e.g., can0, can1")

        self.pcan_channel = QLineEdit("PCAN_USBBUS1")
        self.pcan_channel.setPlaceholderText("e.g., PCAN_USBBUS1")

        self.vector_channel = QLineEdit("0")
        self.vector_channel.setPlaceholderText("Channel number (0, 1, 2...)")
        self.vector_app_name = QLineEdit("PyCANAnalyzer")
        self.vector_app_name.setPlaceholderText("Application name")

        self.kvaser_channel = QLineEdit("0")
        self.kvaser_channel.setPlaceholderText("Channel number (0, 1, 2...)")

        self.gvret_url = QLineEdit("http://localhost:18888")
        self.gvret_url.setPlaceholderText("http://hostname:port")

        self.bitrate = QLineEdit("500000")
        self.bitrate.setPlaceholderText("Bitrate in bps")

        # Virtual CAN interface widget
        self.virtual_channel = QLineEdit("vcan0")
        self.virtual_channel.setPlaceholderText("e.g., vcan0, vcan1")

        # Initially show first available interface settings
        if self.interface_combo.count() > 0:
            first_interface = self.interface_combo.itemData(0)
            self.update_settings_display(first_interface)

        layout.addWidget(self.settings_group)

        # Connection controls
        control_layout = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_device)
        control_layout.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Disconnect All")
        self.disconnect_btn.clicked.connect(self.disconnect_all)
        control_layout.addWidget(self.disconnect_btn)

        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.clicked.connect(self.refresh_status)
        control_layout.addWidget(self.refresh_btn)

        layout.addLayout(control_layout)

        # Status display
        status_group = QGroupBox("Connection Status")
        status_layout = QVBoxLayout(status_group)

        self.status_list = QListWidget()
        status_layout.addWidget(self.status_list)

        layout.addWidget(status_group)

        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        # Initial status refresh
        self.refresh_status()

        # Connect signals after everything is set up
        self.interface_combo.currentTextChanged.connect(self.on_interface_changed)

    def on_interface_changed(self, interface_name):
        interface_type = self.interface_combo.currentData()
        self.update_settings_display(interface_type)

    def update_settings_display(self, interface_type):
        # Clear all items from the layout
        while self.settings_layout.count() > 0:
            item = self.settings_layout.takeAt(0)
            if item.widget():
                item.widget().setVisible(False)

        # Hide all widgets first
        self.socketcan_channel.setVisible(False)
        self.pcan_channel.setVisible(False)
        self.vector_channel.setVisible(False)
        self.vector_app_name.setVisible(False)
        self.kvaser_channel.setVisible(False)
        self.gvret_url.setVisible(False)
        self.bitrate.setVisible(False)
        self.virtual_channel.setVisible(False)

        # Set default values based on interface type
        if interface_type == "socketcan":
            self.socketcan_channel.setText("can0")
            self.bitrate.setText("500000")
            self.settings_layout.addRow("Channel:", self.socketcan_channel)
            self.settings_layout.addRow("Bitrate:", self.bitrate)
            self.socketcan_channel.setVisible(True)
            self.bitrate.setVisible(True)

        elif interface_type == "pcan":
            self.pcan_channel.setText("PCAN_USBBUS1")
            self.bitrate.setText("500000")
            self.settings_layout.addRow("Channel:", self.pcan_channel)
            self.settings_layout.addRow("Bitrate:", self.bitrate)
            self.pcan_channel.setVisible(True)
            self.bitrate.setVisible(True)

        elif interface_type == "vector":
            self.vector_channel.setText("0")
            self.vector_app_name.setText("PyCANAnalyzer")
            self.bitrate.setText("500000")
            self.settings_layout.addRow("Channel:", self.vector_channel)
            self.settings_layout.addRow("Application Name:", self.vector_app_name)
            self.settings_layout.addRow("Bitrate:", self.bitrate)
            self.vector_channel.setVisible(True)
            self.vector_app_name.setVisible(True)
            self.bitrate.setVisible(True)

        elif interface_type == "kvaser":
            self.kvaser_channel.setText("0")
            self.bitrate.setText("500000")
            self.settings_layout.addRow("Channel:", self.kvaser_channel)
            self.settings_layout.addRow("Bitrate:", self.bitrate)
            self.kvaser_channel.setVisible(True)
            self.bitrate.setVisible(True)

        elif interface_type == "gvret":
            self.gvret_url.setText("http://localhost:18888")
            self.bitrate.setText("500000")
            self.settings_layout.addRow("URL:", self.gvret_url)
            self.settings_layout.addRow("Bitrate:", self.bitrate)
            self.gvret_url.setVisible(True)
            self.bitrate.setVisible(True)

        elif interface_type == "virtual":
            self.virtual_channel.setText("vcan0")
            self.settings_layout.addRow("Channel:", self.virtual_channel)
            self.virtual_channel.setVisible(True)
            # Virtual doesn't need bitrate setting

    def connect_device(self):
        interface_type = self.interface_combo.currentData()

        try:
            if interface_type == "socketcan":
                channel = self.socketcan_channel.text().strip()
                if not channel:
                    QMessageBox.warning(self, "Error", "Please enter a channel name")
                    return
                device = SocketCANDevice(channel)

            elif interface_type == "pcan":
                channel = self.pcan_channel.text().strip()
                if not channel:
                    QMessageBox.warning(self, "Error", "Please enter a channel name")
                    return
                device = PCANDevice(channel)

            elif interface_type == "vector":
                try:
                    channel = int(self.vector_channel.text().strip())
                    app_name = self.vector_app_name.text().strip() or "PyCANAnalyzer"
                except ValueError:
                    QMessageBox.warning(self, "Error", "Channel must be a number")
                    return
                device = VectorDevice(channel, app_name)

            elif interface_type == "kvaser":
                try:
                    channel = int(self.kvaser_channel.text().strip())
                except ValueError:
                    QMessageBox.warning(self, "Error", "Channel must be a number")
                    return
                device = KvaserDevice(channel)

            elif interface_type == "gvret":
                url = self.gvret_url.text().strip()
                if not url:
                    QMessageBox.warning(self, "Error", "Please enter a GVRET URL")
                    return
                device = GVRETDevice(url)

            elif interface_type == "virtual":
                device = VirtualCANDevice()

            else:
                QMessageBox.warning(self, "Error", f"Unsupported interface: {interface_type}")
                return

            # Register and connect
            self.device_manager.register(device)
            self.device_manager.connect_all()

            QMessageBox.information(self, "Success", f"Connected to {interface_type.upper()}")
            self.refresh_status()

        except Exception as e:
            error_msg = f"Failed to connect: {str(e)}"
            if "socketcan" in str(e).lower():
                error_msg += "\n\nNote: SocketCAN is only available on Linux systems."
            QMessageBox.critical(self, "Connection Error", error_msg)

    def disconnect_all(self):
        try:
            self.device_manager.disconnect_all()
            QMessageBox.information(self, "Success", "Disconnected all devices")
            self.refresh_status()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to disconnect: {str(e)}")

    def refresh_status(self):
        self.status_list.clear()

        connected_count = len(self.device_manager.connected_devices)
        total_count = len(self.device_manager.devices)

        # Overall status
        status_item = QListWidgetItem(f"Connected: {connected_count}/{total_count} devices")
        if connected_count > 0:
            status_item.setBackground(Qt.green)
        else:
            status_item.setBackground(Qt.red)
        self.status_list.addItem(status_item)

        # Individual device status
        for i, device in enumerate(self.device_manager.devices):
            is_connected = device in self.device_manager.connected_devices
            device_name = type(device).__name__.replace('Device', '')
            status = "Connected" if is_connected else "Disconnected"
            color = Qt.green if is_connected else Qt.red

            item = QListWidgetItem(f"{device_name}: {status}")
            item.setBackground(color)
            self.status_list.addItem(item)