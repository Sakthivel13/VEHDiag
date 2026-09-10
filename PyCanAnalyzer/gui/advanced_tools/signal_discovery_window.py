"""
Signal Discovery Window - Advanced Tool
Automatically discovers CAN signals using machine learning and statistical analysis.
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTableWidget, QTableWidgetItem,
                             QProgressBar, QTextEdit, QGroupBox, QSplitter,
                             QComboBox, QSpinBox, QCheckBox, QTabWidget,
                             QMessageBox, QHeaderView, QTreeWidget, QTreeWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush
import time
import numpy as np


class SignalDiscoveryWorker(QThread):
    """Worker thread for signal discovery analysis"""
    progress = pyqtSignal(int)
    discovered_signal = pyqtSignal(dict)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, frames, config):
        super().__init__()
        self.frames = frames
        self.config = config
        self.is_running = True

    def run(self):
        try:
            self.log_message.emit("Starting signal discovery analysis...")

            if not self.frames:
                self.error.emit("No frames available for analysis")
                return

            # Group frames by ID
            id_groups = self._group_frames_by_id()

            discovered_signals = []
            total_ids = len(id_groups)

            for i, (can_id, frames) in enumerate(id_groups.items()):
                if not self.is_running:
                    break

                self.log_message.emit(f"Analyzing ID 0x{can_id:03X} ({len(frames)} frames)")

                # Analyze this ID for signals
                signals = self._analyze_id_for_signals(can_id, frames)

                for signal in signals:
                    discovered_signals.append(signal)
                    self.discovered_signal.emit(signal)

                # Update progress
                progress = int((i + 1) / total_ids * 100)
                self.progress.emit(progress)

            self.log_message.emit(f"Discovery complete. Found {len(discovered_signals)} potential signals.")
            self.finished.emit(discovered_signals)

        except Exception as e:
            self.error.emit(f"Signal discovery error: {str(e)}")

    def _group_frames_by_id(self):
        """Group frames by CAN ID"""
        id_groups = {}
        for frame in self.frames:
            can_id = frame.can_id
            if can_id not in id_groups:
                id_groups[can_id] = []
            id_groups[can_id].append(frame)
        return id_groups

    def _analyze_id_for_signals(self, can_id, frames):
        """Analyze frames of a single ID for potential signals"""
        if len(frames) < self.config.get('min_frames', 10):
            return []

        # Convert frame data to numpy arrays for analysis
        data_arrays = []
        timestamps = []

        for frame in frames:
            if len(frame.data) >= 2:  # Need at least 2 bytes for meaningful analysis
                data_arrays.append(list(frame.data))
                timestamps.append(frame.timestamp)

        if len(data_arrays) < self.config.get('min_frames', 10):
            return []

        # Analyze each byte position for potential signals
        signals = []
        data_matrix = np.array(data_arrays)

        for byte_pos in range(len(data_arrays[0])):
            byte_data = data_matrix[:, byte_pos]

            # Check for changing values (not constant)
            if len(np.unique(byte_data)) <= 1:
                continue

            # Analyze for different signal types
            signal_candidates = self._detect_signal_patterns(byte_data, timestamps, can_id, byte_pos)

            for candidate in signal_candidates:
                if self._validate_signal(candidate, byte_data, timestamps):
                    signals.append(candidate)

        return signals

    def _detect_signal_patterns(self, byte_data, timestamps, can_id, byte_pos):
        """Detect different types of signal patterns in byte data"""
        candidates = []

        # 1. Counter signals (incrementing values)
        if self._is_counter_signal(byte_data):
            candidates.append({
                'id': can_id,
                'byte_pos': byte_pos,
                'type': 'counter',
                'name': f'Counter_{can_id:03X}_{byte_pos}',
                'description': f'Incrementing counter in byte {byte_pos}',
                'min_val': int(np.min(byte_data)),
                'max_val': int(np.max(byte_data)),
                'confidence': 0.8
            })

        # 2. Bit field signals
        bit_signals = self._detect_bit_signals(byte_data, can_id, byte_pos)
        candidates.extend(bit_signals)

        # 3. Multi-byte signals (if adjacent bytes show correlation)
        # This would require analyzing adjacent bytes

        # 4. Periodic signals
        if self._is_periodic_signal(byte_data, timestamps):
            candidates.append({
                'id': can_id,
                'byte_pos': byte_pos,
                'type': 'periodic',
                'name': f'Periodic_{can_id:03X}_{byte_pos}',
                'description': f'Periodic signal in byte {byte_pos}',
                'frequency': self._estimate_frequency(byte_data, timestamps),
                'confidence': 0.7
            })

        return candidates

    def _is_counter_signal(self, data):
        """Check if data represents an incrementing counter"""
        if len(data) < 3:
            return False

        # Check for mostly increasing values with occasional resets
        increases = 0
        resets = 0

        for i in range(1, len(data)):
            if data[i] > data[i-1]:
                increases += 1
            elif data[i] < data[i-1]:  # Potential reset
                resets += 1

        # Counters should have more increases than resets
        return increases > resets and increases > len(data) * 0.3

    def _detect_bit_signals(self, byte_data, can_id, byte_pos):
        """Detect individual bit signals within a byte"""
        signals = []

        for bit_pos in range(8):
            bit_values = [(data >> bit_pos) & 1 for data in byte_data]

            # Check if bit changes
            unique_values = set(bit_values)
            if len(unique_values) <= 1:
                continue

            # Calculate transitions
            transitions = sum(1 for i in range(1, len(bit_values)) if bit_values[i] != bit_values[i-1])

            if transitions > 0:  # Bit does change
                duty_cycle = sum(bit_values) / len(bit_values)

                signals.append({
                    'id': can_id,
                    'byte_pos': byte_pos,
                    'bit_pos': bit_pos,
                    'type': 'bit',
                    'name': f'Bit_{can_id:03X}_{byte_pos}_{bit_pos}',
                    'description': f'Bit {bit_pos} in byte {byte_pos}',
                    'duty_cycle': duty_cycle,
                    'transitions': transitions,
                    'confidence': min(0.9, transitions / len(bit_values))
                })

        return signals

    def _is_periodic_signal(self, data, timestamps):
        """Check if signal appears periodic"""
        if len(data) < 10:
            return False

        # Simple periodicity check using autocorrelation
        # This is a basic implementation
        try:
            # Calculate differences between consecutive timestamps
            intervals = np.diff(timestamps)
            mean_interval = np.mean(intervals)

            # Check if intervals are relatively consistent
            std_interval = np.std(intervals)
            cv = std_interval / mean_interval if mean_interval > 0 else float('inf')

            return cv < 0.5  # Low coefficient of variation indicates periodicity
        except:
            return False

    def _estimate_frequency(self, data, timestamps):
        """Estimate signal frequency"""
        if len(timestamps) < 2:
            return 0

        intervals = np.diff(timestamps)
        mean_interval = np.mean(intervals)

        return 1.0 / mean_interval if mean_interval > 0 else 0

    def _validate_signal(self, signal, byte_data, timestamps):
        """Validate that a discovered signal is meaningful"""
        # Basic validation - check for minimum activity
        if signal['type'] == 'bit':
            bit_values = [(data >> signal['bit_pos']) & 1 for data in byte_data]
            transitions = sum(1 for i in range(1, len(bit_values)) if bit_values[i] != bit_values[i-1])
            return transitions >= self.config.get('min_transitions', 3)
        elif signal['type'] in ['counter', 'periodic']:
            unique_values = len(np.unique(byte_data))
            return unique_values >= self.config.get('min_unique_values', 3)

        return True

    def stop(self):
        self.is_running = False


class SignalDiscoveryWindow(QMainWindow):
    """Main window for CAN signal discovery"""

    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.discovered_signals = []
        self.discovery_worker = None

        self.setWindowTitle("Signal Discovery - PyCANAnalyzer")
        self.setGeometry(200, 200, 1200, 800)

        self.init_ui()
        self.load_frames()

    def init_ui(self):
        """Initialize the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Control panel
        self.create_control_panel(layout)

        # Main content splitter
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # Top section - Results table
        self.create_results_panel(splitter)

        # Bottom section - Details and log
        bottom_splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(bottom_splitter)

        # Signal details
        self.create_details_panel(bottom_splitter)

        # Log output
        self.create_log_panel(bottom_splitter)

        splitter.setSizes([400, 400])

    def create_control_panel(self, parent_layout):
        """Create the control panel"""
        control_group = QGroupBox("Discovery Controls")
        control_layout = QHBoxLayout(control_group)

        # Analysis controls
        self.start_button = QPushButton("🔍 Start Discovery")
        self.start_button.clicked.connect(self.start_discovery)
        control_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.clicked.connect(self.stop_discovery)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)

        # Configuration
        config_layout = QVBoxLayout()

        # Minimum frames
        min_frames_layout = QHBoxLayout()
        min_frames_layout.addWidget(QLabel("Min frames per ID:"))
        self.min_frames_spin = QSpinBox()
        self.min_frames_spin.setRange(5, 1000)
        self.min_frames_spin.setValue(50)
        min_frames_layout.addWidget(self.min_frames_spin)
        config_layout.addLayout(min_frames_layout)

        # Analysis types
        types_layout = QHBoxLayout()
        self.counter_checkbox = QCheckBox("Counters")
        self.counter_checkbox.setChecked(True)
        types_layout.addWidget(self.counter_checkbox)

        self.bit_checkbox = QCheckBox("Bit Fields")
        self.bit_checkbox.setChecked(True)
        types_layout.addWidget(self.bit_checkbox)

        self.periodic_checkbox = QCheckBox("Periodic")
        self.periodic_checkbox.setChecked(True)
        types_layout.addWidget(self.periodic_checkbox)

        config_layout.addLayout(types_layout)

        control_layout.addLayout(config_layout)

        # Progress
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)

        control_layout.addLayout(progress_layout)

        parent_layout.addWidget(control_group)

    def create_results_panel(self, parent_splitter):
        """Create the results display panel"""
        results_group = QGroupBox("Discovered Signals")
        results_layout = QVBoxLayout(results_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "ID", "Type", "Name", "Description", "Confidence", "Details"
        ])

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.results_table.itemSelectionChanged.connect(self.on_signal_selected)
        results_layout.addWidget(self.results_table)

        parent_splitter.addWidget(results_group)

    def create_details_panel(self, parent_splitter):
        """Create the signal details panel"""
        details_group = QGroupBox("Signal Details")
        details_layout = QVBoxLayout(details_group)

        self.details_tree = QTreeWidget()
        self.details_tree.setHeaderLabel("Property")
        self.details_tree.setColumnCount(2)
        self.details_tree.setHeaderLabels(["Property", "Value"])
        details_layout.addWidget(self.details_tree)

        parent_splitter.addWidget(details_group)

    def create_log_panel(self, parent_splitter):
        """Create the log output panel"""
        log_group = QGroupBox("Analysis Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setFont(QFont("Courier New", 9))
        log_layout.addWidget(self.log_text)

        parent_splitter.addWidget(log_group)

    def load_frames(self):
        """Load frames from the pipeline"""
        try:
            # Get frames from pipeline
            self.frames = self.pipeline.get_all_frames() if hasattr(self.pipeline, 'get_all_frames') else []
            self.log_message(f"Loaded {len(self.frames)} frames for analysis")
        except Exception as e:
            self.log_message(f"Error loading frames: {str(e)}")
            self.frames = []

    def start_discovery(self):
        """Start signal discovery analysis"""
        if not self.frames:
            QMessageBox.warning(self, "No Frames", "No frames available for analysis.")
            return

        if self.discovery_worker and self.discovery_worker.isRunning():
            return

        # Clear previous results
        self.discovered_signals.clear()
        self.results_table.setRowCount(0)
        self.details_tree.clear()
        self.progress_bar.setValue(0)

        # Get configuration
        config = {
            'min_frames': self.min_frames_spin.value(),
            'analyze_counters': self.counter_checkbox.isChecked(),
            'analyze_bits': self.bit_checkbox.isChecked(),
            'analyze_periodic': self.periodic_checkbox.isChecked(),
            'min_transitions': 3,
            'min_unique_values': 3
        }

        # Start discovery worker
        self.discovery_worker = SignalDiscoveryWorker(self.frames, config)
        self.discovery_worker.progress.connect(self.update_progress)
        self.discovery_worker.discovered_signal.connect(self.on_signal_discovered)
        self.discovery_worker.finished.connect(self.on_discovery_finished)
        self.discovery_worker.error.connect(self.on_discovery_error)
        self.discovery_worker.log_message.connect(self.log_message)

        self.discovery_worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Analyzing...")

    def stop_discovery(self):
        """Stop signal discovery"""
        if self.discovery_worker:
            self.discovery_worker.stop()
            self.discovery_worker.wait()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")

    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def on_signal_discovered(self, signal):
        """Handle discovered signal"""
        self.discovered_signals.append(signal)
        self.add_signal_to_table(signal)

    def add_signal_to_table(self, signal):
        """Add a signal to the results table"""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        # ID
        id_item = QTableWidgetItem(f"0x{signal['id']:03X}")
        self.results_table.setItem(row, 0, id_item)

        # Type
        type_item = QTableWidgetItem(signal['type'].title())
        self.results_table.setItem(row, 1, type_item)

        # Name
        name_item = QTableWidgetItem(signal['name'])
        self.results_table.setItem(row, 2, name_item)

        # Description
        desc_item = QTableWidgetItem(signal['description'])
        self.results_table.setItem(row, 3, desc_item)

        # Confidence
        confidence_item = QTableWidgetItem(f"{signal['confidence']:.2f}")
        self.results_table.setItem(row, 4, confidence_item)

        # Details
        details = self._get_signal_details(signal)
        details_item = QTableWidgetItem(details)
        self.results_table.setItem(row, 5, details_item)

    def _get_signal_details(self, signal):
        """Get detailed string for signal"""
        if signal['type'] == 'bit':
            return f"Bit {signal['bit_pos']}, Duty: {signal['duty_cycle']:.2f}"
        elif signal['type'] == 'counter':
            return f"Range: {signal['min_val']}-{signal['max_val']}"
        elif signal['type'] == 'periodic':
            return f"Freq: {signal['frequency']:.2f} Hz"
        return ""

    def on_signal_selected(self):
        """Handle signal selection in table"""
        current_row = self.results_table.currentRow()
        if current_row >= 0 and current_row < len(self.discovered_signals):
            signal = self.discovered_signals[current_row]
            self.display_signal_details(signal)

    def display_signal_details(self, signal):
        """Display detailed information about a signal"""
        self.details_tree.clear()

        # Basic properties
        id_item = QTreeWidgetItem(["CAN ID", f"0x{signal['id']:03X}"])
        self.details_tree.addTopLevelItem(id_item)

        type_item = QTreeWidgetItem(["Type", signal['type'].title()])
        self.details_tree.addTopLevelItem(type_item)

        name_item = QTreeWidgetItem(["Name", signal['name']])
        self.details_tree.addTopLevelItem(name_item)

        desc_item = QTreeWidgetItem(["Description", signal['description']])
        self.details_tree.addTopLevelItem(desc_item)

        confidence_item = QTreeWidgetItem(["Confidence", f"{signal['confidence']:.3f}"])
        self.details_tree.addTopLevelItem(confidence_item)

        # Type-specific details
        if signal['type'] == 'bit':
            bit_pos_item = QTreeWidgetItem(["Bit Position", str(signal['bit_pos'])])
            self.details_tree.addTopLevelItem(bit_pos_item)

            duty_item = QTreeWidgetItem(["Duty Cycle", f"{signal['duty_cycle']:.3f}"])
            self.details_tree.addTopLevelItem(duty_item)

            transitions_item = QTreeWidgetItem(["Transitions", str(signal['transitions'])])
            self.details_tree.addTopLevelItem(transitions_item)

        elif signal['type'] == 'counter':
            min_item = QTreeWidgetItem(["Min Value", str(signal['min_val'])])
            self.details_tree.addTopLevelItem(min_item)

            max_item = QTreeWidgetItem(["Max Value", str(signal['max_val'])])
            self.details_tree.addTopLevelItem(max_item)

        elif signal['type'] == 'periodic':
            freq_item = QTreeWidgetItem(["Frequency", f"{signal['frequency']:.3f} Hz"])
            self.details_tree.addTopLevelItem(freq_item)

        # Expand all items
        self.details_tree.expandAll()

    def on_discovery_finished(self, signals):
        """Handle discovery completion"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText(f"Completed - Found {len(signals)} signals")

    def on_discovery_error(self, error_msg):
        """Handle discovery error"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Error")
        self.log_message(f"Discovery error: {error_msg}")
        QMessageBox.critical(self, "Discovery Error", error_msg)

    def log_message(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        """Handle window close event"""
        if self.discovery_worker and self.discovery_worker.isRunning():
            self.discovery_worker.stop()
            self.discovery_worker.wait()
        event.accept()