"""Status Bar Widget - Real-time System Information Display."""
from PyQt5.QtWidgets import QStatusBar, QLabel, QHBoxLayout, QWidget, QFrame
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
import time


class StatusBar(QStatusBar):
    """Status bar displaying real-time CAN system information."""

    # Signals for status updates
    status_updated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_manager = None
        self.pipeline = None

        # Status indicators
        self.status_indicators = {
            'device': 'No Device',
            'fps': '0 FPS',
            'bus_load': '0%',
            'bus_speed': 'Unknown',
            'logging': 'Not Logging',
            'frames_total': '0 frames'
        }

        # Frame counting
        self.frame_count = 0
        self.last_fps_time = 0
        self.last_frame_count = 0

        self.init_ui()
        self.start_update_timer()

    def init_ui(self):
        """Initialize the status bar UI."""
        # Create status labels
        self.device_label = QLabel(self.status_indicators['device'])
        self.fps_label = QLabel(self.status_indicators['fps'])
        self.bus_label = QLabel(self.status_indicators['bus_load'])
        self.speed_label = QLabel(self.status_indicators['bus_speed'])
        self.logging_label = QLabel(self.status_indicators['logging'])
        self.frames_label = QLabel(self.status_indicators['frames_total'])

        # Set fonts
        font = QFont()
        font.setPointSize(9)
        for label in [self.device_label, self.fps_label, self.bus_label,
                     self.speed_label, self.logging_label, self.frames_label]:
            label.setFont(font)
            label.setMinimumWidth(100)

        # Add permanent widgets (right side)
        self.addPermanentWidget(self.frames_label)
        self.addPermanentWidget(self.logging_label)
        self.addPermanentWidget(self.speed_label)
        self.addPermanentWidget(self.bus_label)
        self.addPermanentWidget(self.fps_label)
        self.addPermanentWidget(self.device_label)

        # Set initial status message
        self.showMessage("Ready")

    def set_device_manager(self, device_manager):
        """Set the device manager for status monitoring.

        Args:
            device_manager: DeviceManager instance
        """
        self.device_manager = device_manager

    def set_pipeline(self, pipeline):
        """Set the pipeline for frame rate monitoring.

        Args:
            pipeline: Pipeline instance
        """
        self.pipeline = pipeline

    def start_update_timer(self):
        """Start the status update timer."""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second

    def update_status(self):
        """Update all status indicators."""
        self.update_device_status()
        self.update_fps()
        self.update_bus_status()
        self.update_logging_status()
        self.update_frame_count()

        # Emit status update signal
        self.status_updated.emit(self.status_indicators.copy())

    def update_device_status(self):
        """Update device connection status."""
        if self.device_manager:
            connected_devices = []
            for device_name, device in self.device_manager.devices.items():
                if getattr(device, 'connected', False):
                    connected_devices.append(device_name)

            if connected_devices:
                self.status_indicators['device'] = f"Connected: {', '.join(connected_devices)}"
            else:
                self.status_indicators['device'] = "No Device Connected"
        else:
            self.status_indicators['device'] = "No Device Manager"

        self.device_label.setText(self.status_indicators['device'])

    def update_fps(self):
        """Update frames per second display."""
        current_time = time.time()

        if self.pipeline and hasattr(self.pipeline, 'frame_count'):
            current_count = self.pipeline.frame_count
            time_diff = current_time - self.last_fps_time

            if time_diff >= 1.0:  # Update every second
                frame_diff = current_count - self.last_frame_count
                fps = frame_diff / time_diff if time_diff > 0 else 0

                self.status_indicators['fps'] = f"{fps:.0f} FPS"
                self.last_fps_time = current_time
                self.last_frame_count = current_count
        else:
            self.status_indicators['fps'] = "0 FPS"

        self.fps_label.setText(self.status_indicators['fps'])

    def update_bus_status(self):
        """Update bus load and speed information."""
        # This would typically get data from the device manager or pipeline
        # For now, show placeholder values
        self.status_indicators['bus_load'] = "0%"
        self.status_indicators['bus_speed'] = "Unknown"

        self.bus_label.setText(self.status_indicators['bus_load'])
        self.speed_label.setText(self.status_indicators['bus_speed'])

    def update_logging_status(self):
        """Update logging status indicator."""
        # This would check if logging is active
        # For now, show placeholder
        self.status_indicators['logging'] = "Not Logging"
        self.logging_label.setText(self.status_indicators['logging'])

    def update_frame_count(self):
        """Update total frame count display."""
        if self.pipeline and hasattr(self.pipeline, 'frame_count'):
            total_frames = self.pipeline.frame_count
            self.status_indicators['frames_total'] = f"{total_frames:,} frames"
        else:
            self.status_indicators['frames_total'] = "0 frames"

        self.frames_label.setText(self.status_indicators['frames_total'])

    def set_logging_status(self, is_logging, filename=None):
        """Set the logging status.

        Args:
            is_logging: Boolean indicating if logging is active
            filename: Optional log filename
        """
        if is_logging:
            if filename:
                self.status_indicators['logging'] = f"Logging: {filename}"
            else:
                self.status_indicators['logging'] = "Logging Active"
        else:
            self.status_indicators['logging'] = "Not Logging"

        self.logging_label.setText(self.status_indicators['logging'])

    def set_bus_info(self, bus_load=None, bus_speed=None):
        """Set bus information.

        Args:
            bus_load: Bus load percentage (0-100)
            bus_speed: Bus speed in kbps
        """
        if bus_load is not None:
            self.status_indicators['bus_load'] = f"{bus_load:.1f}%"
            self.bus_label.setText(self.status_indicators['bus_load'])

        if bus_speed is not None:
            self.status_indicators['bus_speed'] = f"{bus_speed}kbps"
            self.speed_label.setText(self.status_indicators['bus_speed'])

    def show_temporary_message(self, message, timeout=3000):
        """Show a temporary message in the status bar.

        Args:
            message: Message to display
            timeout: Timeout in milliseconds
        """
        self.showMessage(message, timeout)

    def clear_temporary_message(self):
        """Clear any temporary message."""
        self.clearMessage()