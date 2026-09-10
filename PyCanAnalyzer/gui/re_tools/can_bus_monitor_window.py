"""CAN Bus Monitor Window - Real-time CAN Bus Statistics and Health."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QSplitter, QMessageBox,
                             QTextEdit, QSpinBox, QComboBox, QLineEdit,
                             QCheckBox, QProgressBar, QLCDNumber, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QElapsedTimer
from PyQt5.QtGui import QFont, QColor, QPalette
import time
import collections
import statistics


class CanBusMonitorWindow(QMainWindow):
    """Window for real-time monitoring of CAN bus statistics and health."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.monitoring_active = False
        self.bus_stats = {}
        self.error_stats = {}
        self.performance_timer = QElapsedTimer()

        self.init_ui()

    def init_ui(self):
        """Initialize the CAN bus monitor UI."""
        self.setWindowTitle("CAN Bus Monitor")
        self.setGeometry(200, 200, 1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)

        # Control panel
        self.create_control_panel(layout)

        # Statistics display splitter
        stats_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(stats_splitter)

        # Left - Real-time stats
        self.create_realtime_stats(stats_splitter)

        # Right - Detailed analysis
        self.create_detailed_analysis(stats_splitter)

        stats_splitter.setSizes([600, 600])

        # Status bar
        self.status_label = QLabel("Ready - Start monitoring to view bus statistics")
        layout.addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QHBoxLayout(panel)

        # Monitoring controls
        monitor_group = QGroupBox("Monitoring Control")
        monitor_layout = QVBoxLayout()

        # Start/Stop
        button_layout = QHBoxLayout()
        self.start_monitor_button = QPushButton("Start Monitoring")
        self.start_monitor_button.clicked.connect(self.start_monitoring)

        self.stop_monitor_button = QPushButton("Stop Monitoring")
        self.stop_monitor_button.setEnabled(False)
        self.stop_monitor_button.clicked.connect(self.stop_monitoring)

        self.reset_stats_button = QPushButton("Reset Statistics")
        self.reset_stats_button.clicked.connect(self.reset_statistics)

        button_layout.addWidget(self.start_monitor_button)
        button_layout.addWidget(self.stop_monitor_button)
        button_layout.addWidget(self.reset_stats_button)

        # Update interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Update Interval:"))
        self.update_interval_spin = QSpinBox()
        self.update_interval_spin.setRange(100, 5000)
        self.update_interval_spin.setValue(1000)
        self.update_interval_spin.setSuffix(" ms")
        self.update_interval_spin.valueChanged.connect(self.change_update_interval)
        interval_layout.addWidget(self.update_interval_spin)

        monitor_layout.addLayout(button_layout)
        monitor_layout.addLayout(interval_layout)

        monitor_group.setLayout(monitor_layout)
        control_layout.addWidget(monitor_group)

        # Alert settings
        alert_group = QGroupBox("Alert Settings")
        alert_layout = QVBoxLayout()

        # Bus load alerts
        load_layout = QHBoxLayout()
        load_layout.addWidget(QLabel("Bus Load Alert:"))
        self.bus_load_alert_spin = QSpinBox()
        self.bus_load_alert_spin.setRange(10, 100)
        self.bus_load_alert_spin.setValue(80)
        self.bus_load_alert_spin.setSuffix("%")
        load_layout.addWidget(self.bus_load_alert_spin)

        # Error rate alerts
        error_layout = QHBoxLayout()
        error_layout.addWidget(QLabel("Error Rate Alert:"))
        self.error_rate_alert_spin = QSpinBox()
        self.error_rate_alert_spin.setRange(1, 1000)
        self.error_rate_alert_spin.setValue(10)
        self.error_rate_alert_spin.setSuffix(" errors/min")
        error_layout.addWidget(self.error_rate_alert_spin)

        alert_layout.addLayout(load_layout)
        alert_layout.addLayout(error_layout)

        alert_group.setLayout(alert_layout)
        control_layout.addWidget(alert_group)

        # Display options
        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout()

        self.show_fps_check = QCheckBox("Show FPS")
        self.show_fps_check.setChecked(True)

        self.show_bus_load_check = QCheckBox("Show Bus Load")
        self.show_bus_load_check.setChecked(True)

        self.show_error_stats_check = QCheckBox("Show Error Statistics")
        self.show_error_stats_check.setChecked(True)

        display_layout.addWidget(self.show_fps_check)
        display_layout.addWidget(self.show_bus_load_check)
        display_layout.addWidget(self.show_error_stats_check)

        display_group.setLayout(display_layout)
        control_layout.addWidget(display_group)

        parent.addWidget(panel)

    def create_realtime_stats(self, parent):
        """Create the real-time statistics panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Key metrics display
        metrics_group = QGroupBox("Key Metrics")
        metrics_layout = QVBoxLayout()

        # FPS display
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("Frames/sec:"))
        self.fps_lcd = QLCDNumber()
        self.fps_lcd.setDigitCount(6)
        self.fps_lcd.setSegmentStyle(QLCDNumber.Flat)
        fps_layout.addWidget(self.fps_lcd)

        # Bus load display
        load_layout = QHBoxLayout()
        load_layout.addWidget(QLabel("Bus Load:"))
        self.bus_load_lcd = QLCDNumber()
        self.bus_load_lcd.setDigitCount(5)
        self.bus_load_lcd.setSegmentStyle(QLCDNumber.Flat)
        load_layout.addWidget(self.bus_load_lcd)
        load_layout.addWidget(QLabel("%"))

        # Error count display
        error_layout = QHBoxLayout()
        error_layout.addWidget(QLabel("Errors:"))
        self.error_count_lcd = QLCDNumber()
        self.error_count_lcd.setDigitCount(4)
        self.error_count_lcd.setSegmentStyle(QLCDNumber.Flat)
        error_layout.addWidget(self.error_count_lcd)

        metrics_layout.addLayout(fps_layout)
        metrics_layout.addLayout(load_layout)
        metrics_layout.addLayout(error_layout)

        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)

        # Status indicators
        status_group = QGroupBox("Bus Status")
        status_layout = QVBoxLayout()

        # Bus health
        self.bus_health_label = QLabel("Bus Health: Unknown")
        self.bus_health_label.setStyleSheet("font-weight: bold; color: gray;")

        # Bus state
        self.bus_state_label = QLabel("Bus State: Unknown")

        # Last activity
        self.last_activity_label = QLabel("Last Activity: Never")

        status_layout.addWidget(self.bus_health_label)
        status_layout.addWidget(self.bus_state_label)
        status_layout.addWidget(self.last_activity_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Recent activity
        activity_group = QGroupBox("Recent Activity")
        activity_layout = QVBoxLayout()

        self.activity_text = QTextEdit()
        self.activity_text.setReadOnly(True)
        self.activity_text.setMaximumHeight(150)
        self.activity_text.setFont(QFont("Courier New", 9))

        activity_layout.addWidget(self.activity_text)
        activity_group.setLayout(activity_layout)
        layout.addWidget(activity_group)

        parent.addWidget(panel)

    def create_detailed_analysis(self, parent):
        """Create the detailed analysis panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Message statistics
        msg_stats_group = QGroupBox("Message Statistics")
        msg_stats_layout = QVBoxLayout()

        self.msg_stats_table = QTableWidget()
        self.msg_stats_table.setColumnCount(4)
        self.msg_stats_table.setHorizontalHeaderLabels([
            "CAN ID", "Count", "Frequency", "Last Seen"
        ])
        self.msg_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        msg_stats_layout.addWidget(self.msg_stats_table)
        msg_stats_group.setLayout(msg_stats_layout)
        layout.addWidget(msg_stats_group)

        # Error analysis
        error_group = QGroupBox("Error Analysis")
        error_layout = QVBoxLayout()

        self.error_analysis_text = QTextEdit()
        self.error_analysis_text.setReadOnly(True)

        error_layout.addWidget(self.error_analysis_text)
        error_group.setLayout(error_layout)
        layout.addWidget(error_group)

        parent.addWidget(panel)

    def start_monitoring(self):
        """Start the bus monitoring."""
        self.monitoring_active = True
        self.start_monitor_button.setEnabled(False)
        self.stop_monitor_button.setEnabled(True)

        self.performance_timer.start()

        # Initialize statistics
        self.bus_stats = {
            'frame_count': 0,
            'start_time': time.time(),
            'last_update': time.time(),
            'fps': 0,
            'bus_load': 0,
            'error_count': 0,
            'message_counts': collections.Counter(),
            'message_timestamps': {},
            'recent_activity': []
        }

        # Start update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_statistics)
        self.update_timer.start(self.update_interval_spin.value())

        self.status_label.setText("Monitoring active - collecting bus statistics")

    def stop_monitoring(self):
        """Stop the bus monitoring."""
        self.monitoring_active = False
        self.start_monitor_button.setEnabled(True)
        self.stop_monitor_button.setEnabled(False)

        if hasattr(self, 'update_timer'):
            self.update_timer.stop()

        self.status_label.setText("Monitoring stopped")

    def reset_statistics(self):
        """Reset all statistics."""
        self.bus_stats = {
            'frame_count': 0,
            'start_time': time.time(),
            'last_update': time.time(),
            'fps': 0,
            'bus_load': 0,
            'error_count': 0,
            'message_counts': collections.Counter(),
            'message_timestamps': {},
            'recent_activity': []
        }

        self.update_displays()
        self.status_label.setText("Statistics reset")

    def change_update_interval(self):
        """Change the update interval."""
        if hasattr(self, 'update_timer') and self.monitoring_active:
            self.update_timer.setInterval(self.update_interval_spin.value())

    def update_statistics(self):
        """Update bus statistics."""
        if not self.monitoring_active:
            return

        current_time = time.time()
        elapsed = current_time - self.bus_stats['start_time']

        if elapsed > 0:
            # Calculate FPS
            frame_count = len(self.frames) if self.frames else 0
            self.bus_stats['fps'] = frame_count / elapsed

            # Calculate bus load (simplified - assuming 500kbps CAN bus)
            # Each frame has overhead: 47 bits + 8*data_length + 3*stuff_bits
            total_bits = 0
            for frame in (self.frames or []):
                if hasattr(frame, 'data') and frame.data:
                    # Approximate: 47 bits overhead + 8 bits per data byte
                    total_bits += 47 + len(frame.data) * 8

            bus_load_percent = min(100.0, (total_bits / (500000 * elapsed)) * 100)  # 500kbps
            self.bus_stats['bus_load'] = bus_load_percent

        # Update message statistics
        self.update_message_stats()

        # Update displays
        self.update_displays()

        # Check for alerts
        self.check_alerts()

    def update_message_stats(self):
        """Update message statistics."""
        if not self.frames:
            return

        current_time = time.time()

        for frame in self.frames[-1000:]:  # Check last 1000 frames
            can_id = frame.id
            self.bus_stats['message_counts'][can_id] += 1
            self.bus_stats['message_timestamps'][can_id] = current_time

            # Add to recent activity
            if len(self.bus_stats['recent_activity']) >= 10:
                self.bus_stats['recent_activity'].pop(0)

            activity = f"{current_time:.3f}: 0x{can_id:03X}"
            if hasattr(frame, 'data') and frame.data:
                activity += f" [{' '.join(f'{b:02X}' for b in frame.data[:4])}"
                if len(frame.data) > 4:
                    activity += "..."
                activity += "]"

            self.bus_stats['recent_activity'].append(activity)

    def update_displays(self):
        """Update all display elements."""
        # Update LCD displays
        if self.show_fps_check.isChecked():
            self.fps_lcd.display(f"{self.bus_stats['fps']:.1f}")
        else:
            self.fps_lcd.display("---")

        if self.show_bus_load_check.isChecked():
            self.bus_load_lcd.display(f"{self.bus_stats['bus_load']:.1f}")
        else:
            self.bus_load_lcd.display("---")

        if self.show_error_stats_check.isChecked():
            self.error_count_lcd.display(str(self.bus_stats.get('error_count', 0)))
        else:
            self.error_count_lcd.display("---")

        # Update bus health
        self.update_bus_health()

        # Update activity log
        self.activity_text.setText('\n'.join(self.bus_stats['recent_activity']))

        # Update message statistics table
        self.update_message_table()

        # Update error analysis
        self.update_error_analysis()

    def update_bus_health(self):
        """Update bus health status."""
        bus_load = self.bus_stats['bus_load']
        fps = self.bus_stats['fps']

        # Determine health status
        if bus_load > 90:
            health = "CRITICAL"
            color = "red"
            state = "Overloaded"
        elif bus_load > 70:
            health = "WARNING"
            color = "orange"
            state = "High Load"
        elif bus_load > 30:
            health = "GOOD"
            color = "green"
            state = "Normal"
        elif fps > 0:
            health = "GOOD"
            color = "green"
            state = "Active"
        else:
            health = "UNKNOWN"
            color = "gray"
            state = "No Activity"

        self.bus_health_label.setText(f"Bus Health: {health}")
        self.bus_health_label.setStyleSheet(f"font-weight: bold; color: {color};")

        self.bus_state_label.setText(f"Bus State: {state}")

        # Last activity
        current_time = time.time()
        if self.bus_stats['message_timestamps']:
            last_activity = max(self.bus_stats['message_timestamps'].values())
            time_since = current_time - last_activity
            self.last_activity_label.setText(f"Last Activity: {time_since:.1f}s ago")
        else:
            self.last_activity_label.setText("Last Activity: Never")

    def update_message_table(self):
        """Update the message statistics table."""
        message_counts = self.bus_stats['message_counts']
        current_time = time.time()

        # Get top 20 messages
        top_messages = message_counts.most_common(20)

        self.msg_stats_table.setRowCount(len(top_messages))

        for row, (can_id, count) in enumerate(top_messages):
            # CAN ID
            id_item = QTableWidgetItem(f"0x{can_id:03X}")
            self.msg_stats_table.setItem(row, 0, id_item)

            # Count
            count_item = QTableWidgetItem(str(count))
            self.msg_stats_table.setItem(row, 1, count_item)

            # Frequency (messages per second)
            elapsed = current_time - self.bus_stats['start_time']
            if elapsed > 0:
                frequency = count / elapsed
                freq_item = QTableWidgetItem(f"{frequency:.2f}")
            else:
                freq_item = QTableWidgetItem("0.00")
            self.msg_stats_table.setItem(row, 2, freq_item)

            # Last seen
            if can_id in self.bus_stats['message_timestamps']:
                last_seen = current_time - self.bus_stats['message_timestamps'][can_id]
                last_item = QTableWidgetItem(f"{last_seen:.1f}s")
            else:
                last_item = QTableWidgetItem("Never")
            self.msg_stats_table.setItem(row, 3, last_item)

    def update_error_analysis(self):
        """Update error analysis display."""
        error_count = self.bus_stats.get('error_count', 0)
        elapsed_minutes = (time.time() - self.bus_stats['start_time']) / 60

        analysis = "Error Analysis\n\n"

        if elapsed_minutes > 0:
            error_rate = error_count / elapsed_minutes
            analysis += f"Total Errors: {error_count}\n"
            analysis += f"Error Rate: {error_rate:.2f} errors/minute\n\n"

            # Error rate assessment
            if error_rate > 50:
                assessment = "CRITICAL: Very high error rate"
            elif error_rate > 10:
                assessment = "WARNING: High error rate"
            elif error_rate > 1:
                assessment = "NOTICE: Moderate error rate"
            else:
                assessment = "GOOD: Low error rate"

            analysis += f"Assessment: {assessment}\n\n"
        else:
            analysis += "Monitoring time too short for error analysis\n\n"

        # Error types (simplified - would need actual error detection)
        analysis += "Error Types Detected:\n"
        analysis += "- Checksum errors: 0\n"
        analysis += "- Bit errors: 0\n"
        analysis += "- Stuff errors: 0\n"
        analysis += "- Form errors: 0\n"
        analysis += "- ACK errors: 0\n"

        self.error_analysis_text.setText(analysis)

    def check_alerts(self):
        """Check for alert conditions."""
        bus_load = self.bus_stats['bus_load']
        error_count = self.bus_stats.get('error_count', 0)
        elapsed_minutes = (time.time() - self.bus_stats['start_time']) / 60

        # Bus load alert
        if bus_load > self.bus_load_alert_spin.value():
            self.show_alert(f"High Bus Load: {bus_load:.1f}%")

        # Error rate alert
        if elapsed_minutes > 0:
            error_rate = error_count / elapsed_minutes
            if error_rate > self.error_rate_alert_spin.value():
                self.show_alert(f"High Error Rate: {error_rate:.1f} errors/min")

    def show_alert(self, message):
        """Show an alert message."""
        # For now, just update status. Could be enhanced with sound/visual alerts
        self.status_label.setText(f"ALERT: {message}")

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []

        if self.monitoring_active:
            self.update_statistics()

    def closeEvent(self, event):
        """Handle window close event."""
        self.stop_monitoring()
        super().closeEvent(event)