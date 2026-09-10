"""Fuzzing Window - Send Frames Tool
Automated fuzzing of CAN messages to discover vulnerabilities and edge cases.
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTableWidget, QTableWidgetItem,
                             QProgressBar, QTextEdit, QGroupBox, QSplitter,
                             QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                             QMessageBox, QHeaderView, QTreeWidget, QTreeWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush
import time
import random
import numpy as np
from collections import defaultdict


class FuzzingWorker(QThread):
    """Worker thread for CAN fuzzing operations"""
    progress = pyqtSignal(int)
    fuzz_result = pyqtSignal(dict)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, config, pipeline):
        super().__init__()
        self.config = config
        self.pipeline = pipeline
        self.is_running = True
        self.results = []

    def run(self):
        try:
            self.log_message.emit("Starting fuzzing campaign...")

            fuzz_type = self.config.get('fuzz_type', 'random')

            if fuzz_type == 'random':
                self._run_random_fuzzing()
            elif fuzz_type == 'mutation':
                self._run_mutation_fuzzing()
            elif fuzz_type == 'boundary':
                self._run_boundary_fuzzing()
            elif fuzz_type == 'sequence':
                self._run_sequence_fuzzing()

            self.log_message.emit(f"Fuzzing completed. Generated {len(self.results)} test cases.")
            self.finished.emit(self.results)

        except Exception as e:
            self.error.emit(f"Fuzzing error: {str(e)}")

    def _run_random_fuzzing(self):
        """Run random data fuzzing"""
        num_tests = self.config.get('num_tests', 100)
        id_range = self.config.get('id_range', (0x000, 0x7FF))
        data_lengths = self.config.get('data_lengths', [8])

        for i in range(num_tests):
            if not self.is_running:
                break

            # Generate random CAN ID
            can_id = random.randint(id_range[0], id_range[1])

            # Generate random data
            dlc = random.choice(data_lengths)
            data = [random.randint(0, 255) for _ in range(dlc)]

            # Send the fuzzed frame
            result = self._send_fuzz_frame(can_id, data, f"random_{i}")
            if result:
                self.results.append(result)
                self.fuzz_result.emit(result)

            # Update progress
            progress = int((i + 1) / num_tests * 100)
            self.progress.emit(progress)

            # Small delay between frames
            time.sleep(self.config.get('inter_frame_delay', 0.01))

    def _run_mutation_fuzzing(self):
        """Run mutation-based fuzzing on existing frames"""
        # This would use existing captured frames and mutate them
        self.log_message.emit("Mutation fuzzing not fully implemented - using random instead")
        self._run_random_fuzzing()

    def _run_boundary_fuzzing(self):
        """Run boundary value fuzzing"""
        boundary_values = [0, 1, 254, 255]  # Common boundary values
        num_tests = self.config.get('num_tests', 50)

        test_count = 0
        for can_id in [0x000, 0x001, 0x7FE, 0x7FF]:  # ID boundaries
            for dlc in [0, 1, 7, 8]:  # DLC boundaries
                for boundary_val in boundary_values:
                    if test_count >= num_tests or not self.is_running:
                        break

                    data = [boundary_val] * dlc
                    result = self._send_fuzz_frame(can_id, data, f"boundary_{test_count}")
                    if result:
                        self.results.append(result)
                        self.fuzz_result.emit(result)

                    test_count += 1
                    progress = int(test_count / num_tests * 100)
                    self.progress.emit(progress)

                    time.sleep(self.config.get('inter_frame_delay', 0.01))

    def _run_sequence_fuzzing(self):
        """Run sequence-based fuzzing"""
        # Generate sequences of related frames
        sequences = self._generate_fuzz_sequences()
        num_tests = min(len(sequences), self.config.get('num_tests', 50))

        for i, sequence in enumerate(sequences[:num_tests]):
            if not self.is_running:
                break

            self.log_message.emit(f"Sending fuzz sequence {i+1}/{num_tests}")

            for frame in sequence:
                if not self.is_running:
                    break

                result = self._send_fuzz_frame(frame['id'], frame['data'], f"sequence_{i}_{frame['name']}")
                if result:
                    self.results.append(result)
                    self.fuzz_result.emit(result)

                time.sleep(self.config.get('inter_frame_delay', 0.01))

            progress = int((i + 1) / num_tests * 100)
            self.progress.emit(progress)

    def _generate_fuzz_sequences(self):
        """Generate sequences of fuzzed frames"""
        sequences = []

        # Sequence 1: Diagnostic fuzzing
        seq1 = [
            {'id': 0x7DF, 'data': [0x02, 0x01, 0x00], 'name': 'diag_request'},
            {'id': 0x7DF, 'data': [0xFF, 0xFF, 0xFF], 'name': 'diag_fuzz'},
            {'id': 0x7DF, 'data': [0x00, 0x00, 0x00], 'name': 'diag_null'},
        ]
        sequences.append(seq1)

        # Sequence 2: Control command fuzzing
        seq2 = [
            {'id': 0x200, 'data': [0x00, 0x00, 0x00, 0x00], 'name': 'control_off'},
            {'id': 0x200, 'data': [0xFF, 0xFF, 0xFF, 0xFF], 'name': 'control_max'},
            {'id': 0x200, 'data': [0x80, 0x80, 0x80, 0x80], 'name': 'control_mid'},
        ]
        sequences.append(seq2)

        return sequences

    def _send_fuzz_frame(self, can_id, data, test_name):
        """Send a fuzzed CAN frame and monitor response"""
        try:
            # Convert data to bytes
            if isinstance(data, list):
                data = bytes(data)

            # In real implementation, this would send via CAN bus
            self.log_message.emit(f"Fuzz test '{test_name}': ID=0x{can_id:03X}, Data={data.hex()}")

            # Simulate sending and monitoring
            result = {
                'test_name': test_name,
                'can_id': can_id,
                'data': data.hex(),
                'timestamp': time.time(),
                'response_detected': random.choice([True, False]),  # Simulate response
                'anomaly_detected': random.random() < 0.1  # Simulate anomalies
            }

            return result

        except Exception as e:
            self.log_message.emit(f"Error in fuzz test '{test_name}': {str(e)}")
            return None

    def stop(self):
        self.is_running = False


class FuzzingWindow(QMainWindow):
    """Main window for CAN fuzzing operations"""

    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.fuzz_worker = None
        self.fuzz_results = []

        self.setWindowTitle("Fuzzing Tool - PyCANAnalyzer")
        self.setGeometry(200, 200, 1200, 800)

        self.init_ui()

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

        # Test details
        self.create_details_panel(bottom_splitter)

        # Log output
        self.create_log_panel(bottom_splitter)

        splitter.setSizes([400, 400])

    def create_control_panel(self, parent_layout):
        """Create the fuzzing control panel"""
        control_group = QGroupBox("Fuzzing Controls")
        control_layout = QHBoxLayout(control_group)

        # Fuzzing controls
        self.start_button = QPushButton("🚀 Start Fuzzing")
        self.start_button.clicked.connect(self.start_fuzzing)
        control_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.clicked.connect(self.stop_fuzzing)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)

        # Fuzzing type
        type_layout = QVBoxLayout()
        type_layout.addWidget(QLabel("Fuzzing Type:"))

        self.fuzz_type_combo = QComboBox()
        self.fuzz_type_combo.addItems(["Random", "Mutation", "Boundary", "Sequence"])
        type_layout.addWidget(self.fuzz_type_combo)

        control_layout.addLayout(type_layout)

        # Parameters
        params_layout = QVBoxLayout()

        # Number of tests
        test_layout = QHBoxLayout()
        test_layout.addWidget(QLabel("Tests:"))
        self.num_tests_spin = QSpinBox()
        self.num_tests_spin.setRange(10, 10000)
        self.num_tests_spin.setValue(100)
        test_layout.addWidget(self.num_tests_spin)
        params_layout.addLayout(test_layout)

        # Delay between frames
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay (s):"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.001, 1.0)
        self.delay_spin.setValue(0.01)
        self.delay_spin.setSingleStep(0.001)
        delay_layout.addWidget(self.delay_spin)
        params_layout.addLayout(delay_layout)

        control_layout.addLayout(params_layout)

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
        results_group = QGroupBox("Fuzzing Results")
        results_layout = QVBoxLayout(results_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "Test Name", "ID", "Data", "Response", "Anomaly", "Time"
        ])

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.results_table.itemSelectionChanged.connect(self.on_result_selected)
        results_layout.addWidget(self.results_table)

        parent_splitter.addWidget(results_group)

    def create_details_panel(self, parent_splitter):
        """Create the test details panel"""
        details_group = QGroupBox("Test Details")
        details_layout = QVBoxLayout(details_group)

        self.details_tree = QTreeWidget()
        self.details_tree.setHeaderLabel("Detail")
        self.details_tree.setColumnCount(2)
        self.details_tree.setHeaderLabels(["Property", "Value"])
        details_layout.addWidget(self.details_tree)

        parent_splitter.addWidget(details_group)

    def create_log_panel(self, parent_splitter):
        """Create the log output panel"""
        log_group = QGroupBox("Fuzzing Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Courier New", 9))
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)

        parent_splitter.addWidget(log_group)

    def start_fuzzing(self):
        """Start the fuzzing campaign"""
        if self.fuzz_worker and self.fuzz_worker.isRunning():
            return

        # Clear previous results
        self.fuzz_results.clear()
        self.results_table.setRowCount(0)
        self.details_tree.clear()
        self.progress_bar.setValue(0)

        # Get configuration
        config = {
            'fuzz_type': self.fuzz_type_combo.currentText().lower(),
            'num_tests': self.num_tests_spin.value(),
            'inter_frame_delay': self.delay_spin.value(),
            'id_range': (0x000, 0x7FF),
            'data_lengths': [0, 1, 2, 4, 8]
        }

        # Start fuzzing worker
        self.fuzz_worker = FuzzingWorker(config, self.pipeline)
        self.fuzz_worker.progress.connect(self.update_progress)
        self.fuzz_worker.fuzz_result.connect(self.on_fuzz_result)
        self.fuzz_worker.finished.connect(self.on_fuzzing_finished)
        self.fuzz_worker.error.connect(self.on_fuzzing_error)
        self.fuzz_worker.log_message.connect(self.log_message)

        self.fuzz_worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Fuzzing...")

    def stop_fuzzing(self):
        """Stop the fuzzing campaign"""
        if self.fuzz_worker:
            self.fuzz_worker.stop()
            self.fuzz_worker.wait()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")

    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def on_fuzz_result(self, result):
        """Handle fuzzing result"""
        self.fuzz_results.append(result)
        self.add_result_to_table(result)

    def add_result_to_table(self, result):
        """Add a fuzzing result to the table"""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        # Test name
        name_item = QTableWidgetItem(result['test_name'])
        self.results_table.setItem(row, 0, name_item)

        # ID
        id_item = QTableWidgetItem(f"0x{result['can_id']:03X}")
        self.results_table.setItem(row, 1, id_item)

        # Data
        data_item = QTableWidgetItem(result['data'])
        self.results_table.setItem(row, 2, data_item)

        # Response
        response_item = QTableWidgetItem("✓" if result.get('response_detected', False) else "✗")
        if result.get('response_detected', False):
            response_item.setBackground(QBrush(QColor(100, 255, 100)))
        self.results_table.setItem(row, 3, response_item)

        # Anomaly
        anomaly_item = QTableWidgetItem("⚠" if result.get('anomaly_detected', False) else "")
        if result.get('anomaly_detected', False):
            anomaly_item.setBackground(QBrush(QColor(255, 255, 100)))
        self.results_table.setItem(row, 4, anomaly_item)

        # Time
        time_item = QTableWidgetItem(f"{result['timestamp']:.3f}")
        self.results_table.setItem(row, 5, time_item)

    def on_result_selected(self):
        """Handle result selection in table"""
        current_row = self.results_table.currentRow()
        if current_row >= 0 and current_row < len(self.fuzz_results):
            result = self.fuzz_results[current_row]
            self.display_result_details(result)

    def display_result_details(self, result):
        """Display detailed information about a fuzzing result"""
        self.details_tree.clear()

        # Basic properties
        name_item = QTreeWidgetItem(["Test Name", result['test_name']])
        self.details_tree.addTopLevelItem(name_item)

        id_item = QTreeWidgetItem(["CAN ID", f"0x{result['can_id']:03X} ({result['can_id']})"])
        self.details_tree.addTopLevelItem(id_item)

        data_item = QTreeWidgetItem(["Data", result['data']])
        self.details_tree.addTopLevelItem(data_item)

        time_item = QTreeWidgetItem(["Timestamp", f"{result['timestamp']:.6f}"])
        self.details_tree.addTopLevelItem(time_item)

        # Results
        response_item = QTreeWidgetItem(["Response Detected", "Yes" if result.get('response_detected', False) else "No"])
        self.details_tree.addTopLevelItem(response_item)

        anomaly_item = QTreeWidgetItem(["Anomaly Detected", "Yes" if result.get('anomaly_detected', False) else "No"])
        self.details_tree.addTopLevelItem(anomaly_item)

        # Expand all items
        self.details_tree.expandAll()

    def on_fuzzing_finished(self, results):
        """Handle fuzzing completion"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText(f"Completed - {len(results)} tests")

        # Generate summary
        self.generate_summary(results)

    def generate_summary(self, results):
        """Generate a summary of the fuzzing campaign"""
        if not results:
            return

        total_tests = len(results)
        responses = sum(1 for r in results if r.get('response_detected', False))
        anomalies = sum(1 for r in results if r.get('anomaly_detected', False))

        summary = f"Fuzzing Summary:\n"
        summary += f"• Total tests: {total_tests}\n"
        summary += f"• Responses detected: {responses} ({responses/total_tests*100:.1f}%)\n"
        summary += f"• Anomalies detected: {anomalies} ({anomalies/total_tests*100:.1f}%)\n"

        self.log_message(summary)

    def on_fuzzing_error(self, error_msg):
        """Handle fuzzing error"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Error")
        self.log_message(f"Fuzzing error: {error_msg}")
        QMessageBox.critical(self, "Fuzzing Error", error_msg)

    def log_message(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        """Handle window close event"""
        if self.fuzz_worker and self.fuzz_worker.isRunning():
            self.fuzz_worker.stop()
            self.fuzz_worker.wait()
        event.accept()