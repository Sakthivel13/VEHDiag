"""Flow View Window - Visualize CAN Message Relationships."""
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QGraphicsView, QGraphicsScene,
                             QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem,
                             QComboBox, QCheckBox, QGroupBox, QSplitter,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QProgressBar)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import QPen, QBrush, QColor, QFont, QPainter
import math


class FlowViewWindow(QMainWindow):
    """Window for visualizing CAN network topology and message flow."""

    def __init__(self, frames=None, parent=None):
        super().__init__(parent)
        self.frames = frames or []
        self.nodes = {}  # ECU nodes
        self.edges = {}  # Message connections
        self.selected_node = None

        self.init_ui()
        if self.frames:
            self.analyze_network()

    def init_ui(self):
        """Initialize the flow view UI."""
        self.setWindowTitle("CAN Network Flow View")
        self.setGeometry(200, 200, 1000, 700)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        central_widget.setLayout(QVBoxLayout())
        central_widget.layout().addWidget(splitter)

        # Left panel - Controls
        self.create_control_panel(splitter)

        # Right panel - Graph view
        self.create_graph_panel(splitter)

        splitter.setSizes([250, 750])

        # Status bar
        self.status_label = QLabel("Ready")
        central_widget.layout().addWidget(self.status_label)

    def create_control_panel(self, parent):
        """Create the control panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Analysis controls
        analysis_group = QGroupBox("Network Analysis")
        analysis_layout = QVBoxLayout()

        self.analyze_button = QPushButton("Analyze Network")
        self.analyze_button.clicked.connect(self.analyze_network)

        self.clear_button = QPushButton("Clear View")
        self.clear_button.clicked.connect(self.clear_view)

        analysis_layout.addWidget(self.analyze_button)
        analysis_layout.addWidget(self.clear_button)
        analysis_group.setLayout(analysis_layout)
        layout.addWidget(analysis_group)

        # Display options
        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout()

        self.show_labels_check = QCheckBox("Show Node Labels")
        self.show_labels_check.setChecked(True)
        self.show_labels_check.stateChanged.connect(self.update_display)

        self.show_weights_check = QCheckBox("Show Message Counts")
        self.show_weights_check.setChecked(True)
        self.show_weights_check.stateChanged.connect(self.update_display)

        self.auto_layout_check = QCheckBox("Auto Layout")
        self.auto_layout_check.setChecked(True)

        display_layout.addWidget(self.show_labels_check)
        display_layout.addWidget(self.show_weights_check)
        display_layout.addWidget(self.auto_layout_check)
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        # Layout algorithm
        layout_group = QGroupBox("Layout")
        layout_layout = QVBoxLayout()

        self.layout_combo = QComboBox()
        self.layout_combo.addItems([
            "Circular",
            "Force Directed",
            "Hierarchical",
            "Grid"
        ])
        self.layout_combo.currentTextChanged.connect(self.apply_layout)

        layout_layout.addWidget(self.layout_combo)
        layout_group.setLayout(layout_layout)
        layout.addWidget(layout_group)

        # Node info
        info_group = QGroupBox("Selected Node")
        info_layout = QVBoxLayout()

        self.node_info_table = QTableWidget()
        self.node_info_table.setColumnCount(2)
        self.node_info_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.node_info_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.node_info_table.setMaximumHeight(150)

        info_layout.addWidget(self.node_info_table)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        layout.addStretch()
        parent.addWidget(panel)

    def create_graph_panel(self, parent):
        """Create the graph visualization panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Graphics view
        self.graphics_view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.graphics_view.setScene(self.scene)
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        self.graphics_view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.graphics_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # Zoom controls
        zoom_layout = QHBoxLayout()

        zoom_in_button = QPushButton("Zoom In")
        zoom_in_button.clicked.connect(self.zoom_in)

        zoom_out_button = QPushButton("Zoom Out")
        zoom_out_button.clicked.connect(self.zoom_out)

        fit_button = QPushButton("Fit to View")
        fit_button.clicked.connect(self.fit_to_view)

        zoom_layout.addWidget(zoom_in_button)
        zoom_layout.addWidget(zoom_out_button)
        zoom_layout.addWidget(fit_button)
        zoom_layout.addStretch()

        layout.addLayout(zoom_layout)
        layout.addWidget(self.graphics_view)

        parent.addWidget(panel)

    def analyze_network(self):
        """Analyze the CAN frames to build network topology."""
        if not self.frames:
            QMessageBox.warning(self, "No Data",
                               "No CAN frames available for analysis.")
            return

        self.status_label.setText("Analyzing network topology...")

        try:
            # Clear existing data
            self.clear_view()

            # Analyze frames to identify ECUs and message patterns
            self.identify_ecus()
            self.identify_message_flows()

            # Create visual representation
            self.create_visualization()

            self.status_label.setText(f"Network analysis complete. Found {len(self.nodes)} ECUs.")

        except Exception as e:
            self.status_label.setText("Analysis failed")
            QMessageBox.critical(self, "Analysis Error", f"Error analyzing network: {str(e)}")

    def identify_ecus(self):
        """Identify ECUs from CAN frames."""
        ecu_candidates = set()

        # Simple heuristic: group by message patterns
        # In a real implementation, this would use more sophisticated analysis
        for frame in self.frames[:1000]:  # Sample first 1000 frames
            # Use message ID patterns to identify potential ECUs
            msg_id = frame.id

            # Simple clustering based on ID ranges
            if 0x000 <= msg_id <= 0x0FF:
                ecu_candidates.add("ECU_0x000_0x0FF")
            elif 0x100 <= msg_id <= 0x1FF:
                ecu_candidates.add("ECU_0x100_0x1FF")
            elif 0x200 <= msg_id <= 0x2FF:
                ecu_candidates.add("ECU_0x200_0x2FF")
            elif 0x300 <= msg_id <= 0x3FF:
                ecu_candidates.add("ECU_0x300_0x3FF")
            else:
                ecu_candidates.add(f"ECU_{msg_id >> 8:X}XX")

        # Create nodes for identified ECUs
        angle_step = 2 * math.pi / len(ecu_candidates)
        radius = 200

        for i, ecu_id in enumerate(sorted(ecu_candidates)):
            angle = i * angle_step
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)

            node = NetworkNode(ecu_id, x, y)
            self.nodes[ecu_id] = node

    def identify_message_flows(self):
        """Identify message flows between ECUs."""
        # This is a simplified analysis
        # In practice, you'd need more sophisticated logic

        # Create some example connections
        ecu_list = list(self.nodes.keys())
        if len(ecu_list) >= 2:
            # Connect first two ECUs
            source = self.nodes[ecu_list[0]]
            target = self.nodes[ecu_list[1]]

            edge = NetworkEdge(source, target, 150)  # 150 messages
            self.edges[f"{ecu_list[0]}-{ecu_list[1]}"] = edge

    def create_visualization(self):
        """Create the visual representation of the network."""
        # Add nodes to scene
        for node in self.nodes.values():
            self.scene.addItem(node)

        # Add edges to scene
        for edge in self.edges.values():
            self.scene.addItem(edge)

        # Apply layout
        self.apply_layout()

        # Fit view
        self.fit_to_view()

    def apply_layout(self):
        """Apply the selected layout algorithm."""
        layout_type = self.layout_combo.currentText()

        if layout_type == "Circular":
            self.apply_circular_layout()
        elif layout_type == "Force Directed":
            self.apply_force_directed_layout()
        elif layout_type == "Hierarchical":
            self.apply_hierarchical_layout()
        elif layout_type == "Grid":
            self.apply_grid_layout()

        self.update_display()

    def apply_circular_layout(self):
        """Apply circular layout."""
        nodes = list(self.nodes.values())
        if not nodes:
            return

        angle_step = 2 * math.pi / len(nodes)
        radius = 200

        for i, node in enumerate(nodes):
            angle = i * angle_step
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            node.setPos(x, y)

    def apply_force_directed_layout(self):
        """Apply force-directed layout (simplified)."""
        # This would implement a force-directed algorithm
        # For now, just use circular
        self.apply_circular_layout()

    def apply_hierarchical_layout(self):
        """Apply hierarchical layout."""
        nodes = list(self.nodes.values())
        if not nodes:
            return

        # Simple hierarchical layout
        level_height = 100
        for i, node in enumerate(nodes):
            x = (i % 3) * 150 - 150  # 3 nodes per level
            y = (i // 3) * level_height
            node.setPos(x, y)

    def apply_grid_layout(self):
        """Apply grid layout."""
        nodes = list(self.nodes.values())
        if not nodes:
            return

        cols = int(math.sqrt(len(nodes)))
        rows = (len(nodes) + cols - 1) // cols

        spacing = 120
        for i, node in enumerate(nodes):
            row = i // cols
            col = i % cols
            x = (col - (cols - 1) / 2) * spacing
            y = (row - (rows - 1) / 2) * spacing
            node.setPos(x, y)

    def update_display(self):
        """Update the display based on current options."""
        show_labels = self.show_labels_check.isChecked()
        show_weights = self.show_weights_check.isChecked()

        for node in self.nodes.values():
            node.set_labels_visible(show_labels)

        for edge in self.edges.values():
            edge.set_weights_visible(show_weights)

        self.scene.update()

    def zoom_in(self):
        """Zoom in the view."""
        self.graphics_view.scale(1.2, 1.2)

    def zoom_out(self):
        """Zoom out the view."""
        self.graphics_view.scale(0.8, 0.8)

    def fit_to_view(self):
        """Fit the entire network in the view."""
        if self.scene.items():
            self.graphics_view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def clear_view(self):
        """Clear the current network view."""
        self.scene.clear()
        self.nodes.clear()
        self.edges.clear()
        self.selected_node = None
        self.update_node_info()

    def update_node_info(self, node=None):
        """Update the node information panel."""
        self.node_info_table.setRowCount(0)

        if node:
            properties = [
                ("ID", node.node_id),
                ("Messages", str(getattr(node, 'message_count', 0))),
                ("Connections", str(len([e for e in self.edges.values()
                                        if e.source == node or e.target == node]))),
                ("Position", f"({node.pos().x():.1f}, {node.pos().y():.1f})")
            ]

            for prop, value in properties:
                row = self.node_info_table.rowCount()
                self.node_info_table.insertRow(row)
                self.node_info_table.setItem(row, 0, QTableWidgetItem(prop))
                self.node_info_table.setItem(row, 1, QTableWidgetItem(str(value)))

    def set_frames(self, frames):
        """Set the frames to analyze."""
        self.frames = frames or []
        self.status_label.setText(f"Loaded {len(self.frames)} frames")


class NetworkNode(QGraphicsEllipseItem):
    """Represents an ECU node in the network visualization."""

    def __init__(self, node_id, x, y):
        super().__init__(-25, -25, 50, 50)  # 50x50 circle
        self.node_id = node_id
        self.message_count = 0

        # Set appearance
        self.setBrush(QBrush(QColor(100, 150, 255)))
        self.setPen(QPen(Qt.black, 2))

        # Position
        self.setPos(x, y)

        # Label
        self.label = QGraphicsTextItem(node_id, self)
        self.label.setPos(-self.label.boundingRect().width() / 2, 30)
        font = QFont()
        font.setPointSize(8)
        self.label.setFont(font)

        # Make selectable
        self.setFlag(QGraphicsEllipseItem.ItemIsSelectable)

    def set_labels_visible(self, visible):
        """Show or hide node labels."""
        self.label.setVisible(visible)


class NetworkEdge(QGraphicsLineItem):
    """Represents a message connection between ECUs."""

    def __init__(self, source, target, weight=1):
        # Calculate line from center of source to center of target
        source_center = source.pos()
        target_center = target.pos()

        super().__init__(source_center.x(), source_center.y(),
                         target_center.x(), target_center.y())

        self.source = source
        self.target = target
        self.weight = weight

        # Set appearance based on weight
        pen = QPen(QColor(150, 150, 150), max(1, min(5, weight / 50)))
        self.setPen(pen)

        # Weight label
        self.weight_label = QGraphicsTextItem(str(weight), self)
        mid_x = (source_center.x() + target_center.x()) / 2
        mid_y = (source_center.y() + target_center.y()) / 2
        self.weight_label.setPos(mid_x, mid_y)

        font = QFont()
        font.setPointSize(7)
        self.weight_label.setFont(font)

    def set_weights_visible(self, visible):
        """Show or hide weight labels."""
        self.weight_label.setVisible(visible)

    def update_position(self):
        """Update the edge position when nodes move."""
        source_pos = self.source.pos()
        target_pos = self.target.pos()

        self.setLine(source_pos.x(), source_pos.y(),
                   target_pos.x(), target_pos.y())

        # Update weight label position
        mid_x = (source_pos.x() + target_pos.x()) / 2
        mid_y = (source_pos.y() + target_pos.y()) / 2
        self.weight_label.setPos(mid_x, mid_y)