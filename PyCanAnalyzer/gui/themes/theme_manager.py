"""Theme Manager - Handles light and dark theme switching for PyCANAnalyzer."""

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QPalette, QColor


class ThemeManager(QObject):
    """Manages application-wide theme switching between light and dark modes."""

    theme_changed = pyqtSignal(str)  # Emits "dark" or "light"

    DARK = "dark"
    LIGHT = "light"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_theme = self.DARK

    @property
    def current_theme(self):
        return self._current_theme

    def is_dark(self):
        return self._current_theme == self.DARK

    def is_light(self):
        return self._current_theme == self.LIGHT

    def toggle_theme(self):
        """Switch between dark and light themes."""
        if self._current_theme == self.DARK:
            self.set_theme(self.LIGHT)
        else:
            self.set_theme(self.DARK)

    def set_theme(self, theme_name):
        """Apply the specified theme to the entire application."""
        self._current_theme = theme_name
        app = QApplication.instance()
        if app is None:
            return

        if theme_name == self.DARK:
            app.setStyleSheet(self._dark_stylesheet())
            self._apply_dark_palette(app)
        else:
            app.setStyleSheet(self._light_stylesheet())
            self._apply_light_palette(app)

        self.theme_changed.emit(theme_name)

    def _apply_dark_palette(self, app):
        """Set dark color palette."""
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#1a1a2e"))
        palette.setColor(QPalette.WindowText, QColor("#dddddd"))
        palette.setColor(QPalette.Base, QColor("#0d0d1a"))
        palette.setColor(QPalette.AlternateBase, QColor("#141428"))
        palette.setColor(QPalette.ToolTipBase, QColor("#2a2a3e"))
        palette.setColor(QPalette.ToolTipText, QColor("#dddddd"))
        palette.setColor(QPalette.Text, QColor("#dddddd"))
        palette.setColor(QPalette.Button, QColor("#2a2a3e"))
        palette.setColor(QPalette.ButtonText, QColor("#dddddd"))
        palette.setColor(QPalette.BrightText, QColor("#ff4444"))
        palette.setColor(QPalette.Link, QColor("#3498db"))
        palette.setColor(QPalette.Highlight, QColor("#2980b9"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#666666"))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#666666"))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#666666"))
        app.setPalette(palette)

    def _apply_light_palette(self, app):
        """Set light color palette."""
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f0f0f0"))
        palette.setColor(QPalette.WindowText, QColor("#1a1a1a"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f5f5f5"))
        palette.setColor(QPalette.ToolTipBase, QColor("#ffffdc"))
        palette.setColor(QPalette.ToolTipText, QColor("#1a1a1a"))
        palette.setColor(QPalette.Text, QColor("#1a1a1a"))
        palette.setColor(QPalette.Button, QColor("#e0e0e0"))
        palette.setColor(QPalette.ButtonText, QColor("#1a1a1a"))
        palette.setColor(QPalette.BrightText, QColor("#cc0000"))
        palette.setColor(QPalette.Link, QColor("#2471a3"))
        palette.setColor(QPalette.Highlight, QColor("#3498db"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#aaaaaa"))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#aaaaaa"))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#aaaaaa"))
        app.setPalette(palette)

    def _dark_stylesheet(self):
        return """
            /* ═══════════════════════════════════════ */
            /*          DARK THEME STYLESHEET          */
            /* ═══════════════════════════════════════ */

            QMainWindow {
                background-color: #1a1a2e;
            }

            /* ── Menu Bar ── */
            QMenuBar {
                background-color: #16162a;
                color: #cccccc;
                border-bottom: 1px solid #333;
                padding: 2px;
                font-size: 12px;
            }
            QMenuBar::item {
                padding: 4px 10px;
                border-radius: 3px;
            }
            QMenuBar::item:selected {
                background-color: #2980b9;
                color: white;
            }
            QMenu {
                background-color: #1e1e32;
                color: #cccccc;
                border: 1px solid #444;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 30px 5px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #2980b9;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #444;
                margin: 4px 8px;
            }

            /* ── Status Bar ── */
            QStatusBar {
                background-color: #16162a;
                color: #888888;
                border-top: 1px solid #333;
                font-size: 11px;
                padding: 2px;
            }

            /* ── Splitter ── */
            QSplitter::handle {
                background-color: #333;
                width: 3px;
                height: 3px;
            }
            QSplitter::handle:hover {
                background-color: #2980b9;
            }

            /* ── Table Widget ── */
            QTableWidget {
                border: 1px solid #333;
                gridline-color: #2a2a3e;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                background-color: #0d0d1a;
                alternate-background-color: #141428;
                color: #dddddd;
                selection-background-color: #2980b9;
                selection-color: white;
            }
            QTableWidget::item:selected {
                background-color: #2980b9;
                color: white;
            }
            QHeaderView::section {
                background-color: #1a1a2e;
                color: #cccccc;
                padding: 4px 8px;
                border: 1px solid #333;
                font-weight: bold;
                font-size: 11px;
            }
            QTableWidget QTableCornerButton::section {
                background-color: #1a1a2e;
                border: 1px solid #333;
            }

            /* ── Text Edit ── */
            QTextEdit {
                border: 1px solid #444;
                border-radius: 3px;
                padding: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                background-color: #0d0d1a;
                color: #dddddd;
            }

            /* ── Line Edit ── */
            QLineEdit {
                padding: 4px 8px;
                border: 1px solid #444;
                border-radius: 3px;
                background-color: #2a2a3e;
                color: #dddddd;
                font-size: 12px;
                selection-background-color: #2980b9;
            }
            QLineEdit:focus {
                border: 1px solid #2980b9;
            }
            QLineEdit:disabled {
                background-color: #1a1a2e;
                color: #666666;
            }

            /* ── Combo Box ── */
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #444;
                border-radius: 3px;
                background-color: #2a2a3e;
                color: #dddddd;
                font-size: 12px;
                min-height: 20px;
            }
            QComboBox:hover {
                border: 1px solid #2980b9;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #888;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a3e;
                color: #dddddd;
                border: 1px solid #444;
                selection-background-color: #2980b9;
                selection-color: white;
            }

            /* ── Check Box ── */
            QCheckBox {
                color: #dddddd;
                font-size: 12px;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #2a2a3e;
            }
            QCheckBox::indicator:checked {
                background-color: #2980b9;
                border-color: #2980b9;
            }
            QCheckBox::indicator:hover {
                border-color: #2980b9;
            }

            /* ── Spin Box ── */
            QSpinBox {
                padding: 3px 6px;
                border: 1px solid #444;
                border-radius: 3px;
                background-color: #2a2a3e;
                color: #dddddd;
            }

            /* ── Group Box ── */
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #cccccc;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: #cccccc;
            }

            /* ── Push Button ── */
            QPushButton {
                padding: 5px 14px;
                border: 1px solid #444;
                border-radius: 3px;
                background-color: #2a2a3e;
                color: #dddddd;
                font-size: 12px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #3a3a4e;
                border-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1a1a2e;
            }
            QPushButton:disabled {
                background-color: #1e1e2e;
                color: #555555;
                border-color: #333;
            }

            /* ── Tab Widget ── */
            QTabWidget::pane {
                border: 1px solid #444;
                border-radius: 4px;
                background-color: #1a1a2e;
            }
            QTabBar::tab {
                background-color: #16162a;
                color: #999999;
                padding: 8px 18px;
                border: 1px solid #333;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #1a1a2e;
                color: #dddddd;
                border-bottom: 2px solid #2980b9;
            }
            QTabBar::tab:hover:!selected {
                background-color: #222238;
                color: #bbbbbb;
            }

            /* ── Scroll Bar ── */
            QScrollBar:vertical {
                background-color: #1a1a2e;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #444;
                border-radius: 4px;
                min-height: 30px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #555;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #1a1a2e;
                height: 12px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background-color: #444;
                border-radius: 4px;
                min-width: 30px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #555;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }

            /* ── Label ── */
            QLabel {
                color: #dddddd;
                font-size: 12px;
            }

            /* ── Dialog ── */
            QDialog {
                background-color: #1a1a2e;
            }

            /* ── Tool Tip ── */
            QToolTip {
                background-color: #2a2a3e;
                color: #dddddd;
                border: 1px solid #555;
                padding: 4px;
                font-size: 11px;
            }

            /* ── Frame ── */
            QFrame {
                color: #dddddd;
            }

            /* ── Message Box ── */
            QMessageBox {
                background-color: #1a1a2e;
            }
            QMessageBox QLabel {
                color: #dddddd;
            }
        """

    def _light_stylesheet(self):
        return """
            /* ═══════════════════════════════════════ */
            /*         LIGHT THEME STYLESHEET          */
            /* ═══════════════════════════════════════ */

            QMainWindow {
                background-color: #f0f0f0;
            }

            /* ── Menu Bar ── */
            QMenuBar {
                background-color: #e8e8e8;
                color: #1a1a1a;
                border-bottom: 1px solid #c0c0c0;
                padding: 2px;
                font-size: 12px;
            }
            QMenuBar::item {
                padding: 4px 10px;
                border-radius: 3px;
            }
            QMenuBar::item:selected {
                background-color: #3498db;
                color: white;
            }
            QMenu {
                background-color: #ffffff;
                color: #1a1a1a;
                border: 1px solid #c0c0c0;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 30px 5px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #3498db;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #d0d0d0;
                margin: 4px 8px;
            }

            /* ── Status Bar ── */
            QStatusBar {
                background-color: #e0e0e0;
                color: #555555;
                border-top: 1px solid #c0c0c0;
                font-size: 11px;
                padding: 2px;
            }

            /* ── Splitter ── */
            QSplitter::handle {
                background-color: #c0c0c0;
                width: 3px;
                height: 3px;
            }
            QSplitter::handle:hover {
                background-color: #3498db;
            }

            /* ── Table Widget ── */
            QTableWidget {
                border: 1px solid #c0c0c0;
                gridline-color: #e0e0e0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                background-color: #ffffff;
                alternate-background-color: #f8f8f8;
                color: #1a1a1a;
                selection-background-color: #3498db;
                selection-color: white;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                color: #333333;
                padding: 4px 8px;
                border: 1px solid #c0c0c0;
                font-weight: bold;
                font-size: 11px;
            }
            QTableWidget QTableCornerButton::section {
                background-color: #e8e8e8;
                border: 1px solid #c0c0c0;
            }

            /* ── Text Edit ── */
            QTextEdit {
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                padding: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                background-color: #ffffff;
                color: #1a1a1a;
            }

            /* ── Line Edit ── */
            QLineEdit {
                padding: 4px 8px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: #ffffff;
                color: #1a1a1a;
                font-size: 12px;
                selection-background-color: #3498db;
            }
            QLineEdit:focus {
                border: 1px solid #3498db;
            }
            QLineEdit:disabled {
                background-color: #e8e8e8;
                color: #999999;
            }

            /* ── Combo Box ── */
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: #ffffff;
                color: #1a1a1a;
                font-size: 12px;
                min-height: 20px;
            }
            QComboBox:hover {
                border: 1px solid #3498db;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #666;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1a1a1a;
                border: 1px solid #c0c0c0;
                selection-background-color: #3498db;
                selection-color: white;
            }

            /* ── Check Box ── */
            QCheckBox {
                color: #1a1a1a;
                font-size: 12px;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #aaa;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #3498db;
            }
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }

            /* ── Spin Box ── */
            QSpinBox {
                padding: 3px 6px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: #ffffff;
                color: #1a1a1a;
            }

            /* ── Group Box ── */
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #333333;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: #333333;
            }

            /* ── Push Button ── */
            QPushButton {
                padding: 5px 14px;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                background-color: #e8e8e8;
                color: #1a1a1a;
                font-size: 12px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
                border-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
            QPushButton:disabled {
                background-color: #e8e8e8;
                color: #aaaaaa;
                border-color: #d0d0d0;
            }

            /* ── Tab Widget ── */
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                background-color: #f5f5f5;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                color: #666666;
                padding: 8px 18px;
                border: 1px solid #c0c0c0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #f5f5f5;
                color: #1a1a1a;
                border-bottom: 2px solid #3498db;
            }
            QTabBar::tab:hover:!selected {
                background-color: #e8e8e8;
                color: #333333;
            }

            /* ── Scroll Bar ── */
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 4px;
                min-height: 30px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #f0f0f0;
                height: 12px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background-color: #c0c0c0;
                border-radius: 4px;
                min-width: 30px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #a0a0a0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }

            /* ── Label ── */
            QLabel {
                color: #1a1a1a;
                font-size: 12px;
            }

            /* ── Dialog ── */
            QDialog {
                background-color: #f0f0f0;
            }

            /* ── Tool Tip ── */
            QToolTip {
                background-color: #ffffdc;
                color: #1a1a1a;
                border: 1px solid #c0c0c0;
                padding: 4px;
                font-size: 11px;
            }

            /* ── Frame ── */
            QFrame {
                color: #1a1a1a;
            }

            /* ── Message Box ── */
            QMessageBox {
                background-color: #f0f0f0;
            }
            QMessageBox QLabel {
                color: #1a1a1a;
            }
        """

    def get_color(self, color_name):
        """Get a theme-aware color value.
        
        Useful for widgets that set colors programmatically.
        """
        colors = {
            self.DARK: {
                "bg_primary": "#1a1a2e",
                "bg_secondary": "#0d0d1a",
                "bg_tertiary": "#2a2a3e",
                "bg_header": "#16162a",
                "fg_primary": "#dddddd",
                "fg_secondary": "#888888",
                "fg_muted": "#666666",
                "border": "#333333",
                "border_light": "#444444",
                "accent": "#2980b9",
                "accent_hover": "#3498db",
                "success": "#2ecc71",
                "error": "#e74c3c",
                "warning": "#e67e22",
                "info": "#3498db",
                "id_color": "#f1c40f",
                "data_color": "#3498db",
                "tx_color": "#e74c3c",
                "rx_color": "#2ecc71",
                "ext_color": "#e67e22",
                "table_bg": "#0d0d1a",
                "table_alt": "#141428",
                "table_grid": "#2a2a3e",
                "status_bg": "#1a1a2e",
                "filter_bg": "#1a1a2e",
            },
            self.LIGHT: {
                "bg_primary": "#f0f0f0",
                "bg_secondary": "#ffffff",
                "bg_tertiary": "#e8e8e8",
                "bg_header": "#e0e0e0",
                "fg_primary": "#1a1a1a",
                "fg_secondary": "#555555",
                "fg_muted": "#999999",
                "border": "#c0c0c0",
                "border_light": "#d0d0d0",
                "accent": "#2980b9",
                "accent_hover": "#3498db",
                "success": "#27ae60",
                "error": "#c0392b",
                "warning": "#d68910",
                "info": "#2471a3",
                "id_color": "#b7950b",
                "data_color": "#2471a3",
                "tx_color": "#c0392b",
                "rx_color": "#1e8449",
                "ext_color": "#ca6f1e",
                "table_bg": "#ffffff",
                "table_alt": "#f8f8f8",
                "table_grid": "#e0e0e0",
                "status_bg": "#e8e8e8",
                "filter_bg": "#f0f0f0",
            },
        }
        return colors.get(self._current_theme, colors[self.DARK]).get(color_name, "#ff00ff")