"""
Network Topology Window - Advanced Tool
Visualizes the CAN network topology and relationships between ECUs.
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTableWidget, QTableWidgetItem,
                             QProgressBar, QTextEdit, QGroupBox, QSplitter,
                             QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                             QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
                             QGraphicsLineItem, QGraphicsTextItem, QTabWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPointF, QRectF
from PyQt5.QtGui import QFont, QColor, QBrush, QPen, QPainter
import time
import numpy as np
from collections import defaultdict
import networkx as nx


class TopologyAnalysisWorker(QThread):
    """Worker thread for network topology analysis"""
    progress = pyqtSignal(int)
    topology_updated = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, frames, config):
        super().__init__()
        self.frames = frames
        self.config = config
        self.is_running = True

    def run(self):
        try:
            self.log_message.emit("Analyzing network topology...")

            if not self.frames:
                self.error.emit("No frames available for analysis")
                return

            topology = {}

            # Analyze ECU relationships
            topology.update(self._analyze_ecu_relationships())

            # Build communication graph
            topology.update(self._build_communication_graph())

            # Detect network structure
            topology.update(self._detect_network_structure())

            # Calculate network metrics
            topology.update(self._calculate_network_metrics())

            self.log_message.emit("Network topology analysis complete.")
            self.finished.emit(topology)

        except Exception as e:
            self.error.emit(f"Topology analysis error: {str(e)}")

    def _analyze_ecu_relationships(self):
        """Analyze relationships between ECUs based on message patterns"""
        # Group frames by source (if available) or infer from patterns
        ecu_communication = defaultdict(lambda: defaultdict(int))

        # For each frame, try to determine source and destinations
        for frame in self.frames:
            # This is a simplified analysis - in reality, you'd need more sophisticated
            # methods to determine ECU relationships

            # For now, treat each unique ID as a potential ECU
            source_id = frame.can_id

            # Look for response patterns (ID + 8, ID + 0x10, etc.)
            potential_responses = [
                source_id + 8,   # Common response pattern
                source_id + 0x10,  # Another common pattern
                source_id + 0x20,  # Diagnostic response
            ]

            # Count communications
            ecu_communication[source_id][source_id] += 1  # Self-messages

        return {'ecu_relationships': dict(ecu_communication)}

    def _build_communication_graph(self):
        """Build a graph of ECU communications"""
        G = nx.DiGraph()

        # Add nodes (ECUs)
        unique_ids = set(f.can_id for f in self.frames)
        for can_id in unique_ids:
            G.add_node(can_id, type='ecu', messages=len([f for f in self.frames if f.can_id == can_id]))

        # Add edges based on communication patterns
        # This is a simplified version - real analysis would be more complex
        for frame in self.frames:
            source = frame.can_id

            # Look for potential response patterns
            for other_frame in self.frames:
                if other_frame.can_id != source:
                    # Simple heuristic: if IDs are related by common patterns
                    if abs(other_frame.can_id - source) in [8, 0x10, 0x20, 0x100]:
                        G.add_edge(source, other_frame.can_id, weight=1)

        return {'communication_graph': {
            'nodes': list(G.nodes(data=True)),
            'edges': list(G.edges(data=True))
        }}

    def _detect_network_structure(self):
        """Detect the overall network structure"""
        structure = {
            'topology_type': 'unknown',
            'central_nodes': [],
            'leaf_nodes': [],
            'clusters': []
        }

        # Simple structure detection
        unique_ids = set(f.can_id for f in self.frames)
        id_counts = defaultdict(int)

        for frame in self.frames:
            id_counts[frame.can_id] += 1

        # Sort by message count
        sorted_ids = sorted(id_counts.items(), key=lambda x: x[1], reverse=True)

        if sorted_ids:
            # Most active node is likely central
            structure['central_nodes'] = [sorted_ids[0][0]]

            # Least active nodes are likely leaves
            structure['leaf_nodes'] = [id for id, count in sorted_ids[-5:] if count < sorted_ids[0][1] * 0.1]

        # Determine topology type based on ID patterns
        ids_list = sorted(unique_ids)
        if len(ids_list) > 1:
            diffs = np.diff(ids_list)
            if np.all(diffs == diffs[0]):  # Arithmetic progression
                structure['topology_type'] = 'linear'
            elif len(set(diffs)) > len(diffs) * 0.8:  # Mostly different
                structure['topology_type'] = 'star'
            else:
                structure['topology_type'] = 'complex'

        return {'network_structure': structure}

    def _calculate_network_metrics(self):
        """Calculate network-level metrics"""
        metrics = {
            'total_nodes': 0,
            'total_edges': 0,
            'average_degree': 0.0,
            'network_density': 0.0,
            'clustering_coefficient': 0.0
        }

        unique_ids = set(f.can_id for f in self.frames)
        metrics['total_nodes'] = len(unique_ids)

        # Simple metrics calculation
        if len(unique_ids) > 1:
            # Estimate connections based on ID relationships
            potential_connections = 0
            for id1 in unique_ids:
                for id2 in unique_ids:
                    if id1 != id2 and abs(id2 - id1) in [8, 0x10, 0x20, 0x100]:
                        potential_connections += 1

            metrics['total_edges'] = potential_connections
            metrics['average_degree'] = (2 * potential_connections) / len(unique_ids) if len(unique_ids) > 0 else 0
            max_possible_edges = len(unique_ids) * (len(unique_ids) - 1)
            metrics['network_density'] = potential_connections / max_possible_edges if max_possible_edges > 0 else 0

        return {'network_metrics': metrics}

    def stop(self):
        self.is_running = False


class TopologyGraphicsView(QGraphicsView):
    """Custom graphics view for network topology visualization"""

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # Scene data
        self.nodes = {}
        self.edges = []
        self.layout_type = 'circular'

    def set_topology_data(self, topology_data):
        """Set topology data for visualization"""
        self.scene.clear()
        self.nodes.clear()
        self.edges.clear()

        if not topology_data:
            return

        # Get graph data
        graph_data = topology_data.get('communication_graph', {})
        nodes_data = graph_data.get('nodes', [])
        edges_data = graph_data.get('edges', [])

        # Create layout
        self._create_layout(nodes_data, edges_data)

        # Draw edges
        for edge_data in edges_data:
            source, target, data = edge_data
            if source in self.nodes and target in self.nodes:
                self._draw_edge(source, target, data)

        # Draw nodes
        for node_data in nodes_data:
            node_id, attrs = node_data
            self._draw_node(node_id, attrs)

    def _create_layout(self, nodes_data, edges_data):
        """Create node layout"""
        if not nodes_data:
            return

        # Get node IDs
        node_ids = [node[0] for node in nodes_data]

        if self.layout_type == 'circular':
            self._circular_layout(node_ids)
        elif self.layout_type == 'force':
            self._force_layout(node_ids, edges_data)
        else:
            self._grid_layout(node_ids)

    def _circular_layout(self, node_ids):
        """Arrange nodes in a circle"""
        center_x, center_y = 0, 0
        radius = 200
        angle_step = 2 * np.pi / len(node_ids) if node_ids else 0

        for i, node_id in enumerate(node_ids):
            angle = i * angle_step
            x = center_x + radius * np.cos(angle)
            y = center_y + radius * np.sin(angle)
            self.nodes[node_id] = QPointF(x, y)

    def _force_layout(self, node_ids, edges_data):
        """Simple force-directed layout"""
        # Initialize positions randomly
        for node_id in node_ids:
            self.nodes[node_id] = QPointF(
                np.random.uniform(-200, 200),
                np.random.uniform(-200, 200)
            )

        # Simple force-directed algorithm (simplified)
        # In a real implementation, you'd use a proper force-directed algorithm
        # For now, just use circular layout as fallback
        self._circular_layout(node_ids)

    def _grid_layout(self, node_ids):
        """Arrange nodes in a grid"""
        cols = int(np.ceil(np.sqrt(len(node_ids))))
        rows = int(np.ceil(len(node_ids) / cols))

        spacing = 100
        start_x = -(cols - 1) * spacing / 2
        start_y = -(rows - 1) * spacing / 2

        for i, node_id in enumerate(node_ids):
            row = i // cols
            col = i % cols
            x = start_x + col * spacing
            y = start_y + row * spacing
            self.nodes[node_id] = QPointF(x, y)

    def _draw_node(self, node_id, attrs):
        """Draw a node (ECU)"""
        if node_id not in self.nodes:
            return

        pos = self.nodes[node_id]

        # Node size based on message count
        message_count = attrs.get('messages', 1)
        size = 20 + min(message_count / 10, 40)  # Scale node size

        # Create node ellipse
        node_item = QGraphicsEllipseItem(pos.x() - size/2, pos.y() - size/2, size, size)
        node_item.setBrush(QBrush(QColor(100, 150, 255)))
        node_item.setPen(QPen(QColor(50, 100, 200), 2))

        # Add label
        label = QGraphicsTextItem(f"0x{node_id:03X}")
        label.setPos(pos.x() - size/2, pos.y() + size/2 + 5)
        label.setDefaultTextColor(QColor(0, 0, 0))

        self.scene.addItem(node_item)
        self.scene.addItem(label)

    def _draw_edge(self, source_id, target_id, data):
        """Draw an edge between nodes"""
        if source_id not in self.nodes or target_id not in self.nodes:
            return

        source_pos = self.nodes[source_id]
        target_pos = self.nodes[target_id]

        # Create line
        line = QGraphicsLineItem(source_pos.x(), source_pos.y(), target_pos.x(), target_pos.y())
        line.setPen(QPen(QColor(150, 150, 150), 1))

        self.scene.addItem(line)

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor

        self.scale(zoom_factor, zoom_factor)


class NetworkTopologyWindow(QMainWindow):
    """Main window for CAN network topology visualization"""

    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.topology_data = {}
        self.topology_worker = None

        self.setWindowTitle("Network Topology - PyCANAnalyzer")
        self.setGeometry(200, 200, 1200, 800)

        self.init_ui()
        self.load_frames()

    def init_ui(self):
        """Initialize the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Control panel
        self.create_control_panel(layout)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left side - Topology view
        self.create_topology_view(splitter)

        # Right side - Details and statistics
        self.create_details_panel(splitter)

    def create_control_panel(self, parent_layout):
        """Create the control panel"""
        control_group = QGroupBox("Topology Analysis")
        control_layout = QHBoxLayout(control_group)

        # Analysis controls
        self.analyze_button = QPushButton("🔍 Analyze Topology")
        self.analyze_button.clicked.connect(self.analyze_topology)
        control_layout.addWidget(self.analyze_button)

        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.clicked.connect(self.stop_analysis)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)

        # Layout options
        layout_layout = QVBoxLayout()

        layout_label = QLabel("Layout:")
        layout_layout.addWidget(layout_label)

        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Circular", "Grid", "Force-directed"])
        self.layout_combo.currentTextChanged.connect(self.change_layout)
        layout_layout.addWidget(self.layout_combo)

        control_layout.addLayout(layout_layout)

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

    def create_topology_view(self, parent_splitter):
        """Create the topology visualization view"""
        view_group = QGroupBox("Network Topology")
        view_layout = QVBoxLayout(view_group)

        self.topology_view = TopologyGraphicsView()
        view_layout.addWidget(self.topology_view)

        # View controls
        controls_layout = QHBoxLayout()

        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_in_button.clicked.connect(self.zoom_in)
        controls_layout.addWidget(self.zoom_in_button)

        self.zoom_out_button = QPushButton("Zoom Out")
        self.zoom_out_button.clicked.connect(self.zoom_out)
        controls_layout.addWidget(self.zoom_out_button)

        self.fit_button = QPushButton("Fit to View")
        self.fit_button.clicked.connect(self.fit_to_view)
        controls_layout.addWidget(self.fit_button)

        controls_layout.addStretch()
        view_layout.addLayout(controls_layout)

        parent_splitter.addWidget(view_group)

    def create_details_panel(self, parent_splitter):
        """Create the details and statistics panel"""
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)

        # Tabs for different information
        self.details_tab = QTabWidget()
        details_layout.addWidget(self.details_tab)

        # Network metrics tab
        self.create_metrics_tab()

        # Node details tab
        self.create_nodes_tab()

        # Structure tab
        self.create_structure_tab()

        # Log tab
        self.create_log_tab()

        parent_splitter.addWidget(details_widget)

    def create_metrics_tab(self):
        """Create the network metrics tab"""
        metrics_widget = QWidget()
        metrics_layout = QVBoxLayout(metrics_widget)

        self.metrics_tree = QTreeWidget()
        self.metrics_tree.setHeaderLabel("Metric")
        self.metrics_tree.setColumnCount(2)
        self.metrics_tree.setHeaderLabels(["Metric", "Value"])
        metrics_layout.addWidget(self.metrics_tree)

        self.details_tab.addTab(metrics_widget, "Metrics")

    def create_nodes_tab(self):
        """Create the nodes/ECUs tab"""
        nodes_widget = QWidget()
        nodes_layout = QVBoxLayout(nodes_widget)

        self.nodes_table = QTableWidget()
        self.nodes_table.setColumnCount(4)
        self.nodes_table.setHorizontalHeaderLabels([
            "ECU ID", "Messages", "Connections", "Type"
        ])

        header = self.nodes_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        nodes_layout.addWidget(self.nodes_table)

        self.details_tab.addTab(nodes_widget, "Nodes")

    def create_structure_tab(self):
        """Create the network structure tab"""
        structure_widget = QWidget()
        structure_layout = QVBoxLayout(structure_widget)

        self.structure_tree = QTreeWidget()
        self.structure_tree.setHeaderLabel("Property")
        self.structure_tree.setColumnCount(2)
        self.structure_tree.setHeaderLabels(["Property", "Value"])
        structure_layout.addWidget(self.structure_tree)

        self.details_tab.addTab(structure_widget, "Structure")

    def create_log_tab(self):
        """Create the log tab"""
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)

        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Courier New", 9))
        log_layout.addWidget(self.log_text)

        self.details_tab.addTab(log_widget, "Log")

    def load_frames(self):
        """Load frames from the pipeline"""
        try:
            # Get frames from pipeline
            self.frames = self.pipeline.get_all_frames() if hasattr(self.pipeline, 'get_all_frames') else []
            self.log_message(f"Loaded {len(self.frames)} frames for topology analysis")
        except Exception as e:
            self.log_message(f"Error loading frames: {str(e)}")
            self.frames = []

    def analyze_topology(self):
        """Start topology analysis"""
        if not self.frames:
            QMessageBox.warning(self, "No Frames", "No frames available for analysis.")
            return

        if self.topology_worker and self.topology_worker.isRunning():
            return

        # Clear previous results
        self.clear_results()

        # Get configuration
        config = {
            'layout_type': self.layout_combo.currentText().lower().replace('-', '_')
        }

        # Start topology worker
        self.topology_worker = TopologyAnalysisWorker(self.frames, config)
        self.topology_worker.progress.connect(self.update_progress)
        self.topology_worker.topology_updated.connect(self.on_topology_updated)
        self.topology_worker.finished.connect(self.on_analysis_finished)
        self.topology_worker.error.connect(self.on_analysis_error)
        self.topology_worker.log_message.connect(self.log_message)

        self.topology_worker.start()

        self.analyze_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Analyzing...")

    def stop_analysis(self):
        """Stop topology analysis"""
        if self.topology_worker:
            self.topology_worker.stop()
            self.topology_worker.wait()

        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Stopped")

    def clear_results(self):
        """Clear all results displays"""
        self.metrics_tree.clear()
        self.nodes_table.setRowCount(0)
        self.structure_tree.clear()
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.topology_view.scene.clear()

    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def on_topology_updated(self, partial_data):
        """Handle partial topology update"""
        # Update visualization with partial data
        pass

    def on_analysis_finished(self, topology_data):
        """Handle analysis completion"""
        self.topology_data = topology_data
        self.update_all_displays()

        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Completed")

    def update_all_displays(self):
        """Update all display widgets with topology data"""
        self.update_topology_view()
        self.update_metrics_display()
        self.update_nodes_display()
        self.update_structure_display()

    def update_topology_view(self):
        """Update the topology visualization"""
        self.topology_view.set_topology_data(self.topology_data)

    def update_metrics_display(self):
        """Update the network metrics display"""
        if 'network_metrics' not in self.topology_data:
            return

        metrics = self.topology_data['network_metrics']
        self.metrics_tree.clear()

        for metric_name, value in metrics.items():
            if isinstance(value, float):
                display_value = f"{value:.3f}"
            else:
                display_value = str(value)

            item = QTreeWidgetItem([metric_name.replace('_', ' ').title(), display_value])
            self.metrics_tree.addTopLevelItem(item)

    def update_nodes_display(self):
        """Update the nodes/ECUs display"""
        graph_data = self.topology_data.get('communication_graph', {})
        nodes_data = graph_data.get('nodes', [])

        self.nodes_table.setRowCount(len(nodes_data))

        for row, (node_id, attrs) in enumerate(nodes_data):
            # ECU ID
            id_item = QTableWidgetItem(f"0x{node_id:03X}")
            self.nodes_table.setItem(row, 0, id_item)

            # Messages
            messages = attrs.get('messages', 0)
            msg_item = QTableWidgetItem(str(messages))
            self.nodes_table.setItem(row, 1, msg_item)

            # Connections (simplified)
            connections = 0  # Would need to calculate from edges
            conn_item = QTableWidgetItem(str(connections))
            self.nodes_table.setItem(row, 2, conn_item)

            # Type (simplified)
            node_type = "ECU"  # Could be determined from analysis
            type_item = QTableWidgetItem(node_type)
            self.nodes_table.setItem(row, 3, type_item)

    def update_structure_display(self):
        """Update the network structure display"""
        if 'network_structure' not in self.topology_data:
            return

        structure = self.topology_data['network_structure']
        self.structure_tree.clear()

        # Topology type
        type_item = QTreeWidgetItem(["Topology Type", structure['topology_type'].title()])
        self.structure_tree.addTopLevelItem(type_item)

        # Central nodes
        if structure['central_nodes']:
            central_text = ', '.join(f"0x{node:03X}" for node in structure['central_nodes'])
            central_item = QTreeWidgetItem(["Central Nodes", central_text])
            self.structure_tree.addTopLevelItem(central_item)

        # Leaf nodes
        if structure['leaf_nodes']:
            leaf_text = ', '.join(f"0x{node:03X}" for node in structure['leaf_nodes'])
            leaf_item = QTreeWidgetItem(["Leaf Nodes", leaf_text])
            self.structure_tree.addTopLevelItem(leaf_item)

    def change_layout(self, layout_name):
        """Change the layout type"""
        layout_map = {
            'Circular': 'circular',
            'Grid': 'grid',
            'Force-directed': 'force'
        }

        self.topology_view.layout_type = layout_map.get(layout_name, 'circular')
        if self.topology_data:
            self.update_topology_view()

    def zoom_in(self):
        """Zoom in on the topology view"""
        self.topology_view.scale(1.2, 1.2)

    def zoom_out(self):
        """Zoom out on the topology view"""
        self.topology_view.scale(0.8, 0.8)

    def fit_to_view(self):
        """Fit the topology to the view"""
        self.topology_view.fitInView(self.topology_view.scene.sceneRect(), Qt.KeepAspectRatio)

    def on_analysis_error(self, error_msg):
        """Handle analysis error"""
        self.analyze_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Error")
        self.log_message(f"Analysis error: {error_msg}")
        QMessageBox.critical(self, "Analysis Error", error_msg)

    def log_message(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        """Handle window close event"""
        if self.topology_worker and self.topology_worker.isRunning():
            self.topology_worker.stop()
            self.topology_worker.wait()
        event.accept()