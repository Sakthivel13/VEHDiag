"""Frame Analysis Window - Analyze CAN Frame Statistics."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QProgressBar, QTextEdit,
                             QSplitter, QMessageBox, QComboBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import collections
import math


class FrameAnalysisWindow(QMainWindow):
    """Window for analyzing CAN frame statistics and patterns."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.analysis_results = {}

        self.init_ui()

    def init_ui(self):
        """Initialize the frame analysis UI."""
        self.setWindowTitle("CAN Frame Analysis")
        self.setGeometry(200, 200, 1000, 700)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main splitter
        splitter = QSplitter(Qt.Vertical)
        central_widget.setLayout(QVBoxLayout())
        central_widget.layout().addWidget(splitter)

        # Top panel - Analysis controls and summary
        self.create_analysis_panel(splitter)

        # Bottom panel - Detailed results
        self.create_results_panel(splitter)

        splitter.setSizes([300, 400])

        # Status bar
        self.status_label = QLabel("Ready")
        central_widget.layout().addWidget(self.status_label)

    def create_analysis_panel(self, parent):
        """Create the analysis control panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Analysis type selection
        type_group = QGroupBox("Analysis Type")
        type_layout = QVBoxLayout()

        self.analysis_combo = QComboBox()
        self.analysis_combo.addItems([
            "Byte Frequency Analysis",
            "Bit Transition Analysis",
            "Entropy Analysis",
            "Message Timing Analysis",
            "Data Pattern Analysis"
        ])

        analyze_button = QPushButton("Run Analysis")
        analyze_button.clicked.connect(self.run_analysis)

        type_layout.addWidget(self.analysis_combo)
        type_layout.addWidget(analyze_button)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # Progress
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        progress_layout.addWidget(self.progress_bar)
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Summary results
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout()

        self.summary_text = QTextEdit()
        self.summary_text.setMaximumHeight(150)
        self.summary_text.setReadOnly(True)

        summary_layout.addWidget(self.summary_text)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        parent.addWidget(panel)

    def create_results_panel(self, parent):
        """Create the detailed results panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Item", "Value", "Description"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        layout.addWidget(self.results_table)

        parent.addWidget(panel)

    def run_analysis(self):
        """Run the selected analysis."""
        if not self.frames:
            QMessageBox.warning(self, "No Data",
                               "No CAN frames available for analysis.")
            return

        analysis_type = self.analysis_combo.currentText()
        self.status_label.setText(f"Running {analysis_type}...")

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Run analysis in thread
        self.analysis_thread = AnalysisThread(self.frames, analysis_type)
        self.analysis_thread.progress_updated.connect(self.update_progress)
        self.analysis_thread.analysis_complete.connect(self.on_analysis_complete)
        self.analysis_thread.start()

    def update_progress(self, progress):
        """Update analysis progress."""
        self.progress_bar.setValue(progress)

    def on_analysis_complete(self, results, summary):
        """Handle analysis completion."""
        self.progress_bar.setVisible(False)
        self.analysis_results = results

        # Update summary
        self.summary_text.setPlainText(summary)

        # Update results table
        self.display_results(results)

        self.status_label.setText("Analysis complete")

    def display_results(self, results):
        """Display analysis results in the table."""
        self.results_table.setRowCount(0)

        if not results:
            return

        for key, value in results.items():
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)

            # Item
            self.results_table.setItem(row, 0, QTableWidgetItem(str(key)))

            # Value
            if isinstance(value, (int, float)):
                if isinstance(value, float):
                    value_str = f"{value:.4f}"
                else:
                    value_str = str(value)
            elif isinstance(value, dict):
                value_str = f"{len(value)} items"
            else:
                value_str = str(value)

            self.results_table.setItem(row, 1, QTableWidgetItem(value_str))

            # Description (would be analysis-specific)
            description = self.get_result_description(key)
            self.results_table.setItem(row, 2, QTableWidgetItem(description))

    def get_result_description(self, key):
        """Get description for analysis result."""
        descriptions = {
            "total_frames": "Total number of CAN frames analyzed",
            "unique_ids": "Number of unique CAN message IDs",
            "avg_data_length": "Average data payload length in bytes",
            "entropy": "Shannon entropy of the data distribution",
            "most_common_byte": "Most frequently occurring byte value",
            "bit_transitions": "Number of bit transitions detected",
            "avg_interval": "Average time between frames (ms)",
            "jitter": "Timing jitter standard deviation (ms)"
        }
        return descriptions.get(key, "")

    def set_frames(self, frames):
        """Set the frames to analyze."""
        self.frames = frames or []
        self.status_label.setText(f"Loaded {len(self.frames)} frames for analysis")


class AnalysisThread(QThread):
    """Background thread for running frame analysis."""

    progress_updated = pyqtSignal(int)
    analysis_complete = pyqtSignal(dict, str)

    def __init__(self, frames, analysis_type):
        super().__init__()
        self.frames = frames
        self.analysis_type = analysis_type

    def run(self):
        """Run the analysis in background."""
        try:
            if self.analysis_type == "Byte Frequency Analysis":
                results, summary = self.byte_frequency_analysis()
            elif self.analysis_type == "Bit Transition Analysis":
                results, summary = self.bit_transition_analysis()
            elif self.analysis_type == "Entropy Analysis":
                results, summary = self.entropy_analysis()
            elif self.analysis_type == "Message Timing Analysis":
                results, summary = self.timing_analysis()
            elif self.analysis_type == "Data Pattern Analysis":
                results, summary = self.pattern_analysis()
            else:
                results, summary = {}, "Unknown analysis type"

            self.analysis_complete.emit(results, summary)

        except Exception as e:
            self.analysis_complete.emit({}, f"Analysis failed: {str(e)}")

    def byte_frequency_analysis(self):
        """Analyze byte frequency distribution."""
        self.progress_updated.emit(10)

        byte_counts = collections.Counter()
        total_bytes = 0

        for frame in self.frames:
            if hasattr(frame, 'data') and frame.data:
                for byte in frame.data:
                    byte_counts[byte] += 1
                    total_bytes += 1

        self.progress_updated.emit(50)

        # Calculate statistics
        most_common = byte_counts.most_common(1)[0] if byte_counts else (0, 0)
        unique_bytes = len(byte_counts)

        results = {
            "total_bytes": total_bytes,
            "unique_bytes": unique_bytes,
            "most_common_byte": f"0x{most_common[0]:02X}",
            "most_common_count": most_common[1],
            "byte_frequencies": dict(byte_counts.most_common(10))
        }

        summary = f"Analyzed {total_bytes} bytes across {len(self.frames)} frames.\n"
        summary += f"Found {unique_bytes} unique byte values.\n"
        summary += f"Most common byte: 0x{most_common[0]:02X} ({most_common[1]} occurrences)"

        self.progress_updated.emit(100)
        return results, summary

    def bit_transition_analysis(self):
        """Analyze bit transitions in frame data."""
        self.progress_updated.emit(10)

        transitions = 0
        total_bits = 0

        for frame in self.frames:
            if hasattr(frame, 'data') and frame.data:
                for byte in frame.data:
                    # Count bit transitions within each byte
                    for i in range(7):  # 7 transitions possible in 8 bits
                        if (byte >> i) & 1 != (byte >> (i + 1)) & 1:
                            transitions += 1
                    total_bits += 8

        self.progress_updated.emit(50)

        # Calculate transition density
        density = transitions / total_bits if total_bits > 0 else 0

        results = {
            "total_bits": total_bits,
            "bit_transitions": transitions,
            "transition_density": density,
            "transitions_per_byte": transitions / len(self.frames) if self.frames else 0
        }

        summary = f"Analyzed {total_bits} bits across {len(self.frames)} frames.\n"
        summary += f"Found {transitions} bit transitions.\n"
        summary += ".4f"

        self.progress_updated.emit(100)
        return results, summary

    def entropy_analysis(self):
        """Calculate Shannon entropy of the data."""
        self.progress_updated.emit(10)

        byte_counts = collections.Counter()

        for frame in self.frames:
            if hasattr(frame, 'data') and frame.data:
                for byte in frame.data:
                    byte_counts[byte] += 1

        self.progress_updated.emit(50)

        total_bytes = sum(byte_counts.values())
        entropy = 0.0

        for count in byte_counts.values():
            if count > 0:
                probability = count / total_bytes
                entropy -= probability * math.log2(probability)

        max_entropy = math.log2(256)  # 8 bits
        entropy_ratio = entropy / max_entropy if max_entropy > 0 else 0

        results = {
            "total_bytes": total_bytes,
            "unique_bytes": len(byte_counts),
            "entropy": entropy,
            "max_entropy": max_entropy,
            "entropy_ratio": entropy_ratio
        }

        summary = f"Shannon entropy: {entropy:.4f} bits per byte\n"
        summary += f"Maximum possible: {max_entropy:.4f} bits per byte\n"
        summary += ".2%"

        self.progress_updated.emit(100)
        return results, summary

    def timing_analysis(self):
        """Analyze message timing and intervals."""
        self.progress_updated.emit(10)

        if len(self.frames) < 2:
            return {"error": "Need at least 2 frames for timing analysis"}, "Insufficient data"

        # Sort frames by timestamp
        sorted_frames = sorted(self.frames, key=lambda f: getattr(f, 'timestamp', 0))

        intervals = []
        for i in range(1, len(sorted_frames)):
            t1 = getattr(sorted_frames[i-1], 'timestamp', 0)
            t2 = getattr(sorted_frames[i], 'timestamp', 0)
            if t2 > t1:
                intervals.append((t2 - t1) * 1000)  # Convert to ms

        self.progress_updated.emit(50)

        if not intervals:
            return {"error": "No valid timestamps found"}, "No timing data available"

        avg_interval = sum(intervals) / len(intervals)
        min_interval = min(intervals)
        max_interval = max(intervals)

        # Calculate jitter (standard deviation)
        variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
        jitter = math.sqrt(variance)

        results = {
            "total_frames": len(sorted_frames),
            "avg_interval": avg_interval,
            "min_interval": min_interval,
            "max_interval": max_interval,
            "jitter": jitter,
            "intervals_analyzed": len(intervals)
        }

        summary = f"Analyzed timing for {len(sorted_frames)} frames.\n"
        summary += ".2f"
        summary += ".2f"
        summary += ".2f"

        self.progress_updated.emit(100)
        return results, summary

    def pattern_analysis(self):
        """Analyze data patterns and repetitions."""
        self.progress_updated.emit(10)

        patterns = collections.Counter()
        data_sequences = []

        for frame in self.frames:
            if hasattr(frame, 'data') and frame.data:
                data_tuple = tuple(frame.data)
                data_sequences.append(data_tuple)
                patterns[data_tuple] += 1

        self.progress_updated.emit(50)

        # Find most common patterns
        common_patterns = patterns.most_common(10)

        # Calculate pattern diversity
        unique_patterns = len(patterns)
        total_frames = len(data_sequences)
        diversity_ratio = unique_patterns / total_frames if total_frames > 0 else 0

        results = {
            "total_frames": total_frames,
            "unique_patterns": unique_patterns,
            "pattern_diversity": diversity_ratio,
            "most_common_patterns": common_patterns[:5]
        }

        summary = f"Analyzed {total_frames} frames with data.\n"
        summary += f"Found {unique_patterns} unique data patterns.\n"
        summary += ".2%"

        if common_patterns:
            most_common = common_patterns[0]
            summary += f"\nMost common pattern appears {most_common[1]} times."

        self.progress_updated.emit(100)
        return results, summary