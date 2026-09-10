"""Timing Analysis Window - Analyze Signal Timing and Jitter."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QSplitter, QMessageBox,
                             QTextEdit, QSpinBox, QComboBox, QLineEdit,
                             QCheckBox, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
import time
import collections
import statistics
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class TimingAnalysisWindow(QMainWindow):
    """Window for analyzing timing patterns and jitter in CAN signals."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.timing_results = {}

        self.is_analyzing = False

        self.init_ui()

    def init_ui(self):
        """Initialize the timing analysis UI."""
        self.setWindowTitle("CAN Timing Analysis")
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

        # Left - Timing results
        self.create_results_panel(results_splitter)

        # Right - Details panel
        self.create_details_panel(results_splitter)

        results_splitter.setSizes([700, 700])

        # Status bar
        self.status_label = QLabel("Ready - Select CAN ID and run timing analysis")
        layout.addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QVBoxLayout(panel)

        # Target selection
        target_group = QGroupBox("Target Selection")
        target_layout = QVBoxLayout()

        # CAN ID input
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("CAN ID (hex):"))
        self.can_id_edit = QLineEdit()
        self.can_id_edit.setPlaceholderText("e.g., 123")
        id_layout.addWidget(self.can_id_edit)

        # Analysis type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Analysis Type:"))
        self.analysis_type_combo = QComboBox()
        self.analysis_type_combo.addItems([
            "Message Intervals",
            "Bus Load Timing",
            "Signal Jitter",
            "Periodic Analysis"
        ])
        type_layout.addWidget(self.analysis_type_combo)

        target_layout.addLayout(id_layout)
        target_layout.addLayout(type_layout)

        target_group.setLayout(target_layout)
        control_layout.addWidget(target_group)

        # Analysis settings
        settings_group = QGroupBox("Analysis Settings")
        settings_layout = QVBoxLayout()

        # Time range
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("Time Range:"))
        self.start_time_spin = QSpinBox()
        self.start_time_spin.setRange(0, 1000000)
        self.start_time_spin.setValue(0)
        self.start_time_spin.setSuffix(" s")
        range_layout.addWidget(self.start_time_spin)

        range_layout.addWidget(QLabel("to"))
        self.end_time_spin = QSpinBox()
        self.end_time_spin.setRange(0, 1000000)
        self.end_time_spin.setValue(60)
        self.end_time_spin.setSuffix(" s")
        range_layout.addWidget(self.end_time_spin)

        # Bin size for histograms
        bin_layout = QHBoxLayout()
        bin_layout.addWidget(QLabel("Histogram Bins:"))
        self.bin_count_spin = QSpinBox()
        self.bin_count_spin.setRange(10, 1000)
        self.bin_count_spin.setValue(50)
        bin_layout.addWidget(self.bin_count_spin)

        # Outlier threshold
        outlier_layout = QHBoxLayout()
        outlier_layout.addWidget(QLabel("Outlier Threshold:"))
        self.outlier_threshold_spin = QSpinBox()
        self.outlier_threshold_spin.setRange(1, 100)
        self.outlier_threshold_spin.setValue(3)
        self.outlier_threshold_spin.setSuffix(" σ")
        outlier_layout.addWidget(self.outlier_threshold_spin)

        settings_layout.addLayout(range_layout)
        settings_layout.addLayout(bin_layout)
        settings_layout.addLayout(outlier_layout)

        settings_group.setLayout(settings_layout)
        control_layout.addWidget(settings_group)

        # Analysis controls
        action_group = QGroupBox("Analysis")
        action_layout = QHBoxLayout()

        self.analyze_button = QPushButton("Run Timing Analysis")
        self.analyze_button.clicked.connect(self.run_timing_analysis)

        self.stop_analysis_button = QPushButton("Stop Analysis")
        self.stop_analysis_button.setEnabled(False)
        self.stop_analysis_button.clicked.connect(self.stop_analysis)

        self.clear_results_button = QPushButton("Clear Results")
        self.clear_results_button.clicked.connect(self.clear_results)

        action_layout.addWidget(self.analyze_button)
        action_layout.addWidget(self.stop_analysis_button)
        action_layout.addWidget(self.clear_results_button)
        action_layout.addStretch()

        action_group.setLayout(action_layout)
        control_layout.addWidget(action_group)

        parent.addWidget(panel)

    def create_results_panel(self, parent):
        """Create the results panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Summary statistics
        summary_group = QGroupBox("Timing Statistics")
        summary_layout = QVBoxLayout()

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(200)

        summary_layout.addWidget(self.summary_text)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # Interval histogram
        histogram_group = QGroupBox("Interval Distribution")
        histogram_layout = QVBoxLayout()

        self.histogram_text = QTextEdit()
        self.histogram_text.setReadOnly(True)
        self.histogram_text.setFont(QFont("Courier New", 10))

        histogram_layout.addWidget(self.histogram_text)
        histogram_group.setLayout(histogram_layout)
        layout.addWidget(histogram_group)

        # Interval table
        table_group = QGroupBox("Interval Data")
        table_layout = QVBoxLayout()

        self.interval_table = QTableWidget()
        self.interval_table.setColumnCount(4)
        self.interval_table.setHorizontalHeaderLabels([
            "Interval #", "Time (s)", "Interval (ms)", "Deviation (ms)"
        ])
        self.interval_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        table_layout.addWidget(self.interval_table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        parent.addWidget(panel)

    def create_details_panel(self, parent):
        """Create the details panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Periodicity analysis
        periodicity_group = QGroupBox("Periodicity Analysis")
        periodicity_layout = QVBoxLayout()

        self.periodicity_text = QTextEdit()
        self.periodicity_text.setReadOnly(True)

        periodicity_layout.addWidget(self.periodicity_text)
        periodicity_group.setLayout(periodicity_layout)
        layout.addWidget(periodicity_group)

        # Jitter analysis
        jitter_group = QGroupBox("Jitter Analysis")
        jitter_layout = QVBoxLayout()

        self.jitter_text = QTextEdit()
        self.jitter_text.setReadOnly(True)

        jitter_layout.addWidget(self.jitter_text)
        jitter_group.setLayout(jitter_layout)
        layout.addWidget(jitter_group)

        # Outlier detection
        outlier_group = QGroupBox("Outlier Detection")
        outlier_layout = QVBoxLayout()

        self.outlier_table = QTableWidget()
        self.outlier_table.setColumnCount(3)
        self.outlier_table.setHorizontalHeaderLabels([
            "Time (s)", "Interval (ms)", "Z-Score"
        ])
        self.outlier_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        outlier_layout.addWidget(self.outlier_table)
        outlier_group.setLayout(outlier_layout)
        layout.addWidget(outlier_group)

        parent.addWidget(panel)

    def run_timing_analysis(self):
        """Run the timing analysis."""
        try:
            can_id = int(self.can_id_edit.text(), 16)
        except ValueError:
            QMessageBox.warning(self, "Invalid CAN ID",
                               "Please enter a valid hexadecimal CAN ID.")
            return

        if not self.frames:
            QMessageBox.warning(self, "No Data",
                               "No frame data available for analysis.")
            return

        self.is_analyzing = True
        self.analyze_button.setEnabled(False)
        self.stop_analysis_button.setEnabled(True)

        self.status_label.setText("Running timing analysis...")

        # Run analysis in background thread
        self.analysis_thread = TimingAnalysisThread(
            self.frames,
            can_id,
            self.analysis_type_combo.currentText(),
            self.start_time_spin.value(),
            self.end_time_spin.value(),
            self.bin_count_spin.value(),
            self.outlier_threshold_spin.value()
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

        self.timing_results = results
        self.display_results(results)

        self.status_label.setText("Timing analysis complete")

    def display_results(self, results):
        """Display the analysis results."""
        if not results:
            self.summary_text.setText("No timing data found for the specified CAN ID.")
            return

        # Summary statistics
        self.display_summary(results)

        # Interval histogram
        self.display_histogram(results)

        # Interval table
        self.display_interval_table(results)

        # Periodicity analysis
        self.display_periodicity(results)

        # Jitter analysis
        self.display_jitter(results)

        # Outlier detection
        self.display_outliers(results)

    def display_summary(self, results):
        """Display summary statistics."""
        summary = f"Timing Analysis Summary\n"
        summary += f"CAN ID: 0x{results['can_id']:03X}\n"
        summary += f"Analysis Type: {results['analysis_type']}\n"
        summary += f"Time Range: {results['start_time']:.1f}s - {results['end_time']:.1f}s\n\n"

        intervals = results.get('intervals', [])
        if intervals:
            summary += f"Message Count: {len(intervals) + 1}\n"
            summary += f"Intervals Analyzed: {len(intervals)}\n\n"

            summary += f"Interval Statistics:\n"
            summary += f"  Mean: {results['mean_interval']:.6f} ms\n"
            summary += f"  Median: {results['median_interval']:.6f} ms\n"
            summary += f"  Std Dev: {results['std_dev']:.6f} ms\n"
            summary += f"  Min: {results['min_interval']:.6f} ms\n"
            summary += f"  Max: {results['max_interval']:.6f} ms\n"
            summary += f"  Range: {results['max_interval'] - results['min_interval']:.6f} ms\n\n"

            # Frequency analysis
            if results['mean_interval'] > 0:
                frequency = 1000.0 / results['mean_interval']
                summary += f"Estimated Frequency: {frequency:.2f} Hz\n"
                summary += f"Estimated Period: {results['mean_interval']:.2f} ms\n"

        self.summary_text.setText(summary)

    def display_histogram(self, results):
        """Display interval histogram."""
        intervals = results.get('intervals', [])
        if not intervals:
            self.histogram_text.setText("No interval data available.")
            return

        # Create histogram
        if HAS_NUMPY:
            hist, bin_edges = np.histogram(intervals, bins=self.bin_count_spin.value())
        else:
            hist, bin_edges = self.manual_histogram(intervals, self.bin_count_spin.value())

        histogram = "Interval Distribution Histogram\n\n"
        histogram += "Bin Range (ms)    Count    Percentage\n"
        histogram += "-" * 40 + "\n"

        total_count = sum(hist)
        for i, count in enumerate(hist):
            bin_start = bin_edges[i]
            bin_end = bin_edges[i + 1]
            percentage = (count / total_count * 100) if total_count > 0 else 0

            histogram += f"{bin_start:8.3f} - {bin_end:8.3f}  {count:6d}  {percentage:8.2f}%\n"

        # ASCII bar chart
        histogram += "\nASCII Bar Chart:\n"
        max_count = max(hist) if hist.size > 0 else 0
        for i, count in enumerate(hist):
            if max_count > 0:
                bar_length = int(count / max_count * 50)
                bar = "█" * bar_length
            else:
                bar = ""
            histogram += f"{bin_edges[i]:8.3f}: {bar}\n"

        self.histogram_text.setText(histogram)

    def manual_histogram(self, data, bins):
        """Manual histogram calculation."""
        if not data:
            return [], []

        min_val = min(data)
        max_val = max(data)

        if min_val == max_val:
            return [len(data)], [min_val, max_val + 1]

        bin_width = (max_val - min_val) / bins
        bin_edges = [min_val + i * bin_width for i in range(bins + 1)]

        hist = [0] * bins
        for value in data:
            bin_idx = min(int((value - min_val) / bin_width), bins - 1)
            hist[bin_idx] += 1

        return hist, bin_edges

    def display_interval_table(self, results):
        """Display interval data table."""
        intervals = results.get('intervals', [])
        timestamps = results.get('timestamps', [])

        if not intervals:
            self.interval_table.setRowCount(0)
            return

        self.interval_table.setRowCount(len(intervals))

        for row, (timestamp, interval) in enumerate(zip(timestamps[1:], intervals)):
            # Interval number
            num_item = QTableWidgetItem(str(row + 1))
            self.interval_table.setItem(row, 0, num_item)

            # Time
            time_item = QTableWidgetItem(f"{timestamp:.6f}")
            self.interval_table.setItem(row, 1, time_item)

            # Interval
            interval_item = QTableWidgetItem(f"{interval:.6f}")
            self.interval_table.setItem(row, 2, interval_item)

            # Deviation from mean
            deviation = interval - results['mean_interval']
            dev_item = QTableWidgetItem(f"{deviation:.6f}")
            if abs(deviation) > results['std_dev'] * 2:
                dev_item.setBackground(QColor(255, 200, 200))  # Highlight large deviations
            self.interval_table.setItem(row, 3, dev_item)

    def display_periodicity(self, results):
        """Display periodicity analysis."""
        intervals = results.get('intervals', [])
        if not intervals or len(intervals) < 3:
            self.periodicity_text.setText("Insufficient data for periodicity analysis.")
            return

        # Autocorrelation analysis (simplified)
        periodicity = "Periodicity Analysis\n\n"

        # Check for consistent intervals
        mean_interval = results['mean_interval']
        std_dev = results['std_dev']
        cv = std_dev / mean_interval if mean_interval > 0 else 0  # Coefficient of variation

        periodicity += f"Coefficient of Variation: {cv:.6f}\n"

        if cv < 0.01:
            periodicity += "Assessment: Highly periodic (excellent timing)\n"
        elif cv < 0.05:
            periodicity += "Assessment: Periodic (good timing)\n"
        elif cv < 0.1:
            periodicity += "Assessment: Moderately periodic\n"
        elif cv < 0.2:
            periodicity += "Assessment: Irregular timing\n"
        else:
            periodicity += "Assessment: Highly irregular (poor timing)\n"

        periodicity += "\n"

        # Frequency analysis
        if HAS_NUMPY and len(intervals) > 10:
            # Simple FFT for frequency analysis
            try:
                fft = np.fft.fft(intervals)
                freqs = np.fft.fftfreq(len(intervals))

                # Find dominant frequency
                magnitudes = np.abs(fft)
                peak_idx = np.argmax(magnitudes[1:len(magnitudes)//2]) + 1
                peak_freq = abs(freqs[peak_idx])

                if peak_freq > 0:
                    period = 1.0 / peak_freq
                    frequency = peak_freq * 1000  # Convert to Hz
                    periodicity += f"Dominant Frequency: {frequency:.2f} Hz\n"
                    periodicity += f"Corresponding Period: {period:.2f} intervals\n"
            except:
                periodicity += "Frequency analysis failed.\n"
        else:
            periodicity += "Install numpy for frequency analysis.\n"

        self.periodicity_text.setText(periodicity)

    def display_jitter(self, results):
        """Display jitter analysis."""
        intervals = results.get('intervals', [])
        if not intervals:
            self.jitter_text.setText("No interval data for jitter analysis.")
            return

        jitter = "Jitter Analysis\n\n"

        # Calculate jitter metrics
        mean_interval = results['mean_interval']
        intervals_array = np.array(intervals) if HAS_NUMPY else intervals

        # Peak-to-peak jitter
        if HAS_NUMPY:
            ptp_jitter = np.ptp(intervals_array)
        else:
            ptp_jitter = max(intervals) - min(intervals)

        jitter += f"Peak-to-Peak Jitter: {ptp_jitter:.6f} ms\n"

        # RMS jitter (simplified)
        deviations = [abs(interval - mean_interval) for interval in intervals]
        rms_jitter = (sum(d**2 for d in deviations) / len(deviations))**0.5
        jitter += f"RMS Jitter: {rms_jitter:.6f} ms\n"

        # Jitter percentage
        if mean_interval > 0:
            jitter_percent = (rms_jitter / mean_interval) * 100
            jitter += f"Jitter Percentage: {jitter_percent:.2f}%\n\n"

            # Jitter quality assessment
            if jitter_percent < 1:
                quality = "Excellent (< 1%)"
            elif jitter_percent < 5:
                quality = "Good (1-5%)"
            elif jitter_percent < 10:
                quality = "Fair (5-10%)"
            else:
                quality = "Poor (> 10%)"

            jitter += f"Jitter Quality: {quality}\n"

        # Jitter distribution
        jitter += "\nJitter Distribution:\n"
        if deviations:
            jitter += f"  Mean Absolute Deviation: {statistics.mean(deviations):.6f} ms\n"
            jitter += f"  Median Absolute Deviation: {statistics.median(deviations):.6f} ms\n"
            jitter += f"  95th Percentile: {np.percentile(deviations, 95) if HAS_NUMPY else sorted(deviations)[int(len(deviations)*0.95)]:.6f} ms\n"

        self.jitter_text.setText(jitter)

    def display_outliers(self, results):
        """Display outlier detection results."""
        intervals = results.get('intervals', [])
        timestamps = results.get('timestamps', [])

        if not intervals or len(intervals) < 3:
            self.outlier_table.setRowCount(0)
            return

        # Calculate z-scores
        mean_interval = results['mean_interval']
        std_dev = results['std_dev']

        outliers = []
        for i, (timestamp, interval) in enumerate(zip(timestamps[1:], intervals)):
            if std_dev > 0:
                z_score = abs(interval - mean_interval) / std_dev
                if z_score > self.outlier_threshold_spin.value():
                    outliers.append((timestamp, interval, z_score))

        # Display outliers
        self.outlier_table.setRowCount(len(outliers))

        for row, (timestamp, interval, z_score) in enumerate(outliers):
            # Time
            time_item = QTableWidgetItem(f"{timestamp:.6f}")
            self.outlier_table.setItem(row, 0, time_item)

            # Interval
            interval_item = QTableWidgetItem(f"{interval:.6f}")
            self.outlier_table.setItem(row, 1, interval_item)

            # Z-score
            z_item = QTableWidgetItem(f"{z_score:.2f}")
            z_item.setBackground(QColor(255, 200, 200))  # Highlight outliers
            self.outlier_table.setItem(row, 2, z_item)

    def clear_results(self):
        """Clear all results."""
        self.timing_results = {}
        self.summary_text.clear()
        self.histogram_text.clear()
        self.interval_table.setRowCount(0)
        self.periodicity_text.clear()
        self.jitter_text.clear()
        self.outlier_table.setRowCount(0)
        self.status_label.setText("Results cleared")

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []


class TimingAnalysisThread(QThread):
    """Background thread for timing analysis."""

    analysis_complete = pyqtSignal(dict)

    def __init__(self, frames, can_id, analysis_type, start_time, end_time, bins, outlier_threshold):
        super().__init__()
        self.frames = frames
        self.can_id = can_id
        self.analysis_type = analysis_type
        self.start_time = start_time
        self.end_time = end_time
        self.bins = bins
        self.outlier_threshold = outlier_threshold
        self.stop_requested = False

    def stop(self):
        """Request thread stop."""
        self.stop_requested = True

    def run(self):
        """Run the timing analysis."""
        # Filter frames by CAN ID and time range
        filtered_frames = []
        for frame in self.frames:
            if (hasattr(frame, 'id') and frame.id == self.can_id and
                hasattr(frame, 'timestamp') and
                self.start_time <= frame.timestamp <= self.end_time):
                filtered_frames.append(frame)

        if len(filtered_frames) < 2:
            self.analysis_complete.emit({})
            return

        # Extract timestamps
        timestamps = [frame.timestamp for frame in filtered_frames]

        # Calculate intervals
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]) * 1000  # Convert to milliseconds
            intervals.append(interval)

        if not intervals:
            self.analysis_complete.emit({})
            return

        # Calculate statistics
        mean_interval = statistics.mean(intervals)
        median_interval = statistics.median(intervals)
        std_dev = statistics.stdev(intervals) if len(intervals) > 1 else 0
        min_interval = min(intervals)
        max_interval = max(intervals)

        results = {
            'can_id': self.can_id,
            'analysis_type': self.analysis_type,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'timestamps': timestamps,
            'intervals': intervals,
            'mean_interval': mean_interval,
            'median_interval': median_interval,
            'std_dev': std_dev,
            'min_interval': min_interval,
            'max_interval': max_interval
        }

        self.analysis_complete.emit(results)