"""Capture Bisector Window - Find Exact Signal Change Points."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QProgressBar, QSplitter,
                             QMessageBox, QTextEdit, QSpinBox, QComboBox,
                             QLineEdit, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
import time
import bisect


class CaptureBisectorWindow(QMainWindow):
    """Window for finding exact points where CAN signals change using binary search."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.bisect_results = []

        self.is_bisecting = False
        self.current_bisect = None

        self.init_ui()

    def init_ui(self):
        """Initialize the bisector UI."""
        self.setWindowTitle("CAN Capture Bisector")
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

        # Left - Bisect results
        self.create_results_panel(results_splitter)

        # Right - Frame details
        self.create_details_panel(results_splitter)

        results_splitter.setSizes([700, 500])

        # Status bar
        self.status_label = QLabel("Ready - Select target signal and start bisect")
        layout.addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QVBoxLayout(panel)

        # Target signal selection
        target_group = QGroupBox("Target Signal")
        target_layout = QVBoxLayout()

        # CAN ID input
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("CAN ID (hex):"))
        self.can_id_edit = QLineEdit()
        self.can_id_edit.setPlaceholderText("e.g., 123")
        id_layout.addWidget(self.can_id_edit)

        # Byte offset
        byte_layout = QHBoxLayout()
        byte_layout.addWidget(QLabel("Byte Offset:"))
        self.byte_offset_spin = QSpinBox()
        self.byte_offset_spin.setRange(0, 7)
        byte_layout.addWidget(self.byte_offset_spin)

        # Bit position
        bit_layout = QHBoxLayout()
        bit_layout.addWidget(QLabel("Bit Position:"))
        self.bit_position_spin = QSpinBox()
        self.bit_position_spin.setRange(0, 7)
        bit_layout.addWidget(self.bit_position_spin)

        target_layout.addLayout(id_layout)
        target_layout.addLayout(byte_layout)
        target_layout.addLayout(bit_layout)

        target_group.setLayout(target_layout)
        control_layout.addWidget(target_group)

        # Bisect controls
        bisect_group = QGroupBox("Bisect Control")
        bisect_layout = QVBoxLayout()

        # Range selection
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("Frame Range:"))
        self.start_frame_spin = QSpinBox()
        self.start_frame_spin.setRange(0, 1000000)
        self.start_frame_spin.setValue(0)
        range_layout.addWidget(self.start_frame_spin)

        range_layout.addWidget(QLabel("to"))
        self.end_frame_spin = QSpinBox()
        self.end_frame_spin.setRange(0, 1000000)
        self.end_frame_spin.setValue(1000)
        range_layout.addWidget(self.end_frame_spin)

        # Expected change
        change_layout = QHBoxLayout()
        change_layout.addWidget(QLabel("Expected Change:"))
        self.expected_change_combo = QComboBox()
        self.expected_change_combo.addItems([
            "Bit 0→1", "Bit 1→0", "Any Change", "Value Increase", "Value Decrease"
        ])
        change_layout.addWidget(self.expected_change_combo)

        # Precision
        precision_layout = QHBoxLayout()
        precision_layout.addWidget(QLabel("Precision:"))
        self.precision_spin = QSpinBox()
        self.precision_spin.setRange(1, 100)
        self.precision_spin.setValue(1)
        self.precision_spin.setSuffix(" frames")
        precision_layout.addWidget(self.precision_spin)

        bisect_layout.addLayout(range_layout)
        bisect_layout.addLayout(change_layout)
        bisect_layout.addLayout(precision_layout)

        bisect_group.setLayout(bisect_layout)
        control_layout.addWidget(bisect_group)

        # Action controls
        action_group = QGroupBox("Actions")
        action_layout = QHBoxLayout()

        self.start_bisect_button = QPushButton("Start Bisect")
        self.start_bisect_button.clicked.connect(self.start_bisect)

        self.stop_bisect_button = QPushButton("Stop Bisect")
        self.stop_bisect_button.setEnabled(False)
        self.stop_bisect_button.clicked.connect(self.stop_bisect)

        self.clear_results_button = QPushButton("Clear Results")
        self.clear_results_button.clicked.connect(self.clear_results)

        action_layout.addWidget(self.start_bisect_button)
        action_layout.addWidget(self.stop_bisect_button)
        action_layout.addWidget(self.clear_results_button)
        action_layout.addStretch()

        action_group.setLayout(action_layout)
        control_layout.addWidget(action_group)

        parent.addWidget(panel)

    def create_results_panel(self, parent):
        """Create the bisect results panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Progress
        progress_group = QGroupBox("Bisect Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.progress_label = QLabel("Ready to start bisect")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Results table
        results_group = QGroupBox("Bisect Results")
        results_layout = QVBoxLayout()

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "CAN ID", "Byte", "Bit", "Change Frame", "Change Details"
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

        # Frame at change point
        change_group = QGroupBox("Frame at Change Point")
        change_layout = QVBoxLayout()

        self.change_frame_text = QTextEdit()
        self.change_frame_text.setReadOnly(True)
        self.change_frame_text.setFont(QFont("Courier New", 10))

        change_layout.addWidget(self.change_frame_text)
        change_group.setLayout(change_layout)
        layout.addWidget(change_group)

        # Before/After comparison
        comparison_group = QGroupBox("Before/After Comparison")
        comparison_layout = QVBoxLayout()

        self.comparison_text = QTextEdit()
        self.comparison_text.setReadOnly(True)
        self.comparison_text.setFont(QFont("Courier New", 10))

        comparison_layout.addWidget(self.comparison_text)
        comparison_group.setLayout(comparison_layout)
        layout.addWidget(comparison_group)

        parent.addWidget(panel)

    def start_bisect(self):
        """Start the bisect process."""
        try:
            can_id = int(self.can_id_edit.text(), 16)
        except ValueError:
            QMessageBox.warning(self, "Invalid CAN ID",
                               "Please enter a valid hexadecimal CAN ID.")
            return

        start_frame = self.start_frame_spin.value()
        end_frame = self.end_frame_spin.value()

        if start_frame >= end_frame:
            QMessageBox.warning(self, "Invalid Range",
                               "Start frame must be less than end frame.")
            return

        if not self.frames or end_frame >= len(self.frames):
            QMessageBox.warning(self, "Invalid Range",
                               "Frame range exceeds available frames.")
            return

        self.is_bisecting = True
        self.start_bisect_button.setEnabled(False)
        self.stop_bisect_button.setEnabled(True)

        # Create bisect configuration
        self.current_bisect = {
            'can_id': can_id,
            'byte_offset': self.byte_offset_spin.value(),
            'bit_position': self.bit_position_spin.value(),
            'start_frame': start_frame,
            'end_frame': end_frame,
            'expected_change': self.expected_change_combo.currentText(),
            'precision': self.precision_spin.value()
        }

        self.status_label.setText("Starting bisect process...")

        # Start bisect thread
        self.bisect_thread = BisectThread(self.frames, self.current_bisect)
        self.bisect_thread.progress_update.connect(self.on_progress_update)
        self.bisect_thread.bisect_complete.connect(self.on_bisect_complete)
        self.bisect_thread.start()

    def stop_bisect(self):
        """Stop the current bisect process."""
        if self.bisect_thread and self.bisect_thread.isRunning():
            self.bisect_thread.stop()

        self.is_bisecting = False
        self.start_bisect_button.setEnabled(True)
        self.stop_bisect_button.setEnabled(False)
        self.status_label.setText("Bisect stopped")

    def on_progress_update(self, progress, message):
        """Handle progress updates."""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)

    def on_bisect_complete(self, result):
        """Handle bisect completion."""
        self.is_bisecting = False
        self.start_bisect_button.setEnabled(True)
        self.stop_bisect_button.setEnabled(False)

        if result:
            self.bisect_results.append(result)
            self.display_results()
            self.status_label.setText(f"Bisect complete: Change found at frame {result['change_frame']}")
        else:
            self.status_label.setText("Bisect complete: No change found in range")

    def display_results(self):
        """Display the bisect results."""
        self.results_table.setRowCount(len(self.bisect_results))

        for row, result in enumerate(self.bisect_results):
            # CAN ID
            id_item = QTableWidgetItem(f"0x{result['can_id']:03X}")
            self.results_table.setItem(row, 0, id_item)

            # Byte
            byte_item = QTableWidgetItem(str(result['byte_offset']))
            self.results_table.setItem(row, 1, byte_item)

            # Bit
            bit_item = QTableWidgetItem(str(result['bit_position']))
            self.results_table.setItem(row, 2, bit_item)

            # Change frame
            frame_item = QTableWidgetItem(str(result['change_frame']))
            self.results_table.setItem(row, 3, frame_item)

            # Change details
            details = f"{result['before_value']} → {result['after_value']}"
            details_item = QTableWidgetItem(details)
            self.results_table.setItem(row, 4, details_item)

    def on_result_selected(self):
        """Handle result selection."""
        current_row = self.results_table.currentRow()
        if current_row >= 0 and current_row < len(self.bisect_results):
            result = self.bisect_results[current_row]
            self.show_change_details(result)

    def show_change_details(self, result):
        """Show details of the change point."""
        change_frame_idx = result['change_frame']

        if change_frame_idx >= len(self.frames):
            self.change_frame_text.setText("Change frame index out of range.")
            return

        frame = self.frames[change_frame_idx]

        # Frame details
        details = f"Frame {change_frame_idx}:\n"
        details += f"CAN ID: 0x{frame.id:03X}\n"
        if hasattr(frame, 'timestamp'):
            details += f"Timestamp: {frame.timestamp}\n"
        if hasattr(frame, 'data') and frame.data:
            details += f"Data: {' '.join(f'{b:02X}' for b in frame.data)}\n"
            details += f"ASCII: {''.join(chr(b) if 32 <= b <= 126 else '.' for b in frame.data)}\n"
        details += "\n"

        details += f"Target Signal Change:\n"
        details += f"Byte {result['byte_offset']}, Bit {result['bit_position']}: "
        details += f"{result['before_value']} → {result['after_value']}\n"

        self.change_frame_text.setText(details)

        # Before/After comparison
        before_frame = None
        after_frame = None

        # Find frames before and after the change
        for i in range(max(0, change_frame_idx - 5), change_frame_idx):
            if i < len(self.frames) and self.frames[i].id == result['can_id']:
                before_frame = self.frames[i]
                break

        for i in range(change_frame_idx, min(len(self.frames), change_frame_idx + 5)):
            if i < len(self.frames) and self.frames[i].id == result['can_id']:
                after_frame = self.frames[i]
                break

        comparison = "BEFORE CHANGE:\n"
        if before_frame and hasattr(before_frame, 'data'):
            comparison += f"Data: {' '.join(f'{b:02X}' for b in before_frame.data)}\n"
        else:
            comparison += "No frame found\n"

        comparison += "\nAFTER CHANGE:\n"
        if after_frame and hasattr(after_frame, 'data'):
            comparison += f"Data: {' '.join(f'{b:02X}' for b in after_frame.data)}\n"
        else:
            comparison += "No frame found\n"

        self.comparison_text.setText(comparison)

    def clear_results(self):
        """Clear all results."""
        self.bisect_results = []
        self.results_table.setRowCount(0)
        self.change_frame_text.clear()
        self.comparison_text.clear()
        self.progress_bar.setValue(0)
        self.progress_label.setText("Ready to start bisect")
        self.status_label.setText("Results cleared")

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []


class BisectThread(QThread):
    """Background thread for bisect analysis."""

    progress_update = pyqtSignal(int, str)
    bisect_complete = pyqtSignal(dict)

    def __init__(self, frames, config):
        super().__init__()
        self.frames = frames
        self.config = config
        self.stop_requested = False

    def stop(self):
        """Request thread stop."""
        self.stop_requested = True

    def run(self):
        """Run the bisect algorithm."""
        can_id = self.config['can_id']
        byte_offset = self.config['byte_offset']
        bit_position = self.config['bit_position']
        start_frame = self.config['start_frame']
        end_frame = self.config['end_frame']
        expected_change = self.config['expected_change']
        precision = self.config['precision']

        # Binary search for the change point
        left = start_frame
        right = end_frame

        last_change_frame = None
        iterations = 0
        max_iterations = 50  # Prevent infinite loops

        while left < right and iterations < max_iterations and not self.stop_requested:
            iterations += 1

            # Calculate progress
            progress = int(100 * (iterations / max_iterations))
            self.progress_update.emit(progress, f"Iteration {iterations}: Checking range {left}-{right}")

            # Check midpoint
            mid = (left + right) // 2

            # Get frames around midpoint
            check_frames = self.frames[max(0, mid-10):min(len(self.frames), mid+10)]

            # Look for the target CAN ID
            target_frames = [f for f in check_frames if f.id == can_id]

            if not target_frames:
                # No frames of target ID in this range, search right half
                left = mid + 1
                continue

            # Check if change occurs in this range
            change_detected = self.check_for_change(target_frames, byte_offset, bit_position, expected_change)

            if change_detected:
                # Change found, search left half for earlier occurrence
                right = mid
                last_change_frame = mid
            else:
                # No change, search right half
                left = mid + 1

        # Fine-tune the result within precision
        if last_change_frame is not None:
            result = self.fine_tune_change_point(
                last_change_frame, can_id, byte_offset, bit_position,
                expected_change, precision
            )
            self.bisect_complete.emit(result)
        else:
            self.bisect_complete.emit(None)

    def check_for_change(self, frames, byte_offset, bit_position, expected_change):
        """Check if the expected change occurs in the given frames."""
        if not frames:
            return False

        # Get first and last frame values
        first_frame = frames[0]
        last_frame = frames[-1]

        if not (hasattr(first_frame, 'data') and hasattr(last_frame, 'data')):
            return False

        if len(first_frame.data) <= byte_offset or len(last_frame.data) <= byte_offset:
            return False

        first_value = (first_frame.data[byte_offset] >> bit_position) & 1
        last_value = (last_frame.data[byte_offset] >> bit_position) & 1

        if expected_change == "Bit 0→1":
            return first_value == 0 and last_value == 1
        elif expected_change == "Bit 1→0":
            return first_value == 1 and last_value == 0
        elif expected_change == "Any Change":
            return first_value != last_value
        elif expected_change == "Value Increase":
            return last_value > first_value
        elif expected_change == "Value Decrease":
            return last_value < first_value

        return False

    def fine_tune_change_point(self, approx_frame, can_id, byte_offset, bit_position, expected_change, precision):
        """Fine-tune the change point within the specified precision."""
        # Search for the exact frame where the change occurs
        start_search = max(0, approx_frame - 100)
        end_search = min(len(self.frames), approx_frame + 100)

        target_frames = []
        for i in range(start_search, end_search):
            if self.frames[i].id == can_id:
                target_frames.append((i, self.frames[i]))

        if len(target_frames) < 2:
            return None

        # Find the transition point
        prev_value = None
        for frame_idx, frame in target_frames:
            if not hasattr(frame, 'data') or len(frame.data) <= byte_offset:
                continue

            current_value = (frame.data[byte_offset] >> bit_position) & 1

            if prev_value is not None:
                change_detected = self.check_change_type(prev_value, current_value, expected_change)
                if change_detected:
                    return {
                        'can_id': can_id,
                        'byte_offset': byte_offset,
                        'bit_position': bit_position,
                        'change_frame': frame_idx,
                        'before_value': prev_value,
                        'after_value': current_value
                    }

            prev_value = current_value

        return None

    def check_change_type(self, before, after, expected_change):
        """Check if the change matches the expected type."""
        if expected_change == "Bit 0→1":
            return before == 0 and after == 1
        elif expected_change == "Bit 1→0":
            return before == 1 and after == 0
        elif expected_change == "Any Change":
            return before != after
        elif expected_change == "Value Increase":
            return after > before
        elif expected_change == "Value Decrease":
            return after < before
        return False