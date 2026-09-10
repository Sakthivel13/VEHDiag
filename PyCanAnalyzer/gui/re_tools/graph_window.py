"""Graph Window - Plot CAN Signal Values Over Time."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QGroupBox,
                             QCheckBox, QSpinBox, QMessageBox, QSplitter)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
import time


class GraphWindow(QMainWindow):
    """Window for plotting CAN signal values over time."""

    def __init__(self, frames=None, dbc_manager=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.dbc_manager = dbc_manager
        self.plots = []  # List of active plots
        self.signals = {}  # Available signals
        self.data_buffer = {}  # Signal data buffers

        # Check if pyqtgraph is available
        try:
            import pyqtgraph as pg
            self.pg = pg
            self.has_pyqtgraph = True
        except ImportError:
            self.has_pyqtgraph = False
            QMessageBox.warning(self, "Missing Dependency",
                               "pyqtgraph is required for graphing. Install with: pip install pyqtgraph")

        self.init_ui()
        self.load_available_signals()

    def init_ui(self):
        """Initialize the graph window UI."""
        self.setWindowTitle("CAN Signal Graph")
        self.setGeometry(200, 200, 1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        central_widget.setLayout(QVBoxLayout())
        central_widget.layout().addWidget(splitter)

        # Left panel - Controls
        self.create_control_panel(splitter)

        # Right panel - Graph area
        self.create_graph_panel(splitter)

        splitter.setSizes([300, 900])

        # Status bar
        self.status_label = QLabel("Ready")
        central_widget.layout().addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Signal selection
        signal_group = QGroupBox("Signal Selection")
        signal_layout = QVBoxLayout()

        self.signal_combo = QComboBox()
        self.signal_combo.addItem("Select Signal...")
        self.signal_combo.currentTextChanged.connect(self.on_signal_selected)

        add_signal_button = QPushButton("Add to Graph")
        add_signal_button.clicked.connect(self.add_signal_to_graph)

        signal_layout.addWidget(QLabel("Available Signals:"))
        signal_layout.addWidget(self.signal_combo)
        signal_layout.addWidget(add_signal_button)
        signal_group.setLayout(signal_layout)
        layout.addWidget(signal_group)

        # Active signals
        active_group = QGroupBox("Active Signals")
        active_layout = QVBoxLayout()

        self.active_signals_table = QTableWidget()
        self.active_signals_table.setColumnCount(3)
        self.active_signals_table.setHorizontalHeaderLabels(["Signal", "Color", "Remove"])
        self.active_signals_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        active_layout.addWidget(self.active_signals_table)
        active_group.setLayout(active_layout)
        layout.addWidget(active_group)

        # Graph settings
        settings_group = QGroupBox("Graph Settings")
        settings_layout = QVBoxLayout()

        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)

        self.show_grid_check = QCheckBox("Show Grid")
        self.show_grid_check.setChecked(True)

        self.update_rate_spin = QSpinBox()
        self.update_rate_spin.setRange(1, 100)
        self.update_rate_spin.setValue(10)
        self.update_rate_spin.setSuffix(" Hz")

        settings_layout.addWidget(self.auto_scroll_check)
        settings_layout.addWidget(self.show_grid_check)
        settings_layout.addWidget(QLabel("Update Rate:"))
        settings_layout.addWidget(self.update_rate_spin)
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Controls
        control_group = QGroupBox("Controls")
        control_layout = QVBoxLayout()

        self.start_button = QPushButton("Start Plotting")
        self.start_button.clicked.connect(self.start_plotting)

        self.stop_button = QPushButton("Stop Plotting")
        self.stop_button.clicked.connect(self.stop_plotting)
        self.stop_button.setEnabled(False)

        self.clear_button = QPushButton("Clear Data")
        self.clear_button.clicked.connect(self.clear_data)

        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.clear_button)
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        layout.addStretch()
        parent.addWidget(panel)

    def create_graph_panel(self, parent):
        """Create the graph visualization panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        if self.has_pyqtgraph:
            # Create pyqtgraph plot widget
            self.plot_widget = self.pg.PlotWidget()
            self.plot_widget.setBackground('w')
            self.plot_widget.showGrid(x=True, y=True)

            # Configure plot
            self.plot_widget.setLabel('left', 'Value')
            self.plot_widget.setLabel('bottom', 'Time (s)')

            layout.addWidget(self.plot_widget)

            # Legend
            self.legend = self.pg.LegendItem(offset=(70, 30))
            self.legend.setParentItem(self.plot_widget.graphicsItem())

        else:
            # Fallback without pyqtgraph
            self.plot_widget = QLabel("pyqtgraph not available.\nInstall with: pip install pyqtgraph")
            self.plot_widget.setAlignment(Qt.AlignCenter)
            self.plot_widget.setStyleSheet("border: 1px solid black; font-size: 14px;")
            layout.addWidget(self.plot_widget)

        parent.addWidget(panel)

    def load_available_signals(self):
        """Load available signals from DBC manager."""
        self.signal_combo.clear()
        self.signal_combo.addItem("Select Signal...")

        if self.dbc_manager:
            try:
                signals = self.dbc_manager.get_signal_definitions()
                for signal_info in signals:
                    display_name = f"{signal_info.get('message_name', 'Unknown')}.{signal_info['name']}"
                    self.signal_combo.addItem(display_name, signal_info)

                self.signals = {f"{s.get('message_name', 'Unknown')}.{s['name']}": s for s in signals}

            except Exception as e:
                QMessageBox.warning(self, "Signal Load Error",
                                   f"Error loading signals: {str(e)}")

    def on_signal_selected(self, signal_name):
        """Handle signal selection."""
        if signal_name and signal_name != "Select Signal...":
            # Could show signal details here
            pass

    def add_signal_to_graph(self):
        """Add the selected signal to the graph."""
        current_text = self.signal_combo.currentText()
        if current_text == "Select Signal...":
            QMessageBox.warning(self, "No Signal Selected",
                               "Please select a signal to add to the graph.")
            return

        signal_info = self.signal_combo.currentData()
        if not signal_info:
            return

        # Check if already added
        signal_name = f"{signal_info.get('message_name', 'Unknown')}.{signal_info['name']}"
        if any(p['name'] == signal_name for p in self.plots):
            QMessageBox.warning(self, "Duplicate Signal",
                               f"Signal '{signal_name}' is already being plotted.")
            return

        # Add to plots
        plot_info = {
            'name': signal_name,
            'info': signal_info,
            'color': self.get_next_color(),
            'data': {'x': [], 'y': []}
        }

        self.plots.append(plot_info)
        self.update_active_signals_table()

        if self.has_pyqtgraph:
            # Create plot curve
            pen = self.pg.mkPen(color=plot_info['color'], width=2)
            curve = self.plot_widget.plot([], [], pen=pen, name=signal_name)
            plot_info['curve'] = curve

            # Add to legend
            self.legend.addItem(curve, signal_name)

        self.status_label.setText(f"Added signal: {signal_name}")

    def get_next_color(self):
        """Get the next color for plotting."""
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (128, 0, 128),  # Purple
            (255, 165, 0),  # Orange
        ]
        return colors[len(self.plots) % len(colors)]

    def update_active_signals_table(self):
        """Update the active signals table."""
        self.active_signals_table.setRowCount(len(self.plots))

        for row, plot in enumerate(self.plots):
            # Signal name
            name_item = QTableWidgetItem(plot['name'])
            self.active_signals_table.setItem(row, 0, name_item)

            # Color indicator
            color_item = QTableWidgetItem()
            color_item.setBackground(Qt.SolidPattern)
            color_item.setData(Qt.BackgroundColorRole, QColor(*plot['color']))
            self.active_signals_table.setItem(row, 1, color_item)

            # Remove button
            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(lambda checked, p=plot: self.remove_signal(p))
            self.active_signals_table.setCellWidget(row, 2, remove_button)

    def remove_signal(self, plot_info):
        """Remove a signal from the graph."""
        if plot_info in self.plots:
            self.plots.remove(plot_info)

            if self.has_pyqtgraph and 'curve' in plot_info:
                # Remove from plot
                self.plot_widget.removeItem(plot_info['curve'])
                # Remove from legend
                self.legend.removeItem(plot_info['name'])

            self.update_active_signals_table()
            self.status_label.setText(f"Removed signal: {plot_info['name']}")

    def start_plotting(self):
        """Start real-time plotting."""
        if not self.plots:
            QMessageBox.warning(self, "No Signals",
                               "Add some signals to the graph before starting.")
            return

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Plotting active...")

        # Start update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_plot)
        update_interval = 1000 // self.update_rate_spin.value()  # Convert Hz to ms
        self.update_timer.start(update_interval)

    def stop_plotting(self):
        """Stop real-time plotting."""
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Plotting stopped")

    def update_plot(self):
        """Update the plot with new data."""
        if not self.frames:
            return

        current_time = time.time()

        # Process recent frames
        for frame in self.frames[-100:]:  # Check last 100 frames
            frame_time = getattr(frame, 'timestamp', current_time)

            # Decode signals for each active plot
            for plot in self.plots:
                signal_info = plot['info']
                message_id = signal_info.get('message_id')

                # Check if frame matches the signal's message
                if frame.id == message_id:
                    try:
                        # Decode signal value
                        decoded_value = self.decode_signal_value(frame, signal_info)

                        if decoded_value is not None:
                            # Add to plot data
                            plot['data']['x'].append(frame_time)
                            plot['data']['y'].append(decoded_value)

                            # Limit data points
                            max_points = 1000
                            if len(plot['data']['x']) > max_points:
                                plot['data']['x'] = plot['data']['x'][-max_points:]
                                plot['data']['y'] = plot['data']['y'][-max_points:]

                    except Exception as e:
                        # Skip decoding errors
                        continue

        # Update visual plots
        if self.has_pyqtgraph:
            for plot in self.plots:
                if 'curve' in plot and plot['data']['x']:
                    plot['curve'].setData(plot['data']['x'], plot['data']['y'])

    def decode_signal_value(self, frame, signal_info):
        """Decode a signal value from a CAN frame."""
        if not self.dbc_manager:
            return None

        try:
            # Use DBC manager to decode
            decoded_signals = self.dbc_manager.decode_frame(frame)

            signal_name = signal_info['name']
            if signal_name in decoded_signals:
                return decoded_signals[signal_name]

        except Exception:
            # Fallback: manual decoding
            try:
                start_bit = signal_info.get('start_bit', 0)
                length = signal_info.get('length', 8)
                scale = signal_info.get('scale', 1.0)
                offset = signal_info.get('offset', 0.0)

                # Extract bits from frame data
                if hasattr(frame, 'data') and frame.data:
                    # Simple bit extraction (big-endian)
                    byte_index = start_bit // 8
                    bit_index = start_bit % 8

                    if byte_index < len(frame.data):
                        # Extract value (simplified)
                        value = frame.data[byte_index]

                        # Apply scale and offset
                        return value * scale + offset

            except Exception:
                pass

        return None

    def clear_data(self):
        """Clear all plot data."""
        for plot in self.plots:
            plot['data'] = {'x': [], 'y': []}

            if self.has_pyqtgraph and 'curve' in plot:
                plot['curve'].setData([], [])

        if self.has_pyqtgraph:
            self.plot_widget.setXRange(0, 1)
            self.plot_widget.setYRange(0, 1)

        self.status_label.setText("Data cleared")

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []

    def set_dbc_manager(self, dbc_manager):
        """Set the DBC manager for signal decoding."""
        self.dbc_manager = dbc_manager
        self.load_available_signals()

    def closeEvent(self, event):
        """Handle window close event."""
        self.stop_plotting()
        event.accept()