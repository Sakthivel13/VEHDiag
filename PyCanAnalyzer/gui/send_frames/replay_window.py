"""Replay Window - Replay CAN Messages with Precise Timing."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QSplitter, QMessageBox,
                             QTextEdit, QSpinBox, QComboBox, QLineEdit,
                             QCheckBox, QProgressBar, QSlider, QRadioButton,
                             QButtonGroup, QFileDialog, QMenuBar, QAction)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QElapsedTimer
from PyQt5.QtGui import QFont, QColor, QIcon
import time
import json
import os


class ReplayWindow(QMainWindow):
    """Window for replaying CAN messages with precise timing control."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.replay_data = []
        self.is_replaying = False
        self.replay_thread = None

        self.init_ui()
        self.init_menu()

    def init_ui(self):
        """Initialize the replay UI."""
        self.setWindowTitle("Message Replay")
        self.setGeometry(200, 200, 1400, 900)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)

        # Control panel
        self.create_control_panel(layout)

        # Main splitter
        main_splitter = QSplitter(Qt.Vertical)
        layout.addWidget(main_splitter)

        # Top - Message selection and replay controls
        self.create_message_panel(main_splitter)

        # Bottom - Replay progress and statistics
        self.create_progress_panel(main_splitter)

        main_splitter.setSizes([600, 300])

        # Status bar
        self.status_label = QLabel("Ready - Load or select messages to replay")
        layout.addWidget(self.status_label)

    def init_menu(self):
        """Initialize the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        load_action = QAction('Load Replay File', self)
        load_action.triggered.connect(self.load_replay_file)
        file_menu.addAction(load_action)

        save_action = QAction('Save Replay File', self)
        save_action.triggered.connect(self.save_replay_file)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        export_action = QAction('Export Selected Messages', self)
        export_action.triggered.connect(self.export_selected_messages)
        file_menu.addAction(export_action)

        # Edit menu
        edit_menu = menubar.addMenu('Edit')

        clear_action = QAction('Clear All Messages', self)
        clear_action.triggered.connect(self.clear_messages)
        edit_menu.addAction(clear_action)

        select_all_action = QAction('Select All', self)
        select_all_action.triggered.connect(self.select_all_messages)
        edit_menu.addAction(select_all_action)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QVBoxLayout(panel)

        # Source selection
        source_group = QGroupBox("Message Source")
        source_layout = QHBoxLayout()

        self.source_group = QButtonGroup()

        self.from_table_radio = QRadioButton("From Current Table")
        self.from_file_radio = QRadioButton("From File")
        self.from_selection_radio = QRadioButton("From Selection")

        self.from_table_radio.setChecked(True)

        self.source_group.addButton(self.from_table_radio)
        self.source_group.addButton(self.from_file_radio)
        self.source_group.addButton(self.from_selection_radio)

        source_layout.addWidget(self.from_table_radio)
        source_layout.addWidget(self.from_file_radio)
        source_layout.addWidget(self.from_selection_radio)
        source_layout.addStretch()

        source_group.setLayout(source_layout)
        control_layout.addWidget(source_group)

        # Replay configuration
        config_group = QGroupBox("Replay Configuration")
        config_layout = QVBoxLayout()

        # Timing mode
        timing_layout = QHBoxLayout()
        timing_layout.addWidget(QLabel("Timing Mode:"))

        self.timing_combo = QComboBox()
        self.timing_combo.addItems([
            "Original Timing",
            "Fixed Interval",
            "Speed Multiplier",
            "Manual Control"
        ])
        self.timing_combo.currentTextChanged.connect(self.on_timing_mode_changed)
        timing_layout.addWidget(self.timing_combo)

        # Timing parameters
        self.timing_param_layout = QHBoxLayout()

        self.interval_label = QLabel("Interval:")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 10000)
        self.interval_spin.setValue(100)
        self.interval_spin.setSuffix(" ms")

        self.speed_label = QLabel("Speed:")
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 1000)
        self.speed_spin.setValue(100)
        self.speed_spin.setSuffix(" %")

        self.timing_param_layout.addWidget(self.interval_label)
        self.timing_param_layout.addWidget(self.interval_spin)
        self.timing_param_layout.addWidget(self.speed_label)
        self.timing_param_layout.addWidget(self.speed_spin)
        self.timing_param_layout.addStretch()

        # Loop options
        loop_layout = QHBoxLayout()
        self.loop_check = QCheckBox("Loop Replay")
        self.loop_count_label = QLabel("Count:")
        self.loop_count_spin = QSpinBox()
        self.loop_count_spin.setRange(1, 1000)
        self.loop_count_spin.setValue(1)
        self.loop_count_spin.setEnabled(False)

        self.loop_check.stateChanged.connect(self.on_loop_changed)

        loop_layout.addWidget(self.loop_check)
        loop_layout.addWidget(self.loop_count_label)
        loop_layout.addWidget(self.loop_count_spin)
        loop_layout.addStretch()

        config_layout.addLayout(timing_layout)
        config_layout.addLayout(self.timing_param_layout)
        config_layout.addLayout(loop_layout)

        config_group.setLayout(config_layout)
        control_layout.addWidget(config_group)

        parent.addWidget(panel)

    def create_message_panel(self, parent):
        """Create the message selection and replay panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Message table
        table_group = QGroupBox("Messages to Replay")
        table_layout = QVBoxLayout()

        self.message_table = QTableWidget()
        self.message_table.setColumnCount(6)
        self.message_table.setHorizontalHeaderLabels([
            "ID", "Data", "Length", "Timestamp", "Interval", "Count"
        ])
        self.message_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.message_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.message_table.itemSelectionChanged.connect(self.on_selection_changed)

        table_layout.addWidget(self.message_table)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Replay controls
        controls_group = QGroupBox("Replay Controls")
        controls_layout = QHBoxLayout()

        self.add_selected_button = QPushButton("Add Selected")
        self.add_selected_button.clicked.connect(self.add_selected_messages)

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_messages)

        self.clear_replay_button = QPushButton("Clear Replay List")
        self.clear_replay_button.clicked.connect(self.clear_replay_list)

        controls_layout.addWidget(self.add_selected_button)
        controls_layout.addWidget(self.remove_button)
        controls_layout.addWidget(self.clear_replay_button)
        controls_layout.addStretch()

        # Replay buttons
        self.start_replay_button = QPushButton("Start Replay")
        self.start_replay_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.start_replay_button.clicked.connect(self.start_replay)

        self.pause_replay_button = QPushButton("Pause")
        self.pause_replay_button.setEnabled(False)
        self.pause_replay_button.clicked.connect(self.pause_replay)

        self.stop_replay_button = QPushButton("Stop")
        self.stop_replay_button.setEnabled(False)
        self.stop_replay_button.clicked.connect(self.stop_replay)

        controls_layout.addWidget(self.start_replay_button)
        controls_layout.addWidget(self.pause_replay_button)
        controls_layout.addWidget(self.stop_replay_button)

        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)

        parent.addWidget(panel)

    def create_progress_panel(self, parent):
        """Create the progress and statistics panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Progress splitter
        progress_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(progress_splitter)

        # Left - Progress and controls
        progress_panel = QWidget()
        progress_layout = QVBoxLayout(progress_panel)

        # Progress bar
        progress_group = QGroupBox("Replay Progress")
        progress_bar_layout = QVBoxLayout()

        self.replay_progress = QProgressBar()
        self.replay_progress.setRange(0, 100)
        self.replay_progress.setValue(0)

        self.progress_label = QLabel("Ready to replay")

        progress_bar_layout.addWidget(self.replay_progress)
        progress_bar_layout.addWidget(self.progress_label)

        progress_group.setLayout(progress_bar_layout)
        progress_layout.addWidget(progress_group)

        # Manual control (for manual timing mode)
        manual_group = QGroupBox("Manual Control")
        manual_layout = QVBoxLayout()

        self.step_button = QPushButton("Step Forward")
        self.step_button.clicked.connect(self.step_replay)
        self.step_button.setEnabled(False)

        self.rewind_button = QPushButton("Rewind")
        self.rewind_button.clicked.connect(self.rewind_replay)
        self.rewind_button.setEnabled(False)

        manual_layout.addWidget(self.step_button)
        manual_layout.addWidget(self.rewind_button)

        manual_group.setLayout(manual_layout)
        progress_layout.addWidget(manual_group)

        progress_splitter.addWidget(progress_panel)

        # Right - Statistics
        stats_panel = QWidget()
        stats_layout = QVBoxLayout(stats_panel)

        stats_group = QGroupBox("Replay Statistics")
        stats_text_layout = QVBoxLayout()

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(200)

        stats_text_layout.addWidget(self.stats_text)
        stats_group.setLayout(stats_text_layout)
        stats_layout.addWidget(stats_group)

        progress_splitter.addWidget(stats_panel)

        progress_splitter.setSizes([400, 400])

        parent.addWidget(panel)

    def on_timing_mode_changed(self, mode):
        """Handle timing mode changes."""
        if mode == "Fixed Interval":
            self.interval_label.show()
            self.interval_spin.show()
            self.speed_label.hide()
            self.speed_spin.hide()
        elif mode == "Speed Multiplier":
            self.interval_label.hide()
            self.interval_spin.hide()
            self.speed_label.show()
            self.speed_spin.show()
        elif mode == "Manual Control":
            self.interval_label.hide()
            self.interval_spin.hide()
            self.speed_label.hide()
            self.speed_spin.hide()
            self.step_button.setEnabled(True)
            self.rewind_button.setEnabled(True)
        else:  # Original Timing
            self.interval_label.hide()
            self.interval_spin.hide()
            self.speed_label.hide()
            self.speed_spin.hide()

    def on_loop_changed(self, state):
        """Handle loop checkbox changes."""
        self.loop_count_spin.setEnabled(state == Qt.Checked)

    def on_selection_changed(self):
        """Handle message selection changes."""
        selected_count = len(self.message_table.selectionModel().selectedRows())
        self.add_selected_button.setText(f"Add Selected ({selected_count})")

    def add_selected_messages(self):
        """Add selected messages to replay list."""
        # This would add messages from the main table to the replay list
        # For now, just show a message
        QMessageBox.information(self, "Add Messages",
                               "This would add selected messages from the main CAN table to the replay list.")

    def remove_messages(self):
        """Remove selected messages from replay list."""
        current_row = self.message_table.currentRow()
        if current_row >= 0:
            self.message_table.removeRow(current_row)

    def clear_replay_list(self):
        """Clear the replay message list."""
        self.message_table.setRowCount(0)
        self.replay_data = []

    def clear_messages(self):
        """Clear all messages."""
        self.clear_replay_list()

    def select_all_messages(self):
        """Select all messages in the table."""
        self.message_table.selectAll()

    def load_replay_file(self):
        """Load a replay file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Replay File", "", "JSON files (*.json);;All files (*)")
        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)

                self.replay_data = data.get('messages', [])
                self.update_message_table()

                self.status_label.setText(f"Loaded {len(self.replay_data)} messages from {os.path.basename(filename)}")

            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load replay file: {str(e)}")

    def save_replay_file(self):
        """Save the current replay list to file."""
        if not self.replay_data:
            QMessageBox.warning(self, "No Data", "No messages to save.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Replay File", "", "JSON files (*.json);;All files (*)")
        if filename:
            try:
                data = {
                    'messages': self.replay_data,
                    'config': {
                        'timing_mode': self.timing_combo.currentText(),
                        'loop': self.loop_check.isChecked(),
                        'loop_count': self.loop_count_spin.value()
                    }
                }

                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)

                self.status_label.setText(f"Saved {len(self.replay_data)} messages to {os.path.basename(filename)}")

            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save replay file: {str(e)}")

    def export_selected_messages(self):
        """Export selected messages."""
        # This would export selected messages from the main table
        QMessageBox.information(self, "Export Messages",
                               "This would export selected messages from the main CAN table.")

    def start_replay(self):
        """Start the message replay."""
        if not self.replay_data:
            QMessageBox.warning(self, "No Messages", "No messages to replay.")
            return

        self.is_replaying = True
        self.start_replay_button.setEnabled(False)
        self.pause_replay_button.setEnabled(True)
        self.stop_replay_button.setEnabled(True)

        # Create replay configuration
        config = {
            'timing_mode': self.timing_combo.currentText(),
            'interval': self.interval_spin.value(),
            'speed': self.speed_spin.value() / 100.0,
            'loop': self.loop_check.isChecked(),
            'loop_count': self.loop_count_spin.value()
        }

        # Start replay thread
        self.replay_thread = ReplayThread(self.replay_data, config)
        self.replay_thread.progress_update.connect(self.on_replay_progress)
        self.replay_thread.message_sent.connect(self.on_message_sent)
        self.replay_thread.replay_complete.connect(self.on_replay_complete)
        self.replay_thread.start()

        self.status_label.setText("Replaying messages...")

    def pause_replay(self):
        """Pause the current replay."""
        if self.replay_thread:
            self.replay_thread.pause()

        self.pause_replay_button.setText("Resume")
        self.pause_replay_button.clicked.disconnect()
        self.pause_replay_button.clicked.connect(self.resume_replay)

    def resume_replay(self):
        """Resume the paused replay."""
        if self.replay_thread:
            self.replay_thread.resume()

        self.pause_replay_button.setText("Pause")
        self.pause_replay_button.clicked.disconnect()
        self.pause_replay_button.clicked.connect(self.pause_replay)

    def stop_replay(self):
        """Stop the current replay."""
        if self.replay_thread:
            self.replay_thread.stop()

        self.is_replaying = False
        self.start_replay_button.setEnabled(True)
        self.pause_replay_button.setEnabled(False)
        self.stop_replay_button.setEnabled(False)
        self.pause_replay_button.setText("Pause")

        self.status_label.setText("Replay stopped")

    def step_replay(self):
        """Step forward one message in manual mode."""
        if self.replay_thread:
            self.replay_thread.step()

    def rewind_replay(self):
        """Rewind replay to beginning."""
        if self.replay_thread:
            self.replay_thread.rewind()

    def on_replay_progress(self, progress, message):
        """Handle replay progress updates."""
        self.replay_progress.setValue(progress)
        self.progress_label.setText(message)

    def on_message_sent(self, message_info):
        """Handle message sent notification."""
        # Update statistics
        self.update_statistics()

    def on_replay_complete(self):
        """Handle replay completion."""
        self.is_replaying = False
        self.start_replay_button.setEnabled(True)
        self.pause_replay_button.setEnabled(False)
        self.stop_replay_button.setEnabled(False)
        self.pause_replay_button.setText("Pause")

        self.status_label.setText("Replay complete")

    def update_message_table(self):
        """Update the message table with replay data."""
        self.message_table.setRowCount(len(self.replay_data))

        for row, msg in enumerate(self.replay_data):
            # ID
            id_item = QTableWidgetItem(f"0x{msg['id']:03X}")
            self.message_table.setItem(row, 0, id_item)

            # Data
            data_str = ' '.join(f"{b:02X}" for b in msg['data'])
            data_item = QTableWidgetItem(data_str)
            self.message_table.setItem(row, 1, data_item)

            # Length
            len_item = QTableWidgetItem(str(len(msg['data'])))
            self.message_table.setItem(row, 2, len_item)

            # Timestamp
            ts_item = QTableWidgetItem(f"{msg.get('timestamp', 0):.3f}")
            self.message_table.setItem(row, 3, ts_item)

            # Interval
            interval_item = QTableWidgetItem(f"{msg.get('interval', 0):.1f}")
            self.message_table.setItem(row, 4, interval_item)

            # Count
            count_item = QTableWidgetItem(str(msg.get('count', 1)))
            self.message_table.setItem(row, 5, count_item)

    def update_statistics(self):
        """Update replay statistics."""
        if not self.replay_thread:
            return

        stats = self.replay_thread.get_statistics()

        stats_text = "Replay Statistics\n\n"
        stats_text += f"Total Messages: {stats.get('total_messages', 0)}\n"
        stats_text += f"Messages Sent: {stats.get('messages_sent', 0)}\n"
        stats_text += f"Current Loop: {stats.get('current_loop', 1)}\n"
        stats_text += f"Elapsed Time: {stats.get('elapsed_time', 0):.2f}s\n"
        stats_text += f"Average Rate: {stats.get('avg_rate', 0):.1f} msg/s\n"

        if stats.get('errors', 0) > 0:
            stats_text += f"Errors: {stats['errors']}\n"

        self.stats_text.setText(stats_text)

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []


class ReplayThread(QThread):
    """Background thread for message replay."""

    progress_update = pyqtSignal(int, str)
    message_sent = pyqtSignal(dict)
    replay_complete = pyqtSignal()

    def __init__(self, messages, config):
        super().__init__()
        self.messages = messages.copy()
        self.config = config
        self.stop_requested = False
        self.pause_requested = False
        self.step_requested = False
        self.rewind_requested = False

        self.current_index = 0
        self.current_loop = 1
        self.messages_sent = 0
        self.errors = 0
        self.start_time = None

        self.timer = QElapsedTimer()

    def run(self):
        """Run the replay."""
        self.start_time = time.time()
        self.timer.start()

        timing_mode = self.config['timing_mode']
        loop = self.config.get('loop', False)
        max_loops = self.config.get('loop_count', 1)

        while not self.stop_requested:
            if self.pause_requested:
                self.msleep(100)  # Wait while paused
                continue

            if self.rewind_requested:
                self.current_index = 0
                self.rewind_requested = False
                continue

            if timing_mode == "Manual Control" and not self.step_requested:
                self.msleep(100)  # Wait for step command
                continue

            if self.current_index >= len(self.messages):
                if loop and (max_loops == 0 or self.current_loop < max_loops):
                    self.current_index = 0
                    self.current_loop += 1
                else:
                    break

            # Get current message
            msg = self.messages[self.current_index]

            # Send message (simulate)
            try:
                self.send_message(msg)
                self.messages_sent += 1
                self.message_sent.emit({
                    'index': self.current_index,
                    'message': msg,
                    'loop': self.current_loop
                })
            except Exception as e:
                self.errors += 1
                print(f"Error sending message: {e}")

            # Update progress
            total_messages = len(self.messages)
            if loop and max_loops > 0:
                total_messages *= max_loops

            progress = int(100 * (self.messages_sent) / total_messages)
            self.progress_update.emit(progress,
                f"Sent {self.messages_sent}/{total_messages} messages (Loop {self.current_loop})")

            # Calculate delay for next message
            delay = self.calculate_delay(msg, timing_mode)
            if delay > 0 and not self.step_requested:
                self.msleep(int(delay))

            self.current_index += 1
            self.step_requested = False

        self.replay_complete.emit()

    def send_message(self, message):
        """Send a CAN message."""
        # In a real implementation, this would send the message via CAN interface
        # For now, just simulate the delay
        self.msleep(1)  # Simulate transmission time

    def calculate_delay(self, message, timing_mode):
        """Calculate delay before next message."""
        if timing_mode == "Fixed Interval":
            return self.config.get('interval', 100)
        elif timing_mode == "Speed Multiplier":
            original_interval = message.get('interval', 100)
            return original_interval / self.config.get('speed', 1.0)
        elif timing_mode == "Original Timing":
            return message.get('interval', 100)
        else:  # Manual Control
            return 0

    def pause(self):
        """Pause the replay."""
        self.pause_requested = True

    def resume(self):
        """Resume the replay."""
        self.pause_requested = False

    def stop(self):
        """Stop the replay."""
        self.stop_requested = True

    def step(self):
        """Step forward one message."""
        self.step_requested = True

    def rewind(self):
        """Rewind to beginning."""
        self.rewind_requested = True

    def get_statistics(self):
        """Get current replay statistics."""
        elapsed = self.timer.elapsed() / 1000.0  # Convert to seconds

        return {
            'total_messages': len(self.messages),
            'messages_sent': self.messages_sent,
            'current_loop': self.current_loop,
            'elapsed_time': elapsed,
            'avg_rate': self.messages_sent / elapsed if elapsed > 0 else 0,
            'errors': self.errors
        }