"""Scripting Interface Window - Execute Scripted CAN Message Sequences."""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QSplitter, QMessageBox,
                             QTextEdit, QSpinBox, QComboBox, QLineEdit,
                             QCheckBox, QProgressBar, QPlainTextEdit, QListWidget,
                             QFileDialog, QMenuBar, QAction)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QIcon
import re
import json
import os
import time


class ScriptingInterfaceWindow(QMainWindow):
    """Window for executing scripted CAN message sequences."""

    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.script_thread = None
        self.is_running = False

        self.setWindowTitle("Scripting Interface - PyCANAnalyzer")
        self.setGeometry(200, 200, 1000, 700)

        self.init_ui()
        self.init_menu()

    def init_ui(self):
        """Initialize the scripting interface UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Create splitter for main layout
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # Top section - Script editor and controls
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)

        # Control panel
        self.create_control_panel(top_layout)

        # Script editor
        self.create_script_editor(top_layout)

        splitter.addWidget(top_widget)

        # Bottom section - Output and variables
        bottom_splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(bottom_splitter)

        # Output console
        self.create_output_console(bottom_splitter)

        # Variables and functions
        self.create_variables_panel(bottom_splitter)

        splitter.setSizes([400, 300])

    def create_control_panel(self, parent_layout):
        """Create the script control panel."""
        control_group = QGroupBox("Script Controls")
        control_layout = QHBoxLayout(control_group)

        # Execution controls
        self.run_button = QPushButton("▶ Run Script")
        self.run_button.clicked.connect(self.run_script)
        control_layout.addWidget(self.run_button)

        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.clicked.connect(self.stop_script)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)

        # Options
        self.loop_checkbox = QCheckBox("Loop execution")
        control_layout.addWidget(self.loop_checkbox)

        self.real_time_checkbox = QCheckBox("Real-time timing")
        self.real_time_checkbox.setChecked(True)
        control_layout.addWidget(self.real_time_checkbox)

        # Progress
        control_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        control_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        control_layout.addWidget(self.status_label)

        parent_layout.addWidget(control_group)

    def create_script_editor(self, parent_layout):
        """Create the script editor."""
        editor_group = QGroupBox("Script Editor")
        editor_layout = QVBoxLayout(editor_group)

        # Script input
        self.script_edit = QPlainTextEdit()
        self.script_edit.setFont(QFont("Courier New", 10))
        self.script_edit.setPlaceholderText("# Enter your CAN scripting code here\n# Example:\n# send_frame(0x123, [0x11, 0x22, 0x33])\n# sleep(0.1)\n# send_frame(0x124, [0xAA, 0xBB])")

        # Add syntax highlighting (basic)
        self.setup_syntax_highlighting()

        editor_layout.addWidget(self.script_edit)

        # Template buttons
        template_layout = QHBoxLayout()

        self.load_template_button = QPushButton("Load Template")
        self.load_template_button.clicked.connect(self.load_template)
        template_layout.addWidget(self.load_template_button)

        self.save_script_button = QPushButton("Save Script")
        self.save_script_button.clicked.connect(self.save_script)
        template_layout.addWidget(self.save_script_button)

        template_layout.addStretch()
        editor_layout.addLayout(template_layout)

        parent_layout.addWidget(editor_group)

    def create_output_console(self, parent_splitter):
        """Create the output console."""
        console_group = QGroupBox("Output Console")
        console_layout = QVBoxLayout(console_group)

        self.output_text = QTextEdit()
        self.output_text.setFont(QFont("Courier New", 9))
        self.output_text.setMaximumHeight(200)
        console_layout.addWidget(self.output_text)

        parent_splitter.addWidget(console_group)

    def create_variables_panel(self, parent_splitter):
        """Create the variables and functions panel."""
        vars_group = QGroupBox("Variables & Functions")
        vars_layout = QVBoxLayout(vars_group)

        # Variables list
        self.vars_list = QListWidget()
        self.vars_list.addItem("Available functions:")
        self.vars_list.addItem("  send_frame(id, data)")
        self.vars_list.addItem("  sleep(seconds)")
        self.vars_list.addItem("  wait_for_frame(id, timeout)")
        self.vars_list.addItem("  set_variable(name, value)")
        self.vars_list.addItem("  get_variable(name)")
        vars_layout.addWidget(self.vars_list)

        parent_splitter.addWidget(vars_group)

    def setup_syntax_highlighting(self):
        """Setup basic syntax highlighting for the script editor."""
        # This is a simplified implementation
        # In a real application, you'd use a proper syntax highlighter
        pass

    def init_menu(self):
        """Initialize the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        load_action = QAction('Load Script...', self)
        load_action.triggered.connect(self.load_script_file)
        file_menu.addAction(load_action)

        save_action = QAction('Save Script...', self)
        save_action.triggered.connect(self.save_script_file)
        file_menu.addAction(save_action)

        # Templates menu
        templates_menu = menubar.addMenu('Templates')

        basic_action = QAction('Basic Send/Receive', self)
        basic_action.triggered.connect(lambda: self.load_basic_template())
        templates_menu.addAction(basic_action)

        diagnostic_action = QAction('Diagnostic Sequence', self)
        diagnostic_action.triggered.connect(lambda: self.load_diagnostic_template())
        templates_menu.addAction(diagnostic_action)

    def run_script(self):
        """Execute the script."""
        if self.is_running:
            return

        script_text = self.script_edit.toPlainText().strip()
        if not script_text:
            QMessageBox.warning(self, "No Script", "Please enter a script to execute.")
            return

        self.is_running = True
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Running script...")
        self.output_text.clear()

        # Start script execution thread
        self.script_thread = ScriptExecutionThread(script_text, self.pipeline)
        self.script_thread.output.connect(self.append_output)
        self.script_thread.progress.connect(self.update_progress)
        self.script_thread.finished.connect(self.on_script_finished)
        self.script_thread.error.connect(self.on_script_error)

        self.script_thread.start()

    def stop_script(self):
        """Stop script execution."""
        if self.script_thread and self.script_thread.isRunning():
            self.script_thread.stop()
            self.script_thread.wait()

        self.is_running = False
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")

    def append_output(self, text):
        """Append text to the output console."""
        self.output_text.append(text)

    def update_progress(self, value):
        """Update progress bar."""
        self.progress_bar.setValue(value)

    def on_script_finished(self):
        """Handle script execution completion."""
        self.is_running = False
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Script completed")
        self.append_output("Script execution completed.")

    def on_script_error(self, error_msg):
        """Handle script execution error."""
        self.is_running = False
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Error")
        self.append_output(f"Script error: {error_msg}")
        QMessageBox.critical(self, "Script Error", error_msg)

    def load_template(self):
        """Load a script template."""
        # Implementation would show template selection dialog
        self.append_output("Template loading not implemented yet.")

    def save_script(self):
        """Save the current script."""
        # Implementation would save script to file
        self.append_output("Script saving not implemented yet.")

    def load_script_file(self):
        """Load script from file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Script", "", "Python Files (*.py);;All Files (*)")
        if filename:
            try:
                with open(filename, 'r') as f:
                    self.script_edit.setPlainText(f.read())
                self.append_output(f"Loaded script from {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load script: {str(e)}")

    def save_script_file(self):
        """Save script to file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Script", "", "Python Files (*.py);;All Files (*)")
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.script_edit.toPlainText())
                self.append_output(f"Saved script to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save script: {str(e)}")

    def load_basic_template(self):
        """Load basic send/receive template."""
        template = '''# Basic CAN Script Template
# Send a frame and wait for response

# Send a diagnostic request
send_frame(0x7DF, [0x02, 0x01, 0x00])  # Request VIN

# Wait for response (timeout in seconds)
response = wait_for_frame(0x7E8, 2.0)
if response:
    print(f"Received response: {response}")
else:
    print("No response received")

# Sleep for 100ms
sleep(0.1)

# Send another frame
send_frame(0x123, [0x11, 0x22, 0x33, 0x44])
'''
        self.script_edit.setPlainText(template)

    def load_diagnostic_template(self):
        """Load diagnostic sequence template."""
        template = '''# Diagnostic Sequence Template
# Perform a series of diagnostic operations

print("Starting diagnostic sequence...")

# Request ECU identification
send_frame(0x7DF, [0x02, 0x1A, 0x80])  # Read ECU ID
sleep(0.05)

# Request DTCs
send_frame(0x7DF, [0x01, 0x03])  # Request DTCs
sleep(0.05)

# Clear DTCs
send_frame(0x7DF, [0x01, 0x04])  # Clear DTCs
sleep(0.05)

print("Diagnostic sequence completed.")
'''
        self.script_edit.setPlainText(template)

    def closeEvent(self, event):
        """Handle window close event."""
        if self.is_running:
            self.stop_script()
        event.accept()


class ScriptExecutionThread(QThread):
    """Thread for executing CAN scripts."""

    output = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, script_text, pipeline):
        super().__init__()
        self.script_text = script_text
        self.pipeline = pipeline
        self.is_running = True

    def run(self):
        """Execute the script."""
        try:
            # Create script execution environment
            env = self.create_script_environment()

            # Execute the script
            exec(self.script_text, env)

            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))

    def create_script_environment(self):
        """Create the execution environment with CAN functions."""
        env = {}

        # Add CAN functions
        def send_frame(can_id, data):
            """Send a CAN frame."""
            if not self.is_running:
                return

            try:
                # Convert data to bytes if it's a list
                if isinstance(data, list):
                    data = bytes(data)

                # In real implementation, this would send via pipeline
                self.output.emit(f"Sent frame: ID=0x{can_id:03X}, Data={data.hex()}")

                # Simulate some processing time
                time.sleep(0.01)

            except Exception as e:
                self.output.emit(f"Error sending frame: {str(e)}")

        def sleep(seconds):
            """Sleep for specified seconds."""
            if not self.is_running:
                return

            time.sleep(min(seconds, 1.0))  # Cap sleep time

        def wait_for_frame(can_id, timeout=1.0):
            """Wait for a frame with specified ID."""
            if not self.is_running:
                return None

            self.output.emit(f"Waiting for frame 0x{can_id:03X} (timeout: {timeout}s)")
            # In real implementation, this would wait for pipeline frames
            time.sleep(min(timeout, 1.0))  # Simulate waiting
            return None  # Simulate no response

        def set_variable(name, value):
            """Set a script variable."""
            env[name] = value
            self.output.emit(f"Set {name} = {value}")

        def get_variable(name):
            """Get a script variable."""
            return env.get(name)

        # Add functions to environment
        env['send_frame'] = send_frame
        env['sleep'] = sleep
        env['wait_for_frame'] = wait_for_frame
        env['set_variable'] = set_variable
        env['get_variable'] = get_variable
        env['print'] = lambda *args: self.output.emit(' '.join(str(arg) for arg in args))

        return env

    def stop(self):
        """Stop script execution."""
        self.is_running = False