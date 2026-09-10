"""Graphical Interface - Modular PyCANAnalyzer GUI."""
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, QFrame,
                             QMenuBar, QMenu, QAction, QFileDialog, QStatusBar,
                             QListWidget, QSplitter, QLineEdit, QCheckBox, QGroupBox,
                             QMessageBox, QSizePolicy, QComboBox, QGridLayout,
                             QHeaderView, QTableWidget, QTableWidgetItem, QScrollArea)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import sys
from storage.storage import FrameFileIO
from dbc.dbc import DBCManager

# Theme manager
from gui.themes.theme_manager import ThemeManager

# Import dialogs
from gui.dialogs.connection_dialog import ConnectionDialog
from gui.dialogs.preferences_dialog import PreferencesDialog
from gui.dialogs.device_settings_dialog import DeviceSettingsDialog
from gui.dialogs.connection_window import ConnectionWindow

# Import tool windows
from gui.file_tools.log_loader_window import LogLoaderWindow
from gui.file_tools.log_export_window import LogExportWindow
from gui.file_tools.filter_manager_window import FilterManagerWindow
from gui.file_tools.dbc_manager_window import DBCManagerWindow

from gui.re_tools.flow_view_window import FlowViewWindow
from gui.re_tools.graph_window import GraphWindow
from gui.re_tools.frame_analysis_window import FrameAnalysisWindow
from gui.re_tools.sniffer_window import SnifferWindow
from gui.re_tools.capture_bisector_window import CaptureBisectorWindow
from gui.re_tools.signal_viewer_window import SignalViewerWindow
from gui.re_tools.correlation_window import CorrelationWindow
from gui.re_tools.timing_analysis_window import TimingAnalysisWindow
from gui.re_tools.fuzzy_search_window import FuzzySearchWindow
from gui.re_tools.dbc_decoder_window import DbcDecoderWindow
from gui.re_tools.can_bus_monitor_window import CanBusMonitorWindow

from gui.send_frames.replay_window import ReplayWindow
from gui.send_frames.custom_sender_window import CustomSenderWindow
from gui.send_frames.scripting_interface_window import ScriptingInterfaceWindow
from gui.send_frames.fuzzing_window import FuzzingWindow
from gui.send_frames.uds_scanner_window import UdsScannerWindow

from gui.advanced_tools.signal_discovery_window import SignalDiscoveryWindow
from gui.advanced_tools.anomaly_detection_window import AnomalyDetectionWindow
from gui.advanced_tools.bus_statistics_window import BusStatisticsWindow
from gui.advanced_tools.network_topology_window import NetworkTopologyWindow


class ConnectionStatusWidget(QWidget):
    """Connection status indicator shown on the right panel top."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme = theme_manager
        self.theme.theme_changed.connect(self._on_theme_changed)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        self.indicator = QLabel("●")
        layout.addWidget(self.indicator)

        self.status_label = QLabel("Not Connected")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.device_label = QLabel("")
        layout.addWidget(self.device_label)

        self.setFixedHeight(36)
        self._apply_style()
        self.set_connected(False)

    def _on_theme_changed(self, theme_name):
        self._apply_style()

    def _apply_style(self):
        bg = self.theme.get_color("status_bg")
        border = self.theme.get_color("border")
        fg_sec = self.theme.get_color("fg_secondary")
        self.setStyleSheet(f"""
            ConnectionStatusWidget {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
            }}
        """)
        self.device_label.setStyleSheet(f"color: {fg_sec}; font-size: 11px;")

    def set_connected(self, connected, device_info=""):
        success = self.theme.get_color("success")
        error = self.theme.get_color("error")
        if connected:
            self.indicator.setStyleSheet(f"color: {success}; font-size: 14px;")
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet(
                f"font-weight: bold; font-size: 12px; color: {success};"
            )
            self.device_label.setText(device_info)
        else:
            self.indicator.setStyleSheet(f"color: {error}; font-size: 14px;")
            self.status_label.setText("Not Connected")
            self.status_label.setStyleSheet(
                f"font-weight: bold; font-size: 12px; color: {error};"
            )
            self.device_label.setText("")


class FilterPanelWidget(QWidget):
    """Filter controls: ID, Bus, Data, Direction, Frame Type, DLC filters."""

    filter_changed = pyqtSignal()

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme = theme_manager
        self.theme.theme_changed.connect(self._on_theme_changed)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        title = QLabel("Filters")
        title.setStyleSheet("font-weight: bold; font-size: 13px; padding-bottom: 2px;")
        layout.addWidget(title)

        # ID Filter
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("ID:"))
        self.id_filter = QLineEdit()
        self.id_filter.setPlaceholderText("e.g. 0x1A0 or 1A0-1AF")
        self.id_filter.textChanged.connect(self.filter_changed.emit)
        id_layout.addWidget(self.id_filter)
        layout.addLayout(id_layout)

        # Bus Filter
        bus_layout = QHBoxLayout()
        bus_layout.addWidget(QLabel("Bus:"))
        self.bus_filter = QComboBox()
        self.bus_filter.addItems(["All", "0", "1", "2", "3"])
        self.bus_filter.currentIndexChanged.connect(self.filter_changed.emit)
        bus_layout.addWidget(self.bus_filter)
        layout.addLayout(bus_layout)

        # Data Filter
        data_layout = QHBoxLayout()
        data_layout.addWidget(QLabel("Data:"))
        self.data_filter = QLineEdit()
        self.data_filter.setPlaceholderText("e.g. FF or 00 FF *")
        self.data_filter.textChanged.connect(self.filter_changed.emit)
        data_layout.addWidget(self.data_filter)
        layout.addLayout(data_layout)

        # Direction Filter
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Direction:"))
        self.dir_filter = QComboBox()
        self.dir_filter.addItems(["All", "Rx", "Tx"])
        self.dir_filter.currentIndexChanged.connect(self.filter_changed.emit)
        dir_layout.addWidget(self.dir_filter)
        layout.addLayout(dir_layout)

        # Frame Type Filter
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Frame Type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Standard", "Extended", "FD", "Error", "Remote"])
        self.type_filter.currentIndexChanged.connect(self.filter_changed.emit)
        type_layout.addWidget(self.type_filter)
        layout.addLayout(type_layout)

        # DLC Filter
        dlc_layout = QHBoxLayout()
        dlc_layout.addWidget(QLabel("DLC:"))
        self.dlc_filter = QComboBox()
        self.dlc_filter.addItems(["All", "0", "1", "2", "3", "4", "5", "6", "7", "8"])
        self.dlc_filter.currentIndexChanged.connect(self.filter_changed.emit)
        dlc_layout.addWidget(self.dlc_filter)
        layout.addLayout(dlc_layout)

        # Apply / Clear
        btn_layout = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self.filter_changed.emit)
        btn_layout.addWidget(self.apply_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_filters)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)

        self._apply_style()

    def _on_theme_changed(self, theme_name):
        self._apply_style()

    def _apply_style(self):
        bg = self.theme.get_color("filter_bg")
        border = self.theme.get_color("border")
        accent = self.theme.get_color("accent")
        self.setStyleSheet(f"""
            FilterPanelWidget {{
                border: 1px solid {border};
                border-radius: 4px;
                background-color: {bg};
            }}
            QLabel {{ font-size: 11px; min-width: 65px; }}
        """)
        self.apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent}; color: white; border: none;
                border-radius: 3px; padding: 4px 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {self.theme.get_color("accent_hover")}; }}
        """)

    def clear_filters(self):
        self.id_filter.clear()
        self.bus_filter.setCurrentIndex(0)
        self.data_filter.clear()
        self.dir_filter.setCurrentIndex(0)
        self.type_filter.setCurrentIndex(0)
        self.dlc_filter.setCurrentIndex(0)
        self.filter_changed.emit()

    def get_filter_func(self):
        """Build a filter function from current settings."""
        id_text = self.id_filter.text().strip()
        bus_text = self.bus_filter.currentText()
        data_text = self.data_filter.text().strip()
        dir_text = self.dir_filter.currentText()
        type_text = self.type_filter.currentText()
        dlc_text = self.dlc_filter.currentText()

        if (not id_text and bus_text == "All" and not data_text
                and dir_text == "All" and type_text == "All"
                and dlc_text == "All"):
            return None

        def filter_func(frame):
            if id_text:
                try:
                    if '-' in id_text:
                        parts = id_text.replace('0x', '').replace('0X', '').split('-')
                        low, high = int(parts[0], 16), int(parts[1], 16)
                        if not (low <= frame.can_id <= high):
                            return False
                    else:
                        fid = int(id_text.replace('0x', '').replace('0X', ''), 16)
                        if frame.can_id != fid:
                            return False
                except ValueError:
                    pass

            if bus_text != "All":
                if getattr(frame, 'bus', 0) != int(bus_text):
                    return False

            if data_text:
                data_hex = frame.data.hex().upper()
                search = data_text.replace(' ', '').replace('*', '').upper()
                if search and search not in data_hex:
                    return False

            if dir_text != "All":
                frame_dir = getattr(frame, 'direction', 'Rx')
                if isinstance(frame_dir, str) and frame_dir.lower() != dir_text.lower():
                    return False

            if type_text != "All":
                is_ext = getattr(frame, 'extended', False)
                is_fd = getattr(frame, 'is_fd', False)
                is_err = getattr(frame, 'is_error', False)
                is_rmt = getattr(frame, 'is_remote', False)
                if type_text == "Standard" and is_ext:
                    return False
                elif type_text == "Extended" and not is_ext:
                    return False
                elif type_text == "FD" and not is_fd:
                    return False
                elif type_text == "Error" and not is_err:
                    return False
                elif type_text == "Remote" and not is_rmt:
                    return False

            if dlc_text != "All":
                if frame.dlc != int(dlc_text):
                    return False

            return True

        return filter_func


class FrameCaptureTable(QTableWidget):
    """Log capturing grid with columns: Timestamp | ID | Ext | Dir | Bus | DLC | Data"""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme = theme_manager
        self.theme.theme_changed.connect(self._on_theme_changed)
        self.frames = []
        self.filter_func = None
        self.init_ui()

    def init_ui(self):
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "Timestamp", "ID", "Ext", "Dir", "Bus", "DLC", "Data"
        ])

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)

        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

    def _on_theme_changed(self, theme_name):
        self.refresh_display()

    def add_frame(self, frame):
        self.frames.append(frame)
        if self.filter_func is None or self.filter_func(frame):
            self._insert_frame_row(frame)

    def add_frames(self, frames):
        self.frames.extend(frames)
        self.refresh_display()

    def _insert_frame_row(self, frame):
        row = self.rowCount()
        self.insertRow(row)

        id_color = QColor(self.theme.get_color("id_color"))
        data_color = QColor(self.theme.get_color("data_color"))
        tx_color = QColor(self.theme.get_color("tx_color"))
        rx_color = QColor(self.theme.get_color("rx_color"))
        ext_color = QColor(self.theme.get_color("ext_color"))

        # Timestamp
        ts = f"{frame.timestamp:.6f}" if hasattr(frame, 'timestamp') else "0.000000"
        self.setItem(row, 0, QTableWidgetItem(ts))

        # ID
        can_id = f"0x{frame.can_id:03X}" if hasattr(frame, 'can_id') else "0x000"
        id_item = QTableWidgetItem(can_id)
        id_item.setForeground(id_color)
        self.setItem(row, 1, id_item)

        # Extended
        is_ext = getattr(frame, 'extended', False)
        ext_item = QTableWidgetItem("Yes" if is_ext else "No")
        if is_ext:
            ext_item.setForeground(ext_color)
        self.setItem(row, 2, ext_item)

        # Direction
        direction = getattr(frame, 'direction', 'Rx')
        dir_item = QTableWidgetItem(str(direction))
        dir_item.setForeground(tx_color if str(direction).lower() == 'tx' else rx_color)
        self.setItem(row, 3, dir_item)

        # Bus
        bus = getattr(frame, 'bus', 0)
        self.setItem(row, 4, QTableWidgetItem(str(bus)))

        # DLC
        dlc = frame.dlc if hasattr(frame, 'dlc') else 0
        self.setItem(row, 5, QTableWidgetItem(str(dlc)))

        # Data
        if hasattr(frame, 'data') and frame.data:
            data_str = ' '.join(f'{b:02X}' for b in frame.data)
        else:
            data_str = ""
        data_item = QTableWidgetItem(data_str)
        data_item.setForeground(data_color)
        self.setItem(row, 6, data_item)

    def apply_filter(self, filter_func):
        self.filter_func = filter_func
        self.refresh_display()

    def refresh_display(self):
        self.setRowCount(0)
        for frame in self.frames:
            if self.filter_func is None or self.filter_func(frame):
                self._insert_frame_row(frame)

    def clear_frames(self):
        self.frames.clear()
        self.setRowCount(0)

    def get_selected_frame(self):
        selected = self.selectionModel().selectedRows()
        if selected:
            row = selected[0].row()
            visible = [f for f in self.frames
                       if self.filter_func is None or self.filter_func(f)]
            if 0 <= row < len(visible):
                return visible[row]
        return None

    def get_visible_count(self):
        return self.rowCount()


class FrameDetailsWidget(QWidget):
    """Frame details panel showing decoded info for selected frame."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme = theme_manager
        self.theme.theme_changed.connect(self._on_theme_changed)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        title = QLabel("Frame Details")
        title.setStyleSheet("font-weight: bold; font-size: 13px; padding-bottom: 2px;")
        layout.addWidget(title)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("Select a frame to view details...")
        layout.addWidget(self.details_text)

        self._apply_style()

    def _on_theme_changed(self, theme_name):
        self._apply_style()

    def _apply_style(self):
        bg = self.theme.get_color("filter_bg")
        border = self.theme.get_color("border")
        self.setStyleSheet(f"""
            FrameDetailsWidget {{
                border: 1px solid {border};
                border-radius: 4px;
                background-color: {bg};
            }}
        """)

    def show_frame(self, frame, dbc_manager=None):
        if frame is None:
            self.details_text.clear()
            return

        lines = []
        lines.append(f"Timestamp : {frame.timestamp:.6f}")
        lines.append(f"ID        : 0x{frame.can_id:03X} ({frame.can_id})")
        lines.append(f"Extended  : {'Yes' if getattr(frame, 'extended', False) else 'No'}")
        lines.append(f"Direction : {getattr(frame, 'direction', 'Rx')}")
        lines.append(f"Bus       : {getattr(frame, 'bus', 0)}")
        lines.append(f"DLC       : {frame.dlc}")

        if hasattr(frame, 'data') and frame.data:
            hex_str = ' '.join(f'{b:02X}' for b in frame.data)
            lines.append(f"Data (hex): {hex_str}")
            lines.append(f"Data (raw): {frame.data.hex()}")
            bin_str = ' '.join(f'{b:08b}' for b in frame.data)
            lines.append(f"Data (bin): {bin_str}")
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in frame.data)
            lines.append(f"Data (asc): {ascii_str}")

        if dbc_manager:
            decoded = dbc_manager.decode_frame(frame)
            if decoded:
                lines.append("")
                lines.append("── Decoded Signals ──")
                for signal, value in decoded.items():
                    lines.append(f"  {signal}: {value}")

        self.details_text.setPlainText('\n'.join(lines))

    def clear(self):
        self.details_text.clear()


class LoggingControlWidget(QWidget):
    """Bottom logging bar with Start Log / Stop Log buttons."""

    start_logging = pyqtSignal(str)
    stop_logging = pyqtSignal()

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme = theme_manager
        self.theme.theme_changed.connect(self._on_theme_changed)
        self.is_logging = False
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        label = QLabel("Logging:")
        label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(label)

        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("Enter log filename...")
        self.filename_edit.setText("capture.csv")
        self.filename_edit.setMinimumWidth(200)
        layout.addWidget(self.filename_edit)

        self.browse_btn = QPushButton("...")
        self.browse_btn.setFixedWidth(30)
        self.browse_btn.clicked.connect(self._browse_file)
        layout.addWidget(self.browse_btn)

        self.start_btn = QPushButton("▶ Start Log")
        self.start_btn.clicked.connect(self._on_start)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("■ Stop Log")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        layout.addWidget(self.stop_btn)

        self.status_label = QLabel("Not logging")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.frame_count_label = QLabel("Frames: 0")
        self.frame_count_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.frame_count_label)

        self.setFixedHeight(44)
        self._apply_style()

    def _on_theme_changed(self, theme_name):
        self._apply_style()

    def _apply_style(self):
        bg = self.theme.get_color("status_bg")
        border = self.theme.get_color("border")
        success = self.theme.get_color("success")
        error = self.theme.get_color("error")

        self.setStyleSheet(f"""
            LoggingControlWidget {{
                border: 1px solid {border};
                border-radius: 4px;
                background-color: {bg};
            }}
        """)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {success}; color: white; border: none;
                border-radius: 3px; padding: 6px 16px;
                font-weight: bold; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {self.theme.get_color("accent_hover")}; }}
        """)
        self.stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {error}; color: white; border: none;
                border-radius: 3px; padding: 6px 16px;
                font-weight: bold; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: #e74c3c; }}
            QPushButton:disabled {{ background-color: {self.theme.get_color("bg_tertiary")}; color: {self.theme.get_color("fg_muted")}; }}
        """)

    def _browse_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Select Log File", "",
            "CSV Files (*.csv);;Log Files (*.log);;All Files (*)"
        )
        if file_path:
            self.filename_edit.setText(file_path)

    def _on_start(self):
        filename = self.filename_edit.text().strip()
        if not filename:
            QMessageBox.warning(self, "No Filename", "Please enter a log filename.")
            return
        self.is_logging = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.filename_edit.setEnabled(False)
        self.browse_btn.setEnabled(False)
        success = self.theme.get_color("success")
        self.status_label.setText(f"Logging to: {filename}")
        self.status_label.setStyleSheet(f"color: {success}; font-size: 11px;")
        self.start_logging.emit(filename)

    def _on_stop(self):
        self.is_logging = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.filename_edit.setEnabled(True)
        self.browse_btn.setEnabled(True)
        warning = self.theme.get_color("warning")
        self.status_label.setText("Logging stopped")
        self.status_label.setStyleSheet(f"color: {warning}; font-size: 11px;")
        self.stop_logging.emit()

    def update_frame_count(self, count):
        self.frame_count_label.setText(f"Frames: {count}")


class MainWindow(QMainWindow):
    def __init__(self, config, pipeline, discovery, ml_engine):
        super().__init__()
        self.config = config
        self.pipeline = pipeline
        self.discovery = discovery
        self.ml_engine = ml_engine
        self.dbc_manager = DBCManager()
        self.frames = []
        self.filtered_frames = []
        self.tool_windows = {}

        # Theme manager
        self.theme_manager = ThemeManager(self)

        self.init_ui()
        self.init_menus()

        # Apply saved theme or default to dark
        saved_theme = self.config.get("theme", ThemeManager.DARK) if hasattr(self.config, 'get') else ThemeManager.DARK
        self.theme_manager.set_theme(saved_theme)

    def init_ui(self):
        self.setWindowTitle("PyCANAnalyzer")
        self.setGeometry(100, 100, 1400, 850)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        # ── Main horizontal splitter (70:30) ──
        self.main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.main_splitter, 1)

        # LEFT SIDE (70%) - Frame capture table
        self.frame_table = FrameCaptureTable(self.theme_manager)
        self.frame_table.itemSelectionChanged.connect(self._on_frame_selected)
        self.main_splitter.addWidget(self.frame_table)

        # RIGHT SIDE (30%) - Status + Filters + Details
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(2, 0, 2, 0)
        right_layout.setSpacing(4)

        self.connection_status = ConnectionStatusWidget(self.theme_manager)
        right_layout.addWidget(self.connection_status)

        self.filter_panel = FilterPanelWidget(self.theme_manager)
        self.filter_panel.filter_changed.connect(self._apply_filters)
        right_layout.addWidget(self.filter_panel)

        self.frame_details = FrameDetailsWidget(self.theme_manager)
        right_layout.addWidget(self.frame_details, 1)

        self.main_splitter.addWidget(right_widget)

        # 70:30 ratio
        self.main_splitter.setSizes([980, 420])
        self.main_splitter.setStretchFactor(0, 7)
        self.main_splitter.setStretchFactor(1, 3)

        # BOTTOM - Logging controls
        self.logging_control = LoggingControlWidget(self.theme_manager)
        self.logging_control.start_logging.connect(self._start_logging)
        self.logging_control.stop_logging.connect(self._stop_logging)
        main_layout.addWidget(self.logging_control)

        # Status bar
        self.statusBar().showMessage("Ready")

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(100)

    def init_menus(self):
        menubar = self.menuBar()

        # ── File ──
        file_menu = menubar.addMenu('File')

        load_action = QAction('Load CAN Log', self)
        load_action.setShortcut('Ctrl+O')
        load_action.triggered.connect(self.load_file)
        file_menu.addAction(load_action)

        save_action = QAction('Save CAN Log', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ── Edit ──
        edit_menu = menubar.addMenu('Edit')

        preferences_action = QAction('Preferences', self)
        preferences_action.triggered.connect(self.open_preferences_dialog)
        edit_menu.addAction(preferences_action)

        # ── Connection ──
        connection_menu = menubar.addMenu('Connection')

        open_conn_action = QAction('Open Connection Window', self)
        open_conn_action.setShortcut('Ctrl+Shift+C')
        open_conn_action.triggered.connect(self.open_connection_window)
        connection_menu.addAction(open_conn_action)

        connection_menu.addSeparator()

        device_settings_action = QAction('Device Settings', self)
        device_settings_action.triggered.connect(self.open_device_settings_dialog)
        connection_menu.addAction(device_settings_action)

        # ── View ──
        view_menu = menubar.addMenu('View')

        clear_action = QAction('Clear Frames', self)
        clear_action.setShortcut('Ctrl+L')
        clear_action.triggered.connect(self.clear_frames)
        view_menu.addAction(clear_action)

        view_menu.addSeparator()

        # Theme submenu
        theme_menu = view_menu.addMenu('Theme')

        self.dark_theme_action = QAction('Dark Theme', self)
        self.dark_theme_action.setCheckable(True)
        self.dark_theme_action.setChecked(True)
        self.dark_theme_action.triggered.connect(lambda: self._set_theme(ThemeManager.DARK))
        theme_menu.addAction(self.dark_theme_action)

        self.light_theme_action = QAction('Light Theme', self)
        self.light_theme_action.setCheckable(True)
        self.light_theme_action.triggered.connect(lambda: self._set_theme(ThemeManager.LIGHT))
        theme_menu.addAction(self.light_theme_action)

        theme_menu.addSeparator()

        toggle_theme_action = QAction('Toggle Theme', self)
        toggle_theme_action.setShortcut('Ctrl+T')
        toggle_theme_action.triggered.connect(self._toggle_theme)
        theme_menu.addAction(toggle_theme_action)

        # ── Tools ──
        tools_menu = menubar.addMenu('Tools')

        # File Tools
        file_tools_menu = tools_menu.addMenu('File Tools')

        log_loader_action = QAction('Log Loader', self)
        log_loader_action.triggered.connect(self.open_log_loader_window)
        file_tools_menu.addAction(log_loader_action)

        log_export_action = QAction('Log Export', self)
        log_export_action.triggered.connect(self.open_log_export_window)
        file_tools_menu.addAction(log_export_action)

        filter_manager_action = QAction('Filter Manager', self)
        filter_manager_action.triggered.connect(self.open_filter_manager_window)
        file_tools_menu.addAction(filter_manager_action)

        dbc_manager_action = QAction('DBC Manager', self)
        dbc_manager_action.triggered.connect(self.open_dbc_manager_window)
        file_tools_menu.addAction(dbc_manager_action)

        # Reverse Engineering
        re_tools_menu = tools_menu.addMenu('Reverse Engineering')

        for name, slot in [
            ('Network Flow View', self.open_flow_view_window),
            ('Signal Graph', self.open_graph_window),
            ('Frame Analysis', self.open_frame_analysis_window),
            ('Signal Sniffer', self.open_sniffer_window),
            ('Capture Bisector', self.open_capture_bisector_window),
            ('Signal Viewer', self.open_signal_viewer_window),
            ('Signal Correlation', self.open_correlation_window),
            ('Timing Analysis', self.open_timing_analysis_window),
            ('Fuzzy Search', self.open_fuzzy_search_window),
            ('DBC Decoder', self.open_dbc_decoder_window),
            ('CAN Bus Monitor', self.open_can_bus_monitor_window),
        ]:
            action = QAction(name, self)
            action.triggered.connect(slot)
            re_tools_menu.addAction(action)

        # Send Frames
        send_tools_menu = tools_menu.addMenu('Send Frames')

        for name, slot in [
            ('Frame Replay', self.open_replay_window),
            ('Custom Sender', self.open_custom_sender_window),
            ('Scripting Interface', self.open_scripting_interface_window),
            ('Fuzzing Tool', self.open_fuzzing_window),
            ('UDS Scanner', self.open_uds_scanner_window),
        ]:
            action = QAction(name, self)
            action.triggered.connect(slot)
            send_tools_menu.addAction(action)

        # Advanced Tools
        advanced_tools_menu = tools_menu.addMenu('Advanced Tools')

        for name, slot in [
            ('Signal Discovery', self.open_signal_discovery_window),
            ('Anomaly Detection', self.open_anomaly_detection_window),
            ('Bus Statistics', self.open_bus_statistics_window),
            ('Network Topology', self.open_network_topology_window),
        ]:
            action = QAction(name, self)
            action.triggered.connect(slot)
            advanced_tools_menu.addAction(action)

    # ═══════════════════════════════════════════
    # Theme Methods
    # ═══════════════════════════════════════════

    def _set_theme(self, theme_name):
        """Set the application theme."""
        self.theme_manager.set_theme(theme_name)
        self.dark_theme_action.setChecked(theme_name == ThemeManager.DARK)
        self.light_theme_action.setChecked(theme_name == ThemeManager.LIGHT)

        # Save preference
        if hasattr(self.config, '__setitem__'):
            self.config["theme"] = theme_name
        elif hasattr(self.config, 'set'):
            self.config.set("theme", theme_name)

    def _toggle_theme(self):
        """Toggle between dark and light themes."""
        if self.theme_manager.is_dark():
            self._set_theme(ThemeManager.LIGHT)
        else:
            self._set_theme(ThemeManager.DARK)

    # ═══════════════════════════════════════════
    # Internal Slots
    # ═══════════════════════════════════════════

    def _on_frame_selected(self):
        frame = self.frame_table.get_selected_frame()
        self.frame_details.show_frame(frame, self.dbc_manager)

    def _apply_filters(self):
        filter_func = self.filter_panel.get_filter_func()
        self.frame_table.apply_filter(filter_func)
        total = len(self.frame_table.frames)
        visible = self.frame_table.get_visible_count()
        self.statusBar().showMessage(f"Showing {visible} of {total} frames")

    def _update_display(self):
        connected_count = len(self.pipeline.device_manager.connected_devices)
        if connected_count > 0:
            self.connection_status.set_connected(True, f"{connected_count} device(s)")
        else:
            self.connection_status.set_connected(False)
        self.logging_control.update_frame_count(len(self.frame_table.frames))

    def _start_logging(self, filename):
        self.statusBar().showMessage(f"Logging to {filename}")

    def _stop_logging(self):
        self.statusBar().showMessage("Logging stopped")

    # ═══════════════════════════════════════════
    # File Operations
    # ═══════════════════════════════════════════

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load CAN Log", "",
            "CAN Files (*.csv *.log *.gvret);;CSV Files (*.csv);;"
            "GVRET Files (*.gvret);;BusMaster Files (*.log);;All Files (*)"
        )
        if file_path:
            try:
                if file_path.endswith('.csv'):
                    self.frames = list(FrameFileIO.load_csv(file_path))
                elif file_path.endswith('.gvret'):
                    self.frames = list(FrameFileIO.load_gvret(file_path))
                elif file_path.endswith('.log'):
                    self.frames = list(FrameFileIO.load_busmaster(file_path))
                else:
                    self.frames = list(FrameFileIO.load_csv(file_path))

                self.frame_table.clear_frames()
                self.frame_table.add_frames(self.frames)
                self._apply_filters()
                self.statusBar().showMessage(
                    f"Loaded {len(self.frames)} frames from {file_path}"
                )
            except Exception as e:
                self.statusBar().showMessage(f"Failed to load: {e}")

    def save_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save CAN Log", "",
            "CSV Files (*.csv);;GVRET Files (*.gvret);;BusMaster Files (*.log)"
        )
        if file_path:
            try:
                if file_path.endswith('.csv'):
                    FrameFileIO.save_csv(self.frames, file_path)
                elif file_path.endswith('.gvret'):
                    FrameFileIO.save_gvret(self.frames, file_path)
                elif file_path.endswith('.log'):
                    FrameFileIO.save_busmaster(self.frames, file_path)
                self.statusBar().showMessage(
                    f"Saved {len(self.frames)} frames to {file_path}"
                )
            except Exception as e:
                self.statusBar().showMessage(f"Failed to save: {e}")

    def clear_frames(self):
        self.frames.clear()
        self.frame_table.clear_frames()
        self.frame_details.clear()
        self.statusBar().showMessage("Frames cleared")

    # ═══════════════════════════════════════════
    # Connection
    # ═══════════════════════════════════════════

    def open_connection_window(self):
        window = ConnectionWindow(self.pipeline.device_manager, self)
        window.exec_()
        self._update_display()

    def open_device_settings_dialog(self):
        dialog = DeviceSettingsDialog(self.pipeline.device_manager, self)
        dialog.exec_()

    def open_preferences_dialog(self):
        dialog = PreferencesDialog(self.config, self)
        dialog.exec_()

    # ═══════════════════════════════════════════
    # Callbacks
    # ═══════════════════════════════════════════

    def on_frames_loaded(self, frames):
        self.frames = frames
        self.frame_table.clear_frames()
        self.frame_table.add_frames(self.frames)
        self._apply_filters()
        self.statusBar().showMessage(f"Loaded {len(frames)} frames")

    def apply_external_filter(self, filter_config):
        self.frame_table.apply_filter(lambda frame: True)
        self.statusBar().showMessage("External filter applied")

    def on_dbc_loaded(self, dbc_name):
        self.statusBar().showMessage(f"DBC loaded: {dbc_name}")

    def show(self):
        super().show()

    # ═══════════════════════════════════════════
    # Tool Windows
    # ═══════════════════════════════════════════

    def open_flow_view_window(self):
        FlowViewWindow(self.pipeline.get_frames(), self).show()

    def open_graph_window(self):
        GraphWindow(self.pipeline.get_frames(), self.dbc_manager, self).show()

    def open_frame_analysis_window(self):
        FrameAnalysisWindow(self.pipeline.get_frames(), self).show()

    def open_sniffer_window(self):
        SnifferWindow(self.pipeline.get_frames(), self).show()

    def open_capture_bisector_window(self):
        CaptureBisectorWindow(self.pipeline.get_frames(), self).show()

    def open_signal_viewer_window(self):
        SignalViewerWindow(self.pipeline.get_frames(), self).show()

    def open_correlation_window(self):
        CorrelationWindow(self.pipeline.get_frames(), self).show()

    def open_timing_analysis_window(self):
        TimingAnalysisWindow(self.pipeline.get_frames(), self).show()

    def open_fuzzy_search_window(self):
        FuzzySearchWindow(self.pipeline.get_frames(), self).show()

    def open_dbc_decoder_window(self):
        DbcDecoderWindow(self.pipeline.get_frames(), self).show()

    def open_can_bus_monitor_window(self):
        CanBusMonitorWindow(self.pipeline.get_frames(), self).show()

    def open_log_loader_window(self):
        window = LogLoaderWindow(self)
        window.frames_loaded.connect(self.on_frames_loaded)
        window.show()

    def open_log_export_window(self):
        LogExportWindow(self.pipeline.get_frames(), self).show()

    def open_filter_manager_window(self):
        window = FilterManagerWindow(self)
        window.filter_applied.connect(self.apply_external_filter)
        window.show()

    def open_dbc_manager_window(self):
        window = DBCManagerWindow(self)
        window.dbc_loaded.connect(self.on_dbc_loaded)
        window.show()

    def open_replay_window(self):
        ReplayWindow(self.pipeline, self).show()

    def open_custom_sender_window(self):
        CustomSenderWindow(self.pipeline.get_frames(), self).show()

    def open_scripting_interface_window(self):
        ScriptingInterfaceWindow(self.pipeline, self).show()

    def open_fuzzing_window(self):
        FuzzingWindow(self.pipeline, self).show()

    def open_uds_scanner_window(self):
        UdsScannerWindow(self.pipeline, self).show()

    def open_signal_discovery_window(self):
        SignalDiscoveryWindow(self.pipeline, self).show()

    def open_anomaly_detection_window(self):
        AnomalyDetectionWindow(self.pipeline, self).show()

    def open_bus_statistics_window(self):
        BusStatisticsWindow(self.pipeline, self).show()

    def open_network_topology_window(self):
        NetworkTopologyWindow(self.pipeline, self).show()


class DeviceManagerView:
    def refresh(self):
        pass


class FrameSnifferView:
    def update(self, frames):
        pass


class SignalDiscoveryView:
    def update(self, candidates):
        pass


class GraphView:
    def draw(self):
        pass


class ReplayView:
    def play(self):
        pass


class SettingsView:
    def open(self):
        pass