"""
Anomaly Detection Window - Advanced Tool
Detects anomalous CAN traffic patterns using statistical analysis and machine learning.
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTableWidget, QTableWidgetItem,
                             QProgressBar, QTextEdit, QGroupBox, QSplitter,
                             QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                             QTabWidget, QMessageBox, QHeaderView, QTreeWidget,
                             QTreeWidgetItem, QGraphicsView, QGraphicsScene)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush, QPen, QPainter
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis, QScatterSeries
import time
import numpy as np
from collections import defaultdict, deque


class AnomalyDetectionWorker(QThread):
    """Worker thread for anomaly detection analysis"""
    progress = pyqtSignal(int)
    anomaly_detected = pyqtSignal(dict)
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
            self.log_message.emit("Starting anomaly detection analysis...")

            if not self.frames:
                self.error.emit("No frames available for analysis")
                return

            anomalies = []

            # Sort frames by timestamp
            sorted_frames = sorted(self.frames, key=lambda f: f.timestamp)

            # Detect different types of anomalies
            if self.config.get('detect_frequency_anomalies', True):
                freq_anomalies = self._detect_frequency_anomalies(sorted_frames)
                anomalies.extend(freq_anomalies)

            if self.config.get('detect_data_anomalies', True):
                data_anomalies = self._detect_data_anomalies(sorted_frames)
                anomalies.extend(data_anomalies)

            if self.config.get('detect_timing_anomalies', True):
                timing_anomalies = self._detect_timing_anomalies(sorted_frames)
                anomalies.extend(timing_anomalies)

            if self.config.get('detect_burst_anomalies', True):
                burst_anomalies = self._detect_burst_anomalies(sorted_frames)
                anomalies.extend(burst_anomalies)

            # Sort anomalies by timestamp
            anomalies.sort(key=lambda a: a['timestamp'])

            # Emit anomalies
            for anomaly in anomalies:
                self.anomaly_detected.emit(anomaly)

            self.log_message.emit(f"Anomaly detection complete. Found {len(anomalies)} anomalies.")
            self.finished.emit(anomalies)

        except Exception as e:
            self.error.emit(f"Anomaly detection error: {str(e)}")

    def _detect_frequency_anomalies(self, frames):
        """Detect anomalies in message frequency"""
        anomalies = []

        # Group frames by ID
        id_groups = defaultdict(list)
        for frame in frames:
            id_groups[frame.can_id].append(frame)

        for can_id, id_frames in id_groups.items():
            if len(id_frames) < 10:  # Need minimum frames for analysis
                continue

            # Calculate inter-arrival times
            timestamps = [f.timestamp for f in id_frames]
            intervals = np.diff(timestamps)

            if len(intervals) < 5:
                continue

            # Calculate statistics
            mean_interval = np.mean(intervals)
            std_interval = np.std(intervals)

            # Detect outliers using modified Z-score
            median_interval = np.median(intervals)
            mad = np.median(np.abs(intervals - median_interval))

            if mad == 0:  # All intervals are the same
                continue

            for i, interval in enumerate(intervals):
                modified_z = 0.6745 * (interval - median_interval) / mad

                if abs(modified_z) > self.config.get('frequency_threshold', 3.5):
                    anomaly = {
                        'type': 'frequency',
                        'id': can_id,
                        'timestamp': timestamps[i+1],
                        'description': f'Unusual interval: {interval:.6f}s (expected ~{mean_interval:.6f}s)',
                        'severity': min(abs(modified_z) / 5.0, 1.0),
                        'data': {
                            'interval': interval,
                            'expected': mean_interval,
                            'z_score': modified_z
                        }
                    }
                    anomalies.append(anomaly)

        return anomalies

    def _detect_data_anomalies(self, frames):
        """Detect anomalies in message data content"""
        anomalies = []

        # Group frames by ID
        id_groups = defaultdict(list)
        for frame in frames:
            id_groups[frame.can_id].append(frame)

        for can_id, id_frames in id_groups.items():
            if len(id_frames) < 20:  # Need more frames for data analysis
                continue

            # Analyze each byte position
            max_dlc = max(f.dlc for f in id_frames)
            if max_dlc == 0:
                continue

            for byte_pos in range(max_dlc):
                byte_values = []
                timestamps = []

                for frame in id_frames:
                    if len(frame.data) > byte_pos:
                        byte_values.append(frame.data[byte_pos])
                        timestamps.append(frame.timestamp)

                if len(byte_values) < 10:
                    continue

                # Calculate statistics
                mean_val = np.mean(byte_values)
                std_val = np.std(byte_values)

                if std_val == 0:  # Constant value
                    continue

                # Detect outliers
                for i, (value, timestamp) in enumerate(zip(byte_values, timestamps)):
                    z_score = abs(value - mean_val) / std_val

                    if z_score > self.config.get('data_threshold', 3.0):
                        anomaly = {
                            'type': 'data',
                            'id': can_id,
                            'timestamp': timestamp,
                            'description': f'Unusual byte {byte_pos} value: 0x{value:02X} (expected ~0x{int(mean_val):02X})',
                            'severity': min(z_score / 5.0, 1.0),
                            'data': {
                                'byte_pos': byte_pos,
                                'value': value,
                                'expected': mean_val,
                                'z_score': z_score
                            }
                        }
                        anomalies.append(anomaly)

        return anomalies

    def _detect_timing_anomalies(self, frames):
        """Detect anomalies in message timing patterns"""
        anomalies = []

        if len(frames) < 10:
            return anomalies

        # Calculate global timing statistics
        timestamps = [f.timestamp for f in frames]
        intervals = np.diff(timestamps)

        # Look for sudden changes in bus activity
        window_size = min(50, len(intervals) // 4)

        for i in range(window_size, len(intervals) - window_size):
            before_window = intervals[i-window_size:i]
            after_window = intervals[i:i+window_size]

            before_mean = np.mean(before_window)
            after_mean = np.mean(after_window)

            if before_mean == 0:
                continue

            change_ratio = after_mean / before_mean

            if change_ratio > self.config.get('timing_change_threshold', 5.0) or change_ratio < 1/self.config.get('timing_change_threshold', 5.0):
                anomaly = {
                    'type': 'timing',
                    'id': None,  # Global anomaly
                    'timestamp': timestamps[i],
                    'description': f'Sudden timing change: {change_ratio:.1f}x {"faster" if change_ratio < 1 else "slower"}',
                    'severity': min(abs(np.log(change_ratio)) / 2.0, 1.0),
                    'data': {
                        'change_ratio': change_ratio,
                        'before_mean': before_mean,
                        'after_mean': after_mean
                    }
                }
                anomalies.append(anomaly)

        return anomalies

    def _detect_burst_anomalies(self, frames):
        """Detect message burst anomalies"""
        anomalies = []

        # Group frames in time windows
        window_size = self.config.get('burst_window', 0.1)  # 100ms windows
        time_windows = defaultdict(list)

        for frame in frames:
            window_start = int(frame.timestamp / window_size) * window_size
            time_windows[window_start].append(frame)

        # Calculate statistics
        window_counts = [len(frames) for frames in time_windows.values()]
        mean_count = np.mean(window_counts)
        std_count = np.std(window_counts)

        if std_count == 0:
            return anomalies

        # Detect burst windows
        for window_start, window_frames in time_windows.items():
            count = len(window_frames)
            z_score = (count - mean_count) / std_count

            if z_score > self.config.get('burst_threshold', 3.0):
                # Check if it's a burst of the same ID
                id_counts = defaultdict(int)
                for frame in window_frames:
                    id_counts[frame.can_id] += 1

                dominant_id = max(id_counts.items(), key=lambda x: x[1])

                anomaly = {
                    'type': 'burst',
                    'id': dominant_id[0],
                    'timestamp': window_start,
                    'description': f'Message burst: {count} messages in {window_size}s window (expected ~{mean_count:.1f})',
                    'severity': min(z_score / 5.0, 1.0),
                    'data': {
                        'count': count,
                        'expected': mean_count,
                        'dominant_id': dominant_id[0],
                        'dominant_count': dominant_id[1],
                        'z_score': z_score
                    }
                }
                anomalies.append(anomaly)

        return anomalies

    def stop(self):
        self.is_running = False


class AnomalyChart(QGraphicsView):
    """Custom chart view for anomaly visualization"""

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)

        # Chart data
        self.frames = []
        self.anomalies = []
        self.time_range = (0, 0)
        self.id_filter = None

    def set_data(self, frames, anomalies, time_range=None, id_filter=None):
        """Set chart data"""
        self.frames = frames
        self.anomalies = anomalies
        self.id_filter = id_filter

        if time_range:
            self.time_range = time_range
        elif frames:
            self.time_range = (frames[0].timestamp, frames[-1].timestamp)
        else:
            self.time_range = (0, 0)

        self.update_chart()

    def update_chart(self):
        """Update the chart visualization"""
        self.scene.clear()

        if not self.frames:
            return

        # Filter frames if needed
        display_frames = [f for f in self.frames if self.id_filter is None or f.can_id == self.id_filter]

        if not display_frames:
            return

        # Calculate dimensions
        margin = 50
        width = self.width() - 2 * margin
        height = self.height() - 2 * margin

        time_start, time_end = self.time_range
        time_span = time_end - time_start

        if time_span == 0:
            return

        # Draw time axis
        self.scene.addLine(margin, height + margin, width + margin, height + margin)

        # Draw frames as points
        max_id = max(f.can_id for f in display_frames) if display_frames else 0x7FF

        for frame in display_frames:
            x = margin + ((frame.timestamp - time_start) / time_span) * width
            y = margin + (1 - frame.can_id / max_id) * height

            # Color based on whether it's anomalous
            is_anomalous = any(a['timestamp'] <= frame.timestamp <= a['timestamp'] + 0.001 for a in self.anomalies)
            color = QColor(255, 100, 100) if is_anomalous else QColor(100, 100, 255)

            self.scene.addEllipse(x-2, y-2, 4, 4, QPen(color), color)

        # Draw anomaly markers
        for anomaly in self.anomalies:
            if self.id_filter and anomaly['id'] != self.id_filter:
                continue

            x = margin + ((anomaly['timestamp'] - time_start) / time_span) * width
            y = margin + 20  # Fixed position for anomaly markers

            # Draw triangle marker
            points = [QPointF(x, y), QPointF(x-5, y+10), QPointF(x+5, y+10)]
            self.scene.addPolygon(QPolygonF(points), QPen(QColor(255, 0, 0)), QColor(255, 0, 0))


class AnomalyDetectionWindow(QMainWindow):
    """Main window for CAN anomaly detection"""

    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.detected_anomalies = []
        self.detection_worker = None

        self.setWindowTitle("Anomaly Detection - PyCANAnalyzer")
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

        # Results tab
        self.create_results_tab()

        # Visualization tab
        self.create_visualization_tab()

        # Statistics tab
        self.create_statistics_tab()

    def create_control_panel(self, parent_layout):
        """Create the control panel"""
        control_group = QGroupBox("Detection Controls")
        control_layout = QHBoxLayout(control_group)

        # Analysis controls
        self.start_button = QPushButton("🔍 Start Detection")
        self.start_button.clicked.connect(self.start_detection)
        control_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)

        # Detection types
        types_layout = QVBoxLayout()

        detection_types = QHBoxLayout()
        self.frequency_checkbox = QCheckBox("Frequency Anomalies")
        self.frequency_checkbox.setChecked(True)
        detection_types.addWidget(self.frequency_checkbox)

        self.data_checkbox = QCheckBox("Data Anomalies")
        self.data_checkbox.setChecked(True)
        detection_types.addWidget(self.data_checkbox)

        self.timing_checkbox = QCheckBox("Timing Anomalies")
        self.timing_checkbox.setChecked(True)
        detection_types.addWidget(self.timing_checkbox)

        self.burst_checkbox = QCheckBox("Burst Anomalies")
        self.burst_checkbox.setChecked(True)
        detection_types.addWidget(self.burst_checkbox)

        types_layout.addLayout(detection_types)

        # Thresholds
        thresholds_layout = QHBoxLayout()
        thresholds_layout.addWidget(QLabel("Sensitivity:"))

        self.sensitivity_combo = QComboBox()
        self.sensitivity_combo.addItems(["Low", "Medium", "High", "Very High"])
        self.sensitivity_combo.setCurrentText("Medium")
        thresholds_layout.addWidget(self.sensitivity_combo)

        types_layout.addLayout(thresholds_layout)

        control_layout.addLayout(types_layout)

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

    def create_results_tab(self):
        """Create the results display tab"""
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "Time", "ID", "Type", "Description", "Severity"
        ])

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.results_table.itemSelectionChanged.connect(self.on_anomaly_selected)
        results_layout.addWidget(self.results_table)

        self.tab_widget.addTab(results_widget, "Results")

    def create_visualization_tab(self):
        """Create the visualization tab"""
        viz_widget = QWidget()
        viz_layout = QVBoxLayout(viz_widget)

        # Chart controls
        controls_layout = QHBoxLayout()

        self.id_filter_combo = QComboBox()
        self.id_filter_combo.addItem("All IDs", None)
        controls_layout.addWidget(QLabel("Filter ID:"))
        controls_layout.addWidget(self.id_filter_combo)

        self.refresh_chart_button = QPushButton("Refresh Chart")
        self.refresh_chart_button.clicked.connect(self.refresh_chart)
        controls_layout.addWidget(self.refresh_chart_button)

        controls_layout.addStretch()
        viz_layout.addLayout(controls_layout)

        # Chart view
        self.chart_view = AnomalyChart()
        viz_layout.addWidget(self.chart_view)

        self.tab_widget.addTab(viz_widget, "Visualization")

    def create_statistics_tab(self):
        """Create the statistics tab"""
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)

        # Statistics tree
        self.stats_tree = QTreeWidget()
        self.stats_tree.setHeaderLabel("Statistic")
        self.stats_tree.setColumnCount(2)
        self.stats_tree.setHeaderLabels(["Statistic", "Value"])
        stats_layout.addWidget(self.stats_tree)

        # Log output
        log_group = QGroupBox("Detection Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setFont(QFont("Courier New", 9))
        log_layout.addWidget(self.log_text)

        stats_layout.addWidget(log_group)

        self.tab_widget.addTab(stats_widget, "Statistics")

    def load_frames(self):
        """Load frames from the pipeline"""
        try:
            # Get frames from pipeline
            self.frames = self.pipeline.get_all_frames() if hasattr(self.pipeline, 'get_all_frames') else []
            self.log_message(f"Loaded {len(self.frames)} frames for analysis")

            # Update ID filter combo
            self.update_id_filter()

        except Exception as e:
            self.log_message(f"Error loading frames: {str(e)}")
            self.frames = []

    def update_id_filter(self):
        """Update the ID filter combo box"""
        self.id_filter_combo.clear()
        self.id_filter_combo.addItem("All IDs", None)

        if self.frames:
            unique_ids = sorted(set(f.can_id for f in self.frames))
            for can_id in unique_ids:
                self.id_filter_combo.addItem(f"0x{can_id:03X}", can_id)

    def start_detection(self):
        """Start anomaly detection analysis"""
        if not self.frames:
            QMessageBox.warning(self, "No Frames", "No frames available for analysis.")
            return

        if self.discovery_worker and self.discovery_worker.isRunning():
            return

        # Clear previous results
        self.detected_anomalies.clear()
        self.results_table.setRowCount(0)
        self.stats_tree.clear()
        self.progress_bar.setValue(0)

        # Get configuration
        sensitivity_map = {
            "Low": 2.0,
            "Medium": 3.0,
            "High": 4.0,
            "Very High": 5.0
        }
        base_threshold = sensitivity_map[self.sensitivity_combo.currentText()]

        config = {
            'detect_frequency_anomalies': self.frequency_checkbox.isChecked(),
            'detect_data_anomalies': self.data_checkbox.isChecked(),
            'detect_timing_anomalies': self.timing_checkbox.isChecked(),
            'detect_burst_anomalies': self.burst_checkbox.isChecked(),
            'frequency_threshold': base_threshold,
            'data_threshold': base_threshold,
            'timing_change_threshold': base_threshold,
            'burst_threshold': base_threshold,
            'burst_window': 0.1
        }

        # Start detection worker
        self.discovery_worker = AnomalyDetectionWorker(self.frames, config)
        self.discovery_worker.progress.connect(self.update_progress)
        self.discovery_worker.anomaly_detected.connect(self.on_anomaly_detected)
        self.discovery_worker.finished.connect(self.on_detection_finished)
        self.discovery_worker.error.connect(self.on_detection_error)
        self.discovery_worker.log_message.connect(self.log_message)

        self.discovery_worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Analyzing...")

    def stop_detection(self):
        """Stop anomaly detection"""
        if self.discovery_worker:
            self.discovery_worker.stop()
            self.discovery_worker.wait()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")

    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def on_anomaly_detected(self, anomaly):
        """Handle detected anomaly"""
        self.detected_anomalies.append(anomaly)
        self.add_anomaly_to_table(anomaly)

    def add_anomaly_to_table(self, anomaly):
        """Add an anomaly to the results table"""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        # Time
        time_item = QTableWidgetItem(f"{anomaly['timestamp']:.6f}")
        self.results_table.setItem(row, 0, time_item)

        # ID
        id_str = f"0x{anomaly['id']:03X}" if anomaly['id'] is not None else "Global"
        id_item = QTableWidgetItem(id_str)
        self.results_table.setItem(row, 1, id_item)

        # Type
        type_item = QTableWidgetItem(anomaly['type'].title())
        self.results_table.setItem(row, 2, type_item)

        # Description
        desc_item = QTableWidgetItem(anomaly['description'])
        self.results_table.setItem(row, 3, desc_item)

        # Severity
        severity_item = QTableWidgetItem(f"{anomaly['severity']:.2f}")
        # Color code severity
        if anomaly['severity'] > 0.7:
            severity_item.setBackground(QBrush(QColor(255, 100, 100)))
        elif anomaly['severity'] > 0.4:
            severity_item.setBackground(QBrush(QColor(255, 200, 100)))
        self.results_table.setItem(row, 4, severity_item)

    def on_anomaly_selected(self):
        """Handle anomaly selection in table"""
        # Could show detailed information about the selected anomaly
        pass

    def refresh_chart(self):
        """Refresh the anomaly visualization chart"""
        current_id = self.id_filter_combo.currentData()
        self.chart_view.set_data(self.frames, self.detected_anomalies, id_filter=current_id)

    def on_detection_finished(self, anomalies):
        """Handle detection completion"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText(f"Completed - Found {len(anomalies)} anomalies")

        # Update statistics
        self.update_statistics(anomalies)

        # Refresh chart
        self.refresh_chart()

    def update_statistics(self, anomalies):
        """Update the statistics display"""
        self.stats_tree.clear()

        if not anomalies:
            return

        # Basic statistics
        total_item = QTreeWidgetItem(["Total Anomalies", str(len(anomalies))])
        self.stats_tree.addTopLevelItem(total_item)

        # By type
        type_counts = defaultdict(int)
        for anomaly in anomalies:
            type_counts[anomaly['type']] += 1

        types_item = QTreeWidgetItem(["By Type"])
        self.stats_tree.addTopLevelItem(types_item)

        for anomaly_type, count in type_counts.items():
            type_item = QTreeWidgetItem([anomaly_type.title(), str(count)])
            types_item.addChild(type_item)

        # Severity statistics
        severities = [a['severity'] for a in anomalies]
        avg_severity = np.mean(severities)
        max_severity = np.max(severities)

        severity_item = QTreeWidgetItem(["Average Severity", f"{avg_severity:.3f}"])
        self.stats_tree.addTopLevelItem(severity_item)

        max_severity_item = QTreeWidgetItem(["Max Severity", f"{max_severity:.3f}"])
        self.stats_tree.addTopLevelItem(max_severity_item)

        # Time range
        if anomalies:
            time_span = anomalies[-1]['timestamp'] - anomalies[0]['timestamp']
            time_item = QTreeWidgetItem(["Time Span", f"{time_span:.3f}s"])
            self.stats_tree.addTopLevelItem(time_item)

        self.stats_tree.expandAll()

    def on_detection_error(self, error_msg):
        """Handle detection error"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Error")
        self.log_message(f"Detection error: {error_msg}")
        QMessageBox.critical(self, "Detection Error", error_msg)

    def log_message(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        """Handle window close event"""
        if self.detection_worker and self.detection_worker.isRunning():
            self.detection_worker.stop()
            self.detection_worker.wait()
        event.accept()