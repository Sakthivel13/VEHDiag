"""UDS Scanner Window - Scan for UDS Support on CAN Bus."""
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


class UdsScannerWindow(QMainWindow):
    """Window for scanning CAN bus for UDS (Unified Diagnostic Services) support."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.scan_results = []
        self.active_scan = None

        self.is_scanning = False

        self.init_ui()

    def init_ui(self):
        """Initialize the UDS scanner UI."""
        self.setWindowTitle("UDS Scanner")
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

        # Left - Scan results
        self.create_results_panel(results_splitter)

        # Right - Details panel
        self.create_details_panel(results_splitter)

        results_splitter.setSizes([700, 700])

        # Status bar
        self.status_label = QLabel("Ready - Configure scan parameters and start UDS discovery")
        layout.addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QVBoxLayout(panel)

        # Scan configuration
        config_group = QGroupBox("Scan Configuration")
        config_layout = QVBoxLayout()

        # ID range
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("ECU ID Range:"))
        self.start_id_edit = QLineEdit()
        self.start_id_edit.setText("0x700")
        range_layout.addWidget(self.start_id_edit)

        range_layout.addWidget(QLabel("to"))
        self.end_id_edit = QLineEdit()
        self.end_id_edit.setText("0x7FF")
        range_layout.addWidget(self.end_id_edit)

        # Scan type
        type_group = QWidget()
        type_layout = QHBoxLayout(type_group)

        self.scan_type_group = QButtonGroup()

        self.standard_scan_radio = QRadioButton("Standard Diagnostic")
        self.extended_scan_radio = QRadioButton("Extended Diagnostic")
        self.custom_scan_radio = QRadioButton("Custom Services")

        self.standard_scan_radio.setChecked(True)  # Default

        self.scan_type_group.addButton(self.standard_scan_radio)
        self.scan_type_group.addButton(self.extended_scan_radio)
        self.scan_type_group.addButton(self.custom_scan_radio)

        type_layout.addWidget(self.standard_scan_radio)
        type_layout.addWidget(self.extended_scan_radio)
        type_layout.addWidget(self.custom_scan_radio)
        type_layout.addStretch()

        # Timing
        timing_layout = QHBoxLayout()
        timing_layout.addWidget(QLabel("Request Delay:"))
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(10, 1000)
        self.delay_spin.setValue(100)
        self.delay_spin.setSuffix(" ms")
        timing_layout.addWidget(self.delay_spin)

        timing_layout.addWidget(QLabel("Timeout:"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(50, 5000)
        self.timeout_spin.setValue(500)
        self.timeout_spin.setSuffix(" ms")
        timing_layout.addWidget(self.timeout_spin)

        config_layout.addLayout(range_layout)
        config_layout.addWidget(type_group)
        config_layout.addLayout(timing_layout)

        config_group.setLayout(config_layout)
        control_layout.addWidget(config_group)

        # Scan controls
        scan_group = QGroupBox("Scan Control")
        scan_layout = QHBoxLayout()

        self.start_scan_button = QPushButton("Start UDS Scan")
        self.start_scan_button.clicked.connect(self.start_uds_scan)

        self.stop_scan_button = QPushButton("Stop Scan")
        self.stop_scan_button.setEnabled(False)
        self.stop_scan_button.clicked.connect(self.stop_scan)

        self.clear_results_button = QPushButton("Clear Results")
        self.clear_results_button.clicked.connect(self.clear_results)

        scan_layout.addWidget(self.start_scan_button)
        scan_layout.addWidget(self.stop_scan_button)
        scan_layout.addWidget(self.clear_results_button)
        scan_layout.addStretch()

        scan_group.setLayout(scan_layout)
        control_layout.addWidget(scan_group)

        parent.addWidget(panel)

    def create_results_panel(self, parent):
        """Create the scan results panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Progress
        progress_group = QGroupBox("Scan Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.progress_label = QLabel("Ready to start scan")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # Results table
        results_group = QGroupBox("UDS Scan Results")
        results_layout = QVBoxLayout()

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "ECU ID", "Response", "Services", "DTCs", "Status"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.itemSelectionChanged.connect(self.on_result_selected)

        results_layout.addWidget(self.results_table)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        parent.addWidget(panel)

    def create_details_panel(self, parent):
        """Create the details panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # ECU details
        details_group = QGroupBox("ECU Details")
        details_layout = QVBoxLayout()

        self.ecu_details_text = QTextEdit()
        self.ecu_details_text.setReadOnly(True)

        details_layout.addWidget(self.ecu_details_text)
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        # Service details
        service_group = QGroupBox("Supported Services")
        service_layout = QVBoxLayout()

        self.service_details_text = QTextEdit()
        self.service_details_text.setReadOnly(True)

        service_layout.addWidget(self.service_details_text)
        service_group.setLayout(service_layout)
        layout.addWidget(service_group)

        # DTC details
        dtc_group = QGroupBox("Diagnostic Trouble Codes")
        dtc_layout = QVBoxLayout()

        self.dtc_table = QTableWidget()
        self.dtc_table.setColumnCount(3)
        self.dtc_table.setHorizontalHeaderLabels([
            "DTC Code", "Status", "Description"
        ])
        self.dtc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        dtc_layout.addWidget(self.dtc_table)
        dtc_group.setLayout(dtc_layout)
        layout.addWidget(dtc_group)

        parent.addWidget(panel)

    def start_uds_scan(self):
        """Start the UDS scan."""
        try:
            start_id = int(self.start_id_edit.text(), 16)
            end_id = int(self.end_id_edit.text(), 16)
        except ValueError:
            QMessageBox.warning(self, "Invalid ID Range",
                               "Please enter valid hexadecimal ECU IDs.")
            return

        if start_id >= end_id:
            QMessageBox.warning(self, "Invalid Range",
                               "Start ID must be less than end ID.")
            return

        # Determine scan type
        if self.standard_scan_radio.isChecked():
            scan_type = "standard"
        elif self.extended_scan_radio.isChecked():
            scan_type = "extended"
        else:  # custom_scan_radio
            scan_type = "custom"

        self.is_scanning = True
        self.start_scan_button.setEnabled(False)
        self.stop_scan_button.setEnabled(True)

        self.status_label.setText("Starting UDS scan...")

        # Create scan configuration
        self.active_scan = {
            'start_id': start_id,
            'end_id': end_id,
            'scan_type': scan_type,
            'delay': self.delay_spin.value(),
            'timeout': self.timeout_spin.value()
        }

        # Start scan thread
        self.scan_thread = UdsScanThread(self.active_scan)
        self.scan_thread.progress_update.connect(self.on_scan_progress)
        self.scan_thread.scan_complete.connect(self.on_scan_complete)
        self.scan_thread.result_found.connect(self.on_result_found)
        self.scan_thread.start()

    def stop_scan(self):
        """Stop the current scan."""
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()

        self.is_scanning = False
        self.start_scan_button.setEnabled(True)
        self.stop_scan_button.setEnabled(False)
        self.status_label.setText("Scan stopped")

    def on_scan_progress(self, progress, message):
        """Handle scan progress updates."""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)

    def on_result_found(self, result):
        """Handle individual scan result."""
        self.scan_results.append(result)
        self.add_result_to_table(result)

    def on_scan_complete(self, final_results):
        """Handle scan completion."""
        self.is_scanning = False
        self.start_scan_button.setEnabled(True)
        self.stop_scan_button.setEnabled(False)

        self.scan_results = final_results
        self.update_results_table()

        result_count = len([r for r in final_results if r.get('response')])
        self.status_label.setText(f"UDS scan complete: {result_count} ECUs responding")

    def add_result_to_table(self, result):
        """Add a single result to the table."""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        # ECU ID
        id_item = QTableWidgetItem(f"0x{result['ecu_id']:03X}")
        self.results_table.setItem(row, 0, id_item)

        # Response
        response = "Yes" if result.get('response') else "No"
        response_item = QTableWidgetItem(response)
        if result.get('response'):
            response_item.setBackground(QColor(200, 255, 200))
        else:
            response_item.setBackground(QColor(255, 200, 200))
        self.results_table.setItem(row, 1, response_item)

        # Services
        services = result.get('services', [])
        services_str = ", ".join(f"0x{s:02X}" for s in services[:3])
        if len(services) > 3:
            services_str += f" (+{len(services) - 3} more)"
        services_item = QTableWidgetItem(services_str)
        self.results_table.setItem(row, 2, services_item)

        # DTCs
        dtcs = result.get('dtcs', [])
        dtc_item = QTableWidgetItem(str(len(dtcs)))
        self.results_table.setItem(row, 3, dtc_item)

        # Status
        status = result.get('status', 'Unknown')
        status_item = QTableWidgetItem(status)
        if status == "Active":
            status_item.setBackground(QColor(200, 255, 200))
        elif status == "Error":
            status_item.setBackground(QColor(255, 200, 200))
        self.results_table.setItem(row, 4, status_item)

    def update_results_table(self):
        """Update the complete results table."""
        self.results_table.setRowCount(0)

        for result in self.scan_results:
            self.add_result_to_table(result)

    def on_result_selected(self):
        """Handle result selection."""
        current_row = self.results_table.currentRow()
        if current_row >= 0 and current_row < len(self.scan_results):
            result = self.scan_results[current_row]
            self.show_ecu_details(result)

    def show_ecu_details(self, result):
        """Show detailed information about the selected ECU."""
        details = f"ECU Details: 0x{result['ecu_id']:03X}\n\n"

        details += f"Response Received: {result.get('response', False)}\n"
        details += f"Status: {result.get('status', 'Unknown')}\n"
        details += f"Scan Type: {result.get('scan_type', 'Unknown')}\n\n"

        if result.get('response'):
            details += "Supported Services:\n"
            services = result.get('services', [])
            for service in services:
                service_name = self.get_service_name(service)
                details += f"  0x{service:02X} - {service_name}\n"

            details += "\nDiagnostic Trouble Codes:\n"
            dtcs = result.get('dtcs', [])
            if dtcs:
                for dtc in dtcs:
                    details += f"  {dtc}\n"
            else:
                details += "  No DTCs reported\n"

            if 'vin' in result:
                details += f"\nVIN: {result['vin']}\n"

            if 'ecu_name' in result:
                details += f"ECU Name: {result['ecu_name']}\n"

        self.ecu_details_text.setText(details)

        # Update service details
        self.show_service_details(result)

        # Update DTC table
        self.show_dtc_details(result)

    def show_service_details(self, result):
        """Show detailed service information."""
        services_text = "Supported UDS Services\n\n"

        services = result.get('services', [])
        if not services:
            services_text += "No services detected.\n"
        else:
            for service in sorted(services):
                name = self.get_service_name(service)
                description = self.get_service_description(service)
                services_text += f"0x{service:02X} - {name}\n"
                services_text += f"  {description}\n\n"

        self.service_details_text.setText(services_text)

    def show_dtc_details(self, result):
        """Show DTC details in table."""
        dtcs = result.get('dtcs', [])

        self.dtc_table.setRowCount(len(dtcs))

        for row, dtc in enumerate(dtcs):
            # DTC Code
            code_item = QTableWidgetItem(dtc.get('code', 'Unknown'))
            self.dtc_table.setItem(row, 0, code_item)

            # Status
            status = dtc.get('status', 'Unknown')
            status_item = QTableWidgetItem(status)
            if status == "Active":
                status_item.setBackground(QColor(255, 200, 200))
            elif status == "Stored":
                status_item.setBackground(QColor(255, 255, 200))
            self.dtc_table.setItem(row, 1, status_item)

            # Description
            desc = dtc.get('description', 'No description available')
            desc_item = QTableWidgetItem(desc)
            self.dtc_table.setItem(row, 2, desc_item)

    def get_service_name(self, service_id):
        """Get the name of a UDS service."""
        service_names = {
            0x10: "Diagnostic Session Control",
            0x11: "ECU Reset",
            0x14: "Clear Diagnostic Information",
            0x19: "Read DTC Information",
            0x22: "Read Data By Identifier",
            0x23: "Read Memory By Address",
            0x24: "Read Scaling Data By Identifier",
            0x27: "Security Access",
            0x28: "Communication Control",
            0x2A: "Read Data By Periodic Identifier",
            0x2C: "Dynamically Define Data Identifier",
            0x2E: "Write Data By Identifier",
            0x2F: "Input Output Control By Identifier",
            0x31: "Routine Control",
            0x34: "Request Download",
            0x35: "Request Upload",
            0x36: "Transfer Data",
            0x37: "Request Transfer Exit",
            0x3D: "Write Memory By Address",
            0x3E: "Tester Present",
            0x85: "Control DTC Setting",
            0x86: "Response On Event"
        }
        return service_names.get(service_id, f"Unknown Service 0x{service_id:02X}")

    def get_service_description(self, service_id):
        """Get description of a UDS service."""
        descriptions = {
            0x10: "Change diagnostic session (default, programming, extended, etc.)",
            0x11: "Reset ECU to a specific state",
            0x14: "Clear stored DTCs and freeze frame data",
            0x19: "Read diagnostic trouble codes and related information",
            0x22: "Read ECU data by predefined identifiers",
            0x23: "Read ECU memory at specified address",
            0x24: "Read scaling information for data identifiers",
            0x27: "Request access to security-protected functions",
            0x28: "Control ECU communication (enable/disable transmission)",
            0x2A: "Set up periodic transmission of data identifiers",
            0x2C: "Create custom data identifiers for reading",
            0x2E: "Write data to ECU by identifier",
            0x2F: "Control ECU inputs/outputs by identifier",
            0x31: "Start/stop/exec routines in ECU",
            0x34: "Request download of data to ECU",
            0x35: "Request upload of data from ECU",
            0x36: "Transfer data blocks during download/upload",
            0x37: "Exit data transfer mode",
            0x3D: "Write data to ECU memory at specified address",
            0x3E: "Keep diagnostic session alive",
            0x85: "Enable/disable DTC storage and detection",
            0x86: "Configure ECU to respond to specific events"
        }
        return descriptions.get(service_id, "No description available")

    def clear_results(self):
        """Clear all scan results."""
        self.scan_results = []
        self.results_table.setRowCount(0)
        self.ecu_details_text.clear()
        self.service_details_text.clear()
        self.dtc_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Ready to start scan")
        self.status_label.setText("Results cleared")

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []


class UdsScanThread(QThread):
    """Background thread for UDS scanning."""

    progress_update = pyqtSignal(int, str)
    scan_complete = pyqtSignal(list)
    result_found = pyqtSignal(dict)

    def __init__(self, scan_config):
        super().__init__()
        self.scan_config = scan_config
        self.stop_requested = False
        self.results = []

    def stop(self):
        """Request thread stop."""
        self.stop_requested = True

    def run(self):
        """Run the UDS scan."""
        start_id = self.scan_config['start_id']
        end_id = self.scan_config['end_id']
        scan_type = self.scan_config['scan_type']
        delay = self.scan_config['delay']
        timeout = self.scan_config['timeout']

        total_ids = end_id - start_id + 1
        scanned = 0

        for ecu_id in range(start_id, end_id + 1):
            if self.stop_requested:
                break

            # Update progress
            progress = int(100 * scanned / total_ids)
            self.progress_update.emit(progress, f"Scanning ECU 0x{ecu_id:03X} ({scanned}/{total_ids})")

            # Scan this ECU
            result = self.scan_ecu(ecu_id, scan_type, timeout)
            self.results.append(result)

            # Emit result if responsive
            if result.get('response'):
                self.result_found.emit(result)

            scanned += 1

            # Delay between requests
            if delay > 0:
                self.msleep(delay)

        self.scan_complete.emit(self.results)

    def scan_ecu(self, ecu_id, scan_type, timeout):
        """Scan a single ECU for UDS support."""
        result = {
            'ecu_id': ecu_id,
            'scan_type': scan_type,
            'response': False,
            'status': 'No Response',
            'services': [],
            'dtcs': []
        }

        # In a real implementation, this would send actual UDS requests
        # For now, simulate based on ECU ID patterns

        # Simulate some ECUs responding
        if ecu_id % 17 == 0:  # Some ECUs respond
            result['response'] = True
            result['status'] = 'Active'

            # Add some services based on scan type
            if scan_type == "standard":
                result['services'] = [0x10, 0x22, 0x2E, 0x3E]  # Basic services
            elif scan_type == "extended":
                result['services'] = [0x10, 0x11, 0x14, 0x19, 0x22, 0x27, 0x2E, 0x31, 0x3E]
            else:  # custom
                result['services'] = [0x22, 0x2A, 0x2C, 0x2E, 0x86]

            # Add some DTCs
            if ecu_id % 23 == 0:
                result['dtcs'] = [
                    {'code': 'P0101', 'status': 'Stored', 'description': 'Mass Air Flow Circuit Range/Performance'},
                    {'code': 'P0201', 'status': 'Active', 'description': 'Injector Circuit Malfunction - Cylinder 1'}
                ]

            # Add ECU info
            if ecu_id % 29 == 0:
                result['vin'] = f"1HGCM82633A{ecu_id:06X}"
                result['ecu_name'] = f"ECU_{ecu_id:03X}"

        return result