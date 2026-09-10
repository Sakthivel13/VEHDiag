"""Network Topology Window - Visualize CAN Network Structure."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QSplitter, QMessageBox,
                             QTextEdit, QSpinBox, QComboBox, QLineEdit,
                             QCheckBox, QProgressBar, QGraphicsView,
                             QGraphicsScene, QGraphicsEllipseItem,
                             QGraphicsLineItem, QGraphicsTextItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPointF, QRectF
from PyQt5.QtGui import QFont, QColor, QPen, QBrush, QPainter
import time
import collections
import math
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


class NetworkTopologyWindow(QMainWindow):
    """Window for visualizing CAN network topology and ECU relationships."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.network_graph = None
        self.node_positions = {}
        self.ecu_nodes = {}

        self.is_analyzing = False

        self.init_ui()

    def init_ui(self):
        """Initialize the network topology UI."""
        self.setWindowTitle("CAN Network Topology")
        self.setGeometry(200, 200, 1400, 900)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)

        # Control panel
        self.create_control_panel(layout)

        # Main content splitter
        content_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(content_splitter)

        # Left - Network visualization
        self.create_network_view(content_splitter)

        # Right - Analysis panel
        self.create_analysis_panel(content_splitter)

        content_splitter.setSizes([800, 600])

        # Status bar
        self.status_label = QLabel("Ready - Analyze frames to build network topology")
        layout.addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        control_layout = QHBoxLayout(panel)

        # Analysis controls
        analysis_group = QGroupBox("Network Analysis")
        analysis_layout = QVBoxLayout()

        # Build network
        self.build_network_button = QPushButton("Build Network Topology")
        self.build_network_button.clicked.connect(self.build_network_topology)

        # Analysis options
        options_layout = QHBoxLayout()

        self.include_broadcast_check = QCheckBox("Include Broadcast")
        self.include_broadcast_check.setChecked(True)

        self.auto_layout_check = QCheckBox("Auto Layout")
        self.auto_layout_check.setChecked(True)

        options_layout.addWidget(self.include_broadcast_check)
        options_layout.addWidget(self.auto_layout_check)

        # Layout algorithm
        layout_algo_layout = QHBoxLayout()
        layout_algo_layout.addWidget(QLabel("Layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems([
            "Spring", "Circular", "Random", "Shell", "Spectral"
        ])
        layout_algo_layout.addWidget(self.layout_combo)

        analysis_layout.addWidget(self.build_network_button)
        analysis_layout.addLayout(options_layout)
        analysis_layout.addLayout(layout_algo_layout)

        analysis_group.setLayout(analysis_layout)
        control_layout.addWidget(analysis_group)

        # Visualization options
        viz_group = QGroupBox("Visualization")
        viz_layout = QVBoxLayout()

        # Node size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Node Size:"))
        self.node_size_combo = QComboBox()
        self.node_size_combo.addItems([
            "Fixed", "By Message Count", "By Data Volume"
        ])
        size_layout.addWidget(self.node_size_combo)

        # Edge style
        edge_layout = QHBoxLayout()
        edge_layout.addWidget(QLabel("Edge Style:"))
        self.edge_style_combo = QComboBox()
        self.edge_style_combo.addItems([
            "Straight", "Curved", "Bundled"
        ])
        edge_layout.addWidget(self.edge_style_combo)

        # Show labels
        self.show_labels_check = QCheckBox("Show Node Labels")
        self.show_labels_check.setChecked(True)

        viz_layout.addLayout(size_layout)
        viz_layout.addLayout(edge_layout)
        viz_layout.addWidget(self.show_labels_check)

        viz_group.setLayout(viz_layout)
        control_layout.addWidget(viz_group)

        # Export options
        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout()

        self.export_image_button = QPushButton("Export as Image")
        self.export_image_button.clicked.connect(self.export_as_image)

        self.export_graphml_button = QPushButton("Export as GraphML")
        self.export_graphml_button.clicked.connect(self.export_as_graphml)

        export_layout.addWidget(self.export_image_button)
        export_layout.addWidget(self.export_graphml_button)

        export_group.setLayout(export_layout)
        control_layout.addWidget(export_group)

        parent.addWidget(panel)

    def create_network_view(self, parent):
        """Create the network visualization view."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Graphics view for network visualization
        self.network_view = QGraphicsView()
        self.network_scene = QGraphicsScene()
        self.network_view.setScene(self.network_scene)
        self.network_view.setRenderHint(QPainter.Antialiasing)
        self.network_view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.network_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # Zoom controls
        zoom_layout = QHBoxLayout()
        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_in_button.clicked.connect(self.zoom_in)

        self.zoom_out_button = QPushButton("Zoom Out")
        self.zoom_out_button.clicked.connect(self.zoom_out)

        self.fit_view_button = QPushButton("Fit to View")
        self.fit_view_button.clicked.connect(self.fit_to_view)

        zoom_layout.addWidget(self.zoom_in_button)
        zoom_layout.addWidget(self.zoom_out_button)
        zoom_layout.addWidget(self.fit_view_button)
        zoom_layout.addStretch()

        layout.addLayout(zoom_layout)
        layout.addWidget(self.network_view)

        parent.addWidget(panel)

    def create_analysis_panel(self, parent):
        """Create the analysis panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Network statistics
        stats_group = QGroupBox("Network Statistics")
        stats_layout = QVBoxLayout()

        self.network_stats_text = QTextEdit()
        self.network_stats_text.setReadOnly(True)
        self.network_stats_text.setMaximumHeight(150)

        stats_layout.addWidget(self.network_stats_text)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # ECU details
        ecu_group = QGroupBox("ECU Details")
        ecu_layout = QVBoxLayout()

        self.ecu_table = QTableWidget()
        self.ecu_table.setColumnCount(4)
        self.ecu_table.setHorizontalHeaderLabels([
            "ECU ID", "Messages", "Data Volume", "Activity"
        ])
        self.ecu_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ecu_table.itemSelectionChanged.connect(self.on_ecu_selected)

        ecu_layout.addWidget(self.ecu_table)
        ecu_group.setLayout(ecu_layout)
        layout.addWidget(ecu_group)

        # Communication patterns
        comm_group = QGroupBox("Communication Patterns")
        comm_layout = QVBoxLayout()

        self.comm_patterns_text = QTextEdit()
        self.comm_patterns_text.setReadOnly(True)

        comm_layout.addWidget(self.comm_patterns_text)
        comm_group.setLayout(comm_layout)
        layout.addWidget(comm_group)

        parent.addWidget(panel)

    def build_network_topology(self):
        """Build the network topology from CAN frames."""
        if not self.frames:
            QMessageBox.warning(self, "No Data", "No frame data available for analysis.")
            return

        self.is_analyzing = True
        self.build_network_button.setEnabled(False)
        self.status_label.setText("Analyzing network topology...")

        # Run analysis in background thread
        self.analysis_thread = NetworkAnalysisThread(
            self.frames,
            self.include_broadcast_check.isChecked()
        )

        self.analysis_thread.analysis_complete.connect(self.on_analysis_complete)
        self.analysis_thread.start()

    def on_analysis_complete(self, network_data):
        """Handle network analysis completion."""
        self.is_analyzing = False
        self.build_network_button.setEnabled(True)

        self.network_graph = network_data
        self.visualize_network()

        self.status_label.setText("Network topology analysis complete")

    def visualize_network(self):
        """Visualize the network topology."""
        if not self.network_graph:
            return

        # Clear existing visualization
        self.network_scene.clear()
        self.ecu_nodes = {}

        # Get layout positions
        if HAS_NETWORKX and self.auto_layout_check.isChecked():
            positions = self.calculate_layout()
        else:
            positions = self.calculate_circular_layout()

        self.node_positions = positions

        # Create nodes
        for ecu_id, ecu_data in self.network_graph.get('ecus', {}).items():
            self.create_network_node(ecu_id, ecu_data, positions.get(ecu_id, (0, 0)))

        # Create edges
        for connection in self.network_graph.get('connections', []):
            self.create_network_edge(connection)

        # Update analysis displays
        self.update_network_stats()
        self.update_ecu_table()
        self.update_comm_patterns()

        # Fit view
        self.fit_to_view()

    def calculate_layout(self):
        """Calculate node positions using NetworkX."""
        if not HAS_NETWORKX or not self.network_graph:
            return self.calculate_circular_layout()

        try:
            # Create NetworkX graph
            G = nx.DiGraph()

            # Add nodes
            for ecu_id in self.network_graph.get('ecus', {}):
                G.add_node(ecu_id)

            # Add edges with weights
            for conn in self.network_graph.get('connections', []):
                source = conn['source']
                target = conn['target']
                weight = conn.get('message_count', 1)
                G.add_edge(source, target, weight=weight)

            # Calculate layout
            layout_name = self.layout_combo.currentText().lower()
            if layout_name == "spring":
                pos = nx.spring_layout(G, weight='weight')
            elif layout_name == "circular":
                pos = nx.circular_layout(G)
            elif layout_name == "random":
                pos = nx.random_layout(G)
            elif layout_name == "shell":
                pos = nx.shell_layout(G)
            elif layout_name == "spectral":
                pos = nx.spectral_layout(G)
            else:
                pos = nx.spring_layout(G)

            # Scale positions to scene coordinates
            positions = {}
            if pos:
                x_coords = [p[0] for p in pos.values()]
                y_coords = [p[1] for p in pos.values()]

                if x_coords and y_coords:
                    x_min, x_max = min(x_coords), max(x_coords)
                    y_min, y_max = min(y_coords), max(y_coords)

                    x_range = x_max - x_min if x_max != x_min else 1
                    y_range = y_max - y_min if y_max != y_min else 1

                    for node, (x, y) in pos.items():
                        scene_x = (x - x_min) / x_range * 800 + 100
                        scene_y = (y - y_min) / y_range * 600 + 100
                        positions[node] = (scene_x, scene_y)

            return positions

        except Exception as e:
            print(f"Layout calculation failed: {e}")
            return self.calculate_circular_layout()

    def calculate_circular_layout(self):
        """Calculate circular layout as fallback."""
        if not self.network_graph:
            return {}

        ecus = list(self.network_graph.get('ecus', {}).keys())
        n_nodes = len(ecus)

        if n_nodes == 0:
            return {}

        positions = {}
        center_x, center_y = 500, 400
        radius = 200

        for i, ecu_id in enumerate(ecus):
            angle = 2 * math.pi * i / n_nodes
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            positions[ecu_id] = (x, y)

        return positions

    def create_network_node(self, ecu_id, ecu_data, position):
        """Create a network node for an ECU."""
        x, y = position

        # Determine node size based on activity
        message_count = ecu_data.get('message_count', 0)
        if self.node_size_combo.currentText() == "By Message Count":
            size = max(20, min(60, 20 + message_count / 10))
        elif self.node_size_combo.currentText() == "By Data Volume":
            data_volume = ecu_data.get('data_volume', 0)
            size = max(20, min(60, 20 + data_volume / 100))
        else:  # Fixed
            size = 40

        # Create node circle
        node = QGraphicsEllipseItem(x - size/2, y - size/2, size, size)
        node.setBrush(QBrush(QColor(100, 150, 255, 200)))
        node.setPen(QPen(QColor(50, 100, 200), 2))

        # Add to scene
        self.network_scene.addItem(node)

        # Create label
        if self.show_labels_check.isChecked():
            label = QGraphicsTextItem(f"0x{ecu_id:03X}")
            label.setPos(x - 30, y + size/2 + 5)
            label.setDefaultTextColor(QColor(0, 0, 0))
            font = label.font()
            font.setPointSize(8)
            label.setFont(font)
            self.network_scene.addItem(label)

        # Store node reference
        self.ecu_nodes[ecu_id] = {
            'item': node,
            'position': (x, y),
            'size': size,
            'data': ecu_data
        }

    def create_network_edge(self, connection):
        """Create an edge between two ECUs."""
        source_id = connection['source']
        target_id = connection['target']

        if source_id not in self.ecu_nodes or target_id not in self.ecu_nodes:
            return

        source_pos = self.ecu_nodes[source_id]['position']
        target_pos = self.ecu_nodes[target_id]['position']

        # Create line
        line = QGraphicsLineItem(source_pos[0], source_pos[1], target_pos[0], target_pos[1])
        line.setPen(QPen(QColor(150, 150, 150), 2))

        self.network_scene.addItem(line)

        # Add message count label on edge
        if connection.get('message_count', 0) > 0:
            mid_x = (source_pos[0] + target_pos[0]) / 2
            mid_y = (source_pos[1] + target_pos[1]) / 2

            count_label = QGraphicsTextItem(str(connection['message_count']))
            count_label.setPos(mid_x - 10, mid_y - 10)
            count_label.setDefaultTextColor(QColor(100, 100, 100))
            font = count_label.font()
            font.setPointSize(7)
            count_label.setFont(font)
            self.network_scene.addItem(count_label)

    def update_network_stats(self):
        """Update network statistics display."""
        if not self.network_graph:
            return

        stats = "Network Statistics\n\n"

        ecus = self.network_graph.get('ecus', {})
        connections = self.network_graph.get('connections', [])

        stats += f"ECUs Detected: {len(ecus)}\n"
        stats += f"Connections: {len(connections)}\n"
        stats += f"Total Messages: {sum(ecu.get('message_count', 0) for ecu in ecus.values())}\n"
        stats += f"Total Data Volume: {sum(ecu.get('data_volume', 0) for ecu in ecus.values())} bytes\n\n"

        # Network density
        if len(ecus) > 1:
            max_connections = len(ecus) * (len(ecus) - 1)
            density = len(connections) / max_connections if max_connections > 0 else 0
            stats += f"Network Density: {density:.3f}\n"

        # Most active ECU
        if ecus:
            most_active = max(ecus.items(), key=lambda x: x[1].get('message_count', 0))
            stats += f"Most Active ECU: 0x{most_active[0]:03X} ({most_active[1].get('message_count', 0)} messages)\n"

        self.network_stats_text.setText(stats)

    def update_ecu_table(self):
        """Update the ECU details table."""
        if not self.network_graph:
            return

        ecus = self.network_graph.get('ecus', {})
        ecu_list = sorted(ecus.items(), key=lambda x: x[1].get('message_count', 0), reverse=True)

        self.ecu_table.setRowCount(len(ecu_list))

        for row, (ecu_id, ecu_data) in enumerate(ecu_list):
            # ECU ID
            id_item = QTableWidgetItem(f"0x{ecu_id:03X}")
            self.ecu_table.setItem(row, 0, id_item)

            # Messages
            msg_item = QTableWidgetItem(str(ecu_data.get('message_count', 0)))
            self.ecu_table.setItem(row, 1, msg_item)

            # Data volume
            data_item = QTableWidgetItem(str(ecu_data.get('data_volume', 0)))
            self.ecu_table.setItem(row, 2, data_item)

            # Activity level
            msg_count = ecu_data.get('message_count', 0)
            if msg_count > 1000:
                activity = "Very High"
            elif msg_count > 500:
                activity = "High"
            elif msg_count > 100:
                activity = "Medium"
            elif msg_count > 10:
                activity = "Low"
            else:
                activity = "Very Low"

            activity_item = QTableWidgetItem(activity)
            self.ecu_table.setItem(row, 3, activity_item)

    def update_comm_patterns(self):
        """Update communication patterns analysis."""
        if not self.network_graph:
            return

        patterns = "Communication Patterns\n\n"

        connections = self.network_graph.get('connections', [])

        if not connections:
            patterns += "No communication patterns detected.\n"
            self.comm_patterns_text.setText(patterns)
            return

        # Sort by message count
        sorted_connections = sorted(connections,
                                  key=lambda x: x.get('message_count', 0),
                                  reverse=True)

        patterns += "Top Communication Channels:\n"
        for i, conn in enumerate(sorted_connections[:10]):
            patterns += f"{i+1}. 0x{conn['source']:03X} → 0x{conn['target']:03X}: "
            patterns += f"{conn.get('message_count', 0)} messages\n"

        patterns += "\n"

        # Communication direction analysis
        outgoing = collections.Counter()
        incoming = collections.Counter()

        for conn in connections:
            outgoing[conn['source']] += conn.get('message_count', 0)
            incoming[conn['target']] += conn.get('message_count', 0)

        # Most talkative ECU
        if outgoing:
            most_talkative = outgoing.most_common(1)[0]
            patterns += f"Most Talkative ECU: 0x{most_talkative[0]:03X} "
            patterns += f"({most_talkative[1]} outgoing messages)\n"

        # Most listened-to ECU
        if incoming:
            most_listened = incoming.most_common(1)[0]
            patterns += f"Most Listened-to ECU: 0x{most_listened[0]:03X} "
            patterns += f"({most_listened[1]} incoming messages)\n"

        self.comm_patterns_text.setText(patterns)

    def on_ecu_selected(self):
        """Handle ECU selection in table."""
        current_row = self.ecu_table.currentRow()
        if current_row >= 0:
            ecu_id_text = self.ecu_table.item(current_row, 0).text()
            ecu_id = int(ecu_id_text, 16)

            # Highlight selected node
            self.highlight_node(ecu_id)

    def highlight_node(self, ecu_id):
        """Highlight a specific node in the visualization."""
        # Reset all nodes
        for node_data in self.ecu_nodes.values():
            node_data['item'].setBrush(QBrush(QColor(100, 150, 255, 200)))

        # Highlight selected node
        if ecu_id in self.ecu_nodes:
            self.ecu_nodes[ecu_id]['item'].setBrush(QBrush(QColor(255, 200, 100, 255)))

    def zoom_in(self):
        """Zoom in on the network view."""
        self.network_view.scale(1.2, 1.2)

    def zoom_out(self):
        """Zoom out on the network view."""
        self.network_view.scale(0.8, 0.8)

    def fit_to_view(self):
        """Fit the network view to show all nodes."""
        if self.network_scene.items():
            self.network_view.fitInView(self.network_scene.sceneRect(), Qt.KeepAspectRatio)

    def export_as_image(self):
        """Export the network visualization as an image."""
        # This would require additional implementation for image export
        QMessageBox.information(self, "Export", "Image export not yet implemented.")

    def export_as_graphml(self):
        """Export the network as GraphML format."""
        # This would require additional implementation for GraphML export
        QMessageBox.information(self, "Export", "GraphML export not yet implemented.")

    def set_frames(self, frames):
        """Set the frames data source."""
        self.frames = frames or []


class NetworkAnalysisThread(QThread):
    """Background thread for network topology analysis."""

    analysis_complete = pyqtSignal(dict)

    def __init__(self, frames, include_broadcast=True):
        super().__init__()
        self.frames = frames
        self.include_broadcast = include_broadcast

    def run(self):
        """Analyze network topology from frames."""
        # Group frames by source ECU (simplified - using CAN ID ranges)
        ecu_messages = collections.defaultdict(list)

        for frame in self.frames:
            # Simple ECU identification based on CAN ID ranges
            # This is a simplification - real implementation would use DBC or other methods
            ecu_id = self.identify_ecu(frame.id)
            ecu_messages[ecu_id].append(frame)

        # Build ECU data
        ecus = {}
        for ecu_id, messages in ecu_messages.items():
            ecus[ecu_id] = {
                'message_count': len(messages),
                'data_volume': sum(len(frame.data) if hasattr(frame, 'data') and frame.data else 0
                                 for frame in messages),
                'can_ids': set(frame.id for frame in messages),
                'last_activity': max((frame.timestamp for frame in messages
                                    if hasattr(frame, 'timestamp')), default=0)
            }

        # Build connections (simplified - assuming communication patterns)
        connections = []
        ecu_ids = list(ecus.keys())

        # Create connections based on message patterns
        # This is a simplified analysis
        for i, source_id in enumerate(ecu_ids):
            for j, target_id in enumerate(ecu_ids):
                if i != j:
                    # Count messages that could be responses or related
                    source_messages = ecu_messages[source_id]
                    target_messages = ecu_messages[target_id]

                    # Simple heuristic: if there are messages from both ECUs,
                    # assume they communicate
                    if source_messages and target_messages:
                        message_count = min(len(source_messages), len(target_messages))
                        if message_count > 0:
                            connections.append({
                                'source': source_id,
                                'target': target_id,
                                'message_count': message_count,
                                'data_flow': 'bidirectional'
                            })

        network_data = {
            'ecus': ecus,
            'connections': connections,
            'analysis_time': time.time()
        }

        self.analysis_complete.emit(network_data)

    def identify_ecu(self, can_id):
        """Identify ECU from CAN ID (simplified heuristic)."""
        # This is a very simplified ECU identification
        # Real implementation would use DBC files or ECU fingerprinting

        # Group by CAN ID ranges (common in automotive systems)
        if can_id < 0x100:
            return 0x001  # Engine ECU
        elif can_id < 0x200:
            return 0x101  # Transmission ECU
        elif can_id < 0x300:
            return 0x201  # Body Control Module
        elif can_id < 0x400:
            return 0x301  # Instrument Cluster
        elif can_id < 0x500:
            return 0x401  # ABS System
        else:
            return 0x501  # Other Systems