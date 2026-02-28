"""
OSM Downloader Dialog - Dockable Widget
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal, QThread, QTimer
from qgis.PyQt.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
                                 QLabel, QLineEdit, QPushButton, QListWidget, 
                                 QListWidgetItem, QCheckBox, QProgressBar, 
                                 QMessageBox, QGroupBox, QSpinBox, QDoubleSpinBox, QTextEdit, QFileDialog,
                                 QDialog, QComboBox, QDialogButtonBox, QScrollArea)
from qgis.core import (QgsProject, QgsVectorLayer, QgsMessageLog, Qgis, 
                       QgsSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer,
                       QgsSimpleLineSymbolLayer, QgsSimpleFillSymbolLayer,
                       QgsMarkerSymbol, QgsLineSymbol, QgsFillSymbol,
                       QgsRectangle, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsRasterLayer, QgsWkbTypes, QgsFeature, QgsGeometry, QgsUnitTypes)
from qgis.PyQt.QtGui import QColor
from qgis import processing
import json
import tempfile
import os

from .osm_api import OSMAPIHandler
from .feature_configs import get_all_features
from .svg_exporter import SVGExporter


class DownloadWorker(QThread):
    """Worker thread for downloading OSM data"""
    progress = pyqtSignal(str)
    layer_ready = pyqtSignal(dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, place_name, selected_features, bbox):
        super().__init__()
        self.place_name = place_name
        self.selected_features = selected_features
        self.bbox = bbox
        self.api_handler = OSMAPIHandler()
        
    def run(self):
        """Download all selected features"""
        for feature_config in self.selected_features:
            self.progress.emit(f"Downloading {feature_config['display']}...")
            
            try:
                geojson = self.api_handler.download_feature(self.bbox, feature_config)
                
                if geojson and len(geojson['features']) > 0:
                    # Emit layer immediately so it can be added to QGIS
                    self.layer_ready.emit({
                        'config': feature_config,
                        'geojson': geojson
                    })
                    
                    # Create labels if needed
                    if feature_config.get('create_labels', False):
                        labels_geojson = self.api_handler.create_labels_geojson(geojson)
                        if labels_geojson['features']:
                            self.layer_ready.emit({
                                'config': {
                                    'name': feature_config['name'] + '_labels',
                                    'display': feature_config['display'] + ' Labels',
                                    'style': {'color': '#000000', 'weight': 1}
                                },
                                'geojson': labels_geojson
                            })
                    
                    self.progress.emit(f"✓ Downloaded {len(geojson['features'])} features")
                else:
                    self.progress.emit(f"⚠ No features found for {feature_config['display']}")
                
                # Small delay to respect API limits
                self.msleep(2000)
                
            except Exception as e:
                self.error.emit(f"Error downloading {feature_config['display']}: {str(e)}")
        
        self.finished.emit()


class OSMDownloaderDialog(QDockWidget):
    """Dockable widget for OSM Bulk Downloader"""
    
    def __init__(self, iface):
        super().__init__("OSM Bulk Downloader")
        self.iface = iface
        self.api_handler = OSMAPIHandler()
        self.bbox = None
        self.download_worker = None
        self.downloaded_layers = []  # Track downloaded layers for export
        self.osm_basemap = None
        
        # Buffer settings with defaults
        self.buffer_major = 0.00005
        self.buffer_local = 0.000025
        self.buffer_residential = 0.000015
        
        # Create UI
        self.setup_ui()
        
        # Reset state to fresh start
        self.reset_plugin_state()
    
    def reset_plugin_state(self):
        """Reset plugin to fresh state"""
        # Clear search
        self.place_input.clear()
        self.bbox = None
        self.bbox_label.setText("")
        
        # Clear feature selections
        for i in range(self.feature_list.count()):
            item = self.feature_list.item(i)
            item.setSelected(False)
        
        # Clear downloaded layers list
        self.downloaded_layers = []
        
        # Clear progress
        self.progress_text.clear()
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        
        # Reset buttons
        self.download_btn.setEnabled(False)
        self.export_svg_btn.setEnabled(False)
        self.export_svg_btn.setVisible(False)
        self.style_editor_btn.setEnabled(False)
        self.style_editor_btn.setVisible(False)
        self.make_roads_poly_btn.setEnabled(False)
        self.enable_all_labels_btn.setEnabled(False)
        self.make_roads_gray_btn.setEnabled(False)
        
        # Reset zoom padding to default
        self.zoom_padding.setValue(10)
        
        # Uncheck canvas extent
        self.use_canvas_extent.setChecked(False)
        
        self.log_progress("Plugin reset to fresh state")
    
    def closeEvent(self, event):
        """Handle plugin close - clear all state"""
        # Clear map layers if any were added
        if self.downloaded_layers:
            for layer in self.downloaded_layers:
                if layer and layer.isValid():
                    QgsProject.instance().removeMapLayer(layer.id())
        
        # Remove basemap if it exists
        if self.osm_basemap and self.osm_basemap.isValid():
            QgsProject.instance().removeMapLayer(self.osm_basemap.id())
        
        # Clear all state
        self.downloaded_layers = []
        self.osm_basemap = None
        self.bbox = None
        
        # Accept the close event
        event.accept()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Main widget
        main_widget = QWidget()
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # Set main widget in scroll area
        scroll_area.setWidget(main_widget)
        self.setWidget(scroll_area)
        
        # Apply modern styling
        self.apply_modern_style()
        
        # Title header
        title_label = QLabel("🗺️ OSM Bulk Downloader")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #2ecc71);
                color: white;
                border-radius: 5px;
                margin-bottom: 5px;
            }
        """)
        layout.addWidget(title_label)
        
        # Place name input
        place_group = QGroupBox("📍 Location")
        place_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #ecf9ff;
            }
            QGroupBox::title {
                color: #2980b9;
                subcontrol-origin: margin;
                padding: 5px 10px;
                background-color: white;
                border-radius: 3px;
            }
        """)
        place_layout = QVBoxLayout()
        place_group.setLayout(place_layout)
        
        place_input_layout = QHBoxLayout()
        place_layout.addLayout(place_input_layout)
        
        self.place_input = QLineEdit()
        self.place_input.setPlaceholderText("Enter place name (e.g., 'Stow, Ohio')")
        self.place_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #3498db;
                border-radius: 5px;
                font-size: 11px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 2px solid #2ecc71;
            }
        """)
        place_input_layout.addWidget(self.place_input)
        
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self.search_place)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        place_input_layout.addWidget(self.search_btn)
        
        self.bbox_label = QLabel("")
        self.bbox_label.setWordWrap(True)
        self.bbox_label.setStyleSheet("color: #7f8c8d; padding: 5px; font-size: 10px;")
        place_layout.addWidget(self.bbox_label)
        
        # Zoom padding
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom Padding:"))
        self.zoom_padding = QSpinBox()
        self.zoom_padding.setRange(0, 50)
        self.zoom_padding.setValue(10)  # Default 10% padding
        self.zoom_padding.setSuffix("%")
        self.zoom_padding.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                background-color: white;
            }
        """)
        zoom_layout.addWidget(self.zoom_padding)
        zoom_layout.addStretch()
        place_layout.addLayout(zoom_layout)
        
        # Canvas extent option
        self.use_canvas_extent = QCheckBox("🖼️ Use canvas extent (not search area)")
        self.use_canvas_extent.setToolTip("Download features for entire visible map canvas instead of searched location")
        self.use_canvas_extent.stateChanged.connect(self.on_canvas_extent_changed)
        self.use_canvas_extent.setStyleSheet("""
            QCheckBox {
                color: #2c3e50;
                font-weight: bold;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        place_layout.addWidget(self.use_canvas_extent)
        
        layout.addWidget(place_group)
        
        # Feature selection
        features_group = QGroupBox("✨ Select Features to Download")
        features_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #2ecc71;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #eafaf1;
            }
            QGroupBox::title {
                color: #27ae60;
                subcontrol-origin: margin;
                padding: 5px 10px;
                background-color: white;
                border-radius: 3px;
            }
        """)
        features_layout = QVBoxLayout()
        features_group.setLayout(features_layout)
        
        # Feature list
        self.feature_list = QListWidget()
        self.feature_list.setSelectionMode(QListWidget.MultiSelection)
        self.feature_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #2ecc71;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #d5f4e6;
            }
        """)
        self.populate_feature_list()
        features_layout.addWidget(self.feature_list)
        
        layout.addWidget(features_group)
        
        # Options group
        options_group = QGroupBox("⚙️ Options")
        options_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #f39c12;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #fef5e7;
            }
            QGroupBox::title {
                color: #d68910;
                subcontrol-origin: margin;
                padding: 5px 10px;
                background-color: white;
                border-radius: 3px;
            }
        """)
        options_layout = QVBoxLayout()
        options_group.setLayout(options_layout)
        
        checkbox_style = """
            QCheckBox {
                color: #2c3e50;
                padding: 3px;
                font-size: 10px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: white;
                border: 2px solid #bdc3c7;
            }
            QCheckBox::indicator:checked {
                background-color: #f39c12;
                border: 2px solid #d68910;
            }
        """
        
        options_row1 = QHBoxLayout()
        self.clear_basemap_export = QCheckBox("🗺️ Clear base map on export")
        self.clear_basemap_export.setChecked(True)
        self.clear_basemap_export.setStyleSheet(checkbox_style)
        options_row1.addWidget(self.clear_basemap_export)
        
        self.make_roads_gray_export = QCheckBox("⚫ Make all roads gray on export")
        self.make_roads_gray_export.setStyleSheet(checkbox_style)
        options_row1.addWidget(self.make_roads_gray_export)
        options_layout.addLayout(options_row1)
        
        options_row2 = QHBoxLayout()
        self.abbreviate_labels = QCheckBox("✂️ Abbreviate")
        self.abbreviate_labels.setStyleSheet(checkbox_style)
        options_row2.addWidget(self.abbreviate_labels)
        options_row2.addStretch()  # Push to left
        options_layout.addLayout(options_row2)
        
        layout.addWidget(options_group)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        action_button_style = """
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {color1}, stop:1 {color2});
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {hover1}, stop:1 {hover2});
            }}
            QPushButton:disabled {{
                background-color: #bdc3c7;
                color: #7f8c8d;
            }}
        """
        
        self.buffer_settings_btn = QPushButton("⚙️ Buffer Settings")
        self.buffer_settings_btn.clicked.connect(self.open_buffer_settings)
        self.buffer_settings_btn.setStyleSheet(action_button_style.format(
            color1='#8e44ad', color2='#9b59b6', hover1='#7d3c98', hover2='#8e44ad'
        ))
        control_layout.addWidget(self.buffer_settings_btn)
        
        self.make_roads_poly_btn = QPushButton("🛣️ Make Roads Poly")
        self.make_roads_poly_btn.clicked.connect(self.make_roads_poly)
        self.make_roads_poly_btn.setEnabled(False)
        self.make_roads_poly_btn.setStyleSheet(action_button_style.format(
            color1='#e67e22', color2='#f39c12', hover1='#d35400', hover2='#e67e22'
        ))
        control_layout.addWidget(self.make_roads_poly_btn)
        
        layout.addLayout(control_layout)
        
        control_layout2 = QHBoxLayout()
        
        self.enable_all_labels_btn = QPushButton("🏷️ Enable Water Labels")
        self.enable_all_labels_btn.clicked.connect(self.enable_all_labels)
        self.enable_all_labels_btn.setEnabled(False)
        self.enable_all_labels_btn.setToolTip("Enable labels on water bodies (lakes, bays, etc.)")
        self.enable_all_labels_btn.setStyleSheet(action_button_style.format(
            color1='#16a085', color2='#1abc9c', hover1='#138d75', hover2='#16a085'
        ))
        control_layout2.addWidget(self.enable_all_labels_btn)
        
        layout.addLayout(control_layout2)
        
        control_layout3 = QHBoxLayout()
        
        self.make_roads_gray_btn = QPushButton("⚫ Make All Roads Gray")
        self.make_roads_gray_btn.clicked.connect(self.make_all_roads_gray)
        self.make_roads_gray_btn.setEnabled(False)
        self.make_roads_gray_btn.setStyleSheet(action_button_style.format(
            color1='#7f8c8d', color2='#95a5a6', hover1='#5d6d7e', hover2='#7f8c8d'
        ))
        control_layout3.addWidget(self.make_roads_gray_btn)
        
        self.clear_map_btn = QPushButton("🗑️ Clear Map")
        self.clear_map_btn.clicked.connect(self.clear_map)
        self.clear_map_btn.setStyleSheet(action_button_style.format(
            color1='#e74c3c', color2='#c0392b', hover1='#c0392b', hover2='#922b21'
        ))
        control_layout3.addWidget(self.clear_map_btn)
        
        layout.addLayout(control_layout3)
        
        # Download button
        self.download_btn = QPushButton("🚀 Generate Map")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2ecc71, stop:1 #27ae60);
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #27ae60, stop:1 #229954);
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        layout.addWidget(self.download_btn)
        
        # Export to SVG button (hidden until download completes)
        self.export_svg_btn = QPushButton("💾 Export to SVG")
        self.export_svg_btn.clicked.connect(self.export_to_svg)
        self.export_svg_btn.setEnabled(False)
        self.export_svg_btn.setVisible(False)
        self.export_svg_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2980b9, stop:1 #21618c);
            }
        """)
        layout.addWidget(self.export_svg_btn)
        
        # Style Editor button (hidden until download completes)
        self.style_editor_btn = QPushButton("🎨 Edit Layer Styles")
        self.style_editor_btn.clicked.connect(self.open_style_editor)
        self.style_editor_btn.setEnabled(False)
        self.style_editor_btn.setVisible(False)
        self.style_editor_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #9b59b6, stop:1 #8e44ad);
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8e44ad, stop:1 #7d3c98);
            }
        """)
        layout.addWidget(self.style_editor_btn)
        
        # Progress
        self.progress_text = QTextEdit()
        self.progress_text.setReadOnly(True)
        self.progress_text.setMaximumHeight(100)
        self.progress_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #ecf0f1;
                border-radius: 5px;
                padding: 5px;
                background-color: #fdfefe;
                font-family: 'Courier New', monospace;
                font-size: 10px;
            }
        """)
        layout.addWidget(self.progress_text)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
                background-color: white;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #2ecc71);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
    
    def apply_modern_style(self):
        """Apply modern color scheme to the plugin"""
        self.setStyleSheet("""
            QDockWidget {
                background-color: #f8f9fa;
            }
            QWidget {
                background-color: #f8f9fa;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #2c3e50;
            }
            QSpinBox, QDoubleSpinBox {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                background-color: white;
            }
        """)
    
    def populate_feature_list(self):
        """Populate the feature list"""
        self.feature_list.clear()
        self.all_features = get_all_features()
        
        for feature in self.all_features:
            item = QListWidgetItem(feature['display'])
            item.setData(Qt.UserRole, feature)
            self.feature_list.addItem(item)
    
    def on_canvas_extent_changed(self, state):
        """Handle canvas extent checkbox change"""
        if state == Qt.Checked:
            # Enable download button even without search
            self.download_btn.setEnabled(True)
            self.log_progress("Canvas extent mode enabled - will download from visible map area")
        else:
            # Disable if no bbox from search
            if not self.bbox:
                self.download_btn.setEnabled(False)
    
    def search_place(self):
        """Search for a place and get its bounding box"""
        place_name = self.place_input.text().strip()
        
        if not place_name:
            QMessageBox.warning(self, "Warning", "Please enter a place name")
            return
        
        self.log_progress(f"Searching for '{place_name}'...")
        self.bbox = self.api_handler.search_place(place_name)
        
        if self.bbox:
            south, west, north, east = self.bbox
            self.bbox_label.setText(
                f"Found! Bbox: ({south:.4f}, {west:.4f}, {north:.4f}, {east:.4f})"
            )
            self.download_btn.setEnabled(True)
            self.log_progress("✓ Place found! Select features and click Download.")
            
            # Check if we need to add the basemap
            basemap_needs_adding = not (self.osm_basemap and self.osm_basemap in QgsProject.instance().mapLayers().values())
            
            # Add OSM basemap if not already added
            if basemap_needs_adding:
                self.add_osm_basemap()
                # Delay zoom by 200ms to let basemap settle
                QTimer.singleShot(200, lambda: self.zoom_to_bbox(self.bbox))
                self.log_progress("⏳ Loading basemap, then zooming...")
            else:
                # Basemap already exists, zoom immediately
                self.zoom_to_bbox(self.bbox)
        else:
            self.bbox_label.setText("Place not found")
            self.download_btn.setEnabled(False)
            self.log_progress("✗ Place not found. Try a different name.")
    
    def add_osm_basemap(self):
        """Add OpenStreetMap basemap"""
        # Check if OSM basemap already exists
        if self.osm_basemap and self.osm_basemap in QgsProject.instance().mapLayers().values():
            self.log_progress("OSM basemap already loaded")
            return
        
        # OSM tile service URL
        osm_url = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0"
        
        # Create raster layer
        self.osm_basemap = QgsRasterLayer(osm_url, "OpenStreetMap", "wms")
        
        if self.osm_basemap.isValid():
            QgsProject.instance().addMapLayer(self.osm_basemap)
            # Move to bottom of layer stack
            root = QgsProject.instance().layerTreeRoot()
            layer_node = root.findLayer(self.osm_basemap.id())
            if layer_node:
                clone = layer_node.clone()
                parent = layer_node.parent()
                parent.insertChildNode(-1, clone)
                parent.removeChildNode(layer_node)
            self.log_progress("✓ Added OSM basemap")
        else:
            self.log_progress("⚠ Could not load OSM basemap")
    
    def zoom_to_bbox(self, bbox):
        """Zoom map canvas to bounding box"""
        south, west, north, east = bbox
        
        # Create rectangle in WGS84 (EPSG:4326)
        rect = QgsRectangle(west, south, east, north)
        
        # Get canvas
        canvas = self.iface.mapCanvas()
        
        # Set canvas CRS to WGS84 if not already
        canvas_crs = canvas.mapSettings().destinationCrs()
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        
        if canvas_crs != wgs84_crs:
            # Transform rectangle to canvas CRS
            transform = QgsCoordinateTransform(wgs84_crs, canvas_crs, QgsProject.instance())
            try:
                rect = transform.transformBoundingBox(rect)
            except:
                # If transform fails, set canvas to WGS84
                canvas.setDestinationCrs(wgs84_crs)
        
        # Apply zoom padding
        padding_percent = self.zoom_padding.value()
        scale_factor = 1.0 + (padding_percent / 100.0)
        rect.scale(scale_factor)
        
        # Set extent and force multiple refreshes
        canvas.setExtent(rect)
        canvas.refresh()
        canvas.refreshAllLayers()
        
        self.log_progress(f"✓ Zoomed to location (padding: {padding_percent}%)")
    
    def select_all_features(self):
        """Select all features"""
        for i in range(self.feature_list.count()):
            self.feature_list.item(i).setSelected(True)
    
    def select_no_features(self):
        """Deselect all features"""
        self.feature_list.clearSelection()
    
    def select_water_features(self):
        """Select water-related features"""
        self.select_no_features()
        keywords = ['water', 'river', 'bay', 'beach', 'stream']
        for i in range(self.feature_list.count()):
            item = self.feature_list.item(i)
            feature = item.data(Qt.UserRole)
            if any(k in feature['name'] for k in keywords):
                item.setSelected(True)
    
    def select_road_features(self):
        """Select road-related features"""
        self.select_no_features()
        keywords = ['road', 'trails', 'paths', 'residential']
        for i in range(self.feature_list.count()):
            item = self.feature_list.item(i)
            feature = item.data(Qt.UserRole)
            if any(k in feature['name'] for k in keywords):
                item.setSelected(True)
    
    def select_recreation_features(self):
        """Select recreation features (golf, ski, airports)"""
        self.select_no_features()
        keywords = ['golf', 'ski', 'airport', 'runway']
        for i in range(self.feature_list.count()):
            item = self.feature_list.item(i)
            feature = item.data(Qt.UserRole)
            if any(k in feature['name'] for k in keywords):
                item.setSelected(True)
    
    def start_download(self):
        """Start downloading selected features"""
        # Get bbox - either from search or canvas extent
        download_bbox = None
        
        if self.use_canvas_extent.isChecked():
            # Get current canvas extent
            canvas = self.iface.mapCanvas()
            extent = canvas.extent()
            
            # Transform to WGS84 if needed
            canvas_crs = canvas.mapSettings().destinationCrs()
            wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            
            if canvas_crs != wgs84_crs:
                transform = QgsCoordinateTransform(canvas_crs, wgs84_crs, QgsProject.instance())
                extent = transform.transformBoundingBox(extent)
            
            # Convert to bbox format (south, west, north, east)
            download_bbox = (extent.yMinimum(), extent.xMinimum(), extent.yMaximum(), extent.xMaximum())
            self.log_progress(f"Using canvas extent: {download_bbox}")
        else:
            # Use searched location bbox
            if not self.bbox:
                QMessageBox.warning(self, "Warning", "Please search for a place first or enable 'Use canvas extent'")
                return
            download_bbox = self.bbox
        
        selected_items = self.feature_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select at least one feature")
            return
        
        selected_features = [item.data(Qt.UserRole) for item in selected_items]
        place_name = "Canvas Extent" if self.use_canvas_extent.isChecked() else self.place_input.text().strip()
        
        # Clear previous downloads
        self.downloaded_layers = []
        self.export_svg_btn.setVisible(False)
        self.export_svg_btn.setEnabled(False)
        
        # Disable UI during download
        self.download_btn.setEnabled(False)
        self.search_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_text.clear()
        
        # Start worker thread
        self.download_worker = DownloadWorker(place_name, selected_features, download_bbox)
        self.download_worker.progress.connect(self.log_progress)
        self.download_worker.layer_ready.connect(self.add_layer_immediately)
        self.download_worker.finished.connect(self.download_finished)
        self.download_worker.error.connect(self.download_error)
        self.download_worker.start()
    
    def add_layer_immediately(self, result):
        """Add layer to QGIS as soon as it's downloaded"""
        layer = self.add_layer_to_qgis(result)
        if layer:
            self.downloaded_layers.append(layer)
    
    def download_finished(self):
        """Handle download completion"""
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)
        self.search_btn.setEnabled(True)
        
        if not self.downloaded_layers:
            self.log_progress("\nNo features downloaded.")
            return
        
        self.log_progress(f"\n✓ Complete! Added {len(self.downloaded_layers)} layer(s) to QGIS.")
        
        # Show export and style buttons
        self.export_svg_btn.setVisible(True)
        self.export_svg_btn.setEnabled(True)
        self.style_editor_btn.setVisible(True)
        self.style_editor_btn.setEnabled(True)
        self.make_roads_gray_btn.setEnabled(True)
        self.make_roads_poly_btn.setEnabled(True)
        self.enable_all_labels_btn.setEnabled(True)
        
        QMessageBox.information(self, "Success", 
                               f"Successfully added {len(self.downloaded_layers)} layer(s) to QGIS!\n\n"
                               f"You can now:\n"
                               f"- Edit styles (adjust line widths, colors, labels)\n"
                               f"- Export to SVG")
    
    def download_error(self, error_msg):
        """Handle download error"""
        self.log_progress(f"\n✗ Error: {error_msg}")
        QgsMessageLog.logMessage(error_msg, 'OSM Bulk Downloader', Qgis.Critical)
    
    def add_layer_to_qgis(self, result):
        """Add a GeoJSON layer to QGIS and return the layer object"""
        config = result['config']
        geojson = result['geojson']
        
        # Save GeoJSON to temp file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', 
                                                delete=False)
        json.dump(geojson, temp_file)
        temp_file.close()
        
        # Create layer
        layer_name = config['display']
        layer = QgsVectorLayer(temp_file.name, layer_name, "ogr")
        
        if not layer.isValid():
            self.log_progress(f"✗ Failed to create layer: {layer_name}")
            return None
        
        # Apply styling
        self.apply_style(layer, config.get('style', {}))
        
        # Add to project
        QgsProject.instance().addMapLayer(layer)
        self.log_progress(f"✓ Added layer: {layer_name}")
        
        return layer
    
    def export_to_svg(self):
        """Export ALL canvas layers to SVG with automatic professional styling"""
        # Create export options dialog
        from qgis.PyQt.QtWidgets import QDialog, QComboBox, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("SVG Export Options")
        dialog_layout = QVBoxLayout()
        dialog.setLayout(dialog_layout)
        
        # Paper size selection
        paper_group = QGroupBox("Paper Size")
        paper_layout = QVBoxLayout()
        paper_group.setLayout(paper_layout)
        
        paper_combo = QComboBox()
        paper_combo.addItems(['A4 (210 x 297 mm)', 'A3 (297 x 420 mm)', 
                             'Letter (216 x 279 mm)', 'Tabloid (279 x 432 mm)'])
        paper_layout.addWidget(QLabel("Select paper size:"))
        paper_layout.addWidget(paper_combo)
        
        dialog_layout.addWidget(paper_group)
        
        # Orientation selection
        orientation_group = QGroupBox("Orientation")
        orientation_layout = QVBoxLayout()
        orientation_group.setLayout(orientation_layout)
        
        orientation_combo = QComboBox()
        orientation_combo.addItems(['Auto (fit content)', 'Portrait', 'Landscape'])
        orientation_layout.addWidget(QLabel("Select orientation:"))
        orientation_layout.addWidget(orientation_combo)
        
        dialog_layout.addWidget(orientation_group)
        
        # Margin selection
        margin_group = QGroupBox("Margins")
        margin_layout = QVBoxLayout()
        margin_group.setLayout(margin_layout)
        
        margin_spin = QSpinBox()
        margin_spin.setRange(0, 50)
        margin_spin.setValue(10)
        margin_spin.setSuffix(" mm")
        margin_layout.addWidget(QLabel("Margin size:"))
        margin_layout.addWidget(margin_spin)
        
        dialog_layout.addWidget(margin_group)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        # Get selections
        paper_map = {'A4 (210 x 297 mm)': 'A4', 'A3 (297 x 420 mm)': 'A3',
                    'Letter (216 x 279 mm)': 'Letter', 'Tabloid (279 x 432 mm)': 'Tabloid'}
        paper_size = paper_map[paper_combo.currentText()]
        
        orientation_map = {'Auto (fit content)': 'auto', 'Portrait': 'portrait', 'Landscape': 'landscape'}
        orientation = orientation_map[orientation_combo.currentText()]
        
        margin_mm = margin_spin.value()
        
        # Get save file name
        place_name = self.place_input.text().strip().replace(' ', '_').replace(',', '')
        default_filename = f"{place_name}_map.svg"
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save SVG",
            default_filename,
            "SVG Files (*.svg)"
        )
        
        if not filename:
            return
        
        self.log_progress(f"\nExporting to SVG ({paper_size}, {orientation})...")
        
        try:
            # Step 1: Apply professional styling to ALL canvas layers
            self.log_progress("\n🎨 Applying professional styling...")
            self.apply_professional_styling()
            
            # Step 2: Get ALL canvas layers
            canvas = self.iface.mapCanvas()
            canvas.setCanvasColor(QColor('#f5f1e8'))
            canvas.refresh()
            canvas.refreshAllLayers()
            
            # CRITICAL: Wait for rendering to complete before exporting
            from qgis.PyQt.QtCore import QCoreApplication, QTimer, QEventLoop
            
            self.log_progress("⏳ Waiting for map to render completely...")
            
            # Process events multiple times
            for _ in range(10):
                QCoreApplication.processEvents()
            
            # Wait 800ms for full rendering
            loop = QEventLoop()
            QTimer.singleShot(800, loop.quit)
            loop.exec_()
            
            # Final refresh and process
            canvas.refresh()
            QCoreApplication.processEvents()
            
            self.log_progress("✓ Map rendered and ready for export")
            
            canvas_layers = canvas.layers()
            
            self.log_progress(f"✓ Found {len(canvas_layers)} layers in canvas")
            
            # Step 3: Filter out ONLY basemap (keep everything else!)
            layers_to_export = []
            for layer in canvas_layers:
                if not layer.isValid():
                    self.log_progress(f"  ⚠️ Skipping invalid: {layer.name()}")
                    continue
                # Skip basemap (OpenStreetMap, Google, etc.)
                layer_name_lower = layer.name().lower()
                if any(keyword in layer_name_lower for keyword in ['openstreetmap', 'osm', 'basemap', 'google', 'bing']):
                    self.log_progress(f"  ⏭️ Skipping basemap: {layer.name()}")
                    continue
                layers_to_export.append(layer)
            
            if not layers_to_export:
                raise Exception("No layers to export (only basemap found)")
            
            self.log_progress(f"\n📤 Exporting {len(layers_to_export)} layers:")
            for layer in layers_to_export:
                feature_count = layer.featureCount()
                self.log_progress(f"  ✓ {layer.name()} ({feature_count} features)")
            
            # Use canvas extent (what you see!)
            canvas_extent = canvas.extent()
            
            self.log_progress(f"\n📏 Canvas extent (original CRS):")
            self.log_progress(f"  X: {canvas_extent.xMinimum():.6f} to {canvas_extent.xMaximum():.6f}")
            self.log_progress(f"  Y: {canvas_extent.yMinimum():.6f} to {canvas_extent.yMaximum():.6f}")
            
            if canvas_extent.isEmpty():
                raise Exception("Canvas extent is empty")
            
            # CRITICAL FIX: Transform extent to WGS84 (lat/lon) for SVG
            from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform
            
            canvas_crs = canvas.mapSettings().destinationCrs()
            wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            
            self.log_progress(f"\n🌐 Coordinate transformation:")
            self.log_progress(f"  From: {canvas_crs.authid()} ({canvas_crs.description()})")
            self.log_progress(f"  To: WGS84 (EPSG:4326)")
            
            # Transform extent to lat/lon
            transform = QgsCoordinateTransform(canvas_crs, wgs84_crs, QgsProject.instance())
            extent_wgs84 = transform.transformBoundingBox(canvas_extent)
            
            self.log_progress(f"\n📏 Extent in WGS84 (lat/lon):")
            self.log_progress(f"  Longitude: {extent_wgs84.xMinimum():.6f} to {extent_wgs84.xMaximum():.6f}")
            self.log_progress(f"  Latitude: {extent_wgs84.yMinimum():.6f} to {extent_wgs84.yMaximum():.6f}")
            
            # Add small padding (2%)
            extent = QgsRectangle(extent_wgs84)
            padding_x = extent.width() * 0.02
            padding_y = extent.height() * 0.02
            
            extent.setXMinimum(extent.xMinimum() - padding_x)
            extent.setXMaximum(extent.xMaximum() + padding_x)
            extent.setYMinimum(extent.yMinimum() - padding_y)
            extent.setYMaximum(extent.yMaximum() + padding_y)
            
            # Convert QgsRectangle to bbox tuple (south, west, north, east)
            actual_bbox = (extent.yMinimum(), extent.xMinimum(), extent.yMaximum(), extent.xMaximum())
            
            self.log_progress(f"\n📦 Creating SVG exporter:")
            self.log_progress(f"  Paper: {paper_size}")
            self.log_progress(f"  Orientation: {orientation}")
            self.log_progress(f"  Final bbox (WGS84): {actual_bbox}")
            
            # Create SVG exporter with actual extent (already in WGS84)
            exporter = SVGExporter(actual_bbox, paper_size=paper_size, 
                                 orientation=orientation, margin_mm=margin_mm)
            
            # Export (exporter will check each layer's CRS individually)
            self.log_progress(f"\n🔄 Exporting layers...")
            exporter.export_layers_to_svg(layers_to_export, filename)
            
            self.log_progress(f"✓ SVG exported to: {filename}")
            QMessageBox.information(self, "Success", 
                                  f"SVG exported successfully!\n\n"
                                  f"Paper: {paper_size}\n"
                                  f"Orientation: {orientation}\n"
                                  f"File: {filename}")
            
        except Exception as e:
            error_msg = f"Error exporting SVG: {str(e)}"
            self.log_progress(f"✗ {error_msg}")
            QgsMessageLog.logMessage(error_msg, 'OSM Bulk Downloader', Qgis.Critical)
            QMessageBox.critical(self, "Error", error_msg)
    
    def clear_map(self):
        """Clear all downloaded layers from map"""
        if not self.downloaded_layers:
            return
        
        reply = QMessageBox.question(
            self, 
            "Clear Map",
            "Remove all downloaded layers from the map?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for layer in self.downloaded_layers:
                if layer.isValid():
                    QgsProject.instance().removeMapLayer(layer.id())
            
            self.downloaded_layers = []
            self.export_svg_btn.setVisible(False)
            self.style_editor_btn.setVisible(False)
            self.make_roads_gray_btn.setEnabled(False)
            self.make_roads_poly_btn.setEnabled(False)
            self.log_progress("\n✓ Map cleared")
    
    def open_buffer_settings(self):
        """Open dialog to configure buffer settings"""
        dialog = QDialog(self)
        dialog.setWindowTitle("🛣️ Road Buffer Settings")
        dialog.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QLabel {
                color: #2c3e50;
                font-size: 11px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: white;
            }
            QGroupBox::title {
                color: #2980b9;
                subcontrol-origin: margin;
                padding: 5px 10px;
            }
            QDoubleSpinBox {
                padding: 8px;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                background-color: white;
                font-size: 11px;
            }
            QDoubleSpinBox:focus {
                border: 2px solid #3498db;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2980b9, stop:1 #21618c);
            }
        """)
        dialog_layout = QVBoxLayout()
        dialog.setLayout(dialog_layout)
        
        info_label = QLabel("🎯 Set buffer width for each road type:")
        info_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #2c3e50; padding: 10px;")
        dialog_layout.addWidget(info_label)
        
        # Tip label
        tip_label = QLabel("💡 Tip: Keep original road layers when making poly,\n" +
                          "then adjust these settings and rebuild to preview different widths")
        tip_label.setStyleSheet("color: #3498db; font-style: italic; padding: 5px; background-color: #ecf9ff; border-radius: 5px;")
        tip_label.setWordWrap(True)
        dialog_layout.addWidget(tip_label)
        
        # Form layout for buffer inputs
        form_layout = QVBoxLayout()
        
        # Major roads
        major_group = QGroupBox("🛣️ Major Roads (widest)")
        major_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #e67e22;
                background-color: #fef5e7;
            }
            QGroupBox::title {
                color: #d35400;
            }
        """)
        major_layout = QHBoxLayout()
        major_group.setLayout(major_layout)
        major_layout.addWidget(QLabel("Buffer:"))
        major_spin = QDoubleSpinBox()
        major_spin.setDecimals(8)
        major_spin.setRange(0.000001, 0.001)
        major_spin.setSingleStep(0.000001)
        major_spin.setValue(self.buffer_major)
        major_layout.addWidget(major_spin)
        form_layout.addWidget(major_group)
        
        # Local roads
        local_group = QGroupBox("🚗 Local Roads (medium)")
        local_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #f39c12;
                background-color: #fef9e7;
            }
            QGroupBox::title {
                color: #e67e22;
            }
        """)
        local_layout = QHBoxLayout()
        local_group.setLayout(local_layout)
        local_layout.addWidget(QLabel("Buffer:"))
        local_spin = QDoubleSpinBox()
        local_spin.setDecimals(8)
        local_spin.setRange(0.000001, 0.001)
        local_spin.setSingleStep(0.000001)
        local_spin.setValue(self.buffer_local)
        local_layout.addWidget(local_spin)
        form_layout.addWidget(local_group)
        
        # Residential roads
        residential_group = QGroupBox("🏘️ Residential Roads (thinnest)")
        residential_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #16a085;
                background-color: #eafaf1;
            }
            QGroupBox::title {
                color: #138d75;
            }
        """)
        residential_layout = QHBoxLayout()
        residential_group.setLayout(residential_layout)
        residential_layout.addWidget(QLabel("Buffer:"))
        residential_spin = QDoubleSpinBox()
        residential_spin.setDecimals(8)
        residential_spin.setRange(0.000001, 0.001)
        residential_spin.setSingleStep(0.000001)
        residential_spin.setValue(self.buffer_residential)
        residential_layout.addWidget(residential_spin)
        form_layout.addWidget(residential_group)
        
        dialog_layout.addLayout(form_layout)
        
        # Reset to defaults button
        reset_btn = QPushButton("🔄 Reset to Defaults")
        reset_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #95a5a6, stop:1 #7f8c8d);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7f8c8d, stop:1 #5d6d7e);
            }
        """)
        def reset_defaults():
            major_spin.setValue(0.00005)
            local_spin.setValue(0.000025)
            residential_spin.setValue(0.000015)
        reset_btn.clicked.connect(reset_defaults)
        dialog_layout.addWidget(reset_btn)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.setStyleSheet("""
            QPushButton {
                min-width: 80px;
            }
        """)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            self.buffer_major = major_spin.value()
            self.buffer_local = local_spin.value()
            self.buffer_residential = residential_spin.value()
            
            self.log_progress(f"\n✓ Buffer settings updated:")
            self.log_progress(f"  Major: {self.buffer_major}")
            self.log_progress(f"  Local: {self.buffer_local}")
            self.log_progress(f"  Residential: {self.buffer_residential}")
    
    def make_roads_poly(self):
        """Combine all road layers into hollow polygon with different widths per type"""
        if not self.downloaded_layers:
            return
        
        # Find and categorize road layers
        major_roads = []
        local_roads = []
        residential_roads = []
        label_layers = []
        layers_to_remove = []
        
        for layer in self.downloaded_layers:
            if not layer.isValid():
                continue
            
            layer_name = layer.name().lower()
            
            # Categorize road layers
            if 'label' in layer_name:
                if any(keyword in layer_name for keyword in ['road', 'highway', 'street', 'railway']):
                    label_layers.append(layer)
                    layers_to_remove.append(layer)
            elif 'major' in layer_name:
                if layer.geometryType() == QgsWkbTypes.LineGeometry:
                    major_roads.append(layer)
                    layers_to_remove.append(layer)
            elif 'local' in layer_name:
                if layer.geometryType() == QgsWkbTypes.LineGeometry:
                    local_roads.append(layer)
                    layers_to_remove.append(layer)
            elif 'residential' in layer_name:
                if layer.geometryType() == QgsWkbTypes.LineGeometry:
                    residential_roads.append(layer)
                    layers_to_remove.append(layer)
            elif 'railway' in layer_name:
                if layer.geometryType() == QgsWkbTypes.LineGeometry:
                    local_roads.append(layer)  # Treat railways as local
                    layers_to_remove.append(layer)
        
        if not (major_roads or local_roads or residential_roads):
            QMessageBox.warning(self, "Warning", "No road layers found")
            return
        
        # Check if Roads Polygon already exists
        existing_poly = None
        for layer in self.downloaded_layers:
            if layer.isValid() and layer.name() == "Roads Polygon":
                existing_poly = layer
                break
        
        if existing_poly:
            reply = QMessageBox.question(
                self,
                "Roads Polygon Exists",
                "A Roads Polygon already exists. Remove it and create new one?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                QgsProject.instance().removeMapLayer(existing_poly.id())
                if existing_poly in self.downloaded_layers:
                    self.downloaded_layers.remove(existing_poly)
                self.log_progress("\n✓ Removed existing Roads Polygon")
            else:
                return
        
        self.log_progress("\n=== Processing Roads ===")
        
        try:
            buffered_layers = []
            
            # Buffer Major Roads (widest)
            if major_roads:
                self.log_progress(f"Processing {len(major_roads)} Major Roads (buffer: {self.buffer_major})...")
                for layer in major_roads:
                    buffer_result = processing.run("native:buffer", {
                        'INPUT': layer,
                        'DISTANCE': self.buffer_major,
                        'SEGMENTS': 5,
                        'END_CAP_STYLE': 0,
                        'JOIN_STYLE': 0,
                        'MITER_LIMIT': 2,
                        'DISSOLVE': False,
                        'OUTPUT': 'memory:'
                    })
                    buffered_layers.append(buffer_result['OUTPUT'])
                self.log_progress("✓ Major roads buffered")
            
            # Buffer Local Roads (medium)
            if local_roads:
                self.log_progress(f"Processing {len(local_roads)} Local Roads (buffer: {self.buffer_local})...")
                for layer in local_roads:
                    buffer_result = processing.run("native:buffer", {
                        'INPUT': layer,
                        'DISTANCE': self.buffer_local,
                        'SEGMENTS': 5,
                        'END_CAP_STYLE': 0,
                        'JOIN_STYLE': 0,
                        'MITER_LIMIT': 2,
                        'DISSOLVE': False,
                        'OUTPUT': 'memory:'
                    })
                    buffered_layers.append(buffer_result['OUTPUT'])
                self.log_progress("✓ Local roads buffered")
            
            # Buffer Residential Roads (thinnest)
            if residential_roads:
                self.log_progress(f"Processing {len(residential_roads)} Residential Roads (buffer: {self.buffer_residential})...")
                for layer in residential_roads:
                    buffer_result = processing.run("native:buffer", {
                        'INPUT': layer,
                        'DISTANCE': self.buffer_residential,
                        'SEGMENTS': 5,
                        'END_CAP_STYLE': 0,
                        'JOIN_STYLE': 0,
                        'MITER_LIMIT': 2,
                        'DISSOLVE': False,
                        'OUTPUT': 'memory:'
                    })
                    buffered_layers.append(buffer_result['OUTPUT'])
                self.log_progress("✓ Residential roads buffered")
            
            # Merge all buffered layers
            self.log_progress("Merging buffered layers...")
            if len(buffered_layers) > 1:
                merge_result = processing.run("native:mergevectorlayers", {
                    'LAYERS': buffered_layers,
                    'CRS': buffered_layers[0].crs(),
                    'OUTPUT': 'memory:'
                })
                merged_buffered = merge_result['OUTPUT']
            else:
                merged_buffered = buffered_layers[0]
            self.log_progress("✓ Buffered layers merged")
            
            # Dissolve into single polygon
            self.log_progress("Dissolving into single polygon...")
            dissolve_result = processing.run("native:dissolve", {
                'INPUT': merged_buffered,
                'FIELD': [],
                'OUTPUT': 'memory:'
            })
            dissolved_layer = dissolve_result['OUTPUT']
            self.log_progress("✓ Dissolved")
            
            # Create Roads Polygon layer
            poly_layer = QgsVectorLayer(
                f"Polygon?crs={dissolved_layer.crs().authid()}",
                "Roads Polygon",
                "memory"
            )
            
            poly_provider = poly_layer.dataProvider()
            features = []
            for feature in dissolved_layer.getFeatures():
                new_feature = QgsFeature()
                new_feature.setGeometry(feature.geometry())
                features.append(new_feature)
            
            poly_provider.addFeatures(features)
            poly_layer.updateExtents()
            
            # Apply hollow (no fill) gray styling
            gray_color = QColor("#808080")
            symbol = QgsFillSymbol.createSimple({
                'color': 'transparent',
                'outline_color': gray_color.name(),
                'outline_width': '0.5',
                'outline_style': 'solid',
                'style': 'no'
            })
            
            poly_layer.renderer().setSymbol(symbol)
            QgsProject.instance().addMapLayer(poly_layer)
            self.downloaded_layers.append(poly_layer)
            self.log_progress("✓ Roads Polygon created (hollow)")
            
            # Merge all road labels
            if label_layers:
                self.log_progress(f"\nMerging {len(label_layers)} label layers...")
                
                if len(label_layers) > 1:
                    labels_to_merge = [layer.id() for layer in label_layers]
                    merge_labels_result = processing.run("native:mergevectorlayers", {
                        'LAYERS': labels_to_merge,
                        'CRS': label_layers[0].crs(),
                        'OUTPUT': 'memory:'
                    })
                    merged_labels = merge_labels_result['OUTPUT']
                else:
                    merged_labels = label_layers[0]
                
                # Create Roads Labels layer
                labels_layer = QgsVectorLayer(
                    f"Point?crs={merged_labels.crs().authid()}",
                    "Roads Labels",
                    "memory"
                )
                
                labels_provider = labels_layer.dataProvider()
                
                if merged_labels.fields().count() > 0:
                    labels_provider.addAttributes(merged_labels.fields())
                    labels_layer.updateFields()
                
                label_features = []
                for feature in merged_labels.getFeatures():
                    new_feature = QgsFeature(labels_layer.fields())
                    new_feature.setGeometry(feature.geometry())
                    new_feature.setAttributes(feature.attributes())
                    label_features.append(new_feature)
                
                labels_provider.addFeatures(label_features)
                labels_layer.updateExtents()
                
                symbol = QgsMarkerSymbol.createSimple({
                    'color': '#000000',
                    'size': '0.5',
                    'outline_color': 'transparent',
                    'outline_width': '0'
                })
                labels_layer.renderer().setSymbol(symbol)
                
                QgsProject.instance().addMapLayer(labels_layer)
                self.downloaded_layers.append(labels_layer)
                self.log_progress("✓ Roads Labels created")
            
            # Remove individual layers (optional based on user choice)
            reply = QMessageBox.question(
                self,
                "Remove Original Layers?",
                f"Remove {len(layers_to_remove)} original road layers?\n\n" +
                "(Choose 'No' to keep them for adjusting buffer widths later)",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            layers_kept = False
            if reply == QMessageBox.Yes:
                self.log_progress(f"\nRemoving {len(layers_to_remove)} individual layers...")
                for layer in layers_to_remove:
                    if layer.isValid():
                        QgsProject.instance().removeMapLayer(layer.id())
                        if layer in self.downloaded_layers:
                            self.downloaded_layers.remove(layer)
                self.log_progress("✓ Removed individual layers")
            else:
                layers_kept = True
                self.log_progress("\n✓ Kept original layers for adjustment")
            
            self.log_progress("\n=== Complete ===")
            self.log_progress("Result: Roads Polygon + Roads Labels")
            self.log_progress("Tip: Keep original layers to rebuild with different buffer widths")
            
            result_msg = "Roads processing complete!\n\n"
            result_msg += "Buffer widths used:\n"
            result_msg += f"• Major: {self.buffer_major}\n"
            result_msg += f"• Local: {self.buffer_local}\n"
            result_msg += f"• Residential: {self.buffer_residential}\n\n"
            
            if layers_kept:
                result_msg += "Original layers kept.\n"
                result_msg += "To rebuild with different widths:\n"
                result_msg += "1. Click 'Buffer Settings'\n"
                result_msg += "2. Adjust values\n"
                result_msg += "3. Click 'Make Roads Poly' again"
            else:
                result_msg += f"Removed {len(layers_to_remove)} original layers"
            
            QMessageBox.information(self, "Success", result_msg)
            
        except Exception as e:
            error_msg = f"Error processing roads: {str(e)}"
            self.log_progress(f"✗ {error_msg}")
            QgsMessageLog.logMessage(error_msg, 'OSM Bulk Downloader', Qgis.Critical)
            QMessageBox.critical(self, "Error", error_msg)
    
    def apply_design_mode(self):
        """Simplify all layers to single color and line width for design programs"""
        if not self.downloaded_layers:
            return
        
        reply = QMessageBox.question(
            self,
            "Simplify for Design",
            "Convert all layers to:\n• Black color (#000000)\n• 1px line width\n• No fill\n\nThis is useful for importing into design programs like Lightburn.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        self.log_progress("\nApplying design mode...")
        black_color = QColor("#000000")
        
        for layer in self.downloaded_layers:
            if not layer.isValid():
                continue
            
            geom_type = layer.geometryType()
            
            if geom_type == 0:  # Point
                symbol = QgsMarkerSymbol.createSimple({
                    'color': black_color.name(),
                    'size': '1',
                    'outline_color': black_color.name(),
                    'outline_width': '0.5'
                })
            elif geom_type == 1:  # Line
                symbol = QgsLineSymbol.createSimple({
                    'color': black_color.name(),
                    'width': '1',
                    'opacity': '1.0'
                })
            elif geom_type == 2:  # Polygon
                symbol = QgsFillSymbol.createSimple({
                    'color': 'transparent',
                    'outline_color': black_color.name(),
                    'outline_width': '1',
                    'style': 'no'
                })
            
            layer.renderer().setSymbol(symbol)
            layer.triggerRepaint()
        
        self.iface.mapCanvas().refresh()
        self.log_progress("✓ Design mode applied: All layers black, 1px width")
        QMessageBox.information(self, "Success", "All layers simplified:\n• Black color\n• 1px width\n• Ready for design programs")
    
    def enable_all_labels(self):
        """Enable labels on water body layers (lakes, bays, etc.)"""
        if not self.downloaded_layers:
            return
        
        from qgis.core import QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling
        
        self.log_progress("\nEnabling labels on water body layers...")
        
        # FIRST: Hide all "Labels" layers to avoid duplicates
        labels_hidden = 0
        for layer in self.downloaded_layers:
            if layer.isValid() and 'labels' in layer.name().lower():
                # Hide the layer in the layer tree
                layer_tree_layer = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
                if layer_tree_layer:
                    layer_tree_layer.setItemVisibilityChecked(False)
                    labels_hidden += 1
                    self.log_progress(f"  ✓ Hidden: {layer.name()} (to avoid duplicate labels)")
        
        count = 0
        
        # Water body layer names to enable labels on
        water_layer_keywords = ['water bodies', 'water_bodies', 'bays', 'lake']
        
        for layer in self.downloaded_layers:
            if not layer.isValid():
                continue
            
            # Check if this is a water body layer
            layer_name_lower = layer.name().lower()
            is_water_body = any(keyword in layer_name_lower for keyword in water_layer_keywords)
            
            # Skip if not a water body layer OR if it's a Labels layer
            if not is_water_body or 'labels' in layer_name_lower:
                continue
            
            # Check if layer has 'name' field
            fields = layer.fields()
            has_name = False
            for field in fields:
                if field.name().lower() == 'name':
                    has_name = True
                    break
            
            if not has_name:
                continue
            
            # Create label settings with deduplication
            settings = QgsPalLayerSettings()
            settings.fieldName = 'name'
            settings.enabled = True
            
            # Placement settings to avoid duplicates
            settings.placement = QgsPalLayerSettings.OverPoint  # Center of feature
            settings.dist = 0
            settings.distUnits = QgsUnitTypes.RenderMillimeters
            
            # Limit labels to avoid overlaps/duplicates
            settings.displayAll = False  # Don't show all labels
            settings.obstacle = False  # Don't treat as obstacle
            
            # Text format
            text_format = QgsTextFormat()
            text_format.setSize(10)
            text_format.setColor(QColor('#000000'))
            
            # Buffer for readability
            buffer = text_format.buffer()
            buffer.setEnabled(True)
            buffer.setSize(1.5)
            buffer.setColor(QColor('#FFFFFF'))
            text_format.setBuffer(buffer)
            
            settings.setFormat(text_format)
            
            # Apply labeling
            labeling = QgsVectorLayerSimpleLabeling(settings)
            layer.setLabeling(labeling)
            layer.setLabelsEnabled(True)
            layer.triggerRepaint()
            count += 1
            self.log_progress(f"  ✓ Labels enabled on: {layer.name()}")
        
        self.iface.mapCanvas().refresh()
        if count > 0:
            self.log_progress(f"✓ Labels enabled on {count} water body layer(s)")
            QMessageBox.information(self, "Success", f"Labels enabled on {count} water body layer(s)")
        else:
            self.log_progress("ℹ No water body layers found with 'name' field")
            QMessageBox.information(self, "Info", "No water body layers found.\nDownload Water Bodies & Lakes or Bays first.")
    
    def apply_professional_styling(self):
        """Apply professional styling to ALL visible canvas layers (for SVG export)"""
        canvas = self.iface.mapCanvas()
        canvas_layers = canvas.layers()
        
        # Define style scheme
        styles = {
            'water': {'color': '#1a3a52', 'fillColor': '#1a3a52'},
            'roads': {'color': '#8b7355', 'weight': 0.5},
            'buildings': {'color': '#d4c4b0', 'fillColor': '#d4c4b0'},
            'areas': {'color': '#c4b5a0', 'fillColor': '#ebe5dc'},
        }
        
        styled_count = 0
        
        for layer in canvas_layers:
            if not layer.isValid():
                continue
            
            # Skip basemap
            layer_name_lower = layer.name().lower()
            if any(keyword in layer_name_lower for keyword in ['openstreetmap', 'osm', 'basemap', 'google', 'bing']):
                continue
            
            try:
                geom_type = layer.geometryType()
                renderer = layer.renderer()
                
                # Check if it's a single symbol renderer
                from qgis.core import QgsSingleSymbolRenderer
                if not isinstance(renderer, QgsSingleSymbolRenderer):
                    self.log_progress(f"  ⏭️ {layer.name()} (categorized/rule-based)")
                    continue
                
                symbol = None
                
                # Water features - dark blue
                if any(k in layer_name_lower for k in ['water', 'lake', 'river', 'bay', 'stream']):
                    if geom_type == 2:  # Polygon
                        symbol = QgsFillSymbol.createSimple({
                            'color': styles['water']['fillColor'],
                            'outline_color': styles['water']['color'],
                            'outline_width': '0.5'
                        })
                    elif geom_type == 1:  # Line
                        symbol = QgsLineSymbol.createSimple({
                            'color': styles['water']['color'],
                            'width': '1.5'
                        })
                
                # Roads - tan
                elif any(k in layer_name_lower for k in ['road', 'street', 'highway']):
                    if geom_type == 1:  # Line
                        symbol = QgsLineSymbol.createSimple({
                            'color': styles['roads']['color'],
                            'width': str(styles['roads']['weight'])
                        })
                    elif geom_type == 2:  # Roads Polygon
                        symbol = QgsFillSymbol.createSimple({
                            'color': styles['roads']['color'],
                            'outline_color': styles['roads']['color'],
                            'outline_width': '0'
                        })
                
                # Buildings - light tan
                elif 'building' in layer_name_lower:
                    if geom_type == 2:
                        symbol = QgsFillSymbol.createSimple({
                            'color': styles['buildings']['fillColor'],
                            'outline_color': styles['buildings']['color'],
                            'outline_width': '0.3'
                        })
                
                # Other polygons - beige
                elif geom_type == 2:
                    symbol = QgsFillSymbol.createSimple({
                        'color': styles['areas']['fillColor'],
                        'outline_color': styles['areas']['color'],
                        'outline_width': '0.5'
                    })
                
                # Apply symbol if created
                if symbol:
                    renderer.setSymbol(symbol)
                    layer.triggerRepaint()
                    styled_count += 1
                    self.log_progress(f"  ✓ Styled: {layer.name()}")
                
            except Exception as e:
                self.log_progress(f"  ⚠️ Could not style {layer.name()}: {str(e)}")
                continue
        
        self.log_progress(f"✓ Styled {styled_count} layers")
        
        # Set background color
        canvas.setCanvasColor(QColor('#f5f1e8'))
        canvas.refresh()
    
    def generate_styled_map(self):
        """Generate professionally styled map like poster design"""
        if not self.downloaded_layers:
            return
        
        self.log_progress("\nGenerating styled map...")
        
        # Define style scheme (like the poster image)
        styles = {
            'water': {'color': '#1a3a52', 'fillColor': '#1a3a52', 'fillOpacity': 1.0},  # Dark blue
            'roads': {'color': '#8b7355', 'weight': 0.5, 'opacity': 0.8},  # Brown/tan
            'buildings': {'color': '#d4c4b0', 'fillColor': '#d4c4b0', 'fillOpacity': 0.3},  # Light tan
            'areas': {'color': '#c4b5a0', 'fillColor': '#ebe5dc', 'fillOpacity': 0.2},  # Beige
        }
        
        for layer in self.downloaded_layers:
            if not layer.isValid():
                continue
            
            layer_name = layer.name().lower()
            geom_type = layer.geometryType()
            
            # Water features - dark blue fill
            if any(k in layer_name for k in ['water', 'lake', 'river', 'bay', 'stream']):
                if geom_type == 2:  # Polygon
                    symbol = QgsFillSymbol.createSimple({
                        'color': styles['water']['fillColor'],
                        'outline_color': styles['water']['color'],
                        'outline_width': '0.5',
                        'opacity': str(styles['water']['fillOpacity'])
                    })
                elif geom_type == 1:  # Line
                    symbol = QgsLineSymbol.createSimple({
                        'color': styles['water']['color'],
                        'width': '1.5'
                    })
                layer.renderer().setSymbol(symbol)
            
            # Roads - thin tan lines
            elif any(k in layer_name for k in ['road', 'street', 'highway']):
                if geom_type == 1:
                    symbol = QgsLineSymbol.createSimple({
                        'color': styles['roads']['color'],
                        'width': str(styles['roads']['weight']),
                        'opacity': str(styles['roads']['opacity'])
                    })
                    layer.renderer().setSymbol(symbol)
            
            # Buildings - light tan
            elif 'building' in layer_name:
                if geom_type == 2:
                    symbol = QgsFillSymbol.createSimple({
                        'color': styles['buildings']['fillColor'],
                        'outline_color': styles['buildings']['color'],
                        'outline_width': '0.3',
                        'opacity': str(styles['buildings']['fillOpacity'])
                    })
                    layer.renderer().setSymbol(symbol)
            
            # Other areas - beige
            elif geom_type == 2:
                symbol = QgsFillSymbol.createSimple({
                    'color': styles['areas']['fillColor'],
                    'outline_color': styles['areas']['color'],
                    'outline_width': '0.5',
                    'opacity': str(styles['areas']['fillOpacity'])
                })
                layer.renderer().setSymbol(symbol)
            
            layer.triggerRepaint()
        
        # Set background color to cream/beige
        canvas = self.iface.mapCanvas()
        canvas.setCanvasColor(QColor('#f5f1e8'))
        
        # CRITICAL: Force complete re-render and wait for it to finish
        canvas.refresh()
        canvas.refreshAllLayers()
        
        # Process all pending events to ensure rendering completes
        from qgis.PyQt.QtCore import QCoreApplication
        for _ in range(10):  # Process events multiple times
            QCoreApplication.processEvents()
        
        # Additional wait to ensure layers are fully rendered
        from qgis.PyQt.QtCore import QTimer, QEventLoop
        loop = QEventLoop()
        QTimer.singleShot(500, loop.quit)  # Wait 500ms for rendering
        loop.exec_()
        
        self.log_progress("✓ Styled map generated")
        self.log_progress("  - Water: Dark blue")
        self.log_progress("  - Roads: Tan/brown")
        self.log_progress("  - Buildings: Light tan")
        self.log_progress("  - Background: Cream")
        self.log_progress("  - Waiting for rendering to complete...")
        
        # One more refresh to be sure
        canvas.refresh()
        QCoreApplication.processEvents()
        
        # Ask if user wants to create poster with frame and title
        reply = QMessageBox.question(
            self,
            "Create Poster?",
            "Map styled successfully!\n\n"
            "Would you like to create a poster-style map with frame, title, and coordinates?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            self.create_poster_map()
        else:
            QMessageBox.information(self, "Success", 
                                   "Map styled with poster design:\n\n"
                                   "• Water: Dark blue\n"
                                   "• Roads: Tan lines\n"
                                   "• Buildings: Light tan\n"
                                   "• Background: Cream")
    
    def create_poster_map(self):
        """Create poster-style map with frame, title, and coordinates using SVG"""
        from qgis.PyQt.QtSvg import QSvgRenderer
        from qgis.PyQt.QtGui import QImage, QPainter, QFont, QPen, QBrush
        from qgis.PyQt.QtCore import QSize, Qt, QRectF
        import tempfile
        import os
        
        try:
            # Get canvas first (needed for extent and layers)
            canvas = self.iface.mapCanvas()
            canvas_extent = canvas.extent()
            canvas_layers = canvas.layers()
            
            # Get title
            map_title = self.place_input.text().strip()
            
            # Only look for water body name if no search text
            if not map_title:
                water_name = None
                # Search through canvas layers for water body names
                for layer in canvas_layers:
                    if not layer.isValid():
                        continue
                    if any(k in layer.name().lower() for k in ['water', 'lake', 'bay']):
                        for feature in layer.getFeatures():
                            try:
                                name = feature.attribute('name')
                                if name and str(name).strip() and str(name) != 'NULL':
                                    water_name = str(name).upper()
                                    break
                            except:
                                continue
                        if water_name:
                            break
                
                if water_name:
                    map_title = water_name
                else:
                    map_title = "MAP"
            
            map_title = map_title.upper()
            if "MAP" not in map_title:
                map_title = map_title + " MAP"
            
            # Calculate coordinates from canvas extent
            center_lat = (canvas_extent.yMinimum() + canvas_extent.yMaximum()) / 2
            center_lon = (canvas_extent.xMinimum() + canvas_extent.xMaximum()) / 2
            
            # Format coordinates
            lat_dir = "N" if center_lat >= 0 else "S"
            lon_dir = "E" if center_lon >= 0 else "W"
            coord_text = f"{abs(center_lat):.2f}° {lat_dir} / {abs(center_lon):.2f}° {lon_dir}"
            
            # Location text
            location_text = self.place_input.text().strip() or "LOCATION"
            if ", " in location_text:
                location_text = location_text.replace(", ", " / ").upper()
            else:
                location_text = location_text.upper()
            
            self.log_progress("\n📄 Creating poster from current canvas view...")
            
            # Filter out basemap only (keep everything else)
            layers_to_export = []
            for layer in canvas_layers:
                if not layer.isValid():
                    continue
                # Skip basemap (OpenStreetMap, Google, etc.)
                layer_name_lower = layer.name().lower()
                if any(keyword in layer_name_lower for keyword in ['openstreetmap', 'osm', 'basemap', 'google', 'bing']):
                    self.log_progress(f"Skipping basemap: {layer.name()}")
                    continue
                layers_to_export.append(layer)
            
            if not layers_to_export:
                raise Exception("No layers visible in canvas")
            
            self.log_progress(f"Exporting {len(layers_to_export)} visible layers:")
            for layer in layers_to_export:
                self.log_progress(f"  - {layer.name()}")
            
            # Verify canvas extent is valid
            if canvas_extent.isEmpty():
                raise Exception("Canvas extent is empty")
            
            self.log_progress(f"Using canvas extent: {canvas_extent.toString()}")
            
            # Step 1: Export to temporary SVG file
            temp_svg = tempfile.NamedTemporaryFile(suffix='.svg', delete=False)
            temp_svg_path = temp_svg.name
            temp_svg.close()
            
            self.log_progress(f"Exporting to temporary SVG: {temp_svg_path}")
            
            # Add small padding to canvas extent (2%)
            extent = QgsRectangle(canvas_extent)
            padding_x = extent.width() * 0.02
            padding_y = extent.height() * 0.02
            extent.setXMinimum(extent.xMinimum() - padding_x)
            extent.setXMaximum(extent.xMaximum() + padding_x)
            extent.setYMinimum(extent.yMinimum() - padding_y)
            extent.setYMaximum(extent.yMaximum() + padding_y)
            
            # Convert extent to bbox tuple (south, west, north, east)
            svg_bbox = (extent.yMinimum(), extent.xMinimum(), 
                       extent.yMaximum(), extent.xMaximum())
            
            # Export to SVG (A3 size for map portion)
            exporter = SVGExporter(svg_bbox, 'A3', 'portrait')
            exporter.export_layers_to_svg(layers_to_export, temp_svg_path)
            
            self.log_progress("✓ SVG exported successfully")
            
            # Step 2: Load SVG and render to image
            self.log_progress("Loading SVG...")
            
            svg_renderer = QSvgRenderer(temp_svg_path)
            
            if not svg_renderer.isValid():
                raise Exception("Failed to load SVG")
            
            # Poster dimensions (A3 at 300 DPI)
            dpi = 300
            width_mm = 297
            height_mm = 420
            width_px = int(width_mm * dpi / 25.4)
            height_px = int(height_mm * dpi / 25.4)
            
            # Calculate map area (85% of height for map, 15% for title)
            title_height_px = int(height_px * 0.15)
            map_height_px = height_px - title_height_px
            
            self.log_progress(f"Rendering SVG to image ({width_px}x{map_height_px}px)...")
            
            # Create image for map from SVG
            map_image = QImage(width_px, map_height_px, QImage.Format_ARGB32)
            map_image.fill(QColor('#f5f1e8'))  # Cream background
            
            # Render SVG to map image
            map_painter = QPainter(map_image)
            svg_renderer.render(map_painter)
            map_painter.end()
            
            self.log_progress("✓ SVG rendered to image")
            
            # Step 3: Create full poster with title
            self.log_progress("Creating poster with title...")
            
            poster_image = QImage(width_px, height_px, QImage.Format_ARGB32)
            poster_image.fill(QColor('#f5f1e8'))
            
            poster_painter = QPainter(poster_image)
            poster_painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw map
            poster_painter.drawImage(0, 0, map_image)
            
            # Draw frame around map
            frame_pen = QPen(QColor('#2c3e50'), int(dpi / 25.4))
            poster_painter.setPen(frame_pen)
            poster_painter.drawRect(0, 0, width_px, map_height_px)
            
            # Draw title section
            title_y = map_height_px
            poster_painter.fillRect(0, title_y, width_px, title_height_px, QBrush(QColor('#f5f1e8')))
            
            # Draw title text
            title_font = QFont("Arial", int(dpi / 6))
            title_font.setBold(True)
            title_font.setLetterSpacing(QFont.AbsoluteSpacing, dpi / 50)
            poster_painter.setFont(title_font)
            poster_painter.setPen(QColor('#2c3e50'))
            
            title_rect = QRectF(0, title_y + title_height_px * 0.15, width_px, title_height_px * 0.35)
            poster_painter.drawText(title_rect, Qt.AlignCenter, map_title)
            
            # Draw coordinates
            coord_font = QFont("Arial", int(dpi / 12))
            coord_font.setLetterSpacing(QFont.AbsoluteSpacing, dpi / 100)
            poster_painter.setFont(coord_font)
            
            coord_rect = QRectF(0, title_y + title_height_px * 0.50, width_px, title_height_px * 0.20)
            poster_painter.drawText(coord_rect, Qt.AlignCenter, coord_text)
            
            # Draw location text
            location_font = QFont("Arial", int(dpi / 15))
            location_font.setLetterSpacing(QFont.AbsoluteSpacing, dpi / 80)
            poster_painter.setFont(location_font)
            
            location_rect = QRectF(0, title_y + title_height_px * 0.70, width_px, title_height_px * 0.20)
            poster_painter.drawText(location_rect, Qt.AlignCenter, location_text)
            
            poster_painter.end()
            
            self.log_progress("✓ Poster created successfully")
            
            # Clean up temporary SVG
            try:
                os.unlink(temp_svg_path)
            except:
                pass
            
            # Save poster
            place_name = self.place_input.text().strip().replace(' ', '_').replace(',', '')
            default_filename = f"{place_name}_poster.png" if place_name else "map_poster.png"
            
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Save Poster Map",
                default_filename,
                "PNG Images (*.png)"
            )
            
            if filename:
                poster_image.save(filename, "PNG", 100)
                self.log_progress(f"✓ Poster saved: {filename}")
                QMessageBox.information(
                    self,
                    "Success",
                    f"Poster map created successfully!\n\n"
                    f"Title: {map_title}\n"
                    f"Coordinates: {coord_text}\n"
                    f"Location: {location_text}\n\n"
                    f"Saved to: {filename}"
                )
            
        except Exception as e:
            error_msg = f"Error creating poster: {str(e)}"
            self.log_progress(f"✗ {error_msg}")
            QMessageBox.critical(self, "Error", error_msg)
    
    def make_all_roads_gray(self):
        """Make all road layers gray"""
        if not self.downloaded_layers:
            return
        
        gray_color = QColor("#808080")
        road_keywords = ['road', 'highway', 'street']
        
        for layer in self.downloaded_layers:
            if not layer.isValid():
                continue
            
            layer_name = layer.name().lower()
            if any(keyword in layer_name for keyword in road_keywords):
                renderer = layer.renderer()
                if renderer and renderer.symbol():
                    symbol = renderer.symbol().clone()
                    symbol.setColor(gray_color)
                    renderer.setSymbol(symbol)
                    layer.triggerRepaint()
        
        self.iface.mapCanvas().refresh()
        self.log_progress("\n✓ All roads set to gray")
    
    def open_style_editor(self):
        """Open style editor dialog"""
        if not self.downloaded_layers:
            QMessageBox.warning(self, "Warning", "No layers to edit")
            return
        
        from .style_editor_dialog import StyleEditorDialog
        
        dialog = StyleEditorDialog(self.downloaded_layers, self.iface, self)
        if dialog.exec_() == QDialog.Accepted:
            self.log_progress("\n✓ Styles updated")
            self.iface.mapCanvas().refresh()
    
    def apply_style(self, layer, style_config):
        """Apply styling to a layer"""
        if not style_config:
            return
        
        geom_type = layer.geometryType()
        
        # Get color
        color = QColor(style_config.get('color', '#000000'))
        fill_color = QColor(style_config.get('fillColor', color))
        weight = style_config.get('weight', 1)
        opacity = style_config.get('opacity', 1.0)
        fill_opacity = style_config.get('fillOpacity', 0.5)
        dash_array = style_config.get('dashArray', None)
        
        # Create symbol based on geometry type
        if geom_type == 0:  # Point
            symbol = QgsMarkerSymbol.createSimple({
                'color': color.name(),
                'size': '0.5',
                'outline_color': 'transparent',
                'outline_width': '0'
            })
        elif geom_type == 1:  # Line
            properties = {
                'color': color.name(),
                'width': str(weight),
                'opacity': str(opacity)
            }
            if dash_array:
                properties['line_style'] = 'dash'
                properties['dash_pattern'] = dash_array
            symbol = QgsLineSymbol.createSimple(properties)
        elif geom_type == 2:  # Polygon
            symbol = QgsFillSymbol.createSimple({
                'color': fill_color.name(),
                'outline_color': color.name(),
                'outline_width': str(weight),
                'style': 'solid',
                'opacity': str(fill_opacity)
            })
        
        layer.renderer().setSymbol(symbol)
        layer.triggerRepaint()
    
    def log_progress(self, message):
        """Log progress message"""
        self.progress_text.append(message)
        # Scroll to bottom
        cursor = self.progress_text.textCursor()
        cursor.movePosition(cursor.End)
        self.progress_text.setTextCursor(cursor)
