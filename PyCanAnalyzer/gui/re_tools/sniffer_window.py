"""Sniffer Window - Detect Signals That Change During Events."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QProgressBar, QSplitter,
                             QMessageBox, QTextEdit, QCheckBox, QSpinBox,
                             QComboBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
import time
import collections


class SnifferWindow(QMainWindow):
    """Window for detecting CAN signals that change during specific events."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.baseline_frames = []
        self.event_frames = []
        self.detected_changes = []

        self.is_capturing_baseline = False
        self.is_capturing_event = False

        self.init_ui()

    def init_ui(self):
        """Initialize the sniffer UI."""
        self.setWindowTitle("CAN Signal Sniffer")
        self.setGeometry(200, 200, 1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)

        # Control panel
        self.create_control_panel(layout)

        # Results splitter
        results_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(results_splitter)

        # Left - Detection results
        self.create_results_panel(results_splitter)

        # Right - Frame details
        self.create_details_panel(results_splitter)

        results_splitter.setSizes([700, 500])

        # Status bar
        self.status_label = QLabel("Ready - Capture baseline first")
        layout.addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QVBoxLayout(panel)

        # Capture controls
        capture_group = QGroupBox("Capture Control")
        capture_layout = QHBoxLayout()

        self.baseline_button = QPushButton("Capture Baseline")
        self.baseline_button.setMinimumHeight(40)
        self.baseline_button.clicked.connect(self.start_baseline_capture)

        self.stop_baseline_button = QPushButton("Stop Baseline")
        self.stop_baseline_button.setMinimumHeight(40)
        self.stop_baseline_button.setEnabled(False)
        self.stop_baseline_button.clicked.connect(self.stop_baseline_capture)

        self.event_button = QPushButton("Capture Event")
        self.event_button.setMinimumHeight(40)
        self.event_button.setEnabled(False)
        self.event_button.clicked.connect(self.start_event_capture)

        self.stop_event_button = QPushButton("Stop Event")
        self.stop_event_button.setMinimumHeight(40)
        self.stop_event_button.setEnabled(False)
        self.stop_event_button.clicked.connect(self.stop_event_capture)

        capture_layout.addWidget(self.baseline_button)
        capture_layout.addWidget(self.stop_baseline_button)
        capture_layout.addWidget(self.event_button)
        capture_layout.addWidget(self.stop_event_button)

        capture_group.setLayout(capture_layout)
        control_layout.addWidget(capture_group)

        # Detection settings
        settings_group = QGroupBox("Detection Settings")
        settings_layout = QVBoxLayout()

        # Change threshold
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("Change Threshold:"))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 100)
        self.threshold_spin.setValue(5)
        self.threshold_spin.setSuffix(" occurrences")
        threshold_layout.addWidget(self.threshold_spin)
        threshold_layout.addStretch()

        # Minimum signal length
        min_length_layout = QHBoxLayout()
        min_length_layout.addWidget(QLabel("Min Signal Length:"))
        self.min_length_spin = QSpinBox()
        self.min_length_spin.setRange(1, 64)
        self.min_length_spin.setValue(8)
        self.min_length_spin.setSuffix(" bits")
        min_length_layout.addWidget(self.min_length_spin)
        min_length_layout.addStretch()

        # Detection mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Detection Mode:"))
        self.detection_mode_combo = QComboBox()
        self.detection_mode_combo.addItems([
            "Any Change",
            "Value Increase",
            "Value Decrease",
            "Bit Changes Only"
        ])
        mode_layout.addWidget(self.detection_mode_combo)
        mode_layout.addStretch()

        settings_layout.addLayout(threshold_layout)
        settings_layout.addLayout(min_length_layout)
        settings_layout.addLayout(mode_layout)

        settings_group.setLayout(settings_layout)
        control_layout.addWidget(settings_group)

        # Analysis controls
        analysis_group = QGroupBox("Analysis")
        analysis_layout = QHBoxLayout()

        self.analyze_button = QPushButton("Analyze Changes")
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self.analyze_changes)

        self.clear_button = QPushButton("Clear Results")
        self.clear_button.clicked.connect(self.clear_results)

        analysis_layout.addWidget(self.analyze_button)
        analysis_layout.addWidget(self.clear_button)
        analysis_layout.addStretch()

        analysis_group.setLayout(analysis_layout)
        control_layout.addWidget(analysis_group)

        parent.addWidget(panel)

    def create_results_panel(self, parent):
        """Create the detection results panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Results table
        results_group = QGroupBox("Detected Signal Changes")
        results_layout = QVBoxLayout()

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "CAN ID", "Byte Offset", "Bit Position", "Baseline Value",
            "Event Value", "Change Type"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.itemSelectionChanged.connect(self.on_result_selected)

        results_layout.addWidget(self.results_table)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        parent.addWidget(panel)

    def create_details_panel(self, parent):
        """Create the frame details panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Frame comparison
        comparison_group = QGroupBox("Frame Comparison")
        comparison_layout = QVBoxLayout()

        self.comparison_text = QTextEdit()
        self.comparison_text.setReadOnly(True)
        self.comparison_text.setFont(QFont("Courier New", 10))

        comparison_layout.addWidget(self.comparison_text)
        comparison_group.setLayout(comparison_layout)
        layout.addWidget(comparison_group)

        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout()

        self.stats_text = QTextEdit()
        self.stats_text.setMaximumHeight(150)
        self.stats_text.setReadOnly(True)

        stats_layout.addWidget(self.stats_text)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        parent.addWidget(panel)

    def start_baseline_capture(self):
        """Start capturing baseline frames."""
        self.is_capturing_baseline = True
        self.baseline_frames = []

        self.baseline_button.setEnabled(False)
        self.stop_baseline_button.setEnabled(True)
        self.event_button.setEnabled(False)

        self.status_label.setText("Capturing baseline... Click 'Stop Baseline' when ready.")

        # Start capture timer
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_baseline_frame)
        self.capture_timer.start(100)  # Capture every 100ms

    def stop_baseline_capture(self):
        """Stop capturing baseline frames."""
        self.is_capturing_baseline = False

        if hasattr(self, 'capture_timer'):
            self.capture_timer.stop()

        self.baseline_button.setEnabled(True)
        self.stop_baseline_button.setEnabled(False)
        self.event_button.setEnabled(True)

        baseline_count = len(self.baseline_frames)
        self.status_label.setText(f"Baseline captured: {baseline_count} frames. Ready for event capture.")

    def start_event_capture(self):
        """Start capturing event frames."""
        if not self.baseline_frames:
            QMessageBox.warning(self, "No Baseline",
                               "Please capture a baseline first.")
            return

        self.is_capturing_event = True
        self.event_frames = []

        self.event_button.setEnabled(False)
        self.stop_event_button.setEnabled(True)
        self.baseline_button.setEnabled(False)

        self.status_label.setText("Capturing event... Perform the action and click 'Stop Event'.")

        # Start capture timer
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_event_frame)
        self.capture_timer.start(100)  # Capture every 100ms

    def stop_event_capture(self):
        """Stop capturing event frames."""
        self.is_capturing_event = False

        if hasattr(self, 'capture_timer'):
            self.capture_timer.stop()

        self.event_button.setEnabled(True)
        self.stop_event_button.setEnabled(False)
        self.baseline_button.setEnabled(True)
        self.analyze_button.setEnabled(True)

        event_count = len(self.event_frames)
        self.status_label.setText(f"Event captured: {event_count} frames. Ready to analyze.")

    def capture_baseline_frame(self):
        """Capture a frame for baseline."""
        # In a real implementation, this would get frames from the live stream
        # For now, simulate by taking from existing frames
        if self.frames and len(self.baseline_frames) < 100:  # Limit to 100 frames
            frame = self.frames[len(self.baseline_frames) % len(self.frames)]
            self.baseline_frames.append(frame)

    def capture_event_frame(self):
        """Capture a frame during event."""
        # Similar to baseline capture
        if self.frames and len(self.event_frames) < 100:
            # Simulate capturing different frames during event
            offset = len(self.baseline_frames)
            frame = self.frames[(offset + len(self.event_frames)) % len(self.frames)]
            self.event_frames.append(frame)

    def analyze_changes(self):
        """Analyze differences between baseline and event captures."""
        if not self.baseline_frames or not self.event_frames:
            QMessageBox.warning(self, "Missing Data",
                               "Both baseline and event captures are required.")
            return

        self.status_label.setText("Analyzing signal changes...")

        # Run analysis in background thread
        self.analysis_thread = SnifferAnalysisThread(
            self.baseline_frames,
            self.event_frames,
            self.threshold_spin.value(),
            self.min_length_spin.value(),
            self.detection_mode_combo.currentText()
        )

        self.analysis_thread.analysis_complete.connect(self.on_analysis_complete)
        self.analysis_thread.start()

    def on_analysis_complete(self, changes):
        """Handle analysis completion."""
        self.detected_changes = changes
        self.display_results(changes)

        change_count = len(changes)
        self.status_label.setText(f"Analysis complete: {change_count} signal changes detected")

        # Update statistics
        self.update_statistics()

    def display_results(self, changes):
        """Display the detected changes in the table."""
        self.results_table.setRowCount(len(changes))

        for row, change in enumerate(changes):
            # CAN ID
            id_item = QTableWidgetItem(f"0x{change['can_id']:03X}")
            self.results_table.setItem(row, 0, id_item)

            # Byte offset
            byte_item = QTableWidgetItem(str(change['byte_offset']))
            self.results_table.setItem(row, 1, byte_item)

            # Bit position
            bit_item = QTableWidgetItem(str(change['bit_position']))
            self.results_table.setItem(row, 2, bit_item)

            # Baseline value
            baseline_item = QTableWidgetItem(str(change['baseline_value']))
            self.results_table.setItem(row, 3, baseline_item)

            # Event value
            event_item = QTableWidgetItem(str(change['event_value']))
            self.results_table.setItem(row, 4, event_item)

            # Change type
            change_item = QTableWidgetItem(change['change_type'])
            if change['change_type'] == "Increased":
                change_item.setBackground(QColor(200, 255, 200))
            elif change['change_type'] == "Decreased":
                change_item.setBackground(QColor(255, 200, 200))
            self.results_table.setItem(row, 5, change_item)

    def on_result_selected(self):
        """Handle result selection."""
        current_row = self.results_table.currentRow()
        if current_row >= 0 and current_row < len(self.detected_changes):
            change = self.detected_changes[current_row]
            self.show_frame_comparison(change)

    def show_frame_comparison(self, change):
        """Show frame comparison for the selected change."""
        can_id = change['can_id']
        byte_offset = change['byte_offset']

        # Find example frames
        baseline_frame = None
        event_frame = None

        for frame in self.baseline_frames:
            if frame.id == can_id and hasattr(frame, 'data') and len(frame.data) > byte_offset:
                baseline_frame = frame
                break

        for frame in self.event_frames:
            if frame.id == can_id and hasattr(frame, 'data') and len(frame.data) > byte_offset:
                event_frame = frame
                break

        if not baseline_frame or not event_frame:
            self.comparison_text.setText("Could not find matching frames for comparison.")
            return

        # Create comparison text
        comparison = f"Frame ID: 0x{can_id:03X}\n\n"

        comparison += "BASELINE FRAME:\n"
        if hasattr(baseline_frame, 'data') and baseline_frame.data:
            comparison += f"Data: {' '.join(f'{b:02X}' for b in baseline_frame.data)}\n"
            comparison += f"ASCII: {''.join(chr(b) if 32 <= b <= 126 else '.' for b in baseline_frame.data)}\n"
        comparison += "\n"

        comparison += "EVENT FRAME:\n"
        if hasattr(event_frame, 'data') and event_frame.data:
            comparison += f"Data: {' '.join(f'{b:02X}' for b in event_frame.data)}\n"
            comparison += f"ASCII: {''.join(chr(b) if 32 <= b <= 126 else '.' for b in event_frame.data)}\n"
        comparison += "\n"

        comparison += f"CHANGE DETECTED:\n"
        comparison += f"Byte {byte_offset}: 0x{baseline_frame.data[byte_offset]:02X} → 0x{event_frame.data[byte_offset]:02X}\n"
        comparison += f"Bit {change['bit_position']}: {change['baseline_value']} → {change['event_value']}\n"

        self.comparison_text.setText(comparison)

    def update_statistics(self):
        """Update the statistics display."""
        if not self.detected_changes:
            self.stats_text.setText("No changes detected.")
            return

        stats = f"Analysis Statistics:\n"
        stats += f"Baseline frames: {len(self.baseline_frames)}\n"
        stats += f"Event frames: {len(self.event_frames)}\n"
        stats += f"Signal changes detected: {len(self.detected_changes)}\n\n"

        # Count change types
        change_types = collections.Counter(c['change_type'] for c in self.detected_changes)
        stats += "Change Types:\n"
        for change_type, count in change_types.items():
            stats += f"  {change_type}: {count}\n"

        # Most common CAN IDs
        can_ids = collections.Counter(c['can_id'] for c in self.detected_changes)
        most_common = can_ids.most_common(3)
        stats += "\nMost Active IDs:\n"
        for can_id, count in most_common:
            stats += f"  0x{can_id:03X}: {count} changes\n"

        self.stats_text.setText(stats)

    def clear_results(self):
        """Clear all results and reset the interface."""
        self.detected_changes = []
        self.results_table.setRowCount(0)
        self.comparison_text.clear()
        self.stats_text.clear()
        self.analyze_button.setEnabled(False)
        self.status_label.setText("Results cleared")

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []


class SnifferAnalysisThread(QThread):
    """Background thread for sniffer analysis."""

    analysis_complete = pyqtSignal(list)

    def __init__(self, baseline_frames, event_frames, threshold, min_length, detection_mode):
        super().__init__()
        self.baseline_frames = baseline_frames
        self.event_frames = event_frames
        self.threshold = threshold
        self.min_length = min_length
        self.detection_mode = detection_mode

    def run(self):
        """Run the sniffer analysis."""
        changes = []

        # Group frames by CAN ID
        baseline_by_id = self.group_frames_by_id(self.baseline_frames)
        event_by_id = self.group_frames_by_id(self.event_frames)

        # Find common CAN IDs
        common_ids = set(baseline_by_id.keys()) & set(event_by_id.keys())

        for can_id in common_ids:
            baseline_group = baseline_by_id[can_id]
            event_group = event_by_id[can_id]

            # Analyze changes for this CAN ID
            id_changes = self.analyze_id_changes(can_id, baseline_group, event_group)
            changes.extend(id_changes)

        self.analysis_complete.emit(changes)

    def group_frames_by_id(self, frames):
        """Group frames by CAN ID."""
        grouped = {}
        for frame in frames:
            can_id = frame.id
            if can_id not in grouped:
                grouped[can_id] = []
            grouped[can_id].append(frame)
        return grouped

    def analyze_id_changes(self, can_id, baseline_frames, event_frames):
        """Analyze changes for a specific CAN ID."""
        changes = []

        if not baseline_frames or not event_frames:
            return changes

        # Get most common data pattern for baseline and event
        baseline_data = self.get_most_common_data(baseline_frames)
        event_data = self.get_most_common_data(event_frames)

        if not baseline_data or not event_data or len(baseline_data) != len(event_data):
            return changes

        # Compare byte by byte
        for byte_offset in range(len(baseline_data)):
            baseline_byte = baseline_data[byte_offset]
            event_byte = event_data[byte_offset]

            if baseline_byte != event_byte:
                # Analyze bit changes
                bit_changes = self.analyze_bit_changes(
                    baseline_byte, event_byte, byte_offset, can_id
                )
                changes.extend(bit_changes)

        return changes

    def get_most_common_data(self, frames):
        """Get the most common data pattern for a group of frames."""
        data_patterns = collections.Counter()

        for frame in frames:
            if hasattr(frame, 'data') and frame.data:
                data_patterns[tuple(frame.data)] += 1

        if data_patterns:
            most_common = data_patterns.most_common(1)[0][0]
            return list(most_common)

        return None

    def analyze_bit_changes(self, baseline_byte, event_byte, byte_offset, can_id):
        """Analyze which bits changed between baseline and event."""
        changes = []

        for bit_position in range(8):
            baseline_bit = (baseline_byte >> bit_position) & 1
            event_bit = (event_byte >> bit_position) & 1

            if baseline_bit != event_bit:
                change_type = "Increased" if event_bit > baseline_bit else "Decreased"

                # Check detection mode
                if self.detection_mode == "Any Change" or \
                   (self.detection_mode == "Value Increase" and event_bit > baseline_bit) or \
                   (self.detection_mode == "Value Decrease" and event_bit < baseline_bit) or \
                   self.detection_mode == "Bit Changes Only":

                    changes.append({
                        'can_id': can_id,
                        'byte_offset': byte_offset,
                        'bit_position': bit_position,
                        'baseline_value': baseline_bit,
                        'event_value': event_bit,
                        'change_type': change_type
                    })

        return changes