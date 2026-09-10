"""Fuzzy Search Window - Find Signals Matching Patterns."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QSplitter, QMessageBox,
                             QTextEdit, QSpinBox, QComboBox, QLineEdit,
                             QCheckBox, QProgressBar, QRadioButton,
                             QButtonGroup)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
import time
import collections
import re
import difflib


class FuzzySearchWindow(QMainWindow):
    """Window for fuzzy searching CAN signals that match expected patterns."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.search_results = []

        self.is_searching = False

        self.init_ui()

    def init_ui(self):
        """Initialize the fuzzy search UI."""
        self.setWindowTitle("CAN Fuzzy Signal Search")
        self.setGeometry(200, 200, 1400, 900)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)

        # Control panel
        self.create_control_panel(layout)

        # Results splitter
        results_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(results_splitter)

        # Left - Search results
        self.create_results_panel(results_splitter)

        # Right - Pattern details
        self.create_details_panel(results_splitter)

        results_splitter.setSizes([700, 700])

        # Status bar
        self.status_label = QLabel("Ready - Define search pattern and run fuzzy search")
        layout.addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QVBoxLayout(panel)

        # Search pattern
        pattern_group = QGroupBox("Search Pattern")
        pattern_layout = QVBoxLayout()

        # Pattern type selection
        type_group = QWidget()
        type_layout = QHBoxLayout(type_group)

        self.pattern_type_group = QButtonGroup()

        self.exact_radio = QRadioButton("Exact Match")
        self.fuzzy_radio = QRadioButton("Fuzzy Match")
        self.regex_radio = QRadioButton("Regular Expression")
        self.bit_pattern_radio = QRadioButton("Bit Pattern")

        self.fuzzy_radio.setChecked(True)  # Default

        self.pattern_type_group.addButton(self.exact_radio)
        self.pattern_type_group.addButton(self.fuzzy_radio)
        self.pattern_type_group.addButton(self.regex_radio)
        self.pattern_type_group.addButton(self.bit_pattern_radio)

        type_layout.addWidget(self.exact_radio)
        type_layout.addWidget(self.fuzzy_radio)
        type_layout.addWidget(self.regex_radio)
        type_layout.addWidget(self.bit_pattern_radio)
        type_layout.addStretch()

        # Pattern input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Pattern:"))
        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText("Enter search pattern (hex bytes, e.g., '12 34 56')")
        input_layout.addWidget(self.pattern_edit)

        pattern_layout.addWidget(type_group)
        pattern_layout.addLayout(input_layout)

        pattern_group.setLayout(pattern_layout)
        control_layout.addWidget(pattern_group)

        # Search settings
        settings_group = QGroupBox("Search Settings")
        settings_layout = QVBoxLayout()

        # Search scope
        scope_layout = QHBoxLayout()
        scope_layout.addWidget(QLabel("Search In:"))

        self.search_data_check = QCheckBox("Frame Data")
        self.search_data_check.setChecked(True)

        self.search_id_check = QCheckBox("CAN ID")
        self.search_id_check.setChecked(False)

        scope_layout.addWidget(self.search_data_check)
        scope_layout.addWidget(self.search_id_check)
        scope_layout.addStretch()

        # Fuzzy settings
        fuzzy_layout = QHBoxLayout()
        fuzzy_layout.addWidget(QLabel("Similarity Threshold:"))
        self.similarity_spin = QSpinBox()
        self.similarity_spin.setRange(1, 100)
        self.similarity_spin.setValue(70)
        self.similarity_spin.setSuffix("%")
        fuzzy_layout.addWidget(self.similarity_spin)

        # Max results
        results_layout = QHBoxLayout()
        results_layout.addWidget(QLabel("Max Results:"))
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(1, 1000)
        self.max_results_spin.setValue(100)
        results_layout.addWidget(self.max_results_spin)

        settings_layout.addLayout(scope_layout)
        settings_layout.addLayout(fuzzy_layout)
        settings_layout.addLayout(results_layout)

        settings_group.setLayout(settings_layout)
        control_layout.addWidget(settings_group)

        # Search controls
        action_group = QGroupBox("Search")
        action_layout = QHBoxLayout()

        self.search_button = QPushButton("Run Fuzzy Search")
        self.search_button.clicked.connect(self.run_fuzzy_search)

        self.stop_search_button = QPushButton("Stop Search")
        self.stop_search_button.setEnabled(False)
        self.stop_search_button.clicked.connect(self.stop_search)

        self.clear_results_button = QPushButton("Clear Results")
        self.clear_results_button.clicked.connect(self.clear_results)

        action_layout.addWidget(self.search_button)
        action_layout.addWidget(self.stop_search_button)
        action_layout.addWidget(self.clear_results_button)
        action_layout.addStretch()

        action_group.setLayout(action_layout)
        control_layout.addWidget(action_group)

        parent.addWidget(panel)

    def create_results_panel(self, parent):
        """Create the search results panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Progress
        progress_group = QGroupBox("Search Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.progress_label = QLabel("Ready to search")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Results table
        results_group = QGroupBox("Search Results")
        results_layout = QVBoxLayout()

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "CAN ID", "Frame Data", "Match Type", "Similarity", "Match Details"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.itemSelectionChanged.connect(self.on_result_selected)

        results_layout.addWidget(self.results_table)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        parent.addWidget(panel)

    def create_details_panel(self, parent):
        """Create the pattern details panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Match details
        details_group = QGroupBox("Match Details")
        details_layout = QVBoxLayout()

        self.match_details_text = QTextEdit()
        self.match_details_text.setReadOnly(True)
        self.match_details_text.setFont(QFont("Courier New", 10))

        details_layout.addWidget(self.match_details_text)
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        # Pattern analysis
        analysis_group = QGroupBox("Pattern Analysis")
        analysis_layout = QVBoxLayout()

        self.pattern_analysis_text = QTextEdit()
        self.pattern_analysis_text.setReadOnly(True)

        analysis_layout.addWidget(self.pattern_analysis_text)
        analysis_group.setLayout(analysis_layout)
        layout.addWidget(analysis_group)

        # Similar patterns
        similar_group = QGroupBox("Similar Patterns Found")
        similar_layout = QVBoxLayout()

        self.similar_patterns_table = QTableWidget()
        self.similar_patterns_table.setColumnCount(3)
        self.similar_patterns_table.setHorizontalHeaderLabels([
            "Pattern", "Count", "CAN IDs"
        ])
        self.similar_patterns_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        similar_layout.addWidget(self.similar_patterns_table)
        similar_group.setLayout(similar_layout)
        layout.addWidget(similar_group)

        parent.addWidget(panel)

    def run_fuzzy_search(self):
        """Run the fuzzy search."""
        pattern = self.pattern_edit.text().strip()
        if not pattern:
            QMessageBox.warning(self, "No Pattern",
                               "Please enter a search pattern.")
            return

        if not self.frames:
            QMessageBox.warning(self, "No Data",
                               "No frame data available for search.")
            return

        if not (self.search_data_check.isChecked() or self.search_id_check.isChecked()):
            QMessageBox.warning(self, "No Search Scope",
                               "Please select what to search in (Frame Data or CAN ID).")
            return

        self.is_searching = True
        self.search_button.setEnabled(False)
        self.stop_search_button.setEnabled(True)

        self.status_label.setText("Running fuzzy search...")

        # Determine pattern type
        if self.exact_radio.isChecked():
            pattern_type = "exact"
        elif self.fuzzy_radio.isChecked():
            pattern_type = "fuzzy"
        elif self.regex_radio.isChecked():
            pattern_type = "regex"
        else:  # bit_pattern_radio
            pattern_type = "bit_pattern"

        # Run search in background thread
        self.search_thread = FuzzySearchThread(
            self.frames,
            pattern,
            pattern_type,
            self.similarity_spin.value() / 100.0,
            self.max_results_spin.value(),
            self.search_data_check.isChecked(),
            self.search_id_check.isChecked()
        )

        self.search_thread.progress_update.connect(self.on_progress_update)
        self.search_thread.search_complete.connect(self.on_search_complete)
        self.search_thread.start()

    def stop_search(self):
        """Stop the current search."""
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.stop()

        self.is_searching = False
        self.search_button.setEnabled(True)
        self.stop_search_button.setEnabled(False)
        self.status_label.setText("Search stopped")

    def on_progress_update(self, progress, message):
        """Handle progress updates."""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)

    def on_search_complete(self, results):
        """Handle search completion."""
        self.is_searching = False
        self.search_button.setEnabled(True)
        self.stop_search_button.setEnabled(False)

        self.search_results = results
        self.display_results(results)

        result_count = len(results)
        self.status_label.setText(f"Fuzzy search complete: {result_count} matches found")

    def display_results(self, results):
        """Display the search results."""
        self.results_table.setRowCount(len(results))

        for row, result in enumerate(results):
            # CAN ID
            id_item = QTableWidgetItem(f"0x{result['can_id']:03X}")
            self.results_table.setItem(row, 0, id_item)

            # Frame data
            if hasattr(result.get('frame', {}), 'data') and result['frame'].data:
                data_str = ' '.join(f'{b:02X}' for b in result['frame'].data)
            else:
                data_str = "N/A"
            data_item = QTableWidgetItem(data_str)
            self.results_table.setItem(row, 1, data_item)

            # Match type
            match_type_item = QTableWidgetItem(result['match_type'])
            self.results_table.setItem(row, 2, match_type_item)

            # Similarity
            similarity = result.get('similarity', 0)
            sim_item = QTableWidgetItem(f"{similarity:.1%}")
            # Color code similarity
            if similarity >= 0.9:
                sim_item.setBackground(QColor(200, 255, 200))
            elif similarity >= 0.7:
                sim_item.setBackground(QColor(255, 255, 200))
            else:
                sim_item.setBackground(QColor(255, 200, 200))
            self.results_table.setItem(row, 3, sim_item)

            # Match details
            details = result.get('details', '')
            details_item = QTableWidgetItem(details)
            self.results_table.setItem(row, 4, details_item)

    def on_result_selected(self):
        """Handle result selection."""
        current_row = self.results_table.currentRow()
        if current_row >= 0 and current_row < len(self.search_results):
            result = self.search_results[current_row]
            self.show_match_details(result)

    def show_match_details(self, result):
        """Show detailed information about the match."""
        details = f"Match Details\n\n"
        details += f"CAN ID: 0x{result['can_id']:03X}\n"
        details += f"Match Type: {result['match_type']}\n"
        details += f"Similarity: {result.get('similarity', 0):.1%}\n\n"

        if 'frame' in result and result['frame']:
            frame = result['frame']
            details += f"Frame Information:\n"
            if hasattr(frame, 'timestamp'):
                details += f"  Timestamp: {frame.timestamp}\n"
            if hasattr(frame, 'data') and frame.data:
                details += f"  Data: {' '.join(f'{b:02X}' for b in frame.data)}\n"
                details += f"  ASCII: {''.join(chr(b) if 32 <= b <= 126 else '.' for b in frame.data)}\n"
            details += "\n"

        # Show pattern comparison
        if 'pattern_comparison' in result:
            details += f"Pattern Comparison:\n{result['pattern_comparison']}\n"

        self.match_details_text.setText(details)

        # Update pattern analysis
        self.analyze_pattern(result)

    def analyze_pattern(self, result):
        """Analyze the pattern and find similar patterns."""
        analysis = "Pattern Analysis\n\n"

        # Analyze the matched pattern
        if 'frame' in result and result['frame'] and hasattr(result['frame'], 'data'):
            data = result['frame'].data
            analysis += f"Matched Data: {' '.join(f'{b:02X}' for b in data)}\n\n"

            # Bit analysis
            analysis += "Bit Analysis:\n"
            for i, byte in enumerate(data):
                analysis += f"  Byte {i}: {byte:08b} (0x{byte:02X})\n"
            analysis += "\n"

            # Statistical analysis
            if len(data) > 1:
                analysis += "Statistical Properties:\n"
                analysis += f"  Length: {len(data)} bytes\n"
                analysis += f"  Sum: {sum(data)}\n"
                analysis += f"  Mean: {sum(data)/len(data):.2f}\n"
                analysis += f"  Min: {min(data)} (0x{min(data):02X})\n"
                analysis += f"  Max: {max(data)} (0x{max(data):02X})\n"
                analysis += f"  Range: {max(data) - min(data)}\n"

        self.pattern_analysis_text.setText(analysis)

        # Find similar patterns
        self.find_similar_patterns(result)

    def find_similar_patterns(self, result):
        """Find other patterns similar to the matched one."""
        if not result.get('frame') or not hasattr(result['frame'], 'data'):
            self.similar_patterns_table.setRowCount(0)
            return

        target_data = result['frame'].data
        target_pattern = tuple(target_data)

        # Group frames by data pattern
        pattern_counts = collections.Counter()
        pattern_ids = collections.defaultdict(set)

        for frame in self.frames:
            if hasattr(frame, 'data') and frame.data:
                pattern = tuple(frame.data)
                pattern_counts[pattern] += 1
                pattern_ids[pattern].add(frame.id)

        # Find similar patterns
        similar_patterns = []
        for pattern, count in pattern_counts.most_common(20):  # Top 20 patterns
            if pattern == target_pattern:
                continue  # Skip the exact match

            # Calculate similarity
            similarity = self.calculate_pattern_similarity(target_data, list(pattern))
            if similarity >= 0.5:  # At least 50% similar
                similar_patterns.append({
                    'pattern': pattern,
                    'count': count,
                    'similarity': similarity,
                    'can_ids': sorted(list(pattern_ids[pattern]))
                })

        # Sort by similarity
        similar_patterns.sort(key=lambda x: x['similarity'], reverse=True)

        # Display top 10
        self.similar_patterns_table.setRowCount(min(10, len(similar_patterns)))

        for row, pattern_info in enumerate(similar_patterns[:10]):
            # Pattern
            pattern_str = ' '.join(f'{b:02X}' for b in pattern_info['pattern'])
            pattern_item = QTableWidgetItem(pattern_str)
            self.similar_patterns_table.setItem(row, 0, pattern_item)

            # Count
            count_item = QTableWidgetItem(str(pattern_info['count']))
            self.similar_patterns_table.setItem(row, 1, count_item)

            # CAN IDs
            ids_str = ', '.join(f'0x{id:03X}' for id in pattern_info['can_ids'][:5])  # Show first 5
            if len(pattern_info['can_ids']) > 5:
                ids_str += f" (+{len(pattern_info['can_ids']) - 5} more)"
            ids_item = QTableWidgetItem(ids_str)
            self.similar_patterns_table.setItem(row, 2, ids_item)

    def calculate_pattern_similarity(self, pattern1, pattern2):
        """Calculate similarity between two data patterns."""
        if not pattern1 or not pattern2:
            return 0.0

        # Use sequence matcher for similarity
        seq1 = ''.join(f'{b:02X}' for b in pattern1)
        seq2 = ''.join(f'{b:02X}' for b in pattern2)

        return difflib.SequenceMatcher(None, seq1, seq2).ratio()

    def clear_results(self):
        """Clear all results."""
        self.search_results = []
        self.results_table.setRowCount(0)
        self.match_details_text.clear()
        self.pattern_analysis_text.clear()
        self.similar_patterns_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Ready to search")
        self.status_label.setText("Results cleared")

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []


class FuzzySearchThread(QThread):
    """Background thread for fuzzy search."""

    progress_update = pyqtSignal(int, str)
    search_complete = pyqtSignal(list)

    def __init__(self, frames, pattern, pattern_type, similarity_threshold,
                 max_results, search_data, search_id):
        super().__init__()
        self.frames = frames
        self.pattern = pattern
        self.pattern_type = pattern_type
        self.similarity_threshold = similarity_threshold
        self.max_results = max_results
        self.search_data = search_data
        self.search_id = search_id
        self.stop_requested = False

    def stop(self):
        """Request thread stop."""
        self.stop_requested = True

    def run(self):
        """Run the fuzzy search."""
        results = []
        total_frames = len(self.frames)

        # Parse pattern based on type
        parsed_pattern = self.parse_pattern()

        if not parsed_pattern:
            self.search_complete.emit(results)
            return

        for i, frame in enumerate(self.frames):
            if self.stop_requested:
                break

            # Update progress
            if i % 100 == 0:
                progress = int(100 * i / total_frames)
                self.progress_update.emit(progress, f"Searching frame {i}/{total_frames}")

            # Search in frame data
            if self.search_data and hasattr(frame, 'data') and frame.data:
                match = self.search_in_data(frame, parsed_pattern)
                if match:
                    results.append(match)
                    if len(results) >= self.max_results:
                        break

            # Search in CAN ID
            if self.search_id and hasattr(frame, 'id'):
                match = self.search_in_id(frame, parsed_pattern)
                if match:
                    results.append(match)
                    if len(results) >= self.max_results:
                        break

        self.search_complete.emit(results)

    def parse_pattern(self):
        """Parse the search pattern based on type."""
        if self.pattern_type == "exact":
            # Parse hex bytes
            try:
                bytes_list = []
                for part in self.pattern.split():
                    if part.startswith('0x'):
                        bytes_list.append(int(part, 16))
                    else:
                        bytes_list.append(int(part, 16))
                return {'type': 'exact', 'data': bytes_list}
            except ValueError:
                return None

        elif self.pattern_type == "fuzzy":
            # Parse as hex string for fuzzy matching
            try:
                clean_pattern = self.pattern.replace(' ', '').replace('0x', '')
                if len(clean_pattern) % 2 != 0:
                    clean_pattern = '0' + clean_pattern
                bytes_list = [int(clean_pattern[i:i+2], 16) for i in range(0, len(clean_pattern), 2)]
                return {'type': 'fuzzy', 'data': bytes_list}
            except ValueError:
                return None

        elif self.pattern_type == "regex":
            # Compile regex
            try:
                # Convert hex pattern to regex
                hex_pattern = self.pattern.replace(' ', '')
                regex = re.compile(hex_pattern, re.IGNORECASE)
                return {'type': 'regex', 'pattern': regex}
            except re.error:
                return None

        elif self.pattern_type == "bit_pattern":
            # Parse bit pattern
            try:
                bit_string = self.pattern.replace(' ', '')
                if not all(c in '01' for c in bit_string):
                    return None
                return {'type': 'bit_pattern', 'bits': bit_string}
            except:
                return None

        return None

    def search_in_data(self, frame, parsed_pattern):
        """Search for pattern in frame data."""
        if parsed_pattern['type'] == 'exact':
            if frame.data == parsed_pattern['data']:
                return {
                    'can_id': frame.id,
                    'frame': frame,
                    'match_type': 'Exact Data Match',
                    'similarity': 1.0,
                    'details': f"Exact match: {' '.join(f'{b:02X}' for b in parsed_pattern['data'])}"
                }

        elif parsed_pattern['type'] == 'fuzzy':
            similarity = self.calculate_data_similarity(frame.data, parsed_pattern['data'])
            if similarity >= self.similarity_threshold:
                return {
                    'can_id': frame.id,
                    'frame': frame,
                    'match_type': 'Fuzzy Data Match',
                    'similarity': similarity,
                    'details': f"Similarity: {similarity:.1%}"
                }

        elif parsed_pattern['type'] == 'regex':
            data_str = ''.join(f'{b:02X}' for b in frame.data)
            if parsed_pattern['pattern'].search(data_str):
                return {
                    'can_id': frame.id,
                    'frame': frame,
                    'match_type': 'Regex Data Match',
                    'similarity': 1.0,
                    'details': f"Regex match: {self.pattern}"
                }

        elif parsed_pattern['type'] == 'bit_pattern':
            frame_bits = ''.join(f'{b:08b}' for b in frame.data)
            if parsed_pattern['bits'] in frame_bits:
                return {
                    'can_id': frame.id,
                    'frame': frame,
                    'match_type': 'Bit Pattern Match',
                    'similarity': 1.0,
                    'details': f"Bit pattern found: {parsed_pattern['bits']}"
                }

        return None

    def search_in_id(self, frame, parsed_pattern):
        """Search for pattern in CAN ID."""
        id_str = f"{frame.id:03X}"

        if parsed_pattern['type'] == 'exact':
            if str(frame.id) == str(parsed_pattern.get('id_value', '')):
                return {
                    'can_id': frame.id,
                    'frame': frame,
                    'match_type': 'Exact ID Match',
                    'similarity': 1.0,
                    'details': f"Exact ID match: {frame.id}"
                }

        elif parsed_pattern['type'] == 'regex':
            if parsed_pattern['pattern'].search(id_str):
                return {
                    'can_id': frame.id,
                    'frame': frame,
                    'match_type': 'Regex ID Match',
                    'similarity': 1.0,
                    'details': f"Regex ID match: {self.pattern}"
                }

        return None

    def calculate_data_similarity(self, data1, data2):
        """Calculate similarity between two data arrays."""
        if not data1 or not data2:
            return 0.0

        # Use sequence matcher on hex strings
        str1 = ''.join(f'{b:02X}' for b in data1)
        str2 = ''.join(f'{b:02X}' for b in data2)

        return difflib.SequenceMatcher(None, str1, str2).ratio()