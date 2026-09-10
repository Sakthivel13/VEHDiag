"""Log Export Window - Export Captured CAN Frames."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QLineEdit,
                             QProgressBar, QFileDialog, QMessageBox, QGroupBox,
                             QCheckBox, QDateTimeEdit, QSpinBox, QFormLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDateTime
from PyQt5.QtGui import QFont
from storage.storage import FrameFileIO
import os


class LogExportWindow(QMainWindow):
    """Window for exporting captured CAN frames to various formats."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.frame_io = FrameFileIO()

        self.init_ui()

    def init_ui(self):
        """Initialize the log export UI."""
        self.setWindowTitle("Export CAN Log")
        self.setGeometry(200, 200, 600, 500)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Export settings group
        settings_group = QGroupBox("Export Settings")
        settings_layout = QFormLayout()

        # Output file
        file_layout = QHBoxLayout()
        self.output_file_edit = QLineEdit()
        self.output_file_edit.setPlaceholderText("Select output file...")

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_output_file)

        file_layout.addWidget(self.output_file_edit)
        file_layout.addWidget(browse_button)

        settings_layout.addRow("Output File:", file_layout)

        # Format selection
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "CSV",
            "Parquet",
            "ASC (Vector)",
            "BLF (Vector)",
            "TRC (PEAK)",
            "GVRET",
            "Candump",
            "BusMaster"
        ])
        self.format_combo.setCurrentText("CSV")
        settings_layout.addRow("Format:", self.format_combo)

        # Compression (for applicable formats)
        self.compression_combo = QComboBox()
        self.compression_combo.addItems([
            "None",
            "gzip",
            "bz2",
            "xz"
        ])
        settings_layout.addRow("Compression:", self.compression_combo)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Frame filtering group
        filter_group = QGroupBox("Frame Filtering")
        filter_layout = QFormLayout()

        # Time range
        self.time_filter_check = QCheckBox("Filter by time range")
        self.time_filter_check.stateChanged.connect(self.toggle_time_filter)

        start_time_layout = QHBoxLayout()
        start_time_layout.addWidget(QLabel("Start:"))
        self.start_time_edit = QDateTimeEdit()
        self.start_time_edit.setDateTime(QDateTime.currentDateTime().addSecs(-3600))  # 1 hour ago
        self.start_time_edit.setEnabled(False)
        start_time_layout.addWidget(self.start_time_edit)

        end_time_layout = QHBoxLayout()
        end_time_layout.addWidget(QLabel("End:"))
        self.end_time_edit = QDateTimeEdit()
        self.end_time_edit.setDateTime(QDateTime.currentDateTime())
        self.end_time_edit.setEnabled(False)
        end_time_layout.addWidget(self.end_time_edit)

        filter_layout.addRow(self.time_filter_check)
        filter_layout.addRow(start_time_layout)
        filter_layout.addRow(end_time_layout)

        # Frame count limit
        self.frame_limit_check = QCheckBox("Limit frame count")
        self.frame_limit_check.stateChanged.connect(self.toggle_frame_limit)

        limit_layout = QHBoxLayout()
        self.frame_limit_spin = QSpinBox()
        self.frame_limit_spin.setRange(100, 10000000)
        self.frame_limit_spin.setSingleStep(1000)
        self.frame_limit_spin.setValue(100000)
        self.frame_limit_spin.setEnabled(False)
        limit_layout.addWidget(self.frame_limit_spin)
        limit_layout.addStretch()

        filter_layout.addRow(self.frame_limit_check)
        filter_layout.addRow("Max frames:", limit_layout)

        # Bus filter
        self.bus_filter_check = QCheckBox("Filter by bus")
        self.bus_filter_check.stateChanged.connect(self.toggle_bus_filter)

        bus_layout = QHBoxLayout()
        self.bus_filter_combo = QComboBox()
        self.bus_filter_combo.addItem("All Buses", -1)
        self.bus_filter_combo.addItem("Bus 0", 0)
        self.bus_filter_combo.addItem("Bus 1", 1)
        self.bus_filter_combo.addItem("Bus 2", 2)
        self.bus_filter_combo.setEnabled(False)
        bus_layout.addWidget(self.bus_filter_combo)
        bus_layout.addStretch()

        filter_layout.addRow(self.bus_filter_check)
        filter_layout.addRow("Bus:", bus_layout)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Export options group
        options_group = QGroupBox("Export Options")
        options_layout = QVBoxLayout()

        self.include_headers_check = QCheckBox("Include column headers")
        self.include_headers_check.setChecked(True)

        self.pretty_format_check = QCheckBox("Pretty format (human readable)")
        self.pretty_format_check.setChecked(True)

        self.sort_by_time_check = QCheckBox("Sort frames by timestamp")
        self.sort_by_time_check.setChecked(True)

        options_layout.addWidget(self.include_headers_check)
        options_layout.addWidget(self.pretty_format_check)
        options_layout.addWidget(self.sort_by_time_check)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Progress group
        progress_group = QGroupBox("Export Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        self.status_label = QLabel(f"Ready to export {len(self.frames):,} frames")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_frames)
        self.export_button.setDefault(True)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.export_button)

        layout.addLayout(button_layout)

    def browse_output_file(self):
        """Open file browser to select output file."""
        format_ext = {
            "CSV": "csv",
            "Parquet": "parquet",
            "ASC (Vector)": "asc",
            "BLF (Vector)": "blf",
            "TRC (PEAK)": "trc",
            "GVRET": "gvret",
            "Candump": "log",
            "BusMaster": "log"
        }

        current_format = self.format_combo.currentText().split()[0]  # Get first word
        ext = format_ext.get(current_format, "log")

        file_dialog = QFileDialog()
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setNameFilter(f"{current_format} Files (*.{ext});;All Files (*.*)")
        file_dialog.setDefaultSuffix(ext)

        if file_dialog.exec_():
            selected_file = file_dialog.selectedFiles()[0]
            self.output_file_edit.setText(selected_file)

    def toggle_time_filter(self, checked):
        """Enable/disable time filter controls."""
        self.start_time_edit.setEnabled(checked)
        self.end_time_edit.setEnabled(checked)

    def toggle_frame_limit(self, checked):
        """Enable/disable frame limit control."""
        self.frame_limit_spin.setEnabled(checked)

    def toggle_bus_filter(self, checked):
        """Enable/disable bus filter control."""
        self.bus_filter_combo.setEnabled(checked)

    def get_filtered_frames(self):
        """Get frames filtered according to current settings."""
        frames = self.frames.copy()

        # Time filter
        if self.time_filter_check.isChecked():
            start_time = self.start_time_edit.dateTime().toPyDateTime().timestamp()
            end_time = self.end_time_edit.dateTime().toPyDateTime().timestamp()

            frames = [f for f in frames
                     if start_time <= getattr(f, 'timestamp', 0) <= end_time]

        # Bus filter
        if self.bus_filter_check.isChecked():
            bus_num = self.bus_filter_combo.currentData()
            if bus_num >= 0:
                frames = [f for f in frames if getattr(f, 'bus', 0) == bus_num]

        # Frame limit
        if self.frame_limit_check.isChecked():
            max_frames = self.frame_limit_spin.value()
            frames = frames[:max_frames]

        # Sort by time
        if self.sort_by_time_check.isChecked():
            frames.sort(key=lambda f: getattr(f, 'timestamp', 0))

        return frames

    def export_frames(self):
        """Export the filtered frames."""
        output_file = self.output_file_edit.text().strip()
        if not output_file:
            QMessageBox.warning(self, "No Output File",
                               "Please select an output file.")
            return

        # Check if file exists
        if os.path.exists(output_file):
            reply = QMessageBox.question(
                self, "File Exists",
                f"The file '{os.path.basename(output_file)}' already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Get filtered frames
        filtered_frames = self.get_filtered_frames()

        if not filtered_frames:
            QMessageBox.warning(self, "No Frames",
                               "No frames to export after applying filters.")
            return

        # Start export in background thread
        self.export_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Exporting frames...")

        self.exporter_thread = LogExporterThread(
            frames=filtered_frames,
            output_file=output_file,
            format_name=self.format_combo.currentText(),
            compression=self.compression_combo.currentText(),
            include_headers=self.include_headers_check.isChecked(),
            pretty_format=self.pretty_format_check.isChecked()
        )

        self.exporter_thread.progress_updated.connect(self.update_progress)
        self.exporter_thread.export_finished.connect(self.on_export_finished)
        self.exporter_thread.start()

    def update_progress(self, progress, status):
        """Update export progress."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(status)

    def on_export_finished(self, success, message):
        """Handle export completion."""
        self.export_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            self.status_label.setText("Export completed successfully")
            QMessageBox.information(self, "Export Complete", message)
        else:
            self.status_label.setText("Export failed")
            QMessageBox.critical(self, "Export Error", message)

    def set_frames(self, frames):
        """Set the frames to be exported."""
        self.frames = frames or []
        self.status_label.setText(f"Ready to export {len(self.frames):,} frames")


class LogExporterThread(QThread):
    """Background thread for exporting log files."""

    # Signals
    progress_updated = pyqtSignal(int, str)  # progress (0-100), status message
    export_finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, frames, output_file, format_name, compression="None",
                 include_headers=True, pretty_format=True):
        super().__init__()
        self.frames = frames
        self.output_file = output_file
        self.format_name = format_name
        self.compression = compression if compression != "None" else None
        self.include_headers = include_headers
        self.pretty_format = pretty_format
        self.frame_io = FrameFileIO()

    def run(self):
        """Export frames in background thread."""
        try:
            self.progress_updated.emit(10, "Preparing export...")

            # Export frames using FrameFileIO
            success = self.frame_io.save_file(
                self.frames,
                self.output_file,
                self.format_name,
                compression=self.compression,
                include_headers=self.include_headers,
                pretty_format=self.pretty_format
            )

            if success:
                frame_count = len(self.frames)
                self.progress_updated.emit(100, f"Exported {frame_count:,} frames")
                message = f"Successfully exported {frame_count:,} frames to {os.path.basename(self.output_file)}"
                self.export_finished.emit(True, message)
            else:
                self.export_finished.emit(False, "Export failed: Unknown error")

        except Exception as e:
            self.export_finished.emit(False, f"Export failed: {str(e)}")