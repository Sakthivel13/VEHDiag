"""UDS Scanner Window - Send Frames Tool
Unified Diagnostic Services (UDS) scanner for automotive diagnostics.
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTableWidget, QTableWidgetItem,
                             QProgressBar, QTextEdit, QGroupBox, QSplitter,
                             QComboBox, QSpinBox, QCheckBox, QMessageBox,
                             QHeaderView, QTreeWidget, QTreeWidgetItem, QLineEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush
import time
from collections import defaultdict


class UDSScannerWorker(QThread):
    """Worker thread for UDS scanning operations"""
    progress = pyqtSignal(int)
    service_found = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, config, pipeline):
        super().__init__()
        self.config = config
        self.pipeline = pipeline
        self.is_running = True

    def run(self):
        try:
            self.log_message.emit("Starting UDS scan...")

            scan_results = {
                'discovered_ecus': [],
                'supported_services': defaultdict(list),
                'diagnostic_data': {}
            }

            # Scan for ECUs
            ecus = self._scan_for_ecus()
            scan_results['discovered_ecus'] = ecus

            # Test diagnostic services for each ECU
            total_ecus = len(ecus)
            for i, ecu_id in enumerate(ecus):
                if not self.is_running:
                    break

                self.log_message.emit(f"Testing ECU 0x{ecu_id:03X} ({i+1}/{total_ecus})")

                services = self._test_services_for_ecu(ecu_id)
                scan_results['supported_services'][ecu_id] = services

                for service in services:
                    self.service_found.emit({
                        'ecu_id': ecu_id,
                        'service': service
                    })

                progress = int((i + 1) / total_ecus * 100)
                self.progress.emit(progress)

            self.log_message.emit(f"UDS scan completed. Found {len(ecus)} ECUs.")
            self.finished.emit(scan_results)

        except Exception as e:
            self.error.emit(f"UDS scan error: {str(e)}")

    def _scan_for_ecus(self):
        """Scan for ECUs that respond to diagnostic requests"""
        ecus = []

        # Common diagnostic tester present address
        tester_address = 0x7DF

        # Test a range of ECU addresses
        for ecu_addr in range(0x7E0, 0x7F0):  # Common ECU response addresses
            if not self.is_running:
                break

            # Send tester present
            response = self._send_uds_request(tester_address, [0x01, 0x3E])  # Tester present service

            if response and len(response) >= 3:
                # Check if we got a positive response
                if response[0] == 0x7E + (ecu_addr - 0x7E0):  # Response from this ECU
                    ecus.append(ecu_addr)
                    self.log_message.emit(f"Found ECU at 0x{ecu_addr:03X}")

        # Also test some known addresses
        known_addresses = [0x7E0, 0x7E8, 0x7E9, 0x7EA, 0x7EB]
        for addr in known_addresses:
            if addr not in ecus:
                # Quick test
                response = self._send_uds_request(tester_address, [0x02, 0x10, 0x01])  # Start diagnostic session
                if response:
                    ecus.append(addr)
                    self.log_message.emit(f"Found ECU at 0x{addr:03X} (known address)")

        return ecus

    def _test_services_for_ecu(self, ecu_id):
        """Test which UDS services are supported by an ECU"""
        supported_services = []

        # Common UDS services to test
        services_to_test = [
            (0x10, [0x01], "Diagnostic Session Control"),
            (0x11, [0x01], "ECU Reset"),
            (0x22, [0xF1, 0x90], "Read Data By Identifier (VIN)"),
            (0x27, [0x01], "Security Access"),
            (0x31, [0x01, 0x02, 0x03], "Routine Control"),
            (0x3E, [], "Tester Present"),
        ]

        for service_id, sub_params, description in services_to_test:
            if not self.is_running:
                break

            # Build request
            request = [service_id] + sub_params

            try:
                response = self._send_uds_request(0x7DF, request)

                if response and len(response) >= 2:
                    # Check for positive response
                    if response[1] == service_id + 0x40:  # Positive response SID
                        supported_services.append({
                            'id': service_id,
                            'name': description,
                            'response': response.hex(),
                            'supported': True
                        })
                        self.log_message.emit(f"  ✓ {description} (0x{service_id:02X})")
                    elif response[1] == 0x7F and response[2] == service_id:  # Negative response
                        # Service not supported or other error
                        error_code = response[3] if len(response) > 3 else 0
                        supported_services.append({
                            'id': service_id,
                            'name': description,
                            'error_code': error_code,
                            'supported': False
                        })
            except Exception as e:
                self.log_message.emit(f"  ✗ {description} - Error: {str(e)}")

            # Small delay between requests
            time.sleep(0.05)

        return supported_services

    def _send_uds_request(self, target_id, data, timeout=0.5):
        """Send a UDS request and wait for response"""
        try:
            # In real implementation, this would send via CAN bus
            self.log_message.emit(f"Sending UDS request to 0x{target_id:03X}: {bytes(data).hex()}")

            # Simulate response based on request
            if data[0] == 0x3E:  # Tester present
                # Simulate positive response
                response_id = target_id + 8 if target_id < 0x7F8 else target_id
                return bytes([response_id & 0xFF, 0x7E])  # Tester present positive response
            elif data[0] == 0x10:  # Diagnostic session control
                response_id = target_id + 8 if target_id < 0x7F8 else target_id
                return bytes([response_id & 0xFF, 0x50, 0x01])  # Session control positive response
            else:
                # Simulate some responses, some errors
                import random
                if random.random() < 0.7:  # 70% success rate
                    response_id = target_id + 8 if target_id < 0x7F8 else target_id
                    return bytes([response_id & 0xFF, data[0] + 0x40] + [random.randint(0, 255) for _ in range(random.randint(1, 4))])
                else:
                    # Negative response
                    return bytes([0x7E, 0x7F, data[0], random.choice([0x11, 0x12, 0x13])])  # Various error codes

        except Exception as e:
            self.log_message.emit(f"Error sending UDS request: {str(e)}")
            return None

    def stop(self):
        self.is_running = False


class UdsScannerWindow(QMainWindow):
    """Main window for UDS scanning operations"""

    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.scan_worker = None
        self.scan_results = {}

        self.setWindowTitle("UDS Scanner - PyCANAnalyzer")
        self.setGeometry(200, 200, 1200, 800)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Control panel
        self.create_control_panel(layout)

        # Main content splitter
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # Top section - ECU list and services
        self.create_ecu_panel(splitter)

        # Bottom section - Details and log
        bottom_splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(bottom_splitter)

        # Service details
        self.create_details_panel(bottom_splitter)

        # Log output
        self.create_log_panel(bottom_splitter)

        splitter.setSizes([400, 400])

    def create_control_panel(self, parent_layout):
        """Create the UDS scanning control panel"""
        control_group = QGroupBox("UDS Scan Controls")
        control_layout = QHBoxLayout(control_group)

        # Scan controls
        self.start_button = QPushButton("🔍 Start UDS Scan")
        self.start_button.clicked.connect(self.start_scan)
        control_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.clicked.connect(self.stop_scan)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)

        # Scan options
        options_layout = QVBoxLayout()

        self.full_scan_checkbox = QCheckBox("Full service scan")
        self.full_scan_checkbox.setChecked(True)
        options_layout.addWidget(self.full_scan_checkbox)

        self.tester_present_checkbox = QCheckBox("Send tester present")
        self.tester_present_checkbox.setChecked(True)
        options_layout.addWidget(self.tester_present_checkbox)

        control_layout.addLayout(options_layout)

        # Manual request
        manual_layout = QVBoxLayout()
        manual_layout.addWidget(QLabel("Manual Request:"))

        request_layout = QHBoxLayout()
        request_layout.addWidget(QLabel("ID:"))
        self.manual_id_edit = QLineEdit("7DF")
        self.manual_id_edit.setMaximumWidth(60)
        request_layout.addWidget(self.manual_id_edit)

        request_layout.addWidget(QLabel("Data:"))
        self.manual_data_edit = QLineEdit("02 10 01")
        request_layout.addWidget(self.manual_data_edit)

        self.send_manual_button = QPushButton("Send")
        self.send_manual_button.clicked.connect(self.send_manual_request)
        request_layout.addWidget(self.send_manual_button)

        manual_layout.addLayout(request_layout)

        control_layout.addLayout(manual_layout)

        # Progress
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)

        control_layout.addLayout(progress_layout)

        parent_layout.addWidget(control_group)

    def create_ecu_panel(self, parent_splitter):
        """Create the ECU and services display panel"""
        ecu_group = QGroupBox("Discovered ECUs and Services")
        ecu_layout = QVBoxLayout(ecu_group)

        # ECU tree
        self.ecu_tree = QTreeWidget()
        self.ecu_tree.setHeaderLabel("ECU / Service")
        self.ecu_tree.setColumnCount(2)
        self.ecu_tree.setHeaderLabels(["ECU / Service", "Status"])
        self.ecu_tree.itemSelectionChanged.connect(self.on_ecu_selected)
        ecu_layout.addWidget(self.ecu_tree)

        parent_splitter.addWidget(ecu_group)

    def create_details_panel(self, parent_splitter):
        """Create the service details panel"""
        details_group = QGroupBox("Service Details")
        details_layout = QVBoxLayout(details_group)

        self.details_tree = QTreeWidget()
        self.details_tree.setHeaderLabel("Detail")
        self.details_tree.setColumnCount(2)
        self.details_tree.setHeaderLabels(["Property", "Value"])
        details_layout.addWidget(self.details_tree)

        parent_splitter.addWidget(details_group)

    def create_log_panel(self, parent_splitter):
        """Create the log output panel"""
        log_group = QGroupBox("Scan Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Courier New", 9))
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)

        parent_splitter.addWidget(log_group)

    def start_scan(self):
        """Start UDS scanning"""
        if self.scan_worker and self.scan_worker.isRunning():
            return

        # Clear previous results
        self.scan_results.clear()
        self.ecu_tree.clear()
        self.details_tree.clear()
        self.progress_bar.setValue(0)

        # Get configuration
        config = {
            'full_scan': self.full_scan_checkbox.isChecked(),
            'tester_present': self.tester_present_checkbox.isChecked()
        }

        # Start scan worker
        self.scan_worker = UDSScannerWorker(config, self.pipeline)
        self.scan_worker.progress.connect(self.update_progress)
        self.scan_worker.service_found.connect(self.on_service_found)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.error.connect(self.on_scan_error)
        self.scan_worker.log_message.connect(self.log_message)

        self.scan_worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Scanning...")

    def stop_scan(self):
        """Stop UDS scanning"""
        if self.scan_worker:
            self.scan_worker.stop()
            self.scan_worker.wait()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")

    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def on_service_found(self, service_info):
        """Handle discovered service"""
        self.update_ecu_tree()

    def update_ecu_tree(self):
        """Update the ECU tree with current results"""
        self.ecu_tree.clear()

        discovered_ecus = self.scan_results.get('discovered_ecus', [])
        supported_services = self.scan_results.get('supported_services', {})

        for ecu_id in discovered_ecus:
            # Create ECU item
            ecu_item = QTreeWidgetItem([f"ECU 0x{ecu_id:03X}", "Online"])
            ecu_item.setBackground(0, QBrush(QColor(200, 255, 200)))

            # Add services
            services = supported_services.get(ecu_id, [])
            for service in services:
                service_item = QTreeWidgetItem([
                    f"0x{service['id']:02X} - {service['name']}",
                    "✓ Supported" if service.get('supported', False) else f"✗ Error 0x{service.get('error_code', 0):02X}"
                ])

                if service.get('supported', False):
                    service_item.setBackground(1, QBrush(QColor(200, 255, 200)))
                else:
                    service_item.setBackground(1, QBrush(QColor(255, 200, 200)))

                ecu_item.addChild(service_item)

            self.ecu_tree.addTopLevelItem(ecu_item)

        self.ecu_tree.expandAll()

    def on_ecu_selected(self):
        """Handle ECU/service selection"""
        current_item = self.ecu_tree.currentItem()
        if not current_item:
            return

        parent = current_item.parent()
        if parent:  # This is a service item
            ecu_id = int(parent.text(0).split()[1], 16)  # Extract ECU ID from "ECU 0xXXX"
            service_name = current_item.text(0).split(' - ')[1]  # Extract service name

            # Find the service details
            services = self.scan_results.get('supported_services', {}).get(ecu_id, [])
            for service in services:
                if service['name'] == service_name:
                    self.display_service_details(service)
                    break
        else:  # This is an ECU item
            ecu_id = int(current_item.text(0).split()[1], 16)
            self.display_ecu_details(ecu_id)

    def display_service_details(self, service):
        """Display detailed information about a service"""
        self.details_tree.clear()

        # Service properties
        id_item = QTreeWidgetItem(["Service ID", f"0x{service['id']:02X}"])
        self.details_tree.addTopLevelItem(id_item)

        name_item = QTreeWidgetItem(["Service Name", service['name']])
        self.details_tree.addTopLevelItem(name_item)

        supported_item = QTreeWidgetItem(["Supported", "Yes" if service.get('supported', False) else "No"])
        self.details_tree.addTopLevelItem(supported_item)

        if service.get('supported', False):
            if 'response' in service:
                response_item = QTreeWidgetItem(["Last Response", service['response']])
                self.details_tree.addTopLevelItem(response_item)
        else:
            error_item = QTreeWidgetItem(["Error Code", f"0x{service.get('error_code', 0):02X}"])
            self.details_tree.addTopLevelItem(error_item)

        self.details_tree.expandAll()

    def display_ecu_details(self, ecu_id):
        """Display detailed information about an ECU"""
        self.details_tree.clear()

        # ECU properties
        id_item = QTreeWidgetItem(["ECU ID", f"0x{ecu_id:03X}"])
        self.details_tree.addTopLevelItem(id_item)

        status_item = QTreeWidgetItem(["Status", "Online"])
        self.details_tree.addTopLevelItem(status_item)

        # Service count
        services = self.scan_results.get('supported_services', {}).get(ecu_id, [])
        supported_count = sum(1 for s in services if s.get('supported', False))
        service_item = QTreeWidgetItem(["Supported Services", f"{supported_count}/{len(services)}"])
        self.details_tree.addTopLevelItem(service_item)

        self.details_tree.expandAll()

    def send_manual_request(self):
        """Send a manual UDS request"""
        try:
            # Parse ID
            id_text = self.manual_id_edit.text().strip()
            if id_text.startswith('0x'):
                target_id = int(id_text, 16)
            else:
                target_id = int(id_text, 16)

            # Parse data
            data_text = self.manual_data_edit.text().strip()
            data_parts = data_text.split()
            data = []
            for part in data_parts:
                if part.startswith('0x'):
                    data.append(int(part, 16))
                else:
                    data.append(int(part, 16))

            # Send request
            self.log_message(f"Manual request: ID=0x{target_id:03X}, Data={bytes(data).hex()}")

            # In real implementation, send via CAN bus
            # For now, just log it

        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", f"Invalid ID or data format: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Send Error", f"Failed to send request: {str(e)}")

    def on_scan_finished(self, results):
        """Handle scan completion"""
        self.scan_results = results
        self.update_ecu_tree()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText(f"Completed - Found {len(results.get('discovered_ecus', []))} ECUs")

    def on_scan_error(self, error_msg):
        """Handle scan error"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Error")
        self.log_message(f"Scan error: {error_msg}")
        QMessageBox.critical(self, "Scan Error", error_msg)

    def log_message(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        """Handle window close event"""
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.stop()
            self.scan_worker.wait()
        event.accept()