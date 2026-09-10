"""Control Panel Widget - Quick Action Controls."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QGroupBox, QProgressBar, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon


class ControlPanel(QWidget):
    """Panel providing quick access to common CAN operations."""

    # Signals
    connect_requested = pyqtSignal()
    disconnect_requested = pyqtSignal()
    start_capture_requested = pyqtSignal()
    stop_capture_requested = pyqtSignal()
    clear_frames_requested = pyqtSignal()
    start_logging_requested = pyqtSignal(str)  # filename
    stop_logging_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_connected = False
        self.is_capturing = False
        self.is_logging = False
        self.log_filename = None

        self.init_ui()

    def init_ui(self):
        """Initialize the control panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Connection Controls
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout()

        self.connect_button = QPushButton("Connect Device")
        self.connect_button.setMinimumHeight(35)
        self.connect_button.clicked.connect(self.on_connect_clicked)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setMinimumHeight(35)
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.clicked.connect(self.on_disconnect_clicked)

        conn_layout.addWidget(self.connect_button)
        conn_layout.addWidget(self.disconnect_button)
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # Capture Controls
        capture_group = QGroupBox("Capture")
        capture_layout = QVBoxLayout()

        self.start_capture_button = QPushButton("Start Capture")
        self.start_capture_button.setMinimumHeight(35)
        self.start_capture_button.setEnabled(False)
        self.start_capture_button.clicked.connect(self.on_start_capture_clicked)

        self.stop_capture_button = QPushButton("Stop Capture")
        self.stop_capture_button.setMinimumHeight(35)
        self.stop_capture_button.setEnabled(False)
        self.stop_capture_button.clicked.connect(self.on_stop_capture_clicked)

        capture_layout.addWidget(self.start_capture_button)
        capture_layout.addWidget(self.stop_capture_button)
        capture_group.setLayout(capture_layout)
        layout.addWidget(capture_group)

        # Frame Management
        frame_group = QGroupBox("Frames")
        frame_layout = QVBoxLayout()

        self.clear_frames_button = QPushButton("Clear All Frames")
        self.clear_frames_button.setMinimumHeight(35)
        self.clear_frames_button.clicked.connect(self.on_clear_frames_clicked)

        frame_layout.addWidget(self.clear_frames_button)
        frame_group.setLayout(frame_layout)
        layout.addWidget(frame_group)

        # Logging Controls
        logging_group = QGroupBox("Logging")
        logging_layout = QVBoxLayout()

        self.start_logging_button = QPushButton("Start Logging")
        self.start_logging_button.setMinimumHeight(35)
        self.start_logging_button.setEnabled(False)
        self.start_logging_button.clicked.connect(self.on_start_logging_clicked)

        self.stop_logging_button = QPushButton("Stop Logging")
        self.stop_logging_button.setMinimumHeight(35)
        self.stop_logging_button.setEnabled(False)
        self.stop_logging_button.clicked.connect(self.on_stop_logging_clicked)

        logging_layout.addWidget(self.start_logging_button)
        logging_layout.addWidget(self.stop_logging_button)
        logging_group.setLayout(logging_layout)
        layout.addWidget(logging_group)

        # Status Display
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()

        self.status_label = QLabel("Disconnected")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; color: red;")

        status_layout.addWidget(self.status_label)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Set size policy
        self.setMaximumWidth(200)
        self.setMinimumWidth(180)

    def on_connect_clicked(self):
        """Handle connect button click."""
        self.connect_requested.emit()

    def on_disconnect_clicked(self):
        """Handle disconnect button click."""
        self.disconnect_requested.emit()

    def on_start_capture_clicked(self):
        """Handle start capture button click."""
        self.start_capture_requested.emit()

    def on_stop_capture_clicked(self):
        """Handle stop capture button click."""
        self.stop_capture_requested.emit()

    def on_clear_frames_clicked(self):
        """Handle clear frames button click."""
        self.clear_frames_requested.emit()

    def on_start_logging_clicked(self):
        """Handle start logging button click."""
        # This would typically open a file dialog
        # For now, use a default filename
        import time
        filename = f"can_log_{int(time.time())}.csv"
        self.start_logging_requested.emit(filename)

    def on_stop_logging_clicked(self):
        """Handle stop logging button click."""
        self.stop_logging_requested.emit()

    def set_connection_status(self, connected, device_name=None):
        """Update connection status and UI.

        Args:
            connected: Boolean indicating connection status
            device_name: Name of connected device
        """
        self.is_connected = connected

        if connected:
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.start_capture_button.setEnabled(True)
            self.start_logging_button.setEnabled(True)

            status_text = f"Connected: {device_name}" if device_name else "Connected"
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.start_capture_button.setEnabled(False)
            self.stop_capture_button.setEnabled(False)
            self.start_logging_button.setEnabled(False)
            self.stop_logging_button.setEnabled(False)

            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("font-weight: bold; color: red;")

            # Stop any active operations
            if self.is_capturing:
                self.set_capture_status(False)
            if self.is_logging:
                self.set_logging_status(False)

    def set_capture_status(self, capturing):
        """Update capture status and UI.

        Args:
            capturing: Boolean indicating capture status
        """
        self.is_capturing = capturing

        if capturing:
            self.start_capture_button.setEnabled(False)
            self.stop_capture_button.setEnabled(True)
            self.status_label.setText("Capturing...")
            self.status_label.setStyleSheet("font-weight: bold; color: blue;")
        else:
            self.start_capture_button.setEnabled(self.is_connected)
            self.stop_capture_button.setEnabled(False)
            if self.is_connected:
                self.status_label.setText("Connected (Idle)")
                self.status_label.setStyleSheet("font-weight: bold; color: green;")

    def set_logging_status(self, logging, filename=None):
        """Update logging status and UI.

        Args:
            logging: Boolean indicating logging status
            filename: Current log filename
        """
        self.is_logging = logging
        self.log_filename = filename if logging else None

        if logging:
            self.start_logging_button.setEnabled(False)
            self.stop_logging_button.setEnabled(True)
            status_text = f"Logging: {filename}" if filename else "Logging..."
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet("font-weight: bold; color: orange;")
        else:
            self.start_logging_button.setEnabled(self.is_connected)
            self.stop_logging_button.setEnabled(False)

    def update_frame_count(self, count):
        """Update the frame count display.

        Args:
            count: Current frame count
        """
        # Could add a frame counter display here if desired
        pass

    def enable_controls(self, enabled):
        """Enable or disable all controls.

        Args:
            enabled: Boolean to enable/disable controls
        """
        self.connect_button.setEnabled(enabled)
        if not enabled:
            self.disconnect_button.setEnabled(False)
            self.start_capture_button.setEnabled(False)
            self.stop_capture_button.setEnabled(False)
            self.start_logging_button.setEnabled(False)
            self.stop_logging_button.setEnabled(False)
            self.clear_frames_button.setEnabled(False)

    def get_status_summary(self):
        """Get a summary of current status.

        Returns:
            Dictionary with status information
        """
        return {
            'connected': self.is_connected,
            'capturing': self.is_capturing,
            'logging': self.is_logging,
            'log_filename': self.log_filename
        }