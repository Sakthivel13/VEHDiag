"""Custom Sender Window - Send Arbitrary CAN Messages."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QSplitter, QMessageBox,
                             QTextEdit, QSpinBox, QComboBox, QLineEdit,
                             QCheckBox, QProgressBar, QRadioButton,
                             QButtonGroup, QFileDialog, QMenuBar, QAction,
                             QFormLayout, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QIcon, QValidator, QRegExpValidator
import re
import json
import os


class HexValidator(QValidator):
    """Validator for hexadecimal input."""

    def validate(self, input_str, pos):
        # Allow empty string, hex digits, and spaces
        if not input_str:
            return QValidator.Acceptable, input_str, pos

        # Check if all characters are valid hex or space
        valid_chars = set('0123456789abcdefABCDEF ')
        if all(c in valid_chars for c in input_str):
            return QValidator.Acceptable, input_str, pos
        else:
            return QValidator.Invalid, input_str, pos


class CustomSenderWindow(QMainWindow):
    """Window for sending arbitrary CAN messages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sent_messages = []
        self.templates = []
        self.is_sending = False

        self.init_ui()
        self.init_menu()
        self.load_templates()

    def init_ui(self):
        """Initialize the custom sender UI."""
        self.setWindowTitle("Custom Message Sender")
        self.setGeometry(200, 200, 1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)

        # Message composer
        self.create_message_composer(layout)

        # Control panel
        self.create_control_panel(layout)

        # History splitter
        history_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(history_splitter)

        # Left - Send history
        self.create_history_panel(history_splitter)

        # Right - Templates
        self.create_templates_panel(history_splitter)

        history_splitter.setSizes([600, 400])

        # Status bar
        self.status_label = QLabel("Ready - Compose and send CAN messages")
        layout.addWidget(self.status_label)

    def init_menu(self):
        """Initialize the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        save_template_action = QAction('Save as Template', self)
        save_template_action.triggered.connect(self.save_as_template)
        file_menu.addAction(save_template_action)

        load_template_action = QAction('Load Templates', self)
        load_template_action.triggered.connect(self.load_templates)
        file_menu.addAction(load_template_action)

        file_menu.addSeparator()

        export_history_action = QAction('Export Send History', self)
        export_history_action.triggered.connect(self.export_history)
        file_menu.addAction(export_history_action)

        # Edit menu
        edit_menu = menubar.addMenu('Edit')

        clear_history_action = QAction('Clear History', self)
        clear_history_action.triggered.connect(self.clear_history)
        edit_menu.addAction(clear_history_action)

        clear_composer_action = QAction('Clear Composer', self)
        clear_composer_action.triggered.connect(self.clear_composer)
        edit_menu.addAction(clear_composer_action)

    def create_message_composer(self, parent):
        """Create the message composer panel."""
        composer_group = QGroupBox("Message Composer")
        composer_layout = QVBoxLayout()

        # ID input
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("CAN ID (Hex):"))

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("e.g., 123, 0x7DF")
        self.id_edit.setMaximumWidth(150)
        # Add validator for hex input
        hex_validator = QRegExpValidator(re.compile(r'^(0x)?[0-9a-fA-F]{1,8}$'))
        self.id_edit.setValidator(hex_validator)

        id_layout.addWidget(self.id_edit)

        # Extended ID checkbox
        self.extended_check = QCheckBox("Extended ID (29-bit)")
        id_layout.addWidget(self.extended_check)

        # DLC
        dlc_layout = QHBoxLayout()
        dlc_layout.addWidget(QLabel("DLC:"))

        self.dlc_combo = QComboBox()
        self.dlc_combo.addItems([str(i) for i in range(9)])  # 0-8 bytes
        self.dlc_combo.setCurrentText("8")
        self.dlc_combo.currentTextChanged.connect(self.on_dlc_changed)

        dlc_layout.addWidget(self.dlc_combo)
        dlc_layout.addStretch()

        # Data input
        data_layout = QVBoxLayout()

        # Data format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Data Format:"))

        self.format_group = QButtonGroup()

        self.hex_radio = QRadioButton("Hex")
        self.dec_radio = QRadioButton("Decimal")
        self.ascii_radio = QRadioButton("ASCII")

        self.hex_radio.setChecked(True)

        self.format_group.addButton(self.hex_radio)
        self.format_group.addButton(self.dec_radio)
        self.format_group.addButton(self.ascii_radio)

        self.format_group.buttonClicked.connect(self.on_format_changed)

        format_layout.addWidget(self.hex_radio)
        format_layout.addWidget(self.dec_radio)
        format_layout.addWidget(self.ascii_radio)
        format_layout.addStretch()

        # Data input field
        self.data_edit = QLineEdit()
        self.data_edit.setPlaceholderText("Enter data bytes (space separated for hex)")
        hex_validator = HexValidator()
        self.data_edit.setValidator(hex_validator)

        # Individual byte inputs
        bytes_layout = QHBoxLayout()
        bytes_layout.addWidget(QLabel("Bytes:"))

        self.byte_edits = []
        for i in range(8):
            byte_edit = QLineEdit()
            byte_edit.setMaximumWidth(40)
            byte_edit.setPlaceholderText("00")
            byte_edit.setValidator(QRegExpValidator(re.compile(r'^[0-9a-fA-F]{0,2}$')))
            byte_edit.textChanged.connect(self.on_byte_changed)
            self.byte_edits.append(byte_edit)
            bytes_layout.addWidget(byte_edit)

        bytes_layout.addStretch()

        data_layout.addLayout(format_layout)
        data_layout.addWidget(self.data_edit)
        data_layout.addLayout(bytes_layout)

        # Add layouts to composer
        composer_layout.addLayout(id_layout)
        composer_layout.addLayout(dlc_layout)
        composer_layout.addLayout(data_layout)

        composer_group.setLayout(composer_layout)
        parent.addWidget(composer_group)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QVBoxLayout(panel)

        # Send options
        options_group = QGroupBox("Send Options")
        options_layout = QVBoxLayout()

        # Send mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Send Mode:"))

        self.send_mode_combo = QComboBox()
        self.send_mode_combo.addItems([
            "Send Once",
            "Send Repeatedly",
            "Send with Delay"
        ])
        self.send_mode_combo.currentTextChanged.connect(self.on_send_mode_changed)

        mode_layout.addWidget(self.send_mode_combo)

        # Repeat parameters
        self.repeat_layout = QHBoxLayout()

        self.count_label = QLabel("Count:")
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 10000)
        self.count_spin.setValue(10)

        self.delay_label = QLabel("Delay:")
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(10, 10000)
        self.delay_spin.setValue(100)
        self.delay_spin.setSuffix(" ms")

        self.repeat_layout.addWidget(self.count_label)
        self.repeat_layout.addWidget(self.count_spin)
        self.repeat_layout.addWidget(self.delay_label)
        self.repeat_layout.addWidget(self.delay_spin)
        self.repeat_layout.addStretch()

        # Send buttons
        buttons_layout = QHBoxLayout()

        self.send_button = QPushButton("Send Message")
        self.send_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        self.send_button.clicked.connect(self.send_message)

        self.stop_button = QPushButton("Stop Sending")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_sending)

        self.add_to_history_button = QPushButton("Add to History")
        self.add_to_history_button.clicked.connect(self.add_to_history)

        buttons_layout.addWidget(self.send_button)
        buttons_layout.addWidget(self.stop_button)
        buttons_layout.addWidget(self.add_to_history_button)
        buttons_layout.addStretch()

        options_layout.addLayout(mode_layout)
        options_layout.addLayout(self.repeat_layout)
        options_layout.addLayout(buttons_layout)

        options_group.setLayout(options_layout)
        control_layout.addWidget(options_group)

        parent.addWidget(panel)

    def create_history_panel(self, parent):
        """Create the send history panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        history_group = QGroupBox("Send History")
        history_layout = QVBoxLayout()

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels([
            "Time", "ID", "Data", "Status", "Count"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.itemDoubleClicked.connect(self.on_history_double_click)

        history_layout.addWidget(self.history_table)

        # History controls
        history_controls = QHBoxLayout()

        self.resend_button = QPushButton("Resend Selected")
        self.resend_button.clicked.connect(self.resend_selected)

        self.remove_history_button = QPushButton("Remove Selected")
        self.remove_history_button.clicked.connect(self.remove_selected_history)

        history_controls.addWidget(self.resend_button)
        history_controls.addWidget(self.remove_history_button)
        history_controls.addStretch()

        history_layout.addLayout(history_controls)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        parent.addWidget(panel)

    def create_templates_panel(self, parent):
        """Create the templates panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        templates_group = QGroupBox("Message Templates")
        templates_layout = QVBoxLayout()

        self.templates_table = QTableWidget()
        self.templates_table.setColumnCount(4)
        self.templates_table.setHorizontalHeaderLabels([
            "Name", "ID", "Data", "Description"
        ])
        self.templates_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.templates_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.templates_table.itemDoubleClicked.connect(self.on_template_double_click)

        templates_layout.addWidget(self.templates_table)

        # Template controls
        template_controls = QHBoxLayout()

        self.load_template_button = QPushButton("Load Selected")
        self.load_template_button.clicked.connect(self.load_selected_template)

        self.delete_template_button = QPushButton("Delete Selected")
        self.delete_template_button.clicked.connect(self.delete_selected_template)

        template_controls.addWidget(self.load_template_button)
        template_controls.addWidget(self.delete_template_button)
        template_controls.addStretch()

        templates_layout.addLayout(template_controls)
        templates_group.setLayout(templates_layout)
        layout.addWidget(templates_group)

        parent.addWidget(panel)

    def on_dlc_changed(self, dlc_str):
        """Handle DLC changes."""
        dlc = int(dlc_str)
        for i, byte_edit in enumerate(self.byte_edits):
            byte_edit.setEnabled(i < dlc)

        # Update data field based on current format
        self.update_data_field()

    def on_format_changed(self, button):
        """Handle data format changes."""
        self.update_data_field()

    def on_byte_changed(self):
        """Handle individual byte changes."""
        if self.hex_radio.isChecked():
            self.update_data_field()

    def on_send_mode_changed(self, mode):
        """Handle send mode changes."""
        if mode == "Send Once":
            self.count_label.hide()
            self.count_spin.hide()
            self.delay_label.hide()
            self.delay_spin.hide()
        elif mode == "Send Repeatedly":
            self.count_label.show()
            self.count_spin.show()
            self.delay_label.show()
            self.delay_spin.show()
        else:  # Send with Delay
            self.count_label.hide()
            self.count_spin.hide()
            self.delay_label.show()
            self.delay_spin.show()

    def update_data_field(self):
        """Update the data field based on individual byte inputs."""
        if not self.hex_radio.isChecked():
            return

        dlc = int(self.dlc_combo.currentText())
        data_bytes = []

        for i in range(dlc):
            text = self.byte_edits[i].text()
            if text:
                try:
                    data_bytes.append(int(text, 16))
                except ValueError:
                    pass

        if data_bytes:
            hex_str = ' '.join(f"{b:02X}" for b in data_bytes)
            self.data_edit.setText(hex_str)

    def send_message(self):
        """Send the composed message."""
        try:
            # Get CAN ID
            id_text = self.id_edit.text().strip()
            if not id_text:
                QMessageBox.warning(self, "Missing ID", "Please enter a CAN ID.")
                return

            if id_text.startswith('0x'):
                can_id = int(id_text, 16)
            else:
                can_id = int(id_text, 16)  # Assume hex

            # Get data
            data = self.get_message_data()
            if data is None:
                return

            # Create message
            message = {
                'id': can_id,
                'data': data,
                'extended': self.extended_check.isChecked(),
                'timestamp': time.time()
            }

            # Send mode
            send_mode = self.send_mode_combo.currentText()

            if send_mode == "Send Once":
                self.send_single_message(message)
            else:
                self.send_repeated_message(message, send_mode)

        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", f"Invalid input: {str(e)}")

    def get_message_data(self):
        """Get message data based on current format."""
        dlc = int(self.dlc_combo.currentText())

        if self.hex_radio.isChecked():
            data_text = self.data_edit.text().strip()
            if not data_text:
                # Try to get from individual bytes
                data = []
                for i in range(dlc):
                    text = self.byte_edits[i].text()
                    if text:
                        data.append(int(text, 16))
                    else:
                        data.append(0)
                return data
            else:
                # Parse hex string
                parts = data_text.split()
                if len(parts) != dlc:
                    QMessageBox.warning(self, "Data Length Mismatch",
                                       f"Expected {dlc} bytes, got {len(parts)}.")
                    return None

                try:
                    return [int(p, 16) for p in parts]
                except ValueError:
                    QMessageBox.warning(self, "Invalid Hex", "Invalid hexadecimal data.")
                    return None

        elif self.dec_radio.isChecked():
            data_text = self.data_edit.text().strip()
            if not data_text:
                QMessageBox.warning(self, "Missing Data", "Please enter decimal data.")
                return None

            parts = data_text.split()
            if len(parts) != dlc:
                QMessageBox.warning(self, "Data Length Mismatch",
                                   f"Expected {dlc} bytes, got {len(parts)}.")
                return None

            try:
                return [int(p) for p in parts]
            except ValueError:
                QMessageBox.warning(self, "Invalid Decimal", "Invalid decimal data.")
                return None

        else:  # ASCII
            data_text = self.data_edit.text()
            if len(data_text) > dlc:
                QMessageBox.warning(self, "Data Too Long",
                                   f"ASCII data too long for DLC {dlc}.")
                return None

            data = [ord(c) for c in data_text]
            # Pad with zeros
            while len(data) < dlc:
                data.append(0)
            return data

    def send_single_message(self, message):
        """Send a single message."""
        try:
            # In a real implementation, send via CAN interface
            self.add_to_history(message, "Sent", 1)
            self.status_label.setText(f"Sent message ID 0x{message['id']:03X}")

        except Exception as e:
            self.add_to_history(message, f"Error: {str(e)}", 0)
            QMessageBox.critical(self, "Send Error", f"Failed to send message: {str(e)}")

    def send_repeated_message(self, message, mode):
        """Send a message repeatedly."""
        if self.is_sending:
            return

        self.is_sending = True
        self.send_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        if mode == "Send Repeatedly":
            count = self.count_spin.value()
            delay = self.delay_spin.value()
        else:  # Send with Delay
            count = 0  # Send until stopped
            delay = self.delay_spin.value()

        # Start send thread
        self.send_thread = RepeatedSendThread(message, count, delay)
        self.send_thread.progress_update.connect(self.on_send_progress)
        self.send_thread.send_complete.connect(self.on_send_complete)
        self.send_thread.message_sent.connect(self.on_message_sent)
        self.send_thread.start()

        self.status_label.setText("Sending messages...")

    def stop_sending(self):
        """Stop repeated sending."""
        if self.send_thread and self.send_thread.isRunning():
            self.send_thread.stop()

        self.is_sending = False
        self.send_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Sending stopped")

    def on_send_progress(self, sent, total):
        """Handle send progress."""
        if total > 0:
            self.status_label.setText(f"Sent {sent}/{total} messages")
        else:
            self.status_label.setText(f"Sent {sent} messages")

    def on_send_complete(self, total_sent):
        """Handle send completion."""
        self.is_sending = False
        self.send_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText(f"Completed: sent {total_sent} messages")

    def on_message_sent(self, message):
        """Handle individual message sent."""
        self.add_to_history(message, "Sent", 1)

    def add_to_history(self, message, status="Sent", count=1):
        """Add message to send history."""
        import time
        timestamp = time.strftime("%H:%M:%S", time.localtime(message.get('timestamp', time.time())))

        row = self.history_table.rowCount()
        self.history_table.insertRow(row)

        # Time
        time_item = QTableWidgetItem(timestamp)
        self.history_table.setItem(row, 0, time_item)

        # ID
        id_item = QTableWidgetItem(f"0x{message['id']:03X}")
        self.history_table.setItem(row, 1, id_item)

        # Data
        data_str = ' '.join(f"{b:02X}" for b in message['data'])
        data_item = QTableWidgetItem(data_str)
        self.history_table.setItem(row, 2, data_item)

        # Status
        status_item = QTableWidgetItem(status)
        if "Error" in status:
            status_item.setBackground(QColor(255, 200, 200))
        else:
            status_item.setBackground(QColor(200, 255, 200))
        self.history_table.setItem(row, 3, status_item)

        # Count
        count_item = QTableWidgetItem(str(count))
        self.history_table.setItem(row, 4, count_item)

        # Store message
        self.sent_messages.append({
            'message': message,
            'status': status,
            'count': count,
            'timestamp': timestamp
        })

    def resend_selected(self):
        """Resend selected message from history."""
        current_row = self.history_table.currentRow()
        if current_row >= 0 and current_row < len(self.sent_messages):
            message = self.sent_messages[current_row]['message']
            self.send_single_message(message)

    def remove_selected_history(self):
        """Remove selected item from history."""
        current_row = self.history_table.currentRow()
        if current_row >= 0:
            self.history_table.removeRow(current_row)
            self.sent_messages.pop(current_row)

    def clear_history(self):
        """Clear send history."""
        self.history_table.setRowCount(0)
        self.sent_messages = []

    def clear_composer(self):
        """Clear the message composer."""
        self.id_edit.clear()
        self.data_edit.clear()
        for byte_edit in self.byte_edits:
            byte_edit.clear()
        self.dlc_combo.setCurrentText("8")

    def on_history_double_click(self, item):
        """Handle double-click on history item."""
        row = item.row()
        if row >= 0 and row < len(self.sent_messages):
            message = self.sent_messages[row]['message']
            self.load_message_into_composer(message)

    def load_message_into_composer(self, message):
        """Load a message into the composer."""
        # Set ID
        self.id_edit.setText(f"0x{message['id']:03X}")
        self.extended_check.setChecked(message.get('extended', False))

        # Set data
        data = message['data']
        dlc = len(data)
        self.dlc_combo.setCurrentText(str(dlc))

        # Update byte fields
        for i in range(8):
            if i < dlc:
                self.byte_edits[i].setText(f"{data[i]:02X}")
            else:
                self.byte_edits[i].clear()

        # Update data field
        self.update_data_field()

    def save_as_template(self):
        """Save current message as template."""
        name, ok = QInputDialog.getText(self, "Save Template", "Template name:")
        if ok and name:
            try:
                data = self.get_message_data()
                if data is None:
                    return

                id_text = self.id_edit.text().strip()
                if id_text.startswith('0x'):
                    can_id = int(id_text, 16)
                else:
                    can_id = int(id_text, 16)

                template = {
                    'name': name,
                    'id': can_id,
                    'data': data,
                    'extended': self.extended_check.isChecked(),
                    'description': f"Custom template: ID 0x{can_id:03X}"
                }

                self.templates.append(template)
                self.save_templates()
                self.update_templates_table()

                QMessageBox.information(self, "Template Saved",
                                       f"Template '{name}' saved successfully.")

            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save template: {str(e)}")

    def load_templates(self):
        """Load message templates."""
        try:
            template_file = os.path.join(os.path.dirname(__file__), 'templates.json')
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    self.templates = json.load(f)
            else:
                # Load default templates
                self.templates = self.get_default_templates()

            self.update_templates_table()

        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load templates: {str(e)}")
            self.templates = []

    def get_default_templates(self):
        """Get default message templates."""
        return [
            {
                'name': 'OBD2 Engine RPM',
                'id': 0x7DF,
                'data': [0x02, 0x01, 0x0C, 0x00, 0x00, 0x00, 0x00, 0x00],
                'extended': False,
                'description': 'Request engine RPM from ECU'
            },
            {
                'name': 'OBD2 Vehicle Speed',
                'id': 0x7DF,
                'data': [0x02, 0x01, 0x0D, 0x00, 0x00, 0x00, 0x00, 0x00],
                'extended': False,
                'description': 'Request vehicle speed from ECU'
            },
            {
                'name': 'UDS Diagnostic Session',
                'id': 0x7DF,
                'data': [0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00],
                'extended': False,
                'description': 'Request diagnostic session with ECU'
            }
        ]

    def save_templates(self):
        """Save templates to file."""
        try:
            template_file = os.path.join(os.path.dirname(__file__), 'templates.json')
            with open(template_file, 'w') as f:
                json.dump(self.templates, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save templates: {str(e)}")

    def update_templates_table(self):
        """Update the templates table."""
        self.templates_table.setRowCount(len(self.templates))

        for row, template in enumerate(self.templates):
            # Name
            name_item = QTableWidgetItem(template['name'])
            self.templates_table.setItem(row, 0, name_item)

            # ID
            id_item = QTableWidgetItem(f"0x{template['id']:03X}")
            self.templates_table.setItem(row, 1, id_item)

            # Data
            data_str = ' '.join(f"{b:02X}" for b in template['data'])
            data_item = QTableWidgetItem(data_str)
            self.templates_table.setItem(row, 2, data_item)

            # Description
            desc_item = QTableWidgetItem(template.get('description', ''))
            self.templates_table.setItem(row, 3, desc_item)

    def on_template_double_click(self, item):
        """Handle double-click on template."""
        row = item.row()
        if row >= 0 and row < len(self.templates):
            self.load_selected_template()

    def load_selected_template(self):
        """Load selected template into composer."""
        current_row = self.templates_table.currentRow()
        if current_row >= 0 and current_row < len(self.templates):
            template = self.templates[current_row]
            self.load_template_into_composer(template)

    def load_template_into_composer(self, template):
        """Load a template into the composer."""
        # Set ID
        self.id_edit.setText(f"0x{template['id']:03X}")
        self.extended_check.setChecked(template.get('extended', False))

        # Set data
        data = template['data']
        dlc = len(data)
        self.dlc_combo.setCurrentText(str(dlc))

        # Update byte fields
        for i in range(8):
            if i < dlc:
                self.byte_edits[i].setText(f"{data[i]:02X}")
            else:
                self.byte_edits[i].clear()

        # Update data field
        self.update_data_field()

    def delete_selected_template(self):
        """Delete selected template."""
        current_row = self.templates_table.currentRow()
        if current_row >= 0 and current_row < len(self.templates):
            template_name = self.templates[current_row]['name']
            reply = QMessageBox.question(self, "Delete Template",
                                        f"Delete template '{template_name}'?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.templates.pop(current_row)
                self.save_templates()
                self.update_templates_table()

    def export_history(self):
        """Export send history to file."""
        if not self.sent_messages:
            QMessageBox.warning(self, "No History", "No messages to export.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Export History", "", "JSON files (*.json);;CSV files (*.csv);;All files (*)")
        if filename:
            try:
                if filename.endswith('.csv'):
                    self.export_history_csv(filename)
                else:
                    self.export_history_json(filename)

                self.status_label.setText(f"History exported to {os.path.basename(filename)}")

            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export history: {str(e)}")

    def export_history_json(self, filename):
        """Export history as JSON."""
        data = {
            'export_time': time.time(),
            'messages': self.sent_messages
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def export_history_csv(self, filename):
        """Export history as CSV."""
        import csv
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time', 'ID', 'Data', 'Status', 'Count'])

            for item in self.sent_messages:
                msg = item['message']
                data_str = ' '.join(f"{b:02X}" for b in msg['data'])
                writer.writerow([
                    item['timestamp'],
                    f"0x{msg['id']:03X}",
                    data_str,
                    item['status'],
                    item['count']
                ])


class RepeatedSendThread(QThread):
    """Background thread for repeated message sending."""

    progress_update = pyqtSignal(int, int)  # sent, total
    send_complete = pyqtSignal(int)  # total_sent
    message_sent = pyqtSignal(dict)  # message

    def __init__(self, message, count, delay):
        super().__init__()
        self.message = message
        self.count = count  # 0 for infinite
        self.delay = delay
        self.stop_requested = False
        self.sent_count = 0

    def run(self):
        """Run the repeated send."""
        while not self.stop_requested:
            if self.count > 0 and self.sent_count >= self.count:
                break

            try:
                # Send message (simulate)
                self.msleep(1)  # Simulate send time

                self.sent_count += 1
                self.message_sent.emit(self.message.copy())

                # Update progress
                if self.count > 0:
                    self.progress_update.emit(self.sent_count, self.count)
                else:
                    self.progress_update.emit(self.sent_count, 0)

            except Exception as e:
                print(f"Error sending message: {e}")

            # Delay between sends
            if self.delay > 0:
                self.msleep(self.delay)

        self.send_complete.emit(self.sent_count)

    def stop(self):
        """Stop the sending."""
        self.stop_requested = True