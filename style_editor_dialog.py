"""
Style Editor Dialog - Easy styling for downloaded layers
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                 QPushButton, QListWidget, QListWidgetItem,
                                 QSpinBox, QDoubleSpinBox, QGroupBox, QCheckBox,
                                 QColorDialog, QComboBox, QDialogButtonBox,
                                 QTabWidget, QWidget, QScrollArea, QFormLayout)
from qgis.PyQt.QtGui import QColor
from qgis.core import (QgsVectorLayer, QgsSymbol, QgsMarkerSymbol, QgsLineSymbol, 
                       QgsFillSymbol, QgsPalLayerSettings, QgsTextFormat, 
                       QgsVectorLayerSimpleLabeling, QgsProperty)


class StyleEditorDialog(QDialog):
    """Dialog for editing layer styles"""
    
    def __init__(self, layers, iface, parent=None):
        super().__init__(parent)
        self.layers = [l for l in layers if l.isValid()]
        self.iface = iface
        self.current_layer = None
        
        self.setWindowTitle("Layer Style Editor")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Info label
        info_label = QLabel("Select a layer to edit its styling:")
        layout.addWidget(info_label)
        
        # Layer list
        self.layer_list = QListWidget()
        self.layer_list.currentItemChanged.connect(self.on_layer_selected)
        
        for layer in self.layers:
            item = QListWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer)
            self.layer_list.addItem(item)
        
        layout.addWidget(self.layer_list)
        
        # Tabs for different style options
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Symbol tab
        symbol_widget = self.create_symbol_tab()
        self.tabs.addTab(symbol_widget, "Symbol Style")
        
        # Label tab
        label_widget = self.create_label_tab()
        self.tabs.addTab(label_widget, "Labels")
        
        # Quick presets
        presets_group = QGroupBox("Quick Presets for Roads")
        presets_layout = QHBoxLayout()
        presets_group.setLayout(presets_layout)
        
        thin_btn = QPushButton("Thin (1px)")
        thin_btn.clicked.connect(lambda: self.apply_road_preset(1))
        presets_layout.addWidget(thin_btn)
        
        medium_btn = QPushButton("Medium (2px)")
        medium_btn.clicked.connect(lambda: self.apply_road_preset(2))
        presets_layout.addWidget(medium_btn)
        
        thick_btn = QPushButton("Thick (3px)")
        thick_btn.clicked.connect(lambda: self.apply_road_preset(3))
        presets_layout.addWidget(thick_btn)
        
        very_thick_btn = QPushButton("Very Thick (5px)")
        very_thick_btn.clicked.connect(lambda: self.apply_road_preset(5))
        presets_layout.addWidget(very_thick_btn)
        
        layout.addWidget(presets_group)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Close)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self.apply_changes)
        button_box.button(QDialogButtonBox.Close).clicked.connect(self.accept)
        layout.addWidget(button_box)
        
    def create_symbol_tab(self):
        """Create the symbol styling tab"""
        widget = QWidget()
        layout = QFormLayout()
        widget.setLayout(layout)
        
        # Line width
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.1, 20)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setValue(1)
        self.width_spin.setSuffix(" px")
        layout.addRow("Line Width:", self.width_spin)
        
        # Color
        color_layout = QHBoxLayout()
        self.color_btn = QPushButton("Choose Color")
        self.color_btn.clicked.connect(self.choose_color)
        self.current_color = QColor("#000000")
        self.update_color_button()
        color_layout.addWidget(self.color_btn)
        layout.addRow("Line/Stroke Color:", color_layout)
        
        # Fill color (for polygons)
        fill_color_layout = QHBoxLayout()
        self.fill_color_btn = QPushButton("Choose Fill Color")
        self.fill_color_btn.clicked.connect(self.choose_fill_color)
        self.current_fill_color = QColor("#CCCCCC")
        self.update_fill_color_button()
        fill_color_layout.addWidget(self.fill_color_btn)
        layout.addRow("Fill Color:", fill_color_layout)
        
        # Opacity
        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0, 1)
        self.opacity_spin.setSingleStep(0.1)
        self.opacity_spin.setValue(1.0)
        layout.addRow("Opacity:", self.opacity_spin)
        
        # Fill opacity
        self.fill_opacity_spin = QDoubleSpinBox()
        self.fill_opacity_spin.setRange(0, 1)
        self.fill_opacity_spin.setSingleStep(0.1)
        self.fill_opacity_spin.setValue(0.5)
        layout.addRow("Fill Opacity:", self.fill_opacity_spin)
        
        return widget
    
    def create_label_tab(self):
        """Create the label styling tab"""
        widget = QWidget()
        layout = QFormLayout()
        widget.setLayout(layout)
        
        # Enable labels
        self.labels_enabled = QCheckBox("Enable Labels")
        self.labels_enabled.setChecked(False)
        self.labels_enabled.stateChanged.connect(self.on_labels_toggled)
        layout.addRow("", self.labels_enabled)
        
        # Label field
        self.label_field_combo = QComboBox()
        layout.addRow("Label Field:", self.label_field_combo)
        
        # Font size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.setValue(10)
        self.font_size_spin.setSuffix(" pt")
        layout.addRow("Font Size:", self.font_size_spin)
        
        # Font color
        font_color_layout = QHBoxLayout()
        self.font_color_btn = QPushButton("Choose Font Color")
        self.font_color_btn.clicked.connect(self.choose_font_color)
        self.current_font_color = QColor("#000000")
        self.update_font_color_button()
        font_color_layout.addWidget(self.font_color_btn)
        layout.addRow("Font Color:", font_color_layout)
        
        # Text format
        self.text_format_combo = QComboBox()
        self.text_format_combo.addItems(['Normal', 'UPPERCASE', 'lowercase', 'Title Case'])
        layout.addRow("Text Format:", self.text_format_combo)
        
        # Buffer
        self.buffer_enabled = QCheckBox("Enable Buffer (outline)")
        self.buffer_enabled.setChecked(True)
        layout.addRow("", self.buffer_enabled)
        
        self.buffer_size_spin = QDoubleSpinBox()
        self.buffer_size_spin.setRange(0, 10)
        self.buffer_size_spin.setSingleStep(0.1)
        self.buffer_size_spin.setValue(1.0)
        self.buffer_size_spin.setSuffix(" mm")
        layout.addRow("Buffer Size:", self.buffer_size_spin)
        
        # Buffer color
        buffer_color_layout = QHBoxLayout()
        self.buffer_color_btn = QPushButton("Choose Buffer Color")
        self.buffer_color_btn.clicked.connect(self.choose_buffer_color)
        self.current_buffer_color = QColor("#FFFFFF")
        self.update_buffer_color_button()
        buffer_color_layout.addWidget(self.buffer_color_btn)
        layout.addRow("Buffer Color:", buffer_color_layout)
        
        # Placement
        self.placement_combo = QComboBox()
        self.placement_combo.addItems(['Above Line', 'On Line', 'Below Line', 'Horizontal', 'Free (Curved)'])
        layout.addRow("Placement:", self.placement_combo)
        
        return widget
    
    def on_layer_selected(self, current, previous):
        """Handle layer selection"""
        if not current:
            return
        
        self.current_layer = current.data(Qt.UserRole)
        self.load_layer_style()
    
    def load_layer_style(self):
        """Load current layer style into controls"""
        if not self.current_layer or not self.current_layer.isValid():
            return
        
        renderer = self.current_layer.renderer()
        if renderer and renderer.symbol():
            symbol = renderer.symbol()
            
            # Get color
            color = symbol.color()
            self.current_color = color
            self.update_color_button()
            
            # Get width
            if hasattr(symbol, 'width'):
                self.width_spin.setValue(symbol.width())
            
            # Get opacity
            if hasattr(symbol, 'opacity'):
                self.opacity_spin.setValue(symbol.opacity())
            
            # For fill symbols
            geom_type = self.current_layer.geometryType()
            if geom_type == 2:  # Polygon
                self.current_fill_color = color
                self.update_fill_color_button()
        
        # Load label settings
        labeling = self.current_layer.labeling()
        if labeling:
            settings = labeling.settings()
            if isinstance(settings, QgsPalLayerSettings):
                self.labels_enabled.setChecked(True)
                self.font_size_spin.setValue(int(settings.format().size()))
                self.current_font_color = settings.format().color()
                self.update_font_color_button()
                
                if settings.format().buffer().enabled():
                    self.buffer_enabled.setChecked(True)
                    self.buffer_size_spin.setValue(settings.format().buffer().size())
                    self.current_buffer_color = settings.format().buffer().color()
                    self.update_buffer_color_button()
        else:
            self.labels_enabled.setChecked(False)
        
        # Populate label field combo
        self.label_field_combo.clear()
        self.label_field_combo.addItem("name")
        for field in self.current_layer.fields():
            field_name = field.name()
            if field_name != "name" and field_name not in ['fid', 'id']:
                self.label_field_combo.addItem(field_name)
    
    def on_labels_toggled(self, state):
        """Enable/disable label controls"""
        enabled = state == Qt.Checked
        self.label_field_combo.setEnabled(enabled)
        self.font_size_spin.setEnabled(enabled)
        self.font_color_btn.setEnabled(enabled)
        self.text_format_combo.setEnabled(enabled)
        self.buffer_enabled.setEnabled(enabled)
        self.buffer_size_spin.setEnabled(enabled)
        self.buffer_color_btn.setEnabled(enabled)
        self.placement_combo.setEnabled(enabled)
    
    def choose_color(self):
        """Choose line/stroke color"""
        color = QColorDialog.getColor(self.current_color, self, "Choose Line Color")
        if color.isValid():
            self.current_color = color
            self.update_color_button()
    
    def choose_fill_color(self):
        """Choose fill color"""
        color = QColorDialog.getColor(self.current_fill_color, self, "Choose Fill Color")
        if color.isValid():
            self.current_fill_color = color
            self.update_fill_color_button()
    
    def choose_font_color(self):
        """Choose font color"""
        color = QColorDialog.getColor(self.current_font_color, self, "Choose Font Color")
        if color.isValid():
            self.current_font_color = color
            self.update_font_color_button()
    
    def choose_buffer_color(self):
        """Choose buffer color"""
        color = QColorDialog.getColor(self.current_buffer_color, self, "Choose Buffer Color")
        if color.isValid():
            self.current_buffer_color = color
            self.update_buffer_color_button()
    
    def update_color_button(self):
        """Update color button appearance"""
        self.color_btn.setStyleSheet(
            f"background-color: {self.current_color.name()}; "
            f"color: {'white' if self.current_color.lightness() < 128 else 'black'};"
        )
    
    def update_fill_color_button(self):
        """Update fill color button appearance"""
        self.fill_color_btn.setStyleSheet(
            f"background-color: {self.current_fill_color.name()}; "
            f"color: {'white' if self.current_fill_color.lightness() < 128 else 'black'};"
        )
    
    def update_font_color_button(self):
        """Update font color button appearance"""
        self.font_color_btn.setStyleSheet(
            f"background-color: {self.current_font_color.name()}; "
            f"color: {'white' if self.current_font_color.lightness() < 128 else 'black'};"
        )
    
    def update_buffer_color_button(self):
        """Update buffer color button appearance"""
        self.buffer_color_btn.setStyleSheet(
            f"background-color: {self.current_buffer_color.name()}; "
            f"color: {'white' if self.current_buffer_color.lightness() < 128 else 'black'};"
        )
    
    def apply_road_preset(self, width):
        """Apply quick road width preset"""
        if not self.current_layer:
            return
        
        self.width_spin.setValue(width)
        self.apply_changes()
    
    def apply_changes(self):
        """Apply style changes to current layer"""
        if not self.current_layer or not self.current_layer.isValid():
            return
        
        # Apply symbol style
        geom_type = self.current_layer.geometryType()
        renderer = self.current_layer.renderer()
        
        if renderer and renderer.symbol():
            symbol = renderer.symbol().clone()
            
            # Set color
            symbol.setColor(self.current_color)
            
            # Set width
            if hasattr(symbol, 'setWidth'):
                symbol.setWidth(self.width_spin.value())
            
            # Set opacity
            if hasattr(symbol, 'setOpacity'):
                symbol.setOpacity(self.opacity_spin.value())
            
            # For polygons, set fill
            if geom_type == 2:  # Polygon
                symbol.setColor(self.current_fill_color)
                symbol_layer = symbol.symbolLayer(0)
                if symbol_layer:
                    symbol_layer.setStrokeColor(self.current_color)
                    symbol_layer.setFillColor(self.current_fill_color)
                    symbol_layer.setStrokeWidth(self.width_spin.value())
                    fill_color = QColor(self.current_fill_color)
                    fill_color.setAlphaF(self.fill_opacity_spin.value())
                    symbol_layer.setFillColor(fill_color)
            
            renderer.setSymbol(symbol)
        
        # Apply labeling
        if self.labels_enabled.isChecked():
            label_field = self.label_field_combo.currentText()
            
            # Create label settings
            settings = QgsPalLayerSettings()
            settings.fieldName = label_field
            
            # Text format
            text_format = QgsTextFormat()
            text_format.setSize(self.font_size_spin.value())
            text_format.setColor(self.current_font_color)
            
            # Buffer
            if self.buffer_enabled.isChecked():
                buffer = text_format.buffer()
                buffer.setEnabled(True)
                buffer.setSize(self.buffer_size_spin.value())
                buffer.setColor(self.current_buffer_color)
                text_format.setBuffer(buffer)
            
            settings.setFormat(text_format)
            
            # Text format transformation
            text_format_option = self.text_format_combo.currentText()
            if text_format_option == 'UPPERCASE':
                settings.fieldName = f"upper({label_field})"
            elif text_format_option == 'lowercase':
                settings.fieldName = f"lower({label_field})"
            elif text_format_option == 'Title Case':
                settings.fieldName = f"title({label_field})"
            
            # Placement
            if geom_type == 1:  # Line
                placement = self.placement_combo.currentIndex()
                if placement == 0:
                    settings.placement = QgsPalLayerSettings.AboveLine
                elif placement == 1:
                    settings.placement = QgsPalLayerSettings.Line
                elif placement == 2:
                    settings.placement = QgsPalLayerSettings.BelowLine
                elif placement == 3:
                    settings.placement = QgsPalLayerSettings.Horizontal
                else:
                    settings.placement = QgsPalLayerSettings.Curved
            
            # Apply labeling
            labeling = QgsVectorLayerSimpleLabeling(settings)
            self.current_layer.setLabeling(labeling)
            self.current_layer.setLabelsEnabled(True)
        else:
            self.current_layer.setLabelsEnabled(False)
        
        # Refresh
        self.current_layer.triggerRepaint()
        self.iface.layerTreeView().refreshLayerSymbology(self.current_layer.id())
