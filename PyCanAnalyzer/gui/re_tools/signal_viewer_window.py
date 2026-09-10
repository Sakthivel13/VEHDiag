"""Signal Viewer Window - View and Analyze Individual CAN Signals."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QSplitter, QMessageBox,
                             QTextEdit, QSpinBox, QComboBox, QLineEdit,
                             QCheckBox, QDoubleSpinBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
import time
import collections
try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False


class SignalViewerWindow(QMainWindow):
    """Window for viewing and analyzing individual CAN signals over time."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.selected_signals = []
        self.signal_data = {}

        self.is_updating = False

        self.init_ui()

    def init_ui(self):
        """Initialize the signal viewer UI."""
        self.setWindowTitle("CAN Signal Viewer")
        self.setGeometry(200, 200, 1400, 900)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)

        # Control panel
        self.create_control_panel(layout)

        # Main content splitter
        content_splitter = QSplitter(Qt.Vertical)
        layout.addWidget(content_splitter)

        # Top - Plot area
        self.create_plot_area(content_splitter)

        # Bottom - Signal details splitter
        details_splitter = QSplitter(Qt.Horizontal)
        content_splitter.addWidget(details_splitter)

        # Left - Signal list
        self.create_signal_list(details_splitter)

        # Right - Signal details
        self.create_signal_details(details_splitter)

        content_splitter.setSizes([600, 300])

        # Status bar
        self.status_label = QLabel("Ready - Add signals to view")
        layout.addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QHBoxLayout(panel)

        # Signal definition
        signal_group = QGroupBox("Signal Definition")
        signal_layout = QVBoxLayout()

        # CAN ID input
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("CAN ID (hex):"))
        self.can_id_edit = QLineEdit()
        self.can_id_edit.setPlaceholderText("e.g., 123")
        id_layout.addWidget(self.can_id_edit)

        # Signal parameters
        params_layout = QHBoxLayout()
        params_layout.addWidget(QLabel("Start Bit:"))
        self.start_bit_spin = QSpinBox()
        self.start_bit_spin.setRange(0, 63)
        params_layout.addWidget(self.start_bit_spin)

        params_layout.addWidget(QLabel("Length:"))
        self.length_spin = QSpinBox()
        self.length_spin.setRange(1, 64)
        self.length_spin.setValue(8)
        params_layout.addWidget(self.length_spin)

        params_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Unsigned", "Signed", "IEEE Float", "IEEE Double"
        ])
        params_layout.addWidget(self.format_combo)

        # Scale and offset
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scale:"))
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.001, 1000.0)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setSingleStep(0.1)
        scale_layout.addWidget(self.scale_spin)

        scale_layout.addWidget(QLabel("Offset:"))
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-10000.0, 10000.0)
        self.offset_spin.setValue(0.0)
        scale_layout.addWidget(self.offset_spin)

        signal_layout.addLayout(id_layout)
        signal_layout.addLayout(params_layout)
        signal_layout.addLayout(scale_layout)

        signal_group.setLayout(signal_layout)
        control_layout.addWidget(signal_group)

        # Actions
        action_group = QGroupBox("Actions")
        action_layout = QVBoxLayout()

        self.add_signal_button = QPushButton("Add Signal")
        self.add_signal_button.clicked.connect(self.add_signal)

        self.remove_signal_button = QPushButton("Remove Selected")
        self.remove_signal_button.clicked.connect(self.remove_selected_signal)

        self.clear_signals_button = QPushButton("Clear All")
        self.clear_signals_button.clicked.connect(self.clear_all_signals)

        self.update_plot_button = QPushButton("Update Plot")
        self.update_plot_button.clicked.connect(self.update_plot)

        action_layout.addWidget(self.add_signal_button)
        action_layout.addWidget(self.remove_signal_button)
        action_layout.addWidget(self.clear_signals_button)
        action_layout.addWidget(self.update_plot_button)

        action_group.setLayout(action_layout)
        control_layout.addWidget(action_group)

        # Plot settings
        plot_group = QGroupBox("Plot Settings")
        plot_layout = QVBoxLayout()

        # Time range
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Time Range:"))
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems([
            "All", "Last 1s", "Last 5s", "Last 10s", "Last 30s", "Last 1min"
        ])
        time_layout.addWidget(self.time_range_combo)

        # Auto update
        self.auto_update_check = QCheckBox("Auto Update")
        self.auto_update_check.setChecked(True)

        plot_layout.addLayout(time_layout)
        plot_layout.addWidget(self.auto_update_check)

        plot_group.setLayout(plot_layout)
        control_layout.addWidget(plot_group)

        parent.addWidget(panel)

    def create_plot_area(self, parent):
        """Create the plotting area."""
        if HAS_PYQTGRAPH:
            # Use pyqtgraph for plotting
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setBackground('w')
            self.plot_widget.showGrid(x=True, y=True)
            self.plot_widget.setLabel('left', 'Signal Value')
            self.plot_widget.setLabel('bottom', 'Time (s)')

            # Create plot items for different signals
            self.plot_curves = {}
            self.plot_data = {}

            parent.addWidget(self.plot_widget)
        else:
            # Fallback to text display
            self.plot_text = QTextEdit()
            self.plot_text.setReadOnly(True)
            self.plot_text.setFont(QFont("Courier New", 10))
            parent.addWidget(self.plot_text)

    def create_signal_list(self, parent):
        """Create the signal list panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Signal list
        list_group = QGroupBox("Active Signals")
        list_layout = QVBoxLayout()

        self.signal_table = QTableWidget()
        self.signal_table.setColumnCount(4)
        self.signal_table.setHorizontalHeaderLabels([
            "CAN ID", "Start Bit", "Length", "Name"
        ])
        self.signal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.signal_table.itemSelectionChanged.connect(self.on_signal_selected)

        list_layout.addWidget(self.signal_table)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        parent.addWidget(panel)

    def create_signal_details(self, parent):
        """Create the signal details panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Signal statistics
        stats_group = QGroupBox("Signal Statistics")
        stats_layout = QVBoxLayout()

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(150)

        stats_layout.addWidget(self.stats_text)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Signal values
        values_group = QGroupBox("Signal Values")
        values_layout = QVBoxLayout()

        self.values_table = QTableWidget()
        self.values_table.setColumnCount(3)
        self.values_table.setHorizontalHeaderLabels([
            "Frame", "Time", "Value"
        ])
        self.values_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        values_layout.addWidget(self.values_table)
        values_group.setLayout(values_layout)
        layout.addWidget(values_group)

        parent.addWidget(panel)

    def add_signal(self):
        """Add a new signal to monitor."""
        try:
            can_id = int(self.can_id_edit.text(), 16)
        except ValueError:
            QMessageBox.warning(self, "Invalid CAN ID",
                               "Please enter a valid hexadecimal CAN ID.")
            return

        start_bit = self.start_bit_spin.value()
        length = self.length_spin.value()
        format_type = self.format_combo.currentText()
        scale = self.scale_spin.value()
        offset = self.offset_spin.value()

        # Create signal definition
        signal_def = {
            'can_id': can_id,
            'start_bit': start_bit,
            'length': length,
            'format': format_type,
            'scale': scale,
            'offset': offset,
            'name': f"0x{can_id:03X}_{start_bit}_{length}b"
        }

        # Check if signal already exists
        for existing in self.selected_signals:
            if (existing['can_id'] == can_id and
                existing['start_bit'] == start_bit and
                existing['length'] == length):
                QMessageBox.warning(self, "Duplicate Signal",
                                   "This signal is already being monitored.")
                return

        self.selected_signals.append(signal_def)
        self.update_signal_list()

        if self.auto_update_check.isChecked():
            self.update_plot()

        self.status_label.setText(f"Added signal: {signal_def['name']}")

    def remove_selected_signal(self):
        """Remove the selected signal."""
        current_row = self.signal_table.currentRow()
        if current_row >= 0 and current_row < len(self.selected_signals):
            removed_signal = self.selected_signals.pop(current_row)
            self.update_signal_list()

            # Remove from plot
            if HAS_PYQTGRAPH and removed_signal['name'] in self.plot_curves:
                self.plot_widget.removeItem(self.plot_curves[removed_signal['name']])
                del self.plot_curves[removed_signal['name']]
                del self.plot_data[removed_signal['name']]

            if self.auto_update_check.isChecked():
                self.update_plot()

            self.status_label.setText(f"Removed signal: {removed_signal['name']}")

    def clear_all_signals(self):
        """Clear all signals."""
        self.selected_signals = []
        self.signal_data = {}
        self.update_signal_list()

        if HAS_PYQTGRAPH:
            self.plot_widget.clear()
            self.plot_curves = {}
            self.plot_data = {}

        self.stats_text.clear()
        self.values_table.setRowCount(0)

        self.status_label.setText("All signals cleared")

    def update_signal_list(self):
        """Update the signal list table."""
        self.signal_table.setRowCount(len(self.selected_signals))

        for row, signal in enumerate(self.selected_signals):
            # CAN ID
            id_item = QTableWidgetItem(f"0x{signal['can_id']:03X}")
            self.signal_table.setItem(row, 0, id_item)

            # Start bit
            start_item = QTableWidgetItem(str(signal['start_bit']))
            self.signal_table.setItem(row, 1, start_item)

            # Length
            length_item = QTableWidgetItem(str(signal['length']))
            self.signal_table.setItem(row, 2, length_item)

            # Name
            name_item = QTableWidgetItem(signal['name'])
            self.signal_table.setItem(row, 3, name_item)

    def update_plot(self):
        """Update the plot with current signal data."""
        if not self.selected_signals or not self.frames:
            return

        self.is_updating = True
        self.status_label.setText("Updating plot...")

        # Extract signal data
        self.signal_data = self.extract_signal_data()

        # Update plot
        if HAS_PYQTGRAPH:
            self.update_pyqtgraph_plot()
        else:
            self.update_text_plot()

        self.is_updating = False
        self.status_label.setText("Plot updated")

    def extract_signal_data(self):
        """Extract signal data from frames."""
        signal_data = {}

        # Initialize data structures
        for signal in self.selected_signals:
            signal_data[signal['name']] = {
                'times': [],
                'values': [],
                'raw_values': []
            }

        # Get time range
        time_range = self.get_time_range_seconds()

        # Process frames
        start_time = None
        for frame_idx, frame in enumerate(self.frames):
            if not hasattr(frame, 'timestamp'):
                continue

            timestamp = frame.timestamp
            if start_time is None:
                start_time = timestamp

            relative_time = timestamp - start_time

            # Check time range filter
            if time_range > 0 and relative_time < (start_time + timestamp - time_range):
                continue

            # Extract signals from this frame
            for signal in self.selected_signals:
                if frame.id == signal['can_id'] and hasattr(frame, 'data'):
                    value = self.extract_signal_value(frame.data, signal)
                    if value is not None:
                        signal_data[signal['name']]['times'].append(relative_time)
                        signal_data[signal['name']]['values'].append(value)
                        signal_data[signal['name']]['raw_values'].append(value)

        return signal_data

    def extract_signal_value(self, data, signal_def):
        """Extract a signal value from frame data."""
        if not data or len(data) * 8 < signal_def['start_bit'] + signal_def['length']:
            return None

        # Extract bits
        start_bit = signal_def['start_bit']
        length = signal_def['length']

        # Convert data to bit array
        bits = []
        for byte in data:
            for bit in range(8):
                bits.append((byte >> bit) & 1)

        # Extract signal bits (big-endian)
        signal_bits = bits[start_bit:start_bit + length]

        if len(signal_bits) != length:
            return None

        # Convert to value
        raw_value = 0
        for bit in signal_bits:
            raw_value = (raw_value << 1) | bit

        # Apply format
        if signal_def['format'] == "Signed":
            if raw_value & (1 << (length - 1)):
                raw_value -= (1 << length)
        elif signal_def['format'] == "IEEE Float" and length == 32:
            # Convert to float (simplified)
            raw_value = self.bits_to_float(signal_bits)
        elif signal_def['format'] == "IEEE Double" and length == 64:
            # Convert to double (simplified)
            raw_value = self.bits_to_double(signal_bits)

        # Apply scale and offset
        final_value = raw_value * signal_def['scale'] + signal_def['offset']

        return final_value

    def bits_to_float(self, bits):
        """Convert bits to IEEE 754 float (simplified)."""
        if len(bits) != 32:
            return 0.0
        # This is a simplified conversion - real implementation would use struct
        return 0.0

    def bits_to_double(self, bits):
        """Convert bits to IEEE 754 double (simplified)."""
        if len(bits) != 64:
            return 0.0
        # This is a simplified conversion - real implementation would use struct
        return 0.0

    def get_time_range_seconds(self):
        """Get the time range in seconds."""
        range_text = self.time_range_combo.currentText()
        if range_text == "All":
            return 0
        elif range_text == "Last 1s":
            return 1
        elif range_text == "Last 5s":
            return 5
        elif range_text == "Last 10s":
            return 10
        elif range_text == "Last 30s":
            return 30
        elif range_text == "Last 1min":
            return 60
        return 0

    def update_pyqtgraph_plot(self):
        """Update the pyqtgraph plot."""
        self.plot_widget.clear()
        self.plot_curves = {}

        colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k', 'w']

        for i, signal_name in enumerate(self.signal_data.keys()):
            if not self.signal_data[signal_name]['times']:
                continue

            color = colors[i % len(colors)]

            # Create plot curve
            curve = self.plot_widget.plot(
                self.signal_data[signal_name]['times'],
                self.signal_data[signal_name]['values'],
                pen=pg.mkPen(color=color, width=2),
                name=signal_name
            )

            self.plot_curves[signal_name] = curve

        # Add legend
        if self.plot_curves:
            legend = self.plot_widget.addLegend()
            for name, curve in self.plot_curves.items():
                legend.addItem(curve, name)

    def update_text_plot(self):
        """Update the text-based plot."""
        plot_text = "Signal Plot (Text Mode - Install pyqtgraph for graphical plots)\n\n"

        for signal_name, data in self.signal_data.items():
            plot_text += f"Signal: {signal_name}\n"
            plot_text += f"Data points: {len(data['values'])}\n"

            if data['values']:
                min_val = min(data['values'])
                max_val = max(data['values'])
                avg_val = sum(data['values']) / len(data['values'])

                plot_text += f"Min: {min_val:.3f}, Max: {max_val:.3f}, Avg: {avg_val:.3f}\n"

                # Simple ASCII plot
                plot_text += "Values over time:\n"
                for i, (t, v) in enumerate(zip(data['times'][:20], data['values'][:20])):
                    plot_text += f"  {t:.3f}s: {v:.3f}\n"
                if len(data['values']) > 20:
                    plot_text += f"  ... and {len(data['values']) - 20} more points\n"

            plot_text += "\n"

        self.plot_text.setText(plot_text)

    def on_signal_selected(self):
        """Handle signal selection."""
        current_row = self.signal_table.currentRow()
        if current_row >= 0 and current_row < len(self.selected_signals):
            signal = self.selected_signals[current_row]
            self.show_signal_details(signal)

    def show_signal_details(self, signal):
        """Show details for the selected signal."""
        signal_name = signal['name']

        if signal_name not in self.signal_data:
            self.stats_text.setText("No data available for this signal.")
            self.values_table.setRowCount(0)
            return

        data = self.signal_data[signal_name]

        # Update statistics
        if data['values']:
            min_val = min(data['values'])
            max_val = max(data['values'])
            avg_val = sum(data['values']) / len(data['values'])

            stats = f"Signal: {signal_name}\n"
            stats += f"CAN ID: 0x{signal['can_id']:03X}\n"
            stats += f"Bits: {signal['start_bit']}-{signal['start_bit'] + signal['length'] - 1}\n"
            stats += f"Format: {signal['format']}\n"
            stats += f"Scale: {signal['scale']}, Offset: {signal['offset']}\n\n"
            stats += f"Statistics:\n"
            stats += f"Data points: {len(data['values'])}\n"
            stats += f"Minimum: {min_val:.6f}\n"
            stats += f"Maximum: {max_val:.6f}\n"
            stats += f"Average: {avg_val:.6f}\n"
            stats += f"Range: {max_val - min_val:.6f}\n"

            self.stats_text.setText(stats)

            # Update values table
            max_rows = min(100, len(data['values']))  # Limit to 100 rows
            self.values_table.setRowCount(max_rows)

            for row in range(max_rows):
                # Frame number (approximate)
                frame_item = QTableWidgetItem(str(row))
                self.values_table.setItem(row, 0, frame_item)

                # Time
                time_item = QTableWidgetItem(f"{data['times'][row]:.6f}")
                self.values_table.setItem(row, 1, time_item)

                # Value
                value_item = QTableWidgetItem(f"{data['values'][row]:.6f}")
                self.values_table.setItem(row, 2, value_item)
        else:
            self.stats_text.setText("No data available for this signal.")
            self.values_table.setRowCount(0)

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []

        if self.auto_update_check.isChecked() and not self.is_updating:
            self.update_plot()

    def closeEvent(self, event):
        """Handle window close event."""
        # Clean up any running threads
        self.is_updating = False
        super().closeEvent(event)