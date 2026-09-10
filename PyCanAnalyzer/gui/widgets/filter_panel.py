"""Filter Panel Widget - CAN Frame Filtering Controls."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QComboBox, QPushButton, QGroupBox,
                             QCheckBox, QSpinBox, QFormLayout, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIntValidator, QRegExpValidator
from PyQt5.QtCore import QRegExp


class FilterPanel(QWidget):
    """Panel for filtering CAN frames in the main table."""

    # Signals
    filter_changed = pyqtSignal(object)  # Emits filter function
    filter_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_filter = None
        self.init_ui()

    def init_ui(self):
        """Initialize the filter panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # ID Filter Group
        id_group = QGroupBox("ID Filter")
        id_layout = QFormLayout()

        self.id_filter_edit = QLineEdit()
        self.id_filter_edit.setPlaceholderText("e.g., 0x120, 120, 0x1FF-0x2FF")
        self.id_filter_edit.setValidator(QRegExpValidator(QRegExp(r'[0-9A-Fa-fxX\s\-\,]*')))
        self.id_filter_edit.textChanged.connect(self.on_filter_changed)
        id_layout.addRow("CAN ID:", self.id_filter_edit)

        self.id_format_combo = QComboBox()
        self.id_format_combo.addItems(["Hex", "Decimal"])
        self.id_format_combo.currentTextChanged.connect(self.on_filter_changed)
        id_layout.addRow("Format:", self.id_format_combo)

        id_group.setLayout(id_layout)
        layout.addWidget(id_group)

        # Bus Filter Group
        bus_group = QGroupBox("Bus Filter")
        bus_layout = QFormLayout()

        self.bus_filter_combo = QComboBox()
        self.bus_filter_combo.addItem("All Buses", -1)
        self.bus_filter_combo.addItem("Bus 0", 0)
        self.bus_filter_combo.addItem("Bus 1", 1)
        self.bus_filter_combo.addItem("Bus 2", 2)
        self.bus_filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        bus_layout.addRow("Bus:", self.bus_filter_combo)

        bus_group.setLayout(bus_layout)
        layout.addWidget(bus_group)

        # Data Filter Group
        data_group = QGroupBox("Data Filter")
        data_layout = QFormLayout()

        self.data_filter_edit = QLineEdit()
        self.data_filter_edit.setPlaceholderText("e.g., FF 00, 01 02 03")
        self.data_filter_edit.setValidator(QRegExpValidator(QRegExp(r'[0-9A-Fa-f\s]*')))
        self.data_filter_edit.textChanged.connect(self.on_filter_changed)
        data_layout.addRow("Data bytes:", self.data_filter_edit)

        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

        # Direction Filter Group
        dir_group = QGroupBox("Direction Filter")
        dir_layout = QVBoxLayout()

        self.dir_rx_check = QCheckBox("RX (Received)")
        self.dir_tx_check = QCheckBox("TX (Transmitted)")
        self.dir_rx_check.setChecked(True)
        self.dir_tx_check.setChecked(True)
        self.dir_rx_check.stateChanged.connect(self.on_filter_changed)
        self.dir_tx_check.stateChanged.connect(self.on_filter_changed)

        dir_layout.addWidget(self.dir_rx_check)
        dir_layout.addWidget(self.dir_tx_check)
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)

        # Frame Type Filter Group
        type_group = QGroupBox("Frame Type")
        type_layout = QVBoxLayout()

        self.type_data_check = QCheckBox("Data Frames")
        self.type_rtr_check = QCheckBox("RTR Frames")
        self.type_ext_check = QCheckBox("Extended ID")
        self.type_std_check = QCheckBox("Standard ID")

        self.type_data_check.setChecked(True)
        self.type_rtr_check.setChecked(True)
        self.type_ext_check.setChecked(True)
        self.type_std_check.setChecked(True)

        self.type_data_check.stateChanged.connect(self.on_filter_changed)
        self.type_rtr_check.stateChanged.connect(self.on_filter_changed)
        self.type_ext_check.stateChanged.connect(self.on_filter_changed)
        self.type_std_check.stateChanged.connect(self.on_filter_changed)

        type_layout.addWidget(self.type_data_check)
        type_layout.addWidget(self.type_rtr_check)
        type_layout.addWidget(self.type_ext_check)
        type_layout.addWidget(self.type_std_check)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # Control Buttons
        button_layout = QHBoxLayout()

        self.apply_button = QPushButton("Apply Filter")
        self.apply_button.clicked.connect(self.apply_filter)

        self.clear_button = QPushButton("Clear Filter")
        self.clear_button.clicked.connect(self.clear_filter)

        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.clear_button)
        layout.addLayout(button_layout)

        # Set size policy
        self.setMaximumWidth(300)
        self.setMinimumWidth(250)

    def on_filter_changed(self):
        """Handle filter parameter changes."""
        # Auto-apply filter if any input changes
        self.apply_filter()

    def apply_filter(self):
        """Apply the current filter settings."""
        filter_func = self.build_filter_function()

        if filter_func:
            self.current_filter = filter_func
            self.filter_changed.emit(filter_func)
        else:
            self.clear_filter()

    def clear_filter(self):
        """Clear all filters."""
        self.current_filter = None
        self.filter_cleared.emit()

        # Reset UI elements
        self.id_filter_edit.clear()
        self.data_filter_edit.clear()
        self.bus_filter_combo.setCurrentIndex(0)
        self.dir_rx_check.setChecked(True)
        self.dir_tx_check.setChecked(True)
        self.type_data_check.setChecked(True)
        self.type_rtr_check.setChecked(True)
        self.type_ext_check.setChecked(True)
        self.type_std_check.setChecked(True)

    def build_filter_function(self):
        """Build a filter function based on current settings.

        Returns:
            Function that takes a frame and returns True if it should be displayed
        """
        filters = []

        # ID filter
        id_text = self.id_filter_edit.text().strip()
        if id_text:
            id_filter = self._parse_id_filter(id_text)
            if id_filter:
                filters.append(id_filter)

        # Bus filter
        bus_index = self.bus_filter_combo.currentIndex()
        if bus_index > 0:  # Not "All Buses"
            bus_num = self.bus_filter_combo.itemData(bus_index)
            filters.append(lambda f, bus=bus_num: getattr(f, 'bus', 0) == bus)

        # Data filter
        data_text = self.data_filter_edit.text().strip()
        if data_text:
            data_filter = self._parse_data_filter(data_text)
            if data_filter:
                filters.append(data_filter)

        # Direction filter
        show_rx = self.dir_rx_check.isChecked()
        show_tx = self.dir_tx_check.isChecked()
        if not (show_rx and show_tx):
            if show_rx and not show_tx:
                filters.append(lambda f: getattr(f, 'direction', 'RX') == 'RX')
            elif show_tx and not show_rx:
                filters.append(lambda f: getattr(f, 'direction', 'RX') == 'TX')

        # Frame type filters
        show_data = self.type_data_check.isChecked()
        show_rtr = self.type_rtr_check.isChecked()
        show_ext = self.type_ext_check.isChecked()
        show_std = self.type_std_check.isChecked()

        if not (show_data and show_rtr):
            if show_data and not show_rtr:
                filters.append(lambda f: not getattr(f, 'rtr', False))
            elif show_rtr and not show_data:
                filters.append(lambda f: getattr(f, 'rtr', False))

        if not (show_ext and show_std):
            if show_std and not show_ext:
                filters.append(lambda f: not getattr(f, 'extended', False))
            elif show_ext and not show_std:
                filters.append(lambda f: getattr(f, 'extended', False))

        # Combine all filters
        if not filters:
            return None

        def combined_filter(frame):
            return all(f(frame) for f in filters)

        return combined_filter

    def _parse_id_filter(self, id_text):
        """Parse ID filter text into a filter function.

        Args:
            id_text: String like "0x120", "120", "0x1FF-0x2FF"

        Returns:
            Filter function or None if invalid
        """
        try:
            # Handle ranges like "0x1FF-0x2FF"
            if '-' in id_text:
                start_str, end_str = id_text.split('-', 1)
                start_id = self._parse_single_id(start_str.strip())
                end_id = self._parse_single_id(end_str.strip())
                if start_id is not None and end_id is not None:
                    return lambda f, start=start_id, end=end_id: start <= f.id <= end

            # Handle comma-separated list
            elif ',' in id_text:
                ids = []
                for id_str in id_text.split(','):
                    id_val = self._parse_single_id(id_str.strip())
                    if id_val is not None:
                        ids.append(id_val)
                if ids:
                    return lambda f, ids=ids: f.id in ids

            # Handle single ID
            else:
                target_id = self._parse_single_id(id_text)
                if target_id is not None:
                    return lambda f, target=target_id: f.id == target

        except (ValueError, AttributeError):
            pass

        return None

    def _parse_single_id(self, id_str):
        """Parse a single CAN ID string.

        Args:
            id_str: String like "0x120" or "120"

        Returns:
            Integer ID or None if invalid
        """
        try:
            if id_str.startswith('0x') or id_str.startswith('0X'):
                return int(id_str, 16)
            else:
                # Check if it's hex format without 0x
                if all(c in '0123456789ABCDEFabcdef' for c in id_str):
                    return int(id_str, 16)
                else:
                    return int(id_str, 10)
        except (ValueError, AttributeError):
            return None

    def _parse_data_filter(self, data_text):
        """Parse data filter text into a filter function.

        Args:
            data_text: String like "FF 00" or "01 02 03"

        Returns:
            Filter function or None if invalid
        """
        try:
            # Parse hex bytes
            expected_bytes = []
            for byte_str in data_text.split():
                if byte_str:
                    expected_bytes.append(int(byte_str, 16))

            if not expected_bytes:
                return None

            def data_filter(frame):
                if not hasattr(frame, 'data') or not frame.data:
                    return False

                # Check if frame data starts with expected bytes
                frame_bytes = list(frame.data)
                if len(frame_bytes) < len(expected_bytes):
                    return False

                return frame_bytes[:len(expected_bytes)] == expected_bytes

            return data_filter

        except (ValueError, AttributeError):
            return None

    def get_filter_description(self):
        """Get a human-readable description of the current filter.

        Returns:
            String description of active filters
        """
        if not self.current_filter:
            return "No filter active"

        descriptions = []

        id_text = self.id_filter_edit.text().strip()
        if id_text:
            descriptions.append(f"ID: {id_text}")

        bus_index = self.bus_filter_combo.currentIndex()
        if bus_index > 0:
            bus_text = self.bus_filter_combo.currentText()
            descriptions.append(f"Bus: {bus_text}")

        data_text = self.data_filter_edit.text().strip()
        if data_text:
            descriptions.append(f"Data: {data_text}")

        if not (self.dir_rx_check.isChecked() and self.dir_tx_check.isChecked()):
            if self.dir_rx_check.isChecked():
                descriptions.append("RX only")
            if self.dir_tx_check.isChecked():
                descriptions.append("TX only")

        return ", ".join(descriptions) if descriptions else "Custom filter active"