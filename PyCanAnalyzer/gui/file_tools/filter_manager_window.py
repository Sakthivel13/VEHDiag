"""Filter Manager Window - Create and Manage Advanced Filters."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QLineEdit,
                             QListWidget, QListWidgetItem, QMessageBox, QGroupBox,
                             QCheckBox, QSpinBox, QFormLayout, QSplitter,
                             QTextEdit, QTableWidget, QTableWidgetItem,
                             QHeaderView, QInputDialog)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon


class FilterManagerWindow(QMainWindow):
    """Window for creating and managing advanced CAN frame filters."""

    # Signals
    filter_created = pyqtSignal(dict)  # Emitted when a new filter is created
    filter_applied = pyqtSignal(dict)  # Emitted when a filter is applied

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filters = {}  # Dictionary of filter_name -> filter_config
        self.current_filter = None

        self.init_ui()
        self.load_saved_filters()

    def init_ui(self):
        """Initialize the filter manager UI."""
        self.setWindowTitle("Filter Manager")
        self.setGeometry(200, 200, 800, 600)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        central_widget.setLayout(QVBoxLayout())
        central_widget.layout().addWidget(splitter)

        # Left panel - Filter list
        self.create_filter_list_panel(splitter)

        # Right panel - Filter editor
        self.create_filter_editor_panel(splitter)

        splitter.setSizes([200, 600])

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.apply_button = QPushButton("Apply Filter")
        self.apply_button.clicked.connect(self.apply_current_filter)

        self.save_button = QPushButton("Save Filter")
        self.save_button.clicked.connect(self.save_current_filter)

        self.delete_button = QPushButton("Delete Filter")
        self.delete_button.clicked.connect(self.delete_current_filter)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)

        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)

        central_widget.layout().addLayout(button_layout)

    def create_filter_list_panel(self, parent):
        """Create the filter list panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Filter list group
        list_group = QGroupBox("Saved Filters")
        list_layout = QVBoxLayout()

        self.filter_list = QListWidget()
        self.filter_list.itemClicked.connect(self.on_filter_selected)
        self.filter_list.itemDoubleClicked.connect(self.apply_current_filter)

        list_layout.addWidget(self.filter_list)

        # List buttons
        list_button_layout = QHBoxLayout()

        new_button = QPushButton("New")
        new_button.clicked.connect(self.create_new_filter)

        import_button = QPushButton("Import")
        import_button.clicked.connect(self.import_filters)

        export_button = QPushButton("Export")
        export_button.clicked.connect(self.export_filters)

        list_button_layout.addWidget(new_button)
        list_button_layout.addWidget(import_button)
        list_button_layout.addWidget(export_button)

        list_layout.addLayout(list_button_layout)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        parent.addWidget(panel)

    def create_filter_editor_panel(self, parent):
        """Create the filter editor panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Filter name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Filter Name:"))
        self.filter_name_edit = QLineEdit()
        self.filter_name_edit.setPlaceholderText("Enter filter name...")
        name_layout.addWidget(self.filter_name_edit)
        layout.addLayout(name_layout)

        # Filter type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Filter Type:"))
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems([
            "ID Filter",
            "Data Filter",
            "Time Filter",
            "Bus Filter",
            "Complex Filter"
        ])
        self.filter_type_combo.currentTextChanged.connect(self.on_filter_type_changed)
        type_layout.addWidget(self.filter_type_combo)
        layout.addLayout(type_layout)

        # Filter configuration area
        self.filter_config_widget = QWidget()
        self.create_id_filter_config()
        layout.addWidget(self.filter_config_widget)

        # Filter preview
        preview_group = QGroupBox("Filter Preview")
        preview_layout = QVBoxLayout()

        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(100)
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlainText("Select or create a filter to see preview")

        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        parent.addWidget(panel)

    def create_id_filter_config(self):
        """Create configuration widget for ID filters."""
        # Clear existing config
        if hasattr(self, 'current_config_layout'):
            # Remove existing widgets
            while self.filter_config_widget.layout().count():
                child = self.filter_config_widget.layout().takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        layout = QVBoxLayout()
        self.filter_config_widget.setLayout(layout)

        # ID matching mode
        mode_group = QGroupBox("ID Matching")
        mode_layout = QVBoxLayout()

        self.id_mode_combo = QComboBox()
        self.id_mode_combo.addItems([
            "Single ID",
            "ID Range",
            "ID List",
            "ID Mask"
        ])
        self.id_mode_combo.currentTextChanged.connect(self.on_id_mode_changed)
        mode_layout.addWidget(self.id_mode_combo)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # ID input area
        self.id_input_widget = QWidget()
        self.create_single_id_input()
        layout.addWidget(self.id_input_widget)

        # Extended ID option
        ext_layout = QHBoxLayout()
        self.extended_check = QCheckBox("Extended ID (29-bit)")
        ext_layout.addWidget(self.extended_check)
        ext_layout.addStretch()
        layout.addLayout(ext_layout)

        self.current_config_layout = layout

    def create_single_id_input(self):
        """Create input widget for single ID."""
        layout = QVBoxLayout()
        self.id_input_widget.setLayout(layout)

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("CAN ID:"))

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("e.g., 0x123, 123, 1A5")
        input_layout.addWidget(self.id_edit)

        self.id_format_combo = QComboBox()
        self.id_format_combo.addItems(["Hex", "Decimal"])
        input_layout.addWidget(self.id_format_combo)

        layout.addLayout(input_layout)

    def create_data_filter_config(self):
        """Create configuration widget for data filters."""
        # Clear existing config
        if hasattr(self, 'current_config_layout'):
            while self.filter_config_widget.layout().count():
                child = self.filter_config_widget.layout().takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        layout = QVBoxLayout()
        self.filter_config_widget.setLayout(layout)

        # Data matching mode
        mode_group = QGroupBox("Data Matching")
        mode_layout = QVBoxLayout()

        self.data_mode_combo = QComboBox()
        self.data_mode_combo.addItems([
            "Exact Match",
            "Contains Bytes",
            "Byte Pattern",
            "Bit Mask"
        ])
        mode_layout.addWidget(self.data_mode_combo)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Data input
        data_group = QGroupBox("Data Pattern")
        data_layout = QVBoxLayout()

        self.data_edit = QLineEdit()
        self.data_edit.setPlaceholderText("e.g., FF 00 12 34, 01 02 03")
        data_layout.addWidget(self.data_edit)

        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

        self.current_config_layout = layout

    def create_time_filter_config(self):
        """Create configuration widget for time filters."""
        # Clear existing config
        if hasattr(self, 'current_config_layout'):
            while self.filter_config_widget.layout().count():
                child = self.filter_config_widget.layout().takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        layout = QVBoxLayout()
        self.filter_config_widget.setLayout(layout)

        # Time range
        time_group = QGroupBox("Time Range")
        time_layout = QFormLayout()

        self.start_time_edit = QLineEdit()
        self.start_time_edit.setPlaceholderText("Start timestamp (seconds)")
        time_layout.addRow("Start Time:", self.start_time_edit)

        self.end_time_edit = QLineEdit()
        self.end_time_edit.setPlaceholderText("End timestamp (seconds)")
        time_layout.addRow("End Time:", self.end_time_edit)

        time_group.setLayout(time_layout)
        layout.addWidget(time_group)

        self.current_config_layout = layout

    def on_filter_type_changed(self, filter_type):
        """Handle filter type change."""
        if filter_type == "ID Filter":
            self.create_id_filter_config()
        elif filter_type == "Data Filter":
            self.create_data_filter_config()
        elif filter_type == "Time Filter":
            self.create_time_filter_config()
        # Add other filter types as needed

        self.update_preview()

    def on_id_mode_changed(self, mode):
        """Handle ID mode change."""
        # Update input widget based on mode
        self.update_preview()

    def on_filter_selected(self, item):
        """Handle filter selection from list."""
        filter_name = item.text()
        if filter_name in self.filters:
            filter_config = self.filters[filter_name]
            self.load_filter_config(filter_config)

    def load_filter_config(self, config):
        """Load a filter configuration into the editor."""
        self.filter_name_edit.setText(config.get('name', ''))
        self.filter_type_combo.setCurrentText(config.get('type', 'ID Filter'))

        # Load type-specific settings
        if config['type'] == 'ID Filter':
            self.id_mode_combo.setCurrentText(config.get('id_mode', 'Single ID'))
            self.id_edit.setText(config.get('id_value', ''))
            self.id_format_combo.setCurrentText(config.get('id_format', 'Hex'))
            self.extended_check.setChecked(config.get('extended', False))

        self.current_filter = config
        self.update_preview()

    def create_new_filter(self):
        """Create a new empty filter."""
        self.filter_name_edit.clear()
        self.filter_type_combo.setCurrentIndex(0)
        self.current_filter = None
        self.update_preview()

    def save_current_filter(self):
        """Save the current filter configuration."""
        filter_name = self.filter_name_edit.text().strip()
        if not filter_name:
            QMessageBox.warning(self, "No Name",
                               "Please enter a name for the filter.")
            return

        # Create filter config
        config = {
            'name': filter_name,
            'type': self.filter_type_combo.currentText()
        }

        # Add type-specific settings
        if config['type'] == 'ID Filter':
            config.update({
                'id_mode': self.id_mode_combo.currentText(),
                'id_value': self.id_edit.text(),
                'id_format': self.id_format_combo.currentText(),
                'extended': self.extended_check.isChecked()
            })

        # Save to filters dict
        self.filters[filter_name] = config

        # Update list
        self.update_filter_list()

        QMessageBox.information(self, "Filter Saved",
                               f"Filter '{filter_name}' has been saved.")

    def delete_current_filter(self):
        """Delete the currently selected filter."""
        current_item = self.filter_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection",
                               "Please select a filter to delete.")
            return

        filter_name = current_item.text()
        reply = QMessageBox.question(
            self, "Delete Filter",
            f"Are you sure you want to delete the filter '{filter_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if filter_name in self.filters:
                del self.filters[filter_name]
                self.update_filter_list()
                self.create_new_filter()

    def apply_current_filter(self):
        """Apply the current filter."""
        if not self.current_filter:
            QMessageBox.warning(self, "No Filter",
                               "Please create or select a filter to apply.")
            return

        # Create filter function
        filter_func = self.create_filter_function(self.current_filter)
        if filter_func:
            self.filter_applied.emit({
                'config': self.current_filter,
                'function': filter_func
            })

    def create_filter_function(self, config):
        """Create a filter function from configuration."""
        filter_type = config.get('type')

        if filter_type == 'ID Filter':
            return self.create_id_filter_function(config)
        # Add other filter types

        return None

    def create_id_filter_function(self, config):
        """Create ID filter function."""
        id_value = config.get('id_value', '').strip()
        id_format = config.get('id_format', 'Hex')
        extended = config.get('extended', False)
        id_mode = config.get('id_mode', 'Single ID')

        if not id_value:
            return None

        try:
            if id_mode == 'Single ID':
                # Parse single ID
                if id_format == 'Hex':
                    target_id = int(id_value, 16)
                else:
                    target_id = int(id_value, 10)

                def filter_func(frame):
                    frame_id = frame.id
                    frame_extended = getattr(frame, 'extended', False)
                    return frame_id == target_id and frame_extended == extended

                return filter_func

            # Add support for other ID modes (range, list, mask)

        except (ValueError, AttributeError):
            return None

        return None

    def update_filter_list(self):
        """Update the filter list widget."""
        self.filter_list.clear()
        for filter_name in sorted(self.filters.keys()):
            item = QListWidgetItem(filter_name)
            self.filter_list.addItem(item)

    def update_preview(self):
        """Update the filter preview text."""
        if self.current_filter:
            preview = f"Filter: {self.current_filter.get('name', 'Unnamed')}\n"
            preview += f"Type: {self.current_filter.get('type', 'Unknown')}\n"

            if self.current_filter.get('type') == 'ID Filter':
                preview += f"ID: {self.current_filter.get('id_value', 'None')}\n"
                preview += f"Format: {self.current_filter.get('id_format', 'Hex')}\n"
                preview += f"Extended: {self.current_filter.get('extended', 'False')}"

            self.preview_text.setPlainText(preview)
        else:
            self.preview_text.setPlainText("Create a new filter or select an existing one")

    def load_saved_filters(self):
        """Load saved filters from storage."""
        # This would typically load from a config file
        # For now, create some example filters
        self.filters = {
            'Engine RPM': {
                'name': 'Engine RPM',
                'type': 'ID Filter',
                'id_mode': 'Single ID',
                'id_value': '0x0C9',
                'id_format': 'Hex',
                'extended': False
            },
            'Vehicle Speed': {
                'name': 'Vehicle Speed',
                'type': 'ID Filter',
                'id_mode': 'Single ID',
                'id_value': '0x0D1',
                'id_format': 'Hex',
                'extended': False
            }
        }
        self.update_filter_list()

    def import_filters(self):
        """Import filters from file."""
        QMessageBox.information(self, "Import",
                               "Filter import not yet implemented.")

    def export_filters(self):
        """Export filters to file."""
        QMessageBox.information(self, "Export",
                               "Filter export not yet implemented.")