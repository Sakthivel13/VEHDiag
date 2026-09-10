"""DBC Decoder Window - Decode CAN Frames Using DBC Files."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QSplitter, QMessageBox,
                             QTextEdit, QSpinBox, QComboBox, QLineEdit,
                             QCheckBox, QProgressBar, QFileDialog, QTreeWidget,
                             QTreeWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
import time
import os
import re


class DbcDecoderWindow(QMainWindow):
    """Window for decoding CAN frames using DBC database files."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.dbc_database = None
        self.decoded_signals = {}

        self.is_decoding = False

        self.init_ui()

    def init_ui(self):
        """Initialize the DBC decoder UI."""
        self.setWindowTitle("DBC CAN Decoder")
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

        # Top - Decoded signals
        self.create_decoded_signals_view(content_splitter)

        # Bottom - Details splitter
        details_splitter = QSplitter(Qt.Horizontal)
        content_splitter.addWidget(details_splitter)

        # Left - Frame details
        self.create_frame_details(details_splitter)

        # Right - DBC structure
        self.create_dbc_structure(details_splitter)

        content_splitter.setSizes([400, 500])

        # Status bar
        self.status_label = QLabel("Ready - Load DBC file and decode frames")
        layout.addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QHBoxLayout(panel)

        # DBC file management
        dbc_group = QGroupBox("DBC Database")
        dbc_layout = QVBoxLayout()

        # File selection
        file_layout = QHBoxLayout()
        self.dbc_path_edit = QLineEdit()
        self.dbc_path_edit.setPlaceholderText("DBC file path...")
        self.dbc_path_edit.setReadOnly(True)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_dbc_file)

        file_layout.addWidget(self.dbc_path_edit)
        file_layout.addWidget(self.browse_button)

        # Load/save
        action_layout = QHBoxLayout()
        self.load_dbc_button = QPushButton("Load DBC")
        self.load_dbc_button.clicked.connect(self.load_dbc_file)

        self.unload_dbc_button = QPushButton("Unload DBC")
        self.unload_dbc_button.clicked.connect(self.unload_dbc_file)
        self.unload_dbc_button.setEnabled(False)

        action_layout.addWidget(self.load_dbc_button)
        action_layout.addWidget(self.unload_dbc_button)

        dbc_layout.addLayout(file_layout)
        dbc_layout.addLayout(action_layout)

        dbc_group.setLayout(dbc_layout)
        control_layout.addWidget(dbc_group)

        # Decoding options
        options_group = QGroupBox("Decoding Options")
        options_layout = QVBoxLayout()

        # Filter options
        self.decode_all_check = QCheckBox("Decode all messages")
        self.decode_all_check.setChecked(True)

        self.decode_matched_check = QCheckBox("Only messages in DBC")
        self.decode_matched_check.setChecked(False)

        # Update mode
        update_layout = QHBoxLayout()
        update_layout.addWidget(QLabel("Update Mode:"))
        self.update_mode_combo = QComboBox()
        self.update_mode_combo.addItems([
            "Real-time", "On Demand", "Batch"
        ])
        update_layout.addWidget(self.update_mode_combo)

        options_layout.addWidget(self.decode_all_check)
        options_layout.addWidget(self.decode_matched_check)
        options_layout.addLayout(update_layout)

        options_group.setLayout(options_layout)
        control_layout.addWidget(options_group)

        # Decoding controls
        decode_group = QGroupBox("Decoding")
        decode_layout = QVBoxLayout()

        self.decode_button = QPushButton("Decode Frames")
        self.decode_button.clicked.connect(self.decode_frames)
        self.decode_button.setEnabled(False)

        self.stop_decode_button = QPushButton("Stop Decoding")
        self.stop_decode_button.setEnabled(False)
        self.stop_decode_button.clicked.connect(self.stop_decoding)

        self.clear_decoded_button = QPushButton("Clear Results")
        self.clear_decoded_button.clicked.connect(self.clear_decoded_results)

        decode_layout.addWidget(self.decode_button)
        decode_layout.addWidget(self.stop_decode_button)
        decode_layout.addWidget(self.clear_decoded_button)

        decode_group.setLayout(decode_layout)
        control_layout.addWidget(decode_group)

        parent.addWidget(panel)

    def create_decoded_signals_view(self, parent):
        """Create the decoded signals view."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Signals table
        signals_group = QGroupBox("Decoded Signals")
        signals_layout = QVBoxLayout()

        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(6)
        self.signals_table.setHorizontalHeaderLabels([
            "CAN ID", "Message Name", "Signal Name", "Raw Value",
            "Physical Value", "Units"
        ])
        self.signals_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.signals_table.itemSelectionChanged.connect(self.on_signal_selected)

        signals_layout.addWidget(self.signals_table)
        signals_group.setLayout(signals_layout)
        layout.addWidget(signals_group)

        parent.addWidget(panel)

    def create_frame_details(self, parent):
        """Create the frame details panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Frame info
        frame_group = QGroupBox("Frame Information")
        frame_layout = QVBoxLayout()

        self.frame_info_text = QTextEdit()
        self.frame_info_text.setReadOnly(True)
        self.frame_info_text.setMaximumHeight(150)

        frame_layout.addWidget(self.frame_info_text)
        frame_group.setLayout(frame_layout)
        layout.addWidget(frame_group)

        # Signal details
        signal_group = QGroupBox("Signal Details")
        signal_layout = QVBoxLayout()

        self.signal_details_text = QTextEdit()
        self.signal_details_text.setReadOnly(True)

        signal_layout.addWidget(self.signal_details_text)
        signal_group.setLayout(signal_layout)
        layout.addWidget(signal_group)

        parent.addWidget(panel)

    def create_dbc_structure(self, parent):
        """Create the DBC structure panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # DBC tree
        dbc_group = QGroupBox("DBC Structure")
        dbc_layout = QVBoxLayout()

        self.dbc_tree = QTreeWidget()
        self.dbc_tree.setHeaderLabels(["DBC Elements", "Details"])
        self.dbc_tree.itemSelectionChanged.connect(self.on_dbc_item_selected)

        dbc_layout.addWidget(self.dbc_tree)
        dbc_group.setLayout(dbc_layout)
        layout.addWidget(dbc_group)

        parent.addWidget(panel)

    def browse_dbc_file(self):
        """Browse for DBC file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select DBC File", "", "DBC Files (*.dbc);;All Files (*)"
        )

        if file_path:
            self.dbc_path_edit.setText(file_path)

    def load_dbc_file(self):
        """Load the DBC file."""
        dbc_path = self.dbc_path_edit.text().strip()
        if not dbc_path:
            QMessageBox.warning(self, "No File", "Please select a DBC file first.")
            return

        if not os.path.exists(dbc_path):
            QMessageBox.warning(self, "File Not Found",
                               f"DBC file not found: {dbc_path}")
            return

        self.status_label.setText("Loading DBC file...")

        # Load DBC in background thread
        self.load_thread = DbcLoadThread(dbc_path)
        self.load_thread.load_complete.connect(self.on_dbc_loaded)
        self.load_thread.start()

    def on_dbc_loaded(self, dbc_data):
        """Handle DBC file loading completion."""
        if dbc_data:
            self.dbc_database = dbc_data
            self.load_dbc_button.setEnabled(False)
            self.unload_dbc_button.setEnabled(True)
            self.decode_button.setEnabled(True)

            self.populate_dbc_tree()
            self.status_label.setText(f"DBC loaded: {len(dbc_data.get('messages', {}))} messages")
        else:
            QMessageBox.warning(self, "Load Failed", "Failed to load DBC file.")
            self.status_label.setText("DBC load failed")

    def unload_dbc_file(self):
        """Unload the current DBC file."""
        self.dbc_database = None
        self.load_dbc_button.setEnabled(True)
        self.unload_dbc_button.setEnabled(False)
        self.decode_button.setEnabled(False)

        self.dbc_tree.clear()
        self.clear_decoded_results()

        self.status_label.setText("DBC unloaded")

    def populate_dbc_tree(self):
        """Populate the DBC structure tree."""
        if not self.dbc_database:
            return

        self.dbc_tree.clear()

        # Add messages
        messages_item = QTreeWidgetItem(["Messages", f"{len(self.dbc_database.get('messages', {}))} total"])
        self.dbc_tree.addTopLevelItem(messages_item)

        for msg_id, message in self.dbc_database.get('messages', {}).items():
            msg_item = QTreeWidgetItem([
                f"0x{msg_id:03X}: {message.get('name', 'Unknown')}",
                f"{len(message.get('signals', {}))} signals"
            ])
            messages_item.addChild(msg_item)

            # Add signals
            for signal_name, signal in message.get('signals', {}).items():
                signal_item = QTreeWidgetItem([
                    signal_name,
                    f"Bits: {signal.get('start_bit', 0)}-{signal.get('start_bit', 0) + signal.get('length', 0) - 1}"
                ])
                msg_item.addChild(signal_item)

        # Add other DBC elements
        if 'ecus' in self.dbc_database:
            ecus_item = QTreeWidgetItem(["ECUs", f"{len(self.dbc_database['ecus'])} total"])
            self.dbc_tree.addTopLevelItem(ecus_item)

            for ecu in self.dbc_database['ecus']:
                ecu_item = QTreeWidgetItem([ecu.get('name', 'Unknown'), ecu.get('comment', '')])
                ecus_item.addChild(ecu_item)

        self.dbc_tree.expandToDepth(1)

    def decode_frames(self):
        """Decode frames using the loaded DBC."""
        if not self.dbc_database:
            QMessageBox.warning(self, "No DBC", "Please load a DBC file first.")
            return

        if not self.frames:
            QMessageBox.warning(self, "No Frames", "No frame data available.")
            return

        self.is_decoding = True
        self.decode_button.setEnabled(False)
        self.stop_decode_button.setEnabled(True)

        self.status_label.setText("Decoding frames...")

        # Decode in background thread
        self.decode_thread = DbcDecodeThread(
            self.frames,
            self.dbc_database,
            self.decode_all_check.isChecked(),
            self.decode_matched_check.isChecked()
        )

        self.decode_thread.decode_complete.connect(self.on_decode_complete)
        self.decode_thread.start()

    def stop_decoding(self):
        """Stop the current decoding process."""
        if self.decode_thread and self.decode_thread.isRunning():
            self.decode_thread.stop()

        self.is_decoding = False
        self.decode_button.setEnabled(True)
        self.stop_decode_button.setEnabled(False)
        self.status_label.setText("Decoding stopped")

    def on_decode_complete(self, decoded_data):
        """Handle decoding completion."""
        self.is_decoding = False
        self.decode_button.setEnabled(True)
        self.stop_decode_button.setEnabled(False)

        self.decoded_signals = decoded_data
        self.display_decoded_signals(decoded_data)

        signal_count = sum(len(signals) for signals in decoded_data.values())
        self.status_label.setText(f"Decoding complete: {signal_count} signals decoded")

    def display_decoded_signals(self, decoded_data):
        """Display the decoded signals."""
        # Flatten the decoded data for table display
        table_data = []

        for can_id, frame_signals in decoded_data.items():
            for signal_name, signal_data in frame_signals.items():
                table_data.append({
                    'can_id': can_id,
                    'message_name': signal_data.get('message_name', 'Unknown'),
                    'signal_name': signal_name,
                    'raw_value': signal_data.get('raw_value', 0),
                    'physical_value': signal_data.get('physical_value', 0),
                    'units': signal_data.get('units', ''),
                    'signal_info': signal_data
                })

        self.signals_table.setRowCount(len(table_data))

        for row, signal in enumerate(table_data):
            # CAN ID
            id_item = QTableWidgetItem(f"0x{signal['can_id']:03X}")
            self.signals_table.setItem(row, 0, id_item)

            # Message name
            msg_item = QTableWidgetItem(signal['message_name'])
            self.signals_table.setItem(row, 1, msg_item)

            # Signal name
            name_item = QTableWidgetItem(signal['signal_name'])
            self.signals_table.setItem(row, 2, name_item)

            # Raw value
            raw_item = QTableWidgetItem(str(signal['raw_value']))
            self.signals_table.setItem(row, 3, raw_item)

            # Physical value
            phys_item = QTableWidgetItem(f"{signal['physical_value']:.6f}")
            self.signals_table.setItem(row, 4, phys_item)

            # Units
            units_item = QTableWidgetItem(signal['units'])
            self.signals_table.setItem(row, 5, units_item)

    def on_signal_selected(self):
        """Handle signal selection."""
        current_row = self.signals_table.currentRow()
        if current_row >= 0:
            # Get signal data from table (this is a simplified approach)
            can_id_text = self.signals_table.item(current_row, 0).text()
            signal_name = self.signals_table.item(current_row, 2).text()

            can_id = int(can_id_text, 16)

            if can_id in self.decoded_signals and signal_name in self.decoded_signals[can_id]:
                signal_data = self.decoded_signals[can_id][signal_name]
                self.show_signal_details(signal_data)

    def show_signal_details(self, signal_data):
        """Show detailed information about the selected signal."""
        details = f"Signal Details: {signal_data.get('name', 'Unknown')}\n\n"

        details += f"Message: {signal_data.get('message_name', 'Unknown')}\n"
        details += f"Raw Value: {signal_data.get('raw_value', 0)}\n"
        details += f"Physical Value: {signal_data.get('physical_value', 0):.6f}"
        if signal_data.get('units'):
            details += f" {signal_data['units']}\n"
        else:
            details += "\n"

        details += "\nSignal Definition:\n"
        details += f"  Start Bit: {signal_data.get('start_bit', 0)}\n"
        details += f"  Length: {signal_data.get('length', 0)} bits\n"
        details += f"  Byte Order: {signal_data.get('byte_order', 'Unknown')}\n"
        details += f"  Value Type: {signal_data.get('value_type', 'Unknown')}\n"

        if 'factor' in signal_data and 'offset' in signal_data:
            details += f"  Factor: {signal_data['factor']}\n"
            details += f"  Offset: {signal_data['offset']}\n"
            details += f"  Physical = Raw × {signal_data['factor']} + {signal_data['offset']}\n"

        if 'min_value' in signal_data and 'max_value' in signal_data:
            details += f"  Valid Range: {signal_data['min_value']} - {signal_data['max_value']}\n"

        self.signal_details_text.setText(details)

        # Also show frame info if available
        frame_info = f"Frame Information\n\n"
        frame_info += f"CAN ID: 0x{signal_data.get('can_id', 0):03X}\n"
        if 'timestamp' in signal_data:
            frame_info += f"Timestamp: {signal_data['timestamp']}\n"
        if 'frame_data' in signal_data:
            frame_data = signal_data['frame_data']
            frame_info += f"Raw Data: {' '.join(f'{b:02X}' for b in frame_data)}\n"

        self.frame_info_text.setText(frame_info)

    def on_dbc_item_selected(self):
        """Handle DBC tree item selection."""
        selected_items = self.dbc_tree.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        item_text = item.text(0)

        # Show details based on item type
        if ":" in item_text and item_text.startswith("0x"):  # Message item
            msg_id = int(item_text.split(":")[0], 16)
            self.show_message_details(msg_id)
        elif item.parent() and ":" in item.parent().text(0):  # Signal item
            msg_id = int(item.parent().text(0).split(":")[0], 16)
            signal_name = item_text
            self.show_dbc_signal_details(msg_id, signal_name)

    def show_message_details(self, msg_id):
        """Show details of a DBC message."""
        if not self.dbc_database or 'messages' not in self.dbc_database:
            return

        messages = self.dbc_database['messages']
        if msg_id not in messages:
            return

        message = messages[msg_id]

        details = f"Message Details: {message.get('name', 'Unknown')}\n\n"
        details += f"CAN ID: 0x{msg_id:03X}\n"
        details += f"DLC: {message.get('dlc', 8)} bytes\n"
        details += f"Signals: {len(message.get('signals', {}))}\n"

        if 'comment' in message:
            details += f"Comment: {message['comment']}\n"

        if 'ecu' in message:
            details += f"Transmitting ECU: {message['ecu']}\n"

        self.signal_details_text.setText(details)

    def show_dbc_signal_details(self, msg_id, signal_name):
        """Show details of a DBC signal."""
        if not self.dbc_database or 'messages' not in self.dbc_database:
            return

        messages = self.dbc_database['messages']
        if msg_id not in messages or 'signals' not in messages[msg_id]:
            return

        signals = messages[msg_id]['signals']
        if signal_name not in signals:
            return

        signal = signals[signal_name]

        details = f"DBC Signal Details: {signal_name}\n\n"
        details += f"Message: 0x{msg_id:03X}\n"
        details += f"Start Bit: {signal.get('start_bit', 0)}\n"
        details += f"Length: {signal.get('length', 0)} bits\n"
        details += f"Byte Order: {signal.get('byte_order', 'Motorola')}\n"
        details += f"Value Type: {signal.get('value_type', 'Unsigned')}\n"

        if 'factor' in signal and 'offset' in signal:
            details += f"Factor: {signal['factor']}\n"
            details += f"Offset: {signal['offset']}\n"

        if 'min_value' in signal and 'max_value' in signal:
            details += f"Valid Range: {signal['min_value']} - {signal['max_value']}\n"

        if 'units' in signal:
            details += f"Units: {signal['units']}\n"

        if 'comment' in signal:
            details += f"Comment: {signal['comment']}\n"

        self.signal_details_text.setText(details)

    def clear_decoded_results(self):
        """Clear all decoded results."""
        self.decoded_signals = {}
        self.signals_table.setRowCount(0)
        self.frame_info_text.clear()
        self.signal_details_text.clear()
        self.status_label.setText("Results cleared")

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []


class DbcLoadThread(QThread):
    """Background thread for loading DBC files."""

    load_complete = pyqtSignal(dict)

    def __init__(self, dbc_path):
        super().__init__()
        self.dbc_path = dbc_path

    def run(self):
        """Load and parse the DBC file."""
        try:
            dbc_data = self.parse_dbc_file(self.dbc_path)
            self.load_complete.emit(dbc_data)
        except Exception as e:
            print(f"Error loading DBC: {e}")
            self.load_complete.emit({})

    def parse_dbc_file(self, filepath):
        """Parse a DBC file into a structured format."""
        dbc_data = {
            'messages': {},
            'ecus': [],
            'version': '',
            'comments': []
        }

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except:
            return {}

        lines = content.split('\n')
        current_message = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith('//'):
                continue

            # Parse version
            if line.startswith('VERSION'):
                match = re.search(r'VERSION\s+"([^"]*)"', line)
                if match:
                    dbc_data['version'] = match.group(1)

            # Parse ECUs
            elif line.startswith('BU_:'):
                ecu_part = line[4:].strip()
                if ecu_part:
                    ecus = [ecu.strip() for ecu in ecu_part.split()]
                    for ecu in ecus:
                        dbc_data['ecus'].append({'name': ecu})

            # Parse messages
            elif line.startswith('BO_'):
                # Format: BO_ <id> <name>:<dlc> <ecu>
                match = re.match(r'BO_\s+(\d+)\s+(\w+):(\d+)\s+(\w+)', line)
                if match:
                    msg_id = int(match.group(1))
                    msg_name = match.group(2)
                    dlc = int(match.group(3))
                    ecu = match.group(4)

                    current_message = {
                        'id': msg_id,
                        'name': msg_name,
                        'dlc': dlc,
                        'ecu': ecu,
                        'signals': {}
                    }
                    dbc_data['messages'][msg_id] = current_message

            # Parse signals
            elif line.startswith('SG_') and current_message:
                # Format: SG_ <name> : <start>|<length>@<order><type> (<factor>,<offset>) [<min|<max>] "<units>" <receivers>
                match = re.match(r'SG_\s+(\w+)\s*:\s*(\d+)\|(\d+)@(\d)([+-])\s*\(([^,]+),([^\)]+)\)\s*\[([^\|]+)\|([^\]]+)\]\s*"([^"]*)"(.+)', line)
                if match:
                    sig_name = match.group(1)
                    start_bit = int(match.group(2))
                    length = int(match.group(3))
                    byte_order = 'Intel' if match.group(4) == '1' else 'Motorola'
                    value_type = 'Signed' if match.group(5) == '-' else 'Unsigned'
                    factor = float(match.group(6))
                    offset = float(match.group(7))
                    min_val = float(match.group(8))
                    max_val = float(match.group(9))
                    units = match.group(10).strip()

                    signal = {
                        'name': sig_name,
                        'start_bit': start_bit,
                        'length': length,
                        'byte_order': byte_order,
                        'value_type': value_type,
                        'factor': factor,
                        'offset': offset,
                        'min_value': min_val,
                        'max_value': max_val,
                        'units': units
                    }

                    current_message['signals'][sig_name] = signal

        return dbc_data


class DbcDecodeThread(QThread):
    """Background thread for DBC decoding."""

    decode_complete = pyqtSignal(dict)

    def __init__(self, frames, dbc_database, decode_all, decode_matched):
        super().__init__()
        self.frames = frames
        self.dbc_database = dbc_database
        self.decode_all = decode_all
        self.decode_matched = decode_matched
        self.stop_requested = False

    def stop(self):
        """Request thread stop."""
        self.stop_requested = True

    def run(self):
        """Decode frames using DBC database."""
        decoded_data = {}

        messages = self.dbc_database.get('messages', {})

        for frame in self.frames:
            if self.stop_requested:
                break

            can_id = frame.id

            # Check if we should decode this message
            if self.decode_matched and can_id not in messages:
                continue

            if can_id in messages:
                message = messages[can_id]
                frame_signals = self.decode_frame_signals(frame, message)

                if frame_signals:
                    decoded_data[can_id] = frame_signals

        self.decode_complete.emit(decoded_data)

    def decode_frame_signals(self, frame, message):
        """Decode all signals in a frame."""
        signals = message.get('signals', {})
        decoded_signals = {}

        for signal_name, signal_def in signals.items():
            try:
                decoded_value = self.decode_signal(frame.data, signal_def)
                if decoded_value is not None:
                    decoded_signals[signal_name] = {
                        'name': signal_name,
                        'message_name': message.get('name', 'Unknown'),
                        'can_id': frame.id,
                        'raw_value': decoded_value['raw'],
                        'physical_value': decoded_value['physical'],
                        'units': signal_def.get('units', ''),
                        'start_bit': signal_def.get('start_bit', 0),
                        'length': signal_def.get('length', 0),
                        'byte_order': signal_def.get('byte_order', 'Motorola'),
                        'value_type': signal_def.get('value_type', 'Unsigned'),
                        'factor': signal_def.get('factor', 1.0),
                        'offset': signal_def.get('offset', 0.0),
                        'timestamp': getattr(frame, 'timestamp', 0),
                        'frame_data': frame.data
                    }
            except:
                continue  # Skip signals that can't be decoded

        return decoded_signals

    def decode_signal(self, data, signal_def):
        """Decode a single signal from frame data."""
        if not data:
            return None

        start_bit = signal_def.get('start_bit', 0)
        length = signal_def.get('length', 0)
        byte_order = signal_def.get('byte_order', 'Motorola')
        value_type = signal_def.get('value_type', 'Unsigned')
        factor = signal_def.get('factor', 1.0)
        offset = signal_def.get('offset', 0.0)

        # Extract bits
        if len(data) * 8 < start_bit + length:
            return None

        # Convert data to bit array
        bits = []
        for byte in data:
            for bit in range(8):
                bits.append((byte >> bit) & 1)

        # Extract signal bits
        signal_bits = bits[start_bit:start_bit + length]

        if len(signal_bits) != length:
            return None

        # Convert to raw value
        raw_value = 0
        if byte_order == 'Motorola':  # Big-endian
            for bit in signal_bits:
                raw_value = (raw_value << 1) | bit
        else:  # Intel (little-endian)
            for bit in reversed(signal_bits):
                raw_value = (raw_value << 1) | bit

        # Apply sign extension for signed values
        if value_type == 'Signed' and length > 0:
            if raw_value & (1 << (length - 1)):
                raw_value -= (1 << length)

        # Apply factor and offset
        physical_value = raw_value * factor + offset

        return {
            'raw': raw_value,
            'physical': physical_value
        }