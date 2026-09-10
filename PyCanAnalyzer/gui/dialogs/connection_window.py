"""CAN Connection Settings Window with Status.

Opens via Connection menu -> Open Connection Window.
Shows connection configuration AND live connection status.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QLineEdit, QGroupBox,
                             QGridLayout, QTableWidget, QTableWidgetItem,
                             QHeaderView, QWidget, QCheckBox, QSpinBox,
                             QTabWidget, QTextEdit, QMessageBox, QFrame)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
import datetime


class ConnectionWindow(QDialog):
    """CAN Connection Settings with live Status.

    Tab 1: Connection Settings (interface, channel, bitrate, modes)
    Tab 2: Active Connections with status table
    Tab 3: Connection Log
    """

    connection_changed = pyqtSignal()

    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.setWindowTitle("CAN Connection Settings")
        self.setMinimumSize(700, 550)
        self.resize(800, 600)
        self.setModal(True)
        self.init_ui()
        self.refresh_status()

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(1000)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # ── Status Bar at Top ──
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.StyledPanel)
        status_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
                background-color: #1a1a2e;
            }
        """)
        status_layout = QHBoxLayout(status_frame)

        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("font-size: 20px; color: #e74c3c;")
        status_layout.addWidget(self.status_indicator)

        self.status_title = QLabel("Disconnected")
        self.status_title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e74c3c;"
        )
        status_layout.addWidget(self.status_title)

        self.status_detail = QLabel("No active connections")
        self.status_detail.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self.status_detail)

        status_layout.addStretch()
        main_layout.addWidget(status_frame)

        # ── Tabs ──
        self.tabs = QTabWidget()

        # Tab 1: Connection Settings
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)

        config_group = QGroupBox("Interface Configuration")
        config_grid = QGridLayout(config_group)
        config_grid.setSpacing(8)

        config_grid.addWidget(QLabel("Interface:"), 0, 0)
        self.interface_combo = QComboBox()
        self.interface_combo.addItems([
            "socketcan", "pcan", "kvaser", "vector",
            "ixxat", "usb2can", "serial", "slcan", "virtual"
        ])
        self.interface_combo.currentTextChanged.connect(self._update_channels)
        config_grid.addWidget(self.interface_combo, 0, 1)

        config_grid.addWidget(QLabel("Channel:"), 1, 0)
        self.channel_combo = QComboBox()
        self.channel_combo.setEditable(True)
        self.channel_combo.addItems(["can0", "can1", "vcan0"])
        config_grid.addWidget(self.channel_combo, 1, 1)

        config_grid.addWidget(QLabel("Bitrate:"), 2, 0)
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.setEditable(True)
        self.bitrate_combo.addItems([
            "125000", "250000", "500000", "1000000"
        ])
        self.bitrate_combo.setCurrentText("500000")
        config_grid.addWidget(self.bitrate_combo, 2, 1)

        config_grid.addWidget(QLabel("CAN FD:"), 3, 0)
        self.fd_check = QCheckBox("Enable")
        config_grid.addWidget(self.fd_check, 3, 1)

        config_grid.addWidget(QLabel("Listen Only:"), 4, 0)
        self.listen_check = QCheckBox("Enable")
        config_grid.addWidget(self.listen_check, 4, 1)

        settings_layout.addWidget(config_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        connect_btn = QPushButton("Connect")
        connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; border: none;
                border-radius: 4px; padding: 8px 24px;
                font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        connect_btn.clicked.connect(self._connect)
        btn_layout.addWidget(connect_btn)

        disconnect_btn = QPushButton("Disconnect All")
        disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #c0392b; color: white; border: none;
                border-radius: 4px; padding: 8px 24px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e74c3c; }
        """)
        disconnect_btn.clicked.connect(self._disconnect_all)
        btn_layout.addWidget(disconnect_btn)

        btn_layout.addStretch()
        settings_layout.addLayout(btn_layout)
        settings_layout.addStretch()

        self.tabs.addTab(settings_tab, "Settings")

        # Tab 2: Status
        status_tab = QWidget()
        status_tab_layout = QVBoxLayout(status_tab)

        self.conn_table = QTableWidget()
        self.conn_table.setColumnCount(5)
        self.conn_table.setHorizontalHeaderLabels([
            "Status", "Interface", "Channel", "Bitrate", "Frames"
        ])
        self.conn_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.conn_table.setAlternatingRowColors(True)
        self.conn_table.verticalHeader().setVisible(False)
        status_tab_layout.addWidget(self.conn_table)

        self.tabs.addTab(status_tab, "Status")

        # Tab 3: Log
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', monospace; font-size: 11px;
            }
        """)
        log_layout.addWidget(self.log_text)
        self.tabs.addTab(log_tab, "Log")

        main_layout.addWidget(self.tabs)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setMinimumSize(80, 32)
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)
        main_layout.addLayout(close_layout)

    def _update_channels(self, interface):
        self.channel_combo.clear()
        channels = {
            "socketcan": ["can0", "can1", "vcan0"],
            "pcan": ["PCAN_USBBUS1", "PCAN_USBBUS2"],
            "kvaser": ["0", "1"],
            "vector": ["0", "1"],
            "serial": ["/dev/ttyUSB0", "COM3"],
            "slcan": ["/dev/ttyUSB0", "COM3"],
            "virtual": ["vcan0"],
        }
        self.channel_combo.addItems(channels.get(interface, ["0"]))

    def _log(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.append(f"[{ts}] {msg}")

    def _connect(self):
        interface = self.interface_combo.currentText()
        channel = self.channel_combo.currentText()
        bitrate = int(self.bitrate_combo.currentText())
        self._log(f"Connecting {interface}:{channel} @ {bitrate}...")

        try:
            if hasattr(self.device_manager, 'connect'):
                self.device_manager.connect(
                    interface=interface, channel=channel, bitrate=bitrate
                )
            elif hasattr(self.device_manager, 'add_device'):
                self.device_manager.add_device(interface, channel, bitrate)

            self._log(f"Connected to {interface}:{channel}")
            self.refresh_status()
            self.connection_changed.emit()
        except Exception as e:
            self._log(f"Failed: {e}")
            QMessageBox.critical(self, "Error", f"Connection failed:\n{e}")

    def _disconnect_all(self):
        self._log("Disconnecting all...")
        try:
            if hasattr(self.device_manager, 'disconnect_all'):
                self.device_manager.disconnect_all()
            self._log("All disconnected")
            self.refresh_status()
            self.connection_changed.emit()
        except Exception as e:
            self._log(f"Error: {e}")

    def refresh_status(self):
        devices = []
        if hasattr(self.device_manager, 'connected_devices'):
            devices = list(self.device_manager.connected_devices)

        count = len(devices)
        if count > 0:
            self.status_indicator.setStyleSheet("font-size: 20px; color: #2ecc71;")
            self.status_title.setText(f"Connected ({count})")
            self.status_title.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #2ecc71;"
            )
            self.status_detail.setText(f"{count} active connection(s)")
        else:
            self.status_indicator.setStyleSheet("font-size: 20px; color: #e74c3c;")
            self.status_title.setText("Disconnected")
            self.status_title.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #e74c3c;"
            )
            self.status_detail.setText("No active connections")

        self.conn_table.setRowCount(0)
        for i, dev in enumerate(devices):
            self.conn_table.insertRow(i)
            status_item = QTableWidgetItem("● Connected")
            status_item.setForeground(QColor("#2ecc71"))
            self.conn_table.setItem(i, 0, status_item)
            self.conn_table.setItem(
                i, 1, QTableWidgetItem(getattr(dev, 'interface', 'N/A'))
            )
            self.conn_table.setItem(
                i, 2, QTableWidgetItem(str(getattr(dev, 'channel', dev)))
            )
            self.conn_table.setItem(
                i, 3, QTableWidgetItem(str(getattr(dev, 'bitrate', 'N/A')))
            )
            self.conn_table.setItem(
                i, 4, QTableWidgetItem(str(getattr(dev, 'rx_count', 0)))
            )

    def closeEvent(self, event):
        self.refresh_timer.stop()
        super().closeEvent(event)