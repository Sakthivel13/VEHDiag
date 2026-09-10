"""
Bus Statistics Window - Advanced Tool
Provides comprehensive statistics and analysis of CAN bus performance and health.
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTableWidget, QTableWidgetItem,
                             QProgressBar, QTextEdit, QGroupBox, QSplitter,
                             QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                             QTabWidget, QMessageBox, QHeaderView, QTreeWidget,
                             QTreeWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush, QPen
from PyQt5.QtChart import (QChart, QChartView, QLineSeries, QValueAxis,
                           QBarSeries, QBarSet, QBarCategoryAxis, QPieSeries)
import time
import numpy as np
from collections import defaultdict, Counter


class BusStatisticsWorker(QThread):
    """Worker thread for bus statistics calculation"""
    progress = pyqtSignal(int)
    statistics_updated = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, frames, config):
        super().__init__()
        self.frames = frames
        self.config = config
        self.is_running = True

    def run(self):
        try:
            self.log_message.emit("Calculating bus statistics...")

            if not self.frames:
                self.error.emit("No frames available for analysis")
                return

            # Sort frames by timestamp
            sorted_frames = sorted(self.frames, key=lambda f: f.timestamp)

            statistics = {}

            # Basic statistics
            statistics.update(self._calculate_basic_stats(sorted_frames))

            # ID statistics
            statistics.update(self._calculate_id_stats(sorted_frames))

            # Timing statistics
            statistics.update(self._calculate_timing_stats(sorted_frames))

            # Data statistics
            statistics.update(self._calculate_data_stats(sorted_frames))

            # Bus load statistics
            statistics.update(self._calculate_bus_load_stats(sorted_frames))

            # Error statistics (if available)
            statistics.update(self._calculate_error_stats(sorted_frames))

            self.log_message.emit("Bus statistics calculation complete.")
            self.finished.emit(statistics)

        except Exception as e:
            self.error.emit(f"Statistics calculation error: {str(e)}")

    def _calculate_basic_stats(self, frames):
        """Calculate basic frame statistics"""
        stats = {
            'total_frames': len(frames),
            'unique_ids': len(set(f.can_id for f in frames)),
            'time_span': 0.0,
            'avg_frame_rate': 0.0,
            'total_data_bytes': sum(f.dlc for f in frames)
        }

        if len(frames) > 1:
            stats['time_span'] = frames[-1].timestamp - frames[0].timestamp
            if stats['time_span'] > 0:
                stats['avg_frame_rate'] = len(frames) / stats['time_span']

        return {'basic': stats}

    def _calculate_id_stats(self, frames):
        """Calculate statistics per CAN ID"""
        id_counts = Counter(f.can_id for f in frames)
        id_stats = {}

        for can_id, count in id_counts.items():
            id_frames = [f for f in frames if f.can_id == can_id]

            # Calculate timing stats for this ID
            if len(id_frames) > 1:
                timestamps = [f.timestamp for f in id_frames]
                intervals = np.diff(timestamps)
                avg_interval = np.mean(intervals)
                std_interval = np.std(intervals)
                min_interval = np.min(intervals)
                max_interval = np.max(intervals)
            else:
                avg_interval = std_interval = min_interval = max_interval = 0

            # Calculate data entropy
            data_entropy = self._calculate_data_entropy(id_frames)

            id_stats[can_id] = {
                'count': count,
                'percentage': (count / len(frames)) * 100,
                'avg_interval': avg_interval,
                'std_interval': std_interval,
                'min_interval': min_interval,
                'max_interval': max_interval,
                'data_entropy': data_entropy,
                'first_seen': id_frames[0].timestamp,
                'last_seen': id_frames[-1].timestamp
            }

        return {'id_stats': id_stats}

    def _calculate_timing_stats(self, frames):
        """Calculate timing-related statistics"""
        if len(frames) < 2:
            return {'timing': {'intervals': [], 'stats': {}}}

        timestamps = [f.timestamp for f in frames]
        intervals = np.diff(timestamps)

        timing_stats = {
            'mean_interval': float(np.mean(intervals)),
            'std_interval': float(np.std(intervals)),
            'min_interval': float(np.min(intervals)),
            'max_interval': float(np.max(intervals)),
            'median_interval': float(np.median(intervals)),
            'q25_interval': float(np.percentile(intervals, 25)),
            'q75_interval': float(np.percentile(intervals, 75))
        }

        # Calculate jitter (coefficient of variation)
        if timing_stats['mean_interval'] > 0:
            timing_stats['jitter'] = timing_stats['std_interval'] / timing_stats['mean_interval']
        else:
            timing_stats['jitter'] = 0

        return {'timing': {'intervals': intervals.tolist(), 'stats': timing_stats}}

    def _calculate_data_stats(self, frames):
        """Calculate data content statistics"""
        data_stats = {
            'avg_dlc': 0,
            'dlc_distribution': defaultdict(int),
            'byte_frequency': [defaultdict(int) for _ in range(8)],
            'data_patterns': Counter()
        }

        if not frames:
            return {'data': data_stats}

        # DLC statistics
        dlcs = [f.dlc for f in frames]
        data_stats['avg_dlc'] = np.mean(dlcs)
        for dlc in dlcs:
            data_stats['dlc_distribution'][dlc] += 1

        # Byte frequency analysis
        for frame in frames:
            # Count patterns (first 2-4 bytes as pattern)
            if len(frame.data) >= 2:
                pattern = frame.data[:min(4, len(frame.data))]
                data_stats['data_patterns'][pattern] += 1

            # Count byte frequencies
            for i, byte in enumerate(frame.data):
                if i < 8:
                    data_stats['byte_frequency'][i][byte] += 1

        return {'data': data_stats}

    def _calculate_bus_load_stats(self, frames):
        """Calculate bus load statistics"""
        if not frames:
            return {'bus_load': {}}

        # Calculate bus load over time windows
        window_size = self.config.get('load_window', 0.1)  # 100ms windows
        time_windows = defaultdict(list)

        for frame in frames:
            window_start = int(frame.timestamp / window_size) * window_size
            time_windows[window_start].append(frame)

        # Calculate load per window
        window_loads = []
        for window_start, window_frames in time_windows.items():
            # Estimate bus load (rough calculation)
            # CAN bus load = (bits per second) / 1000000 * 100%
            # This is a simplified calculation
            total_bits = sum((f.dlc * 8 + 47) for f in window_frames)  # 47 bits overhead per frame
            load_percentage = (total_bits / (window_size * 1000000)) * 100
            window_loads.append(load_percentage)

        bus_load_stats = {
            'avg_load': np.mean(window_loads) if window_loads else 0,
            'max_load': np.max(window_loads) if window_loads else 0,
            'min_load': np.min(window_loads) if window_loads else 0,
            'load_std': np.std(window_loads) if window_loads else 0,
            'window_size': window_size
        }

        return {'bus_load': bus_load_stats}

    def _calculate_error_stats(self, frames):
        """Calculate error statistics (if error frames are available)"""
        error_stats = {
            'error_frames': 0,
            'error_rate': 0.0,
            'error_types': defaultdict(int)
        }

        # This would require error frame detection in the pipeline
        # For now, return empty stats
        return {'errors': error_stats}

    def _calculate_data_entropy(self, frames):
        """Calculate Shannon entropy of frame data"""
        if not frames:
            return 0

        # Collect all data bytes
        all_bytes = []
        for frame in frames:
            all_bytes.extend(frame.data)

        if not all_bytes:
            return 0

        # Calculate byte frequencies
        byte_counts = Counter(all_bytes)
        total_bytes = len(all_bytes)

        # Calculate entropy
        entropy = 0
        for count in byte_counts.values():
            p = count / total_bytes
            if p > 0:
                entropy -= p * np.log2(p)

        return entropy

    def stop(self):
        self.is_running = False


class BusStatisticsWindow(QMainWindow):
    """Main window for CAN bus statistics"""

    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.statistics = {}
        self.stats_worker = None

        self.setWindowTitle("Bus Statistics - PyCANAnalyzer")
        self.setGeometry(200, 200, 1400, 900)

        self.init_ui()
        self.load_frames()

    def init_ui(self):
        """Initialize the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Control panel
        self.create_control_panel(layout)

        # Main content tabs
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Overview tab
        self.create_overview_tab()

        # ID Analysis tab
        self.create_id_analysis_tab()

        # Timing Analysis tab
        self.create_timing_tab()

        # Data Analysis tab
        self.create_data_tab()

        # Bus Load tab
        self.create_bus_load_tab()

    def create_control_panel(self, parent_layout):
        """Create the control panel"""
        control_group = QGroupBox("Statistics Controls")
        control_layout = QHBoxLayout(control_group)

        # Analysis controls
        self.calculate_button = QPushButton("📊 Calculate Statistics")
        self.calculate_button.clicked.connect(self.calculate_statistics)
        control_layout.addWidget(self.calculate_button)

        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.clicked.connect(self.stop_calculation)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)

        # Options
        options_layout = QVBoxLayout()

        self.realtime_checkbox = QCheckBox("Real-time updates")
        self.realtime_checkbox.setChecked(False)
        options_layout.addWidget(self.realtime_checkbox)

        window_layout = QHBoxLayout()
        window_layout.addWidget(QLabel("Load window (s):"))
        self.window_spin = QDoubleSpinBox()
        self.window_spin.setRange(0.01, 1.0)
        self.window_spin.setValue(0.1)
        self.window_spin.setSingleStep(0.01)
        window_layout.addWidget(self.window_spin)
        options_layout.addLayout(window_layout)

        control_layout.addLayout(options_layout)

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

    def create_overview_tab(self):
        """Create the overview statistics tab"""
        overview_widget = QWidget()
        overview_layout = QVBoxLayout(overview_widget)

        # Basic statistics tree
        self.overview_tree = QTreeWidget()
        self.overview_tree.setHeaderLabel("Statistic")
        self.overview_tree.setColumnCount(2)
        self.overview_tree.setHeaderLabels(["Statistic", "Value"])
        overview_layout.addWidget(self.overview_tree)

        # Summary text
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_group)

        self.summary_text = QTextEdit()
        self.summary_text.setMaximumHeight(150)
        self.summary_text.setReadOnly(True)
        summary_layout.addWidget(self.summary_text)

        overview_layout.addWidget(summary_group)

        self.tab_widget.addTab(overview_widget, "Overview")

    def create_id_analysis_tab(self):
        """Create the ID analysis tab"""
        id_widget = QWidget()
        id_layout = QVBoxLayout(id_widget)

        # ID statistics table
        self.id_table = QTableWidget()
        self.id_table.setColumnCount(8)
        self.id_table.setHorizontalHeaderLabels([
            "ID", "Count", "%", "Avg Interval", "Std Dev", "Min Interval",
            "Max Interval", "Data Entropy"
        ])

        header = self.id_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

        id_layout.addWidget(self.id_table)

        # ID details
        details_group = QGroupBox("ID Details")
        details_layout = QVBoxLayout(details_group)

        self.id_details_tree = QTreeWidget()
        self.id_details_tree.setHeaderLabel("Detail")
        self.id_details_tree.setColumnCount(2)
        self.id_details_tree.setHeaderLabels(["Detail", "Value"])
        details_layout.addWidget(self.id_details_tree)

        id_layout.addWidget(details_group)

        self.tab_widget.addTab(id_widget, "ID Analysis")

    def create_timing_tab(self):
        """Create the timing analysis tab"""
        timing_widget = QWidget()
        timing_layout = QVBoxLayout(timing_widget)

        # Timing statistics
        stats_group = QGroupBox("Timing Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.timing_tree = QTreeWidget()
        self.timing_tree.setHeaderLabel("Statistic")
        self.timing_tree.setColumnCount(2)
        self.timing_tree.setHeaderLabels(["Statistic", "Value"])
        stats_layout.addWidget(self.timing_tree)

        timing_layout.addWidget(stats_group)

        # Interval distribution chart would go here
        chart_group = QGroupBox("Interval Distribution")
        chart_layout = QVBoxLayout(chart_group)

        self.timing_chart_view = QLabel("Chart view - not implemented")
        chart_layout.addWidget(self.timing_chart_view)

        timing_layout.addWidget(chart_group)

        self.tab_widget.addTab(timing_widget, "Timing")

    def create_data_tab(self):
        """Create the data analysis tab"""
        data_widget = QWidget()
        data_layout = QVBoxLayout(data_widget)

        # Data statistics
        stats_group = QGroupBox("Data Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.data_tree = QTreeWidget()
        self.data_tree.setHeaderLabel("Statistic")
        self.data_tree.setColumnCount(2)
        self.data_tree.setHeaderLabels(["Statistic", "Value"])
        stats_layout.addWidget(self.data_tree)

        data_layout.addWidget(stats_group)

        # DLC distribution
        dlc_group = QGroupBox("DLC Distribution")
        dlc_layout = QVBoxLayout(dlc_group)

        self.dlc_table = QTableWidget()
        self.dlc_table.setColumnCount(2)
        self.dlc_table.setHorizontalHeaderLabels(["DLC", "Count"])
        dlc_layout.addWidget(self.dlc_table)

        data_layout.addWidget(dlc_group)

        self.tab_widget.addTab(data_widget, "Data Analysis")

    def create_bus_load_tab(self):
        """Create the bus load tab"""
        load_widget = QWidget()
        load_layout = QVBoxLayout(load_widget)

        # Bus load statistics
        stats_group = QGroupBox("Bus Load Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.load_tree = QTreeWidget()
        self.load_tree.setHeaderLabel("Statistic")
        self.load_tree.setColumnCount(2)
        self.load_tree.setHeaderLabels(["Statistic", "Value"])
        stats_layout.addWidget(self.load_tree)

        load_layout.addWidget(stats_group)

        # Load chart
        chart_group = QGroupBox("Bus Load Over Time")
        chart_layout = QVBoxLayout(chart_group)

        self.load_chart_view = QLabel("Load chart - not implemented")
        chart_layout.addWidget(self.load_chart_view)

        load_layout.addWidget(chart_group)

        self.tab_widget.addTab(load_widget, "Bus Load")

    def load_frames(self):
        """Load frames from the pipeline"""
        try:
            # Get frames from pipeline
            self.frames = self.pipeline.get_all_frames() if hasattr(self.pipeline, 'get_all_frames') else []
            self.log_message(f"Loaded {len(self.frames)} frames for analysis")
        except Exception as e:
            self.log_message(f"Error loading frames: {str(e)}")
            self.frames = []

    def calculate_statistics(self):
        """Start statistics calculation"""
        if not self.frames:
            QMessageBox.warning(self, "No Frames", "No frames available for analysis.")
            return

        if self.stats_worker and self.stats_worker.isRunning():
            return

        # Clear previous results
        self.clear_results()

        # Get configuration
        config = {
            'load_window': self.window_spin.value(),
            'realtime': self.realtime_checkbox.isChecked()
        }

        # Start statistics worker
        self.stats_worker = BusStatisticsWorker(self.frames, config)
        self.stats_worker.progress.connect(self.update_progress)
        self.stats_worker.statistics_updated.connect(self.on_statistics_updated)
        self.stats_worker.finished.connect(self.on_calculation_finished)
        self.stats_worker.error.connect(self.on_calculation_error)
        self.stats_worker.log_message.connect(self.log_message)

        self.stats_worker.start()

        self.calculate_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Calculating...")

    def stop_calculation(self):
        """Stop statistics calculation"""
        if self.stats_worker:
            self.stats_worker.stop()
            self.stats_worker.wait()

        self.calculate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")

    def clear_results(self):
        """Clear all results displays"""
        self.overview_tree.clear()
        self.id_table.setRowCount(0)
        self.id_details_tree.clear()
        self.timing_tree.clear()
        self.data_tree.clear()
        self.dlc_table.setRowCount(0)
        self.load_tree.clear()
        self.summary_text.clear()
        self.progress_bar.setValue(0)

    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def on_statistics_updated(self, partial_stats):
        """Handle partial statistics update"""
        # Update displays with partial results
        pass

    def on_calculation_finished(self, statistics):
        """Handle calculation completion"""
        self.statistics = statistics
        self.update_all_displays()

        self.calculate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Completed")

    def update_all_displays(self):
        """Update all display widgets with statistics"""
        self.update_overview_display()
        self.update_id_display()
        self.update_timing_display()
        self.update_data_display()
        self.update_bus_load_display()

    def update_overview_display(self):
        """Update the overview statistics display"""
        if 'basic' not in self.statistics:
            return

        basic = self.statistics['basic']
        self.overview_tree.clear()

        # Basic stats
        total_item = QTreeWidgetItem(["Total Frames", str(basic['total_frames'])])
        self.overview_tree.addTopLevelItem(total_item)

        unique_item = QTreeWidgetItem(["Unique IDs", str(basic['unique_ids'])])
        self.overview_tree.addTopLevelItem(unique_item)

        time_item = QTreeWidgetItem(["Time Span", f"{basic['time_span']:.3f}s"])
        self.overview_tree.addTopLevelItem(time_item)

        rate_item = QTreeWidgetItem(["Avg Frame Rate", f"{basic['avg_frame_rate']:.1f} fps"])
        self.overview_tree.addTopLevelItem(rate_item)

        data_item = QTreeWidgetItem(["Total Data Bytes", str(basic['total_data_bytes'])])
        self.overview_tree.addTopLevelItem(data_item)

        # Generate summary text
        summary = f"CAN Bus Analysis Summary:\n\n"
        summary += f"• Captured {basic['total_frames']} frames from {basic['unique_ids']} different IDs\n"
        summary += f"• Recording duration: {basic['time_span']:.1f} seconds\n"
        summary += f"• Average frame rate: {basic['avg_frame_rate']:.1f} frames/second\n"
        summary += f"• Total data transferred: {basic['total_data_bytes']} bytes\n"

        if basic['time_span'] > 0:
            data_rate = basic['total_data_bytes'] / basic['time_span']
            summary += f"• Average data rate: {data_rate:.1f} bytes/second\n"

        self.summary_text.setPlainText(summary)

    def update_id_display(self):
        """Update the ID analysis display"""
        if 'id_stats' not in self.statistics:
            return

        id_stats = self.statistics['id_stats']
        self.id_table.setRowCount(len(id_stats))

        for row, (can_id, stats) in enumerate(sorted(id_stats.items())):
            # ID
            id_item = QTableWidgetItem(f"0x{can_id:03X}")
            self.id_table.setItem(row, 0, id_item)

            # Count
            count_item = QTableWidgetItem(str(stats['count']))
            self.id_table.setItem(row, 1, count_item)

            # Percentage
            pct_item = QTableWidgetItem(f"{stats['percentage']:.1f}%")
            self.id_table.setItem(row, 2, pct_item)

            # Timing stats
            avg_item = QTableWidgetItem(f"{stats['avg_interval']:.6f}")
            self.id_table.setItem(row, 3, avg_item)

            std_item = QTableWidgetItem(f"{stats['std_interval']:.6f}")
            self.id_table.setItem(row, 4, std_item)

            min_item = QTableWidgetItem(f"{stats['min_interval']:.6f}")
            self.id_table.setItem(row, 5, min_item)

            max_item = QTableWidgetItem(f"{stats['max_interval']:.6f}")
            self.id_table.setItem(row, 6, max_item)

            # Data entropy
            entropy_item = QTableWidgetItem(f"{stats['data_entropy']:.3f}")
            self.id_table.setItem(row, 7, entropy_item)

    def update_timing_display(self):
        """Update the timing statistics display"""
        if 'timing' not in self.statistics:
            return

        timing = self.statistics['timing']['stats']
        self.timing_tree.clear()

        for stat_name, value in timing.items():
            if isinstance(value, float):
                display_value = f"{value:.6f}"
            else:
                display_value = str(value)

            item = QTreeWidgetItem([stat_name.replace('_', ' ').title(), display_value])
            self.timing_tree.addTopLevelItem(item)

    def update_data_display(self):
        """Update the data statistics display"""
        if 'data' not in self.statistics:
            return

        data = self.statistics['data']
        self.data_tree.clear()

        # Basic data stats
        avg_dlc_item = QTreeWidgetItem(["Average DLC", f"{data['avg_dlc']:.2f}"])
        self.data_tree.addTopLevelItem(avg_dlc_item)

        patterns_item = QTreeWidgetItem(["Unique Data Patterns", str(len(data['data_patterns']))])
        self.data_tree.addTopLevelItem(patterns_item)

        # DLC distribution
        self.dlc_table.setRowCount(len(data['dlc_distribution']))
        for row, (dlc, count) in enumerate(sorted(data['dlc_distribution'].items())):
            dlc_item = QTableWidgetItem(str(dlc))
            self.dlc_table.setItem(row, 0, dlc_item)

            count_item = QTableWidgetItem(str(count))
            self.dlc_table.setItem(row, 1, count_item)

    def update_bus_load_display(self):
        """Update the bus load statistics display"""
        if 'bus_load' not in self.statistics:
            return

        bus_load = self.statistics['bus_load']
        self.load_tree.clear()

        for stat_name, value in bus_load.items():
            if isinstance(value, float):
                display_value = f"{value:.3f}"
            else:
                display_value = str(value)

            item = QTreeWidgetItem([stat_name.replace('_', ' ').title(), display_value])
            self.load_tree.addTopLevelItem(item)

    def on_calculation_error(self, error_msg):
        """Handle calculation error"""
        self.calculate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Error")
        self.log_message(f"Calculation error: {error_msg}")
        QMessageBox.critical(self, "Calculation Error", error_msg)

    def log_message(self, message):
        """Add message to log"""
        # For now, just print to console. Could add a log widget later.
        print(f"[BusStats] {message}")

    def closeEvent(self, event):
        """Handle window close event"""
        if self.stats_worker and self.stats_worker.isRunning():
            self.stats_worker.stop()
            self.stats_worker.wait()
        event.accept()