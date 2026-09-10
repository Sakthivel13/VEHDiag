"""DBC Manager Window - Manage DBC Database Files."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
                             QListWidget, QListWidgetItem, QMessageBox, QGroupBox,
                             QSplitter, QTextEdit, QTableWidget, QTableWidgetItem,
                             QHeaderView, QFileDialog, QInputDialog, QMenu,
                             QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from dbc.dbc import DBCManager
import os


class DBCManagerWindow(QMainWindow):
    """Window for managing DBC (CAN Database) files and signals."""

    # Signals
    dbc_loaded = pyqtSignal(str)  # Emitted when DBC is loaded
    dbc_unloaded = pyqtSignal(str)  # Emitted when DBC is unloaded
    signal_selected = pyqtSignal(dict)  # Emitted when signal is selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dbc_manager = DBCManager()
        self.current_dbc = None

        self.init_ui()
        self.refresh_dbc_list()

    def init_ui(self):
        """Initialize the DBC manager UI."""
        self.setWindowTitle("DBC Manager")
        self.setGeometry(200, 200, 1000, 700)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main splitter
        main_splitter = QSplitter(Qt.Horizontal)
        central_widget.setLayout(QVBoxLayout())
        central_widget.layout().addWidget(main_splitter)

        # Left panel - DBC list
        self.create_dbc_list_panel(main_splitter)

        # Right panel - Content viewer
        self.create_content_viewer_panel(main_splitter)

        main_splitter.setSizes([300, 700])

        # Bottom status
        self.status_label = QLabel("Ready")
        central_widget.layout().addWidget(self.status_label)

    def create_dbc_list_panel(self, parent):
        """Create the DBC list panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # DBC Files group
        dbc_group = QGroupBox("DBC Files")
        dbc_layout = QVBoxLayout()

        self.dbc_list = QListWidget()
        self.dbc_list.itemClicked.connect(self.on_dbc_selected)
        self.dbc_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.dbc_list.customContextMenuRequested.connect(self.show_dbc_context_menu)

        dbc_layout.addWidget(self.dbc_list)

        # DBC buttons
        dbc_button_layout = QHBoxLayout()

        load_button = QPushButton("Load DBC")
        load_button.clicked.connect(self.load_dbc_file)

        unload_button = QPushButton("Unload")
        unload_button.clicked.connect(self.unload_dbc)

        dbc_button_layout.addWidget(load_button)
        dbc_button_layout.addWidget(unload_button)

        dbc_layout.addLayout(dbc_button_layout)
        dbc_group.setLayout(dbc_layout)
        layout.addWidget(dbc_group)

        parent.addWidget(panel)

    def create_content_viewer_panel(self, parent):
        """Create the content viewer panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Content splitter
        content_splitter = QSplitter(Qt.Vertical)

        # Top - Messages/Signals tree
        self.create_messages_tree(content_splitter)

        # Bottom - Signal details
        self.create_signal_details(content_splitter)

        content_splitter.setSizes([400, 300])
        layout.addWidget(content_splitter)

        parent.addWidget(panel)

    def create_messages_tree(self, parent):
        """Create the messages and signals tree view."""
        tree_group = QGroupBox("Messages & Signals")
        tree_layout = QVBoxLayout()

        self.messages_tree = QTreeWidget()
        self.messages_tree.setHeaderLabels(["Name", "ID", "DLC", "Signals"])
        self.messages_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.messages_tree.itemClicked.connect(self.on_tree_item_clicked)

        tree_layout.addWidget(self.messages_tree)
        tree_group.setLayout(tree_layout)

        parent.addWidget(tree_group)

    def create_signal_details(self, parent):
        """Create the signal details panel."""
        details_group = QGroupBox("Signal Details")
        details_layout = QVBoxLayout()

        # Signal info table
        self.signal_table = QTableWidget()
        self.signal_table.setColumnCount(4)
        self.signal_table.setHorizontalHeaderLabels(["Property", "Value", "", ""])
        self.signal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.signal_table.setMaximumHeight(200)

        details_layout.addWidget(self.signal_table)

        # Signal description
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("Description:"))
        self.signal_desc_edit = QTextEdit()
        self.signal_desc_edit.setMaximumHeight(60)
        self.signal_desc_edit.setReadOnly(True)
        desc_layout.addWidget(self.signal_desc_edit)

        details_layout.addLayout(desc_layout)

        details_group.setLayout(details_layout)
        parent.addWidget(details_group)

    def load_dbc_file(self):
        """Load a DBC file."""
        file_dialog = QFileDialog()
        file_dialog.setNameFilter("DBC Files (*.dbc);;All Files (*.*)")

        if file_dialog.exec_():
            dbc_file = file_dialog.selectedFiles()[0]

            try:
                self.status_label.setText(f"Loading DBC: {os.path.basename(dbc_file)}...")

                # Load DBC using DBCManager
                success = self.dbc_manager.load_dbc(dbc_file)

                if success:
                    self.status_label.setText(f"Loaded DBC: {os.path.basename(dbc_file)}")
                    self.refresh_dbc_list()
                    self.dbc_loaded.emit(dbc_file)

                    QMessageBox.information(
                        self, "DBC Loaded",
                        f"Successfully loaded DBC file: {os.path.basename(dbc_file)}"
                    )
                else:
                    self.status_label.setText("Failed to load DBC")
                    QMessageBox.critical(self, "Load Error",
                                        "Failed to load DBC file. Check file format.")

            except Exception as e:
                self.status_label.setText("Error loading DBC")
                QMessageBox.critical(self, "Load Error", f"Error loading DBC: {str(e)}")

    def unload_dbc(self):
        """Unload the currently selected DBC."""
        current_item = self.dbc_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection",
                               "Please select a DBC file to unload.")
            return

        dbc_name = current_item.text()
        reply = QMessageBox.question(
            self, "Unload DBC",
            f"Are you sure you want to unload '{dbc_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Unload DBC
                success = self.dbc_manager.unload_dbc(dbc_name)

                if success:
                    self.status_label.setText(f"Unloaded DBC: {dbc_name}")
                    self.refresh_dbc_list()
                    self.dbc_unloaded.emit(dbc_name)
                    self.clear_content_view()
                else:
                    QMessageBox.warning(self, "Unload Error",
                                       f"Failed to unload DBC: {dbc_name}")

            except Exception as e:
                QMessageBox.critical(self, "Unload Error", f"Error unloading DBC: {str(e)}")

    def refresh_dbc_list(self):
        """Refresh the DBC files list."""
        self.dbc_list.clear()

        # Get loaded DBCs from manager
        loaded_dbcs = self.dbc_manager.get_loaded_dbcs()

        for dbc_name in loaded_dbcs:
            item = QListWidgetItem(dbc_name)
            self.dbc_list.addItem(item)

    def on_dbc_selected(self, item):
        """Handle DBC selection."""
        dbc_name = item.text()
        self.current_dbc = dbc_name
        self.populate_messages_tree(dbc_name)

    def populate_messages_tree(self, dbc_name):
        """Populate the messages tree for the selected DBC."""
        self.messages_tree.clear()

        try:
            messages = self.dbc_manager.get_messages(dbc_name)

            for msg_id, message in messages.items():
                # Create message item
                msg_item = QTreeWidgetItem([
                    message.name,
                    f"0x{msg_id:03X}",
                    str(message.length),
                    str(len(message.signals))
                ])

                # Add signal children
                for signal in message.signals:
                    signal_item = QTreeWidgetItem([
                        signal.name,
                        "",
                        "",
                        ""
                    ])
                    signal_item.setData(0, Qt.UserRole, {
                        'type': 'signal',
                        'message': message,
                        'signal': signal
                    })
                    msg_item.addChild(signal_item)

                msg_item.setData(0, Qt.UserRole, {
                    'type': 'message',
                    'message': message
                })

                self.messages_tree.addTopLevelItem(msg_item)

            self.messages_tree.expandAll()

        except Exception as e:
            QMessageBox.warning(self, "Error",
                               f"Error loading messages: {str(e)}")

    def on_tree_item_clicked(self, item, column):
        """Handle tree item click."""
        data = item.data(0, Qt.UserRole)

        if data and data.get('type') == 'signal':
            self.show_signal_details(data['signal'], data['message'])
        elif data and data.get('type') == 'message':
            self.show_message_details(data['message'])

    def show_signal_details(self, signal, message):
        """Show detailed information for a signal."""
        self.signal_table.setRowCount(0)

        # Signal properties
        properties = [
            ("Name", signal.name),
            ("Start Bit", str(signal.start)),
            ("Length", str(signal.length)),
            ("Byte Order", "Intel" if signal.byte_order == 'little_endian' else "Motorola"),
            ("Scale", str(signal.scale)),
            ("Offset", str(signal.offset)),
            ("Min", str(signal.minimum) if signal.minimum is not None else "N/A"),
            ("Max", str(signal.maximum) if signal.maximum is not None else "N/A"),
            ("Unit", signal.unit or "N/A"),
            ("Comment", signal.comment or "N/A")
        ]

        for prop, value in properties:
            row = self.signal_table.rowCount()
            self.signal_table.insertRow(row)
            self.signal_table.setItem(row, 0, QTableWidgetItem(prop))
            self.signal_table.setItem(row, 1, QTableWidgetItem(str(value)))

        # Description
        description = signal.comment or "No description available"
        self.signal_desc_edit.setPlainText(description)

        # Emit signal selected
        signal_data = {
            'name': signal.name,
            'message_id': message.frame_id,
            'start_bit': signal.start,
            'length': signal.length,
            'scale': signal.scale,
            'offset': signal.offset,
            'unit': signal.unit
        }
        self.signal_selected.emit(signal_data)

    def show_message_details(self, message):
        """Show detailed information for a message."""
        self.signal_table.setRowCount(0)

        # Message properties
        properties = [
            ("Name", message.name),
            ("ID", f"0x{message.frame_id:03X}"),
            ("DLC", str(message.length)),
            ("Cycle Time", str(getattr(message, 'cycle_time', 'N/A'))),
            ("Send Type", getattr(message, 'send_type', 'N/A')),
            ("Comment", getattr(message, 'comment', 'N/A'))
        ]

        for prop, value in properties:
            row = self.signal_table.rowCount()
            self.signal_table.insertRow(row)
            self.signal_table.setItem(row, 0, QTableWidgetItem(prop))
            self.signal_table.setItem(row, 1, QTableWidgetItem(str(value)))

        self.signal_desc_edit.setPlainText(getattr(message, 'comment', 'No description available'))

    def clear_content_view(self):
        """Clear the content view."""
        self.messages_tree.clear()
        self.signal_table.setRowCount(0)
        self.signal_desc_edit.clear()

    def show_dbc_context_menu(self, position):
        """Show context menu for DBC list."""
        menu = QMenu()

        load_action = menu.addAction("Load DBC...")
        load_action.triggered.connect(self.load_dbc_file)

        if self.dbc_list.currentItem():
            unload_action = menu.addAction("Unload DBC")
            unload_action.triggered.connect(self.unload_dbc)

            menu.addSeparator()
            info_action = menu.addAction("DBC Info")
            info_action.triggered.connect(self.show_dbc_info)

        menu.exec_(self.dbc_list.mapToGlobal(position))

    def show_dbc_info(self):
        """Show information about the selected DBC."""
        current_item = self.dbc_list.currentItem()
        if not current_item:
            return

        dbc_name = current_item.text()

        try:
            info = self.dbc_manager.get_dbc_info(dbc_name)

            info_text = f"DBC File: {dbc_name}\n\n"
            info_text += f"Messages: {info.get('message_count', 0)}\n"
            info_text += f"Signals: {info.get('signal_count', 0)}\n"
            info_text += f"ECUs: {info.get('ecu_count', 0)}\n"

            QMessageBox.information(self, "DBC Information", info_text)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not get DBC info: {str(e)}")

    def get_signal_definitions(self):
        """Get all signal definitions from loaded DBCs."""
        return self.dbc_manager.get_all_signals()

    def decode_frame(self, frame):
        """Decode a CAN frame using loaded DBCs."""
        return self.dbc_manager.decode_frame(frame)