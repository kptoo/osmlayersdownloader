"""
SVG Exporter - Export QGIS layers to SVG format
"""

import xml.etree.ElementTree as ET
from typing import List, Tuple
import math
from qgis.core import (QgsVectorLayer, QgsFeature, QgsGeometry, 
                       QgsWkbTypes, QgsMessageLog, Qgis)


class SVGExporter:
    # Standard paper sizes in mm
    PAPER_SIZES = {
        'A4': (210, 297),
        'A3': (297, 420),
        'Letter': (216, 279),
        'Tabloid': (279, 432)
    }
    
    def __init__(self, bbox: Tuple[float, float, float, float], 
                 paper_size: str = 'A4', orientation: str = 'auto', margin_mm: float = 10):
        """
        Initialize SVG exporter
        bbox: (south, west, north, east) in WGS84
        paper_size: 'A4', 'A3', 'Letter', or 'Tabloid'
        orientation: 'portrait', 'landscape', or 'auto'
        margin_mm: margin in millimeters
        """
        self.south, self.west, self.north, self.east = bbox
        self.margin_mm = margin_mm
        
        # Get paper dimensions
        if paper_size not in self.PAPER_SIZES:
            paper_size = 'A4'
        
        paper_width_mm, paper_height_mm = self.PAPER_SIZES[paper_size]
        
        # Calculate bbox aspect ratio
        self.lon_range = self.east - self.west
        self.lat_range = self.north - self.south
        
        # Adjust for latitude distortion (approximate)
        avg_lat = (self.north + self.south) / 2
        lat_correction = math.cos(math.radians(avg_lat))
        corrected_lon_range = self.lon_range * lat_correction
        
        bbox_aspect = corrected_lon_range / self.lat_range if self.lat_range > 0 else 1
        
        # Determine orientation
        if orientation == 'auto':
            if bbox_aspect > 1:
                orientation = 'landscape'
            else:
                orientation = 'portrait'
        
        # Set dimensions based on orientation
        if orientation == 'landscape':
            self.page_width_mm = max(paper_width_mm, paper_height_mm)
            self.page_height_mm = min(paper_width_mm, paper_height_mm)
        else:
            self.page_width_mm = min(paper_width_mm, paper_height_mm)
            self.page_height_mm = max(paper_width_mm, paper_height_mm)
        
        # Calculate content area (page minus margins)
        self.content_width_mm = self.page_width_mm - (2 * margin_mm)
        self.content_height_mm = self.page_height_mm - (2 * margin_mm)
        
        # Convert to pixels (assuming 96 DPI: 1mm = 3.7795px)
        mm_to_px = 3.7795
        self.width = self.page_width_mm * mm_to_px
        self.height = self.page_height_mm * mm_to_px
        self.margin_px = margin_mm * mm_to_px
        
        # Calculate drawing area
        self.draw_width = self.content_width_mm * mm_to_px
        self.draw_height = self.content_height_mm * mm_to_px
        
        # Calculate scale to fit content in drawing area while maintaining aspect ratio
        content_aspect = self.draw_width / self.draw_height
        
        if bbox_aspect > content_aspect:
            # Width is limiting factor
            self.scale = self.draw_width / corrected_lon_range
            actual_height = self.lat_range * self.scale
            # Center vertically
            self.y_offset = self.margin_px + (self.draw_height - actual_height) / 2
            self.x_offset = self.margin_px
        else:
            # Height is limiting factor
            self.scale = self.draw_height / self.lat_range
            actual_width = corrected_lon_range * self.scale
            # Center horizontally
            self.x_offset = self.margin_px + (self.draw_width - actual_width) / 2
            self.y_offset = self.margin_px
        
        QgsMessageLog.logMessage(
            f"SVG: {paper_size} {orientation}, bbox aspect: {bbox_aspect:.2f}, "
            f"scale: {self.scale:.2f}, size: {self.width:.0f}x{self.height:.0f}px",
            'OSM Bulk Downloader', Qgis.Info
        )
        
    def lon_to_x(self, lon: float) -> float:
        """Convert longitude to SVG x coordinate"""
        # Normalize to 0-1 range
        normalized_x = (lon - self.west) / self.lon_range if self.lon_range > 0 else 0
        
        # Apply latitude correction for aspect ratio
        avg_lat = (self.north + self.south) / 2
        lat_correction = math.cos(math.radians(avg_lat))
        
        # Convert to SVG coordinates
        # normalized_x is already 0-1, just scale by draw width with lat correction
        svg_x = self.x_offset + (normalized_x * self.draw_width)
        
        return svg_x
    
    def lat_to_y(self, lat: float) -> float:
        """Convert latitude to SVG y coordinate (inverted)"""
        # Normalize to 0-1 range (inverted for SVG coordinate system)
        normalized_y = (self.north - lat) / self.lat_range if self.lat_range > 0 else 0
        
        # Convert to SVG coordinates  
        # normalized_y is already 0-1, just scale by draw height
        svg_y = self.y_offset + (normalized_y * self.draw_height)
        
        return svg_y
    
    def export_layers_to_svg(self, layers: List[QgsVectorLayer], output_file: str, source_crs=None):
        """Export multiple QGIS layers to a single SVG file with coordinate transformation"""
        from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
        
        QgsMessageLog.logMessage(f"Starting SVG export to {output_file}", 'OSM Bulk Downloader', Qgis.Info)
        QgsMessageLog.logMessage(f"Bbox (WGS84): {self.south}, {self.west}, {self.north}, {self.east}", 'OSM Bulk Downloader', Qgis.Info)
        QgsMessageLog.logMessage(f"Number of layers to export: {len(layers)}", 'OSM Bulk Downloader', Qgis.Info)
        
        # Setup coordinate transformation to WGS84
        wgs84_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        
        # Create SVG root with proper dimensions
        svg = ET.Element('svg', {
            'xmlns': 'http://www.w3.org/2000/svg',
            'width': f'{self.page_width_mm}mm',
            'height': f'{self.page_height_mm}mm',
            'viewBox': f'0 0 {self.width:.0f} {self.height:.0f}'
        })
        
        # Add background (full page)
        bg = ET.SubElement(svg, 'rect', {
            'width': str(self.width),
            'height': str(self.height),
            'fill': 'white'
        })
        
        # Create groups for features and labels
        features_group = ET.SubElement(svg, 'g', {'id': 'features'})
        labels_group = ET.SubElement(svg, 'g', {'id': 'labels'})
        
        # Track unique label names to prevent duplicates
        used_label_names = set()
        
        total_features = 0
        
        # Process each layer
        for layer in layers:
            if not layer.isValid():
                QgsMessageLog.logMessage(f"  Layer invalid: {layer.name()}", 'OSM Bulk Downloader', Qgis.Warning)
                continue
            
            layer_name = layer.name().replace(' ', '_').replace('&', 'and')
            layer_group = ET.SubElement(features_group, 'g', {
                'id': layer_name,
                'class': 'layer'
            })
            
            # Get layer styling
            renderer = layer.renderer()
            symbol = renderer.symbol() if renderer else None
            
            # Check THIS layer's CRS (each layer might be different!)
            layer_crs = layer.crs()
            transform = None
            
            if layer_crs != wgs84_crs:
                # Layer is NOT in WGS84, need to transform
                transform = QgsCoordinateTransform(layer_crs, wgs84_crs, QgsProject.instance())
                QgsMessageLog.logMessage(
                    f"  Layer '{layer.name()}' CRS: {layer_crs.authid()} → transforming to WGS84", 
                    'OSM Bulk Downloader', Qgis.Info
                )
            else:
                QgsMessageLog.logMessage(
                    f"  Layer '{layer.name()}' already in WGS84", 
                    'OSM Bulk Downloader', Qgis.Info
                )
            
            # Count features in this layer
            feature_count = 0
            
            # Process features
            for feature in layer.getFeatures():
                # Transform geometry if needed
                if transform:
                    try:
                        geom = QgsGeometry(feature.geometry())
                        geom.transform(transform)
                        # Create new feature with transformed geometry
                        transformed_feature = QgsFeature(feature)
                        transformed_feature.setGeometry(geom)
                        self.add_feature_to_svg(transformed_feature, layer_group, labels_group, symbol, layer.name(), used_label_names)
                    except Exception as e:
                        QgsMessageLog.logMessage(f"    Error transforming feature: {str(e)}", 'OSM Bulk Downloader', Qgis.Warning)
                        continue
                else:
                    # No transformation needed
                    self.add_feature_to_svg(feature, layer_group, labels_group, symbol, layer.name(), used_label_names)
                
                feature_count += 1
                total_features += 1
            
            QgsMessageLog.logMessage(f"  Layer '{layer.name()}': {feature_count} features exported", 'OSM Bulk Downloader', Qgis.Info)
        
        QgsMessageLog.logMessage(f"Total features exported: {total_features}", 'OSM Bulk Downloader', Qgis.Info)
        
        # Write SVG file
        tree = ET.ElementTree(svg)
        ET.indent(tree, space='  ')
        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        
        QgsMessageLog.logMessage(
            f"SVG exported: {self.page_width_mm}x{self.page_height_mm}mm ({self.width:.0f}x{self.height:.0f}px) to {output_file}",
            'OSM Bulk Downloader', Qgis.Info
        )
    
    def add_feature_to_svg(self, feature: QgsFeature, features_group: ET.Element, 
                          labels_group: ET.Element, symbol, layer_name: str, used_label_names: set):
        """Add a single feature to SVG"""
        geometry = feature.geometry()
        
        if geometry.isNull():
            return
        
        geom_type = geometry.wkbType()
        
        # Get styling from symbol
        style_attrs = self.get_style_attrs(symbol, geom_type)
        
        # Handle different geometry types
        if QgsWkbTypes.geometryType(geom_type) == QgsWkbTypes.PointGeometry:
            self.add_point_to_svg(geometry, features_group, labels_group, feature, style_attrs, layer_name, used_label_names)
        elif QgsWkbTypes.geometryType(geom_type) == QgsWkbTypes.LineGeometry:
            self.add_line_to_svg(geometry, features_group, style_attrs)
        elif QgsWkbTypes.geometryType(geom_type) == QgsWkbTypes.PolygonGeometry:
            self.add_polygon_to_svg(geometry, features_group, labels_group, feature, style_attrs, layer_name, used_label_names)
    
    def get_style_attrs(self, symbol, geom_type):
        """Extract style attributes from QGIS symbol"""
        attrs = {
            'stroke': 'black',
            'stroke-width': '1',
            'fill': 'none',
            'fill-opacity': '0.5',
            'stroke-opacity': '1.0'
        }
        
        if not symbol:
            return attrs
        
        try:
            # Get the main color
            color = symbol.color()
            
            # For polygons, set both fill and stroke
            if QgsWkbTypes.geometryType(geom_type) == QgsWkbTypes.PolygonGeometry:
                attrs['fill'] = color.name()
                attrs['fill-opacity'] = str(color.alphaF())
                attrs['stroke'] = color.darker(110).name()  # Slightly darker outline
                attrs['stroke-width'] = '0.5'
                
                # Try to get outline width from symbol layer
                if symbol.symbolLayerCount() > 0:
                    symbol_layer = symbol.symbolLayer(0)
                    if hasattr(symbol_layer, 'strokeWidth'):
                        attrs['stroke-width'] = str(symbol_layer.strokeWidth())
                    if hasattr(symbol_layer, 'strokeColor'):
                        stroke_color = symbol_layer.strokeColor()
                        if stroke_color.isValid():
                            attrs['stroke'] = stroke_color.name()
            
            # For lines, use the color as stroke
            elif QgsWkbTypes.geometryType(geom_type) == QgsWkbTypes.LineGeometry:
                attrs['stroke'] = color.name()
                attrs['fill'] = 'none'
                attrs['stroke-opacity'] = str(color.alphaF())
                
                # Try to get line width
                if hasattr(symbol, 'width'):
                    width = symbol.width()
                    attrs['stroke-width'] = str(max(0.1, width))  # Min 0.1 to ensure visibility
                
                # Try from symbol layer
                if symbol.symbolLayerCount() > 0:
                    symbol_layer = symbol.symbolLayer(0)
                    if hasattr(symbol_layer, 'width'):
                        width = symbol_layer.width()
                        attrs['stroke-width'] = str(max(0.1, width))
            
            # For points
            else:
                attrs['fill'] = color.name()
                attrs['stroke'] = color.darker(110).name()
                
        except Exception as e:
            QgsMessageLog.logMessage(f"Error extracting style: {str(e)}", 'OSM Bulk Downloader', Qgis.Warning)
        
        return attrs
    
    def add_point_to_svg(self, geometry: QgsGeometry, features_group: ET.Element,
                        labels_group: ET.Element, feature: QgsFeature, style_attrs: dict, layer_name: str, used_label_names: set):
        """Add point geometry to SVG"""
        point = geometry.asPoint()
        x = self.lon_to_x(point.x())
        y = self.lat_to_y(point.y())
        
        # Draw point as circle
        circle_attrs = {
            'cx': f'{x:.2f}',
            'cy': f'{y:.2f}',
            'r': '3',
            'fill': style_attrs.get('stroke', '#4682B4'),
            'stroke': 'black',
            'stroke-width': '1'
        }
        ET.SubElement(features_group, 'circle', circle_attrs)
        
        # Only add labels for water body layers
        water_layer_keywords = ['water bodies', 'water_bodies', 'bays', 'bay']
        layer_name_lower = layer_name.lower()
        is_water_body = any(keyword in layer_name_lower for keyword in water_layer_keywords)
        
        if is_water_body:
            # Add label if feature has name AND it hasn't been used yet
            try:
                name = feature.attribute('name')
                if name and str(name).strip() and str(name) != 'NULL':
                    name_str = str(name).strip()
                    # Only add if this name hasn't been used before
                    if name_str not in used_label_names:
                        used_label_names.add(name_str)
                        # Match QGIS label styling with white buffer/halo
                        text_attrs = {
                            'x': f'{x:.2f}',
                            'y': f'{y:.2f}',
                            'font-size': '10',  # Match QGIS default
                            'font-family': 'Arial, sans-serif',
                            'font-weight': 'normal',
                            'fill': '#000000',  # Black text
                            'text-anchor': 'start',
                            'stroke': '#FFFFFF',  # White buffer/halo
                            'stroke-width': '3',  # Buffer width
                            'paint-order': 'stroke fill'  # Draw stroke first, then fill
                        }
                        text = ET.SubElement(labels_group, 'text', text_attrs)
                        text.text = name_str
            except (KeyError, AttributeError):
                # Feature doesn't have a name field, skip label
                pass
    
    def add_line_to_svg(self, geometry: QgsGeometry, features_group: ET.Element, style_attrs: dict):
        """Add line geometry to SVG"""
        if geometry.isMultipart():
            lines = geometry.asMultiPolyline()
            for line in lines:
                self.add_single_line(line, features_group, style_attrs)
        else:
            line = geometry.asPolyline()
            self.add_single_line(line, features_group, style_attrs)
    
    def add_single_line(self, line, features_group: ET.Element, style_attrs: dict):
        """Add a single line to SVG"""
        if not line:
            return
        
        points = []
        for point in line:
            x = self.lon_to_x(point.x())
            y = self.lat_to_y(point.y())
            points.append(f"{x:.2f},{y:.2f}")
        
        # Ensure minimum stroke width for visibility
        stroke_width = style_attrs.get('stroke-width', '1')
        try:
            width_val = float(stroke_width)
            if width_val < 0.5:
                stroke_width = '1'  # Minimum 1px for SVG visibility
        except:
            stroke_width = '1'
        
        path_attrs = {
            'd': f'M {" L ".join(points)}',
            'fill': 'none',
            'stroke': style_attrs.get('stroke', 'black'),
            'stroke-width': stroke_width,
            'stroke-opacity': style_attrs.get('stroke-opacity', '1.0')
        }
        
        ET.SubElement(features_group, 'path', path_attrs)
    
    def add_polygon_to_svg(self, geometry: QgsGeometry, features_group: ET.Element,
                          labels_group: ET.Element, feature: QgsFeature, style_attrs: dict, layer_name: str, used_label_names: set):
        """Add polygon geometry to SVG"""
        # Draw all polygon parts
        if geometry.isMultipart():
            polygons = geometry.asMultiPolygon()
            for polygon in polygons:
                self.add_single_polygon(polygon, features_group, style_attrs)
        else:
            polygon = geometry.asPolygon()
            self.add_single_polygon(polygon, features_group, style_attrs)
        
        # Only add labels for water body layers
        water_layer_keywords = ['water bodies', 'water_bodies', 'bays', 'bay']
        layer_name_lower = layer_name.lower()
        is_water_body = any(keyword in layer_name_lower for keyword in water_layer_keywords)
        
        if is_water_body:
            # Add ONE label per feature (not per polygon part) AND only if name not used
            try:
                name = feature.attribute('name')
                if name and str(name).strip() and str(name) != 'NULL':
                    name_str = str(name).strip()
                    # Only add if this name hasn't been used before
                    if name_str not in used_label_names:
                        used_label_names.add(name_str)
                        # Use centroid of entire geometry (all parts combined)
                        centroid = geometry.centroid().asPoint()
                        x = self.lon_to_x(centroid.x())
                        y = self.lat_to_y(centroid.y())
                        
                        # Match QGIS label styling with white buffer/halo
                        text_attrs = {
                            'x': f'{x:.2f}',
                            'y': f'{y:.2f}',
                            'font-size': '10',  # Match QGIS default
                            'font-family': 'Arial, sans-serif',
                            'font-weight': 'normal',
                            'fill': '#000000',  # Black text
                            'text-anchor': 'middle',
                            'stroke': '#FFFFFF',  # White buffer/halo
                            'stroke-width': '3',  # Buffer width
                            'paint-order': 'stroke fill'  # Draw stroke first, then fill
                        }
                        text = ET.SubElement(labels_group, 'text', text_attrs)
                        text.text = name_str
            except (KeyError, AttributeError):
                # Feature doesn't have a name field, skip label
                pass
    
    def add_single_polygon(self, polygon, features_group: ET.Element, style_attrs: dict):
        """Add a single polygon to SVG"""
        if not polygon or not polygon[0]:
            return
        
        # Outer ring
        outer_ring = polygon[0]
        points = []
        for point in outer_ring:
            x = self.lon_to_x(point.x())
            y = self.lat_to_y(point.y())
            points.append(f"{x:.2f},{y:.2f}")
        
        path_attrs = {
            'd': f'M {" L ".join(points)} Z',
            'fill': style_attrs.get('fill', 'gray'),
            'fill-opacity': style_attrs.get('fill-opacity', '0.5'),
            'stroke': style_attrs.get('stroke', 'black'),
            'stroke-width': style_attrs.get('stroke-width', '1'),
            'stroke-opacity': style_attrs.get('stroke-opacity', '1.0')
        }
        
        ET.SubElement(features_group, 'path', path_attrs)
        
        # Inner rings (holes)
        for inner_ring in polygon[1:]:
            points = []
            for point in inner_ring:
                x = self.lon_to_x(point.x())
                y = self.lat_to_y(point.y())
                points.append(f"{x:.2f},{y:.2f}")
            
            hole_attrs = {
                'd': f'M {" L ".join(points)} Z',
                'fill': 'white',
                'stroke': 'none'
            }
            
            ET.SubElement(features_group, 'path', hole_attrs)
