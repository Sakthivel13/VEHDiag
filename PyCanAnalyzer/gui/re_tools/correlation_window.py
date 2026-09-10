"""Correlation Window - Analyze Relationships Between CAN Signals."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QSplitter, QMessageBox,
                             QTextEdit, QSpinBox, QComboBox, QLineEdit,
                             QCheckBox, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
import time
import collections
import math
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class CorrelationWindow(QMainWindow):
    """Window for analyzing correlations between CAN signals."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.signal_definitions = []
        self.correlation_results = []

        self.is_analyzing = False

        self.init_ui()

    def init_ui(self):
        """Initialize the correlation UI."""
        self.setWindowTitle("CAN Signal Correlation Analyzer")
        self.setGeometry(200, 200, 1400, 900)

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

        # Left - Correlation matrix
        self.create_correlation_matrix(results_splitter)

        # Right - Details panel
        self.create_details_panel(results_splitter)

        results_splitter.setSizes([800, 600])

        # Status bar
        self.status_label = QLabel("Ready - Define signals and run correlation analysis")
        layout.addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QVBoxLayout(panel)

        # Signal definition
        signal_group = QGroupBox("Signal Definition")
        signal_layout = QVBoxLayout()

        # Signal input form
        form_layout = QHBoxLayout()

        # CAN ID
        form_layout.addWidget(QLabel("CAN ID (hex):"))
        self.can_id_edit = QLineEdit()
        self.can_id_edit.setPlaceholderText("e.g., 123")
        form_layout.addWidget(self.can_id_edit)

        # Start bit
        form_layout.addWidget(QLabel("Start Bit:"))
        self.start_bit_spin = QSpinBox()
        self.start_bit_spin.setRange(0, 63)
        form_layout.addWidget(self.start_bit_spin)

        # Length
        form_layout.addWidget(QLabel("Length:"))
        self.length_spin = QSpinBox()
        self.length_spin.setRange(1, 64)
        self.length_spin.setValue(8)
        form_layout.addWidget(self.length_spin)

        # Name
        form_layout.addWidget(QLabel("Name:"))
        self.signal_name_edit = QLineEdit()
        self.signal_name_edit.setPlaceholderText("e.g., Engine_Speed")
        form_layout.addWidget(self.signal_name_edit)

        signal_layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.add_signal_button = QPushButton("Add Signal")
        self.add_signal_button.clicked.connect(self.add_signal)

        self.remove_signal_button = QPushButton("Remove Selected")
        self.remove_signal_button.clicked.connect(self.remove_selected_signal)

        self.clear_signals_button = QPushButton("Clear All")
        self.clear_signals_button.clicked.connect(self.clear_signals)

        button_layout.addWidget(self.add_signal_button)
        button_layout.addWidget(self.remove_signal_button)
        button_layout.addWidget(self.clear_signals_button)
        button_layout.addStretch()

        signal_layout.addLayout(button_layout)

        signal_group.setLayout(signal_layout)
        control_layout.addWidget(signal_group)

        # Analysis settings
        analysis_group = QGroupBox("Analysis Settings")
        analysis_layout = QVBoxLayout()

        # Correlation method
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Correlation Method:"))
        self.correlation_method_combo = QComboBox()
        self.correlation_method_combo.addItems([
            "Pearson", "Spearman", "Kendall", "Mutual Information"
        ])
        method_layout.addWidget(self.correlation_method_combo)

        # Time window
        window_layout = QHBoxLayout()
        window_layout.addWidget(QLabel("Time Window (ms):"))
        self.time_window_spin = QSpinBox()
        self.time_window_spin.setRange(0, 10000)
        self.time_window_spin.setValue(100)
        self.time_window_spin.setSuffix(" ms")
        window_layout.addWidget(self.time_window_spin)

        # Min samples
        samples_layout = QHBoxLayout()
        samples_layout.addWidget(QLabel("Min Samples:"))
        self.min_samples_spin = QSpinBox()
        self.min_samples_spin.setRange(10, 10000)
        self.min_samples_spin.setValue(50)
        samples_layout.addWidget(self.min_samples_spin)

        analysis_layout.addLayout(method_layout)
        analysis_layout.addLayout(window_layout)
        analysis_layout.addLayout(samples_layout)

        analysis_group.setLayout(analysis_layout)
        control_layout.addWidget(analysis_group)

        # Analysis controls
        action_group = QGroupBox("Analysis")
        action_layout = QHBoxLayout()

        self.analyze_button = QPushButton("Run Correlation Analysis")
        self.analyze_button.clicked.connect(self.run_correlation_analysis)

        self.stop_analysis_button = QPushButton("Stop Analysis")
        self.stop_analysis_button.setEnabled(False)
        self.stop_analysis_button.clicked.connect(self.stop_analysis)

        action_layout.addWidget(self.analyze_button)
        action_layout.addWidget(self.stop_analysis_button)
        action_layout.addStretch()

        action_group.setLayout(action_layout)
        control_layout.addWidget(action_group)

        parent.addWidget(panel)

    def create_correlation_matrix(self, parent):
        """Create the correlation matrix panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Matrix table
        matrix_group = QGroupBox("Correlation Matrix")
        matrix_layout = QVBoxLayout()

        self.matrix_table = QTableWidget()
        self.matrix_table.setMinimumSize(600, 400)
        self.matrix_table.itemSelectionChanged.connect(self.on_matrix_selection)

        matrix_layout.addWidget(self.matrix_table)
        matrix_group.setLayout(matrix_layout)
        layout.addWidget(matrix_group)

        # Signal list
        list_group = QGroupBox("Defined Signals")
        list_layout = QVBoxLayout()

        self.signal_list_table = QTableWidget()
        self.signal_list_table.setColumnCount(4)
        self.signal_list_table.setHorizontalHeaderLabels([
            "Name", "CAN ID", "Start Bit", "Length"
        ])
        self.signal_list_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.signal_list_table.setMaximumHeight(200)

        list_layout.addWidget(self.signal_list_table)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        parent.addWidget(panel)

    def create_details_panel(self, parent):
        """Create the details panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Correlation details
        details_group = QGroupBox("Correlation Details")
        details_layout = QVBoxLayout()

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)

        details_layout.addWidget(self.details_text)
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        # Scatter plot area (text-based for now)
        plot_group = QGroupBox("Signal Relationship")
        plot_layout = QVBoxLayout()

        self.scatter_text = QTextEdit()
        self.scatter_text.setReadOnly(True)
        self.scatter_text.setFont(QFont("Courier New", 10))

        plot_layout.addWidget(self.scatter_text)
        plot_group.setLayout(plot_layout)
        layout.addWidget(plot_group)

        parent.addWidget(panel)

    def add_signal(self):
        """Add a signal to the analysis."""
        try:
            can_id = int(self.can_id_edit.text(), 16)
        except ValueError:
            QMessageBox.warning(self, "Invalid CAN ID",
                               "Please enter a valid hexadecimal CAN ID.")
            return

        name = self.signal_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name",
                               "Please enter a name for the signal.")
            return

        start_bit = self.start_bit_spin.value()
        length = self.length_spin.value()

        # Check for duplicate names
        for existing in self.signal_definitions:
            if existing['name'] == name:
                QMessageBox.warning(self, "Duplicate Name",
                                   f"Signal name '{name}' already exists.")
                return

        signal_def = {
            'name': name,
            'can_id': can_id,
            'start_bit': start_bit,
            'length': length
        }

        self.signal_definitions.append(signal_def)
        self.update_signal_list()

        # Clear form
        self.can_id_edit.clear()
        self.signal_name_edit.clear()
        self.start_bit_spin.setValue(0)
        self.length_spin.setValue(8)

        self.status_label.setText(f"Added signal: {name}")

    def remove_selected_signal(self):
        """Remove the selected signal."""
        current_row = self.signal_list_table.currentRow()
        if current_row >= 0 and current_row < len(self.signal_definitions):
            removed = self.signal_definitions.pop(current_row)
            self.update_signal_list()
            self.status_label.setText(f"Removed signal: {removed['name']}")

    def clear_signals(self):
        """Clear all signals."""
        self.signal_definitions = []
        self.correlation_results = []
        self.update_signal_list()
        self.update_matrix_table()
        self.details_text.clear()
        self.scatter_text.clear()
        self.status_label.setText("All signals cleared")

    def update_signal_list(self):
        """Update the signal list table."""
        self.signal_list_table.setRowCount(len(self.signal_definitions))

        for row, signal in enumerate(self.signal_definitions):
            # Name
            name_item = QTableWidgetItem(signal['name'])
            self.signal_list_table.setItem(row, 0, name_item)

            # CAN ID
            id_item = QTableWidgetItem(f"0x{signal['can_id']:03X}")
            self.signal_list_table.setItem(row, 1, id_item)

            # Start bit
            start_item = QTableWidgetItem(str(signal['start_bit']))
            self.signal_list_table.setItem(row, 2, start_item)

            # Length
            length_item = QTableWidgetItem(str(signal['length']))
            self.signal_list_table.setItem(row, 3, length_item)

    def run_correlation_analysis(self):
        """Run the correlation analysis."""
        if len(self.signal_definitions) < 2:
            QMessageBox.warning(self, "Insufficient Signals",
                               "Need at least 2 signals to perform correlation analysis.")
            return

        if not self.frames:
            QMessageBox.warning(self, "No Data",
                               "No frame data available for analysis.")
            return

        self.is_analyzing = True
        self.analyze_button.setEnabled(False)
        self.stop_analysis_button.setEnabled(True)

        self.status_label.setText("Running correlation analysis...")

        # Run analysis in background thread
        self.analysis_thread = CorrelationAnalysisThread(
            self.frames,
            self.signal_definitions,
            self.correlation_method_combo.currentText(),
            self.time_window_spin.value(),
            self.min_samples_spin.value()
        )

        self.analysis_thread.analysis_complete.connect(self.on_analysis_complete)
        self.analysis_thread.start()

    def stop_analysis(self):
        """Stop the current analysis."""
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()

        self.is_analyzing = False
        self.analyze_button.setEnabled(True)
        self.stop_analysis_button.setEnabled(False)
        self.status_label.setText("Analysis stopped")

    def on_analysis_complete(self, results):
        """Handle analysis completion."""
        self.is_analyzing = False
        self.analyze_button.setEnabled(True)
        self.stop_analysis_button.setEnabled(False)

        self.correlation_results = results
        self.update_matrix_table()

        self.status_label.setText(f"Analysis complete: {len(results)} correlations calculated")

    def update_matrix_table(self):
        """Update the correlation matrix table."""
        if not self.correlation_results:
            self.matrix_table.setRowCount(0)
            self.matrix_table.setColumnCount(0)
            return

        # Get unique signal names
        signal_names = list(set())
        for result in self.correlation_results:
            signal_names.add(result['signal1'])
            signal_names.add(result['signal2'])
        signal_names = sorted(list(signal_names))

        # Set up table
        n_signals = len(signal_names)
        self.matrix_table.setRowCount(n_signals)
        self.matrix_table.setColumnCount(n_signals)

        # Set headers
        self.matrix_table.setHorizontalHeaderLabels(signal_names)
        self.matrix_table.setVerticalHeaderLabels(signal_names)

        # Create correlation matrix
        correlation_matrix = {}
        for result in self.correlation_results:
            key = (result['signal1'], result['signal2'])
            correlation_matrix[key] = result['correlation']
            correlation_matrix[(result['signal2'], result['signal1'])] = result['correlation']

        # Fill table
        for i, signal1 in enumerate(signal_names):
            for j, signal2 in enumerate(signal_names):
                if i == j:
                    # Diagonal - signal names
                    item = QTableWidgetItem(signal1)
                    item.setBackground(QColor(240, 240, 240))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    # Correlation value
                    key = (signal1, signal2)
                    if key in correlation_matrix:
                        corr_value = correlation_matrix[key]
                        item = QTableWidgetItem(f"{corr_value:.3f}")

                        # Color code based on correlation strength
                        if abs(corr_value) > 0.8:
                            item.setBackground(QColor(200, 255, 200))  # Strong correlation
                        elif abs(corr_value) > 0.5:
                            item.setBackground(QColor(255, 255, 200))  # Moderate correlation
                        else:
                            item.setBackground(QColor(255, 200, 200))  # Weak correlation
                    else:
                        item = QTableWidgetItem("N/A")
                        item.setBackground(QColor(240, 240, 240))

                self.matrix_table.setItem(i, j, item)

        # Resize columns
        self.matrix_table.resizeColumnsToContents()

    def on_matrix_selection(self):
        """Handle matrix cell selection."""
        current_row = self.matrix_table.currentRow()
        current_col = self.matrix_table.currentColumn()

        if current_row >= 0 and current_col >= 0 and current_row != current_col:
            signal1 = self.matrix_table.verticalHeaderItem(current_row).text()
            signal2 = self.matrix_table.horizontalHeaderItem(current_col).text()

            self.show_correlation_details(signal1, signal2)

    def show_correlation_details(self, signal1, signal2):
        """Show detailed correlation information."""
        # Find the correlation result
        result = None
        for r in self.correlation_results:
            if (r['signal1'] == signal1 and r['signal2'] == signal2) or \
               (r['signal1'] == signal2 and r['signal2'] == signal1):
                result = r
                break

        if not result:
            self.details_text.setText("No correlation data found.")
            self.scatter_text.clear()
            return

        # Show details
        details = f"Correlation Analysis: {signal1} vs {signal2}\n\n"
        details += f"Correlation Coefficient: {result['correlation']:.6f}\n"
        details += f"P-value: {result.get('p_value', 'N/A')}\n"
        details += f"Method: {result['method']}\n"
        details += f"Time Window: {result['time_window']} ms\n"
        details += f"Samples: {result['sample_count']}\n\n"

        # Interpret correlation
        corr = abs(result['correlation'])
        if corr > 0.9:
            strength = "Very Strong"
        elif corr > 0.7:
            strength = "Strong"
        elif corr > 0.5:
            strength = "Moderate"
        elif corr > 0.3:
            strength = "Weak"
        else:
            strength = "Very Weak"

        details += f"Correlation Strength: {strength}\n"

        if result['correlation'] > 0:
            direction = "Positive (signals move together)"
        else:
            direction = "Negative (signals move opposite)"

        details += f"Direction: {direction}\n\n"

        # Signal statistics
        details += f"{signal1} Statistics:\n"
        details += f"  Mean: {result['signal1_mean']:.6f}\n"
        details += f"  Std Dev: {result['signal1_std']:.6f}\n"
        details += f"  Min: {result['signal1_min']:.6f}\n"
        details += f"  Max: {result['signal1_max']:.6f}\n\n"

        details += f"{signal2} Statistics:\n"
        details += f"  Mean: {result['signal2_mean']:.6f}\n"
        details += f"  Std Dev: {result['signal2_std']:.6f}\n"
        details += f"  Min: {result['signal2_min']:.6f}\n"
        details += f"  Max: {result['signal2_max']:.6f}\n"

        self.details_text.setText(details)

        # Show scatter plot data
        self.show_scatter_plot(result)

    def show_scatter_plot(self, result):
        """Show a text-based scatter plot."""
        scatter = f"Scatter Plot: {result['signal1']} vs {result['signal2']}\n\n"

        if 'signal1_values' in result and 'signal2_values' in result:
            values1 = result['signal1_values']
            values2 = result['signal2_values']

            # Simple text-based scatter plot
            scatter += "Value pairs (first 20):\n"
            for i, (v1, v2) in enumerate(zip(values1[:20], values2[:20])):
                scatter += f"  {v1:.3f}, {v2:.3f}\n"

            if len(values1) > 20:
                scatter += f"  ... and {len(values1) - 20} more pairs\n"
        else:
            scatter += "Detailed value data not available.\n"

        self.scatter_text.setText(scatter)

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []


class CorrelationAnalysisThread(QThread):
    """Background thread for correlation analysis."""

    analysis_complete = pyqtSignal(list)

    def __init__(self, frames, signal_definitions, method, time_window, min_samples):
        super().__init__()
        self.frames = frames
        self.signal_definitions = signal_definitions
        self.method = method
        self.time_window = time_window / 1000.0  # Convert to seconds
        self.min_samples = min_samples
        self.stop_requested = False

    def stop(self):
        """Request thread stop."""
        self.stop_requested = True

    def run(self):
        """Run the correlation analysis."""
        results = []

        # Extract signal data
        signal_data = self.extract_signal_data()

        if not signal_data:
            self.analysis_complete.emit(results)
            return

        # Calculate correlations between all pairs
        signal_names = list(signal_data.keys())

        for i in range(len(signal_names)):
            for j in range(i + 1, len(signal_names)):
                if self.stop_requested:
                    break

                signal1 = signal_names[i]
                signal2 = signal_names[j]

                correlation = self.calculate_correlation(
                    signal_data[signal1], signal_data[signal2]
                )

                if correlation is not None:
                    results.append(correlation)

            if self.stop_requested:
                break

        self.analysis_complete.emit(results)

    def extract_signal_data(self):
        """Extract signal data from frames."""
        signal_data = {}

        # Initialize
        for signal_def in self.signal_definitions:
            signal_data[signal_def['name']] = {
                'times': [],
                'values': []
            }

        # Process frames
        for frame in self.frames:
            if not hasattr(frame, 'timestamp') or not hasattr(frame, 'data'):
                continue

            timestamp = frame.timestamp

            for signal_def in self.signal_definitions:
                if frame.id == signal_def['can_id']:
                    value = self.extract_signal_value(frame.data, signal_def)
                    if value is not None:
                        signal_data[signal_def['name']]['times'].append(timestamp)
                        signal_data[signal_def['name']]['values'].append(value)

        # Filter signals with insufficient data
        filtered_data = {}
        for name, data in signal_data.items():
            if len(data['values']) >= self.min_samples:
                filtered_data[name] = data

        return filtered_data

    def extract_signal_value(self, data, signal_def):
        """Extract signal value from frame data."""
        start_bit = signal_def['start_bit']
        length = signal_def['length']

        if len(data) * 8 < start_bit + length:
            return None

        # Extract bits
        bits = []
        for byte in data:
            for bit in range(8):
                bits.append((byte >> bit) & 1)

        # Get signal bits
        signal_bits = bits[start_bit:start_bit + length]

        # Convert to value
        value = 0
        for bit in signal_bits:
            value = (value << 1) | bit

        return value

    def calculate_correlation(self, data1, data2):
        """Calculate correlation between two signal datasets."""
        times1 = data1['times']
        values1 = data1['values']
        times2 = data2['times']
        values2 = data2['values']

        if len(values1) < self.min_samples or len(values2) < self.min_samples:
            return None

        # Align data by time if time window is specified
        if self.time_window > 0:
            aligned_values = self.align_by_time(times1, values1, times2, values2)
            if not aligned_values:
                return None
            values1_aligned, values2_aligned = aligned_values
        else:
            # Use all available data
            min_len = min(len(values1), len(values2))
            values1_aligned = values1[:min_len]
            values2_aligned = values2[:min_len]

        if len(values1_aligned) < self.min_samples:
            return None

        # Calculate correlation based on method
        if self.method == "Pearson":
            correlation = self.pearson_correlation(values1_aligned, values2_aligned)
        elif self.method == "Spearman":
            correlation = self.spearman_correlation(values1_aligned, values2_aligned)
        elif self.method == "Kendall":
            correlation = self.kendall_correlation(values1_aligned, values2_aligned)
        else:  # Mutual Information
            correlation = self.mutual_information(values1_aligned, values2_aligned)

        if correlation is None:
            return None

        # Calculate statistics
        signal1_stats = self.calculate_stats(values1_aligned)
        signal2_stats = self.calculate_stats(values2_aligned)

        return {
            'signal1': data1.get('name', 'Signal1'),
            'signal2': data2.get('name', 'Signal2'),
            'correlation': correlation,
            'method': self.method,
            'time_window': int(self.time_window * 1000),
            'sample_count': len(values1_aligned),
            'signal1_mean': signal1_stats['mean'],
            'signal1_std': signal1_stats['std'],
            'signal1_min': signal1_stats['min'],
            'signal1_max': signal1_stats['max'],
            'signal2_mean': signal2_stats['mean'],
            'signal2_std': signal2_stats['std'],
            'signal2_min': signal2_stats['min'],
            'signal2_max': signal2_stats['max'],
            'signal1_values': values1_aligned[:50],  # Store first 50 values for plotting
            'signal2_values': values2_aligned[:50]
        }

    def align_by_time(self, times1, values1, times2, values2):
        """Align two datasets by time within the specified window."""
        if not times1 or not times2:
            return None

        aligned1 = []
        aligned2 = []

        # For each point in signal1, find corresponding points in signal2 within time window
        for i, t1 in enumerate(times1):
            # Find values in signal2 within time window
            window_values2 = []
            for j, t2 in enumerate(times2):
                if abs(t2 - t1) <= self.time_window:
                    window_values2.append(values2[j])

            if window_values2:
                # Use average of values in window
                avg_v2 = sum(window_values2) / len(window_values2)
                aligned1.append(values1[i])
                aligned2.append(avg_v2)

        if len(aligned1) < self.min_samples:
            return None

        return aligned1, aligned2

    def pearson_correlation(self, x, y):
        """Calculate Pearson correlation coefficient."""
        if HAS_NUMPY:
            return np.corrcoef(x, y)[0, 1]
        else:
            return self.manual_pearson(x, y)

    def manual_pearson(self, x, y):
        """Manual calculation of Pearson correlation."""
        n = len(x)
        if n != len(y) or n < 2:
            return 0.0

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)
        sum_y2 = sum(yi * yi for yi in y)

        numerator = n * sum_xy - sum_x * sum_y
        denominator = math.sqrt((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def spearman_correlation(self, x, y):
        """Calculate Spearman rank correlation."""
        # Simplified implementation
        return self.pearson_correlation(x, y)  # Placeholder

    def kendall_correlation(self, x, y):
        """Calculate Kendall rank correlation."""
        # Simplified implementation
        return self.pearson_correlation(x, y)  # Placeholder

    def mutual_information(self, x, y):
        """Calculate mutual information (simplified)."""
        # Very simplified mutual information calculation
        return abs(self.pearson_correlation(x, y))  # Placeholder

    def calculate_stats(self, values):
        """Calculate basic statistics for a dataset."""
        if not values:
            return {'mean': 0, 'std': 0, 'min': 0, 'max': 0}

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = math.sqrt(variance)

        return {
            'mean': mean,
            'std': std,
            'min': min(values),
            'max': max(values)
        }