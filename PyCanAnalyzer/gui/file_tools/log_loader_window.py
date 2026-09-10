"""Log Loader Window - Load CAN Log Files."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QListWidget,
                             QProgressBar, QFileDialog, QMessageBox, QGroupBox,
                             QCheckBox, QTextEdit, QSpinBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from storage.storage import FrameFileIO
import os


class LogLoaderWindow(QMainWindow):
    """Window for loading CAN log files into the application."""

    # Signals
    frames_loaded = pyqtSignal(list)  # Emitted when frames are loaded

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame_io = FrameFileIO()
        self.loaded_frames = []
        self.current_file = None

        self.init_ui()
        self.populate_recent_files()

    def init_ui(self):
        """Initialize the log loader UI."""
        self.setWindowTitle("Load CAN Log")
        self.setGeometry(200, 200, 600, 500)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout()

        # File path controls
        path_layout = QHBoxLayout()

        self.file_path_edit = QTextEdit()
        self.file_path_edit.setMaximumHeight(60)
        self.file_path_edit.setPlaceholderText("Select log files to load...")

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_files)

        path_layout.addWidget(self.file_path_edit)
        path_layout.addWidget(browse_button)

        file_layout.addLayout(path_layout)

        # Format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))

        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Auto Detect",
            "CSV",
            "Parquet",
            "ASC (Vector)",
            "BLF (Vector)",
            "TRC (PEAK)",
            "GVRET",
            "Candump",
            "BusMaster"
        ])
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()

        file_layout.addLayout(format_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # Options group
        options_group = QGroupBox("Load Options")
        options_layout = QVBoxLayout()

        self.merge_files_check = QCheckBox("Merge multiple files (sort by timestamp)")
        self.merge_files_check.setChecked(True)

        self.filter_duplicates_check = QCheckBox("Filter duplicate frames")
        self.filter_duplicates_check.setChecked(False)

        self.limit_frames_check = QCheckBox("Limit frame count:")
        self.limit_frames_check.setChecked(False)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1000, 10000000)
        self.limit_spin.setSingleStep(1000)
        self.limit_spin.setValue(100000)
        self.limit_spin.setEnabled(False)

        self.limit_frames_check.stateChanged.connect(
            lambda: self.limit_spin.setEnabled(self.limit_frames_check.isChecked())
        )

        limit_layout = QHBoxLayout()
        limit_layout.addWidget(self.limit_frames_check)
        limit_layout.addWidget(self.limit_spin)
        limit_layout.addStretch()

        options_layout.addWidget(self.merge_files_check)
        options_layout.addWidget(self.filter_duplicates_check)
        options_layout.addLayout(limit_layout)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Progress group
        progress_group = QGroupBox("Loading Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        self.status_label = QLabel("Ready to load files")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Recent files group
        recent_group = QGroupBox("Recent Files")
        recent_layout = QVBoxLayout()

        self.recent_files_list = QListWidget()
        self.recent_files_list.itemDoubleClicked.connect(self.load_recent_file)

        recent_layout.addWidget(self.recent_files_list)
        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.load_button = QPushButton("Load Files")
        self.load_button.clicked.connect(self.load_files)
        self.load_button.setDefault(True)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.load_button)

        layout.addLayout(button_layout)

    def browse_files(self):
        """Open file browser to select log files."""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter(
            "CAN Log Files (*.csv *.parquet *.asc *.blf *.trc *.gvret *.log);;"
            "CSV Files (*.csv);;"
            "Parquet Files (*.parquet);;"
            "Vector ASC (*.asc);;"
            "Vector BLF (*.blf);;"
            "PEAK TRC (*.trc);;"
            "GVRET (*.gvret);;"
            "All Files (*.*)"
        )

        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.file_path_edit.setText('\n'.join(selected_files))

    def load_files(self):
        """Load the selected files."""
        file_text = self.file_path_edit.toPlainText().strip()
        if not file_text:
            QMessageBox.warning(self, "No Files Selected",
                               "Please select one or more log files to load.")
            return

        file_paths = [line.strip() for line in file_text.split('\n') if line.strip()]

        # Validate files exist
        missing_files = [f for f in file_paths if not os.path.exists(f)]
        if missing_files:
            QMessageBox.warning(self, "Files Not Found",
                               f"The following files were not found:\n" +
                               '\n'.join(missing_files))
            return

        # Start loading in background thread
        self.load_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Loading files...")

        self.loader_thread = LogLoaderThread(
            file_paths=file_paths,
            format_name=self.format_combo.currentText(),
            merge_files=self.merge_files_check.isChecked(),
            filter_duplicates=self.filter_duplicates_check.isChecked(),
            max_frames=self.limit_spin.value() if self.limit_frames_check.isChecked() else None
        )

        self.loader_thread.progress_updated.connect(self.update_progress)
        self.loader_thread.loading_finished.connect(self.on_loading_finished)
        self.loader_thread.start()

    def update_progress(self, progress, status):
        """Update loading progress."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(status)

    def on_loading_finished(self, frames, error_message):
        """Handle loading completion."""
        self.load_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if error_message:
            QMessageBox.critical(self, "Loading Error", error_message)
            self.status_label.setText("Loading failed")
        else:
            self.loaded_frames = frames
            frame_count = len(frames)
            self.status_label.setText(f"Loaded {frame_count:,} frames successfully")

            # Add to recent files
            self.add_to_recent_files()

            # Emit signal with loaded frames
            self.frames_loaded.emit(frames)

            QMessageBox.information(
                self, "Loading Complete",
                f"Successfully loaded {frame_count:,} frames from {len(self.loader_thread.file_paths)} file(s)."
            )

    def populate_recent_files(self):
        """Populate the recent files list."""
        # This would typically load from application settings
        # For now, show some example entries
        recent_files = [
            "/path/to/recent/log1.csv",
            "/path/to/recent/log2.asc",
            "/path/to/recent/capture.parquet"
        ]

        self.recent_files_list.clear()
        for file_path in recent_files:
            if os.path.exists(file_path):
                self.recent_files_list.addItem(os.path.basename(file_path))

    def load_recent_file(self, item):
        """Load a file from the recent files list."""
        # This would need to map back to full paths
        # For now, just show a message
        QMessageBox.information(self, "Recent File",
                               f"Would load: {item.text()}")

    def add_to_recent_files(self):
        """Add loaded files to recent files list."""
        # Implementation would save to application settings
        pass


class LogLoaderThread(QThread):
    """Background thread for loading log files."""

    # Signals
    progress_updated = pyqtSignal(int, str)  # progress (0-100), status message
    loading_finished = pyqtSignal(list, str)  # frames, error_message

    def __init__(self, file_paths, format_name, merge_files=True,
                 filter_duplicates=False, max_frames=None):
        super().__init__()
        self.file_paths = file_paths
        self.format_name = format_name
        self.merge_files = merge_files
        self.filter_duplicates = filter_duplicates
        self.max_frames = max_frames
        self.frame_io = FrameFileIO()

    def run(self):
        """Load files in background thread."""
        try:
            all_frames = []
            total_files = len(self.file_paths)

            for i, file_path in enumerate(self.file_paths):
                progress = int((i / total_files) * 100)
                self.progress_updated.emit(progress, f"Loading {os.path.basename(file_path)}...")

                # Load frames from file
                frames = self.frame_io.load_file(file_path, self.format_name)

                if frames:
                    all_frames.extend(frames)

                # Check frame limit
                if self.max_frames and len(all_frames) >= self.max_frames:
                    all_frames = all_frames[:self.max_frames]
                    break

            # Post-processing
            self.progress_updated.emit(90, "Processing frames...")

            if self.merge_files and len(self.file_paths) > 1:
                # Sort by timestamp
                all_frames.sort(key=lambda f: getattr(f, 'timestamp', 0))

            if self.filter_duplicates:
                # Remove duplicate frames (same ID, data, timestamp within 1ms)
                filtered_frames = []
                seen = set()

                for frame in all_frames:
                    key = (frame.id, tuple(frame.data) if hasattr(frame, 'data') else (),
                          int(getattr(frame, 'timestamp', 0) * 1000))  # Convert to ms

                    if key not in seen:
                        seen.add(key)
                        filtered_frames.append(frame)

                all_frames = filtered_frames

            self.progress_updated.emit(100, "Loading complete")
            self.loading_finished.emit(all_frames, "")

        except Exception as e:
            self.loading_finished.emit([], f"Error loading files: {str(e)}")