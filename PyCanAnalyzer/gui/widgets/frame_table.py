"""Frame Table Widget - Main CAN Traffic Viewer."""
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
import time


class FrameTable(QTableWidget):
    """Main CAN frame display table with sorting and filtering capabilities."""

    # Column definitions
    COLUMNS = {
        'timestamp': 0,
        'id': 1,
        'ext': 2,
        'rtr': 3,
        'dir': 4,
        'bus': 5,
        'len': 6,
        'data': 7,
        'ascii': 8
    }

    COLUMN_HEADERS = [
        'Timestamp',
        'ID',
        'Ext',
        'RTR',
        'Dir',
        'Bus',
        'Len',
        'Data',
        'ASCII'
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.max_rows = 10000  # Limit to prevent UI slowdown
        self.frames = []
        self.filtered_frames = []
        self.current_filter = None

        self.init_ui()
        self.init_table()

    def init_ui(self):
        """Initialize the table UI."""
        self.setColumnCount(len(self.COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(self.COLUMN_HEADERS)

        # Configure table appearance
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)

        # Set column widths
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)

        # Set reasonable default widths
        self.setColumnWidth(self.COLUMNS['timestamp'], 120)
        self.setColumnWidth(self.COLUMNS['id'], 80)
        self.setColumnWidth(self.COLUMNS['ext'], 40)
        self.setColumnWidth(self.COLUMNS['rtr'], 40)
        self.setColumnWidth(self.COLUMNS['dir'], 40)
        self.setColumnWidth(self.COLUMNS['bus'], 40)
        self.setColumnWidth(self.COLUMNS['len'], 40)
        self.setColumnWidth(self.COLUMNS['data'], 200)
        self.setColumnWidth(self.COLUMNS['ascii'], 100)

        # Enable word wrap for data column
        self.setWordWrap(False)

    def init_table(self):
        """Initialize table data structures."""
        self.clearContents()
        self.setRowCount(0)

    def add_frame(self, frame):
        """Add a new frame to the table.

        Args:
            frame: CAN frame object with attributes: timestamp, id, extended, rtr, data, bus
        """
        # Add to internal storage
        self.frames.append(frame)

        # Maintain max rows limit
        if len(self.frames) > self.max_rows:
            self.frames.pop(0)

        # Update display
        self.update_display()

    def update_display(self):
        """Update the table display with current frames."""
        frames_to_show = self.filtered_frames if self.current_filter else self.frames

        self.setRowCount(len(frames_to_show))

        for row, frame in enumerate(frames_to_show):
            self._populate_row(row, frame)

        # Auto-scroll to bottom for new frames
        if frames_to_show:
            self.scrollToBottom()

    def _populate_row(self, row, frame):
        """Populate a table row with frame data."""
        # Timestamp
        timestamp_str = ".6f"
        self.setItem(row, self.COLUMNS['timestamp'],
                    QTableWidgetItem(timestamp_str))

        # CAN ID (hex format)
        id_str = f"{frame.id:03X}" if frame.id <= 0x7FF else f"{frame.id:08X}"
        id_item = QTableWidgetItem(id_str)
        self.setItem(row, self.COLUMNS['id'], id_item)

        # Extended flag
        ext_str = "X" if getattr(frame, 'extended', False) else ""
        self.setItem(row, self.COLUMNS['ext'], QTableWidgetItem(ext_str))

        # RTR flag
        rtr_str = "R" if getattr(frame, 'rtr', False) else ""
        self.setItem(row, self.COLUMNS['rtr'], QTableWidgetItem(rtr_str))

        # Direction (RX/TX)
        direction = getattr(frame, 'direction', 'RX')
        self.setItem(row, self.COLUMNS['dir'], QTableWidgetItem(direction))

        # Bus number
        bus = getattr(frame, 'bus', 0)
        self.setItem(row, self.COLUMNS['bus'], QTableWidgetItem(str(bus)))

        # Data length
        data_len = len(frame.data) if hasattr(frame, 'data') else 0
        self.setItem(row, self.COLUMNS['len'], QTableWidgetItem(str(data_len)))

        # Data bytes (hex format)
        if hasattr(frame, 'data') and frame.data:
            data_str = ' '.join(f"{b:02X}" for b in frame.data)
        else:
            data_str = ""
        data_item = QTableWidgetItem(data_str)
        data_item.setFont(QFont("Courier New", 10))
        self.setItem(row, self.COLUMNS['data'], data_item)

        # ASCII representation
        if hasattr(frame, 'data') and frame.data:
            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in frame.data)
        else:
            ascii_str = ""
        ascii_item = QTableWidgetItem(ascii_str)
        ascii_item.setFont(QFont("Courier New", 10))
        self.setItem(row, self.COLUMNS['ascii'], ascii_item)

        # Color coding for different frame types
        if getattr(frame, 'rtr', False):
            self._color_row(row, QColor(255, 255, 200))  # Light yellow for RTR
        elif direction == 'TX':
            self._color_row(row, QColor(200, 255, 200))  # Light green for TX

    def _color_row(self, row, color):
        """Apply background color to an entire row."""
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                item.setBackground(color)

    def apply_filter(self, filter_func):
        """Apply a filter function to the frames.

        Args:
            filter_func: Function that takes a frame and returns True if it should be shown
        """
        if filter_func:
            self.filtered_frames = [f for f in self.frames if filter_func(f)]
            self.current_filter = filter_func
        else:
            self.filtered_frames = []
            self.current_filter = None

        self.update_display()

    def clear_filter(self):
        """Remove any active filter."""
        self.apply_filter(None)

    def clear_frames(self):
        """Clear all frames from the table."""
        self.frames.clear()
        self.filtered_frames.clear()
        self.update_display()

    def get_selected_frames(self):
        """Get the currently selected frames.

        Returns:
            List of frame objects that are currently selected
        """
        selected_rows = set()
        for item in self.selectedItems():
            selected_rows.add(item.row())

        frames_to_show = self.filtered_frames if self.current_filter else self.frames
        return [frames_to_show[row] for row in selected_rows if row < len(frames_to_show)]

    def set_max_rows(self, max_rows):
        """Set the maximum number of rows to display.

        Args:
            max_rows: Maximum number of frames to keep in memory
        """
        self.max_rows = max_rows
        # Trim existing frames if needed
        if len(self.frames) > max_rows:
            self.frames = self.frames[-max_rows:]
            self.update_display()