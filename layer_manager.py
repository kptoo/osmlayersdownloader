"""
Layer Manager - Loading, styling and managing downloaded OSM layers in QGIS
"""

import json
import tempfile
import os

from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsLayerTreeGroup,
    QgsSymbol,
    QgsLineSymbol,
    QgsFillSymbol,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling,
    QgsMessageLog,
    QgsWkbTypes,
    Qgis,
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QSizeF

GROUP_NAME = "OSM Downloads"


class LayerManager:
    """Manages loading, styling, and grouping of OSM feature layers in QGIS."""

    def __init__(self, iface=None):
        self.iface = iface
        self._plugin_layers = []  # track layer IDs added by this plugin

    # ------------------------------------------------------------------
    # Group helpers
    # ------------------------------------------------------------------

    def _get_or_create_group(self):
        """Return (or create) the top-level 'OSM Downloads' layer group."""
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(GROUP_NAME)
        if group is None:
            group = root.insertGroup(0, GROUP_NAME)
        return group

    # ------------------------------------------------------------------
    # Layer loading
    # ------------------------------------------------------------------

    def load_geojson_as_layer(self, geojson_str, layer_name, style_config):
        """
        Create a QGIS vector layer from a GeoJSON string, apply styling,
        add it to the 'OSM Downloads' group and return the layer.

        Args:
            geojson_str: GeoJSON feature collection as a string
            layer_name:  Display name for the layer
            style_config: Feature config dict containing 'style' sub-dict

        Returns:
            QgsVectorLayer or None on failure
        """
        # Write GeoJSON to a temp file so ogr can load it
        tmp = tempfile.NamedTemporaryFile(
            suffix=".geojson", mode="w", encoding="utf-8", delete=False
        )
        try:
            tmp.write(geojson_str)
            tmp.close()

            layer = QgsVectorLayer(tmp.name, layer_name, "ogr")
            if not layer.isValid():
                QgsMessageLog.logMessage(
                    f"Failed to create layer '{layer_name}'",
                    "OSM Bulk Downloader",
                    Qgis.Warning,
                )
                return None

            # Set CRS to WGS84
            layer.setCrs(
                QgsProject.instance().crs()
                if QgsProject.instance().crs().isValid()
                else layer.crs()
            )

            # Apply style BEFORE adding to project
            self.apply_style(layer, style_config)

            # Add to project (not directly to layer tree yet)
            QgsProject.instance().addMapLayer(layer, False)

            # Put into our group
            group = self._get_or_create_group()
            group.addLayer(layer)

            self._plugin_layers.append(layer.id())
            return layer

        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Error loading layer '{layer_name}': {exc}",
                "OSM Bulk Downloader",
                Qgis.Critical,
            )
            return None
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def apply_style(self, layer, style_config):
        """
        Apply fill/stroke/line styling from a feature config dict.

        The 'style' sub-dict may contain:
          color, fillColor, weight, opacity, fillOpacity
        """
        style = style_config.get("style", {})
        if not style:
            return

        geom_type = layer.geometryType()  # 0=Point, 1=Line, 2=Polygon

        try:
            if geom_type == QgsWkbTypes.PointGeometry:  # 0
                self._style_point(layer, style)
            elif geom_type == QgsWkbTypes.LineGeometry:  # 1
                self._style_line(layer, style)
            elif geom_type == QgsWkbTypes.PolygonGeometry:  # 2
                self._style_polygon(layer, style)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Style error on '{layer.name()}': {exc}",
                "OSM Bulk Downloader",
                Qgis.Warning,
            )

    def _style_point(self, layer, style):
        color_str = style.get("color", "#FF0000")
        symbol = QgsMarkerSymbol.createSimple(
            {"color": color_str, "size": "3", "outline_style": "no"}
        )
        opacity = style.get("opacity", 1.0)
        symbol.setOpacity(opacity)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    def _style_line(self, layer, style):
        color_str = style.get("color", "#000000")
        weight = style.get("weight", 1)
        opacity = style.get("opacity", 1.0)
        symbol = QgsLineSymbol.createSimple(
            {"color": color_str, "width": str(weight), "capstyle": "round"}
        )
        symbol.setOpacity(opacity)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    def _style_polygon(self, layer, style):
        stroke_color = style.get("color", "#000000")
        fill_color = style.get("fillColor", "#CCCCCC")
        weight = style.get("weight", 0.5)
        fill_opacity = style.get("fillOpacity", 0.5)
        opacity = style.get("opacity", 1.0)

        # Build fill color with alpha
        fill_qcolor = QColor(fill_color)
        fill_qcolor.setAlphaF(fill_opacity)

        symbol = QgsFillSymbol.createSimple(
            {
                "color": fill_qcolor.name(QColor.HexArgb),
                "outline_color": stroke_color,
                "outline_width": str(weight),
                "style": "solid",
                "outline_style": "solid",
            }
        )
        symbol.setOpacity(opacity)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def apply_labels(self, layer, field="name", font_size=10):
        """Enable simple text labels on *field* for the given layer."""
        settings = QgsPalLayerSettings()
        settings.fieldName = field
        settings.enabled = True

        text_format = QgsTextFormat()
        text_format.setSize(font_size)
        text_format.setColor(QColor("#333333"))

        # White buffer for readability
        buffer = QgsTextBufferSettings()
        buffer.setEnabled(True)
        buffer.setSize(1.0)
        buffer.setColor(QColor("white"))
        text_format.setBuffer(buffer)

        settings.setFormat(text_format)
        labeling = QgsVectorLayerSimpleLabeling(settings)
        layer.setLabeling(labeling)
        layer.setLabelsEnabled(True)
        layer.triggerRepaint()

    def disable_labels(self, layer):
        """Disable labels on a layer."""
        layer.setLabelsEnabled(False)
        layer.triggerRepaint()

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def remove_all_plugin_layers(self):
        """Remove the entire 'OSM Downloads' group and all its layers."""
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(GROUP_NAME)
        if group:
            # Collect layer ids in the group
            for tree_layer in group.findLayers():
                layer_id = tree_layer.layerId()
                QgsProject.instance().removeMapLayer(layer_id)
            root.removeChildNode(group)
        self._plugin_layers.clear()
        QgsMessageLog.logMessage(
            "Removed all OSM Downloads layers", "OSM Bulk Downloader", Qgis.Info
        )

    def gray_all_roads(self):
        """Set all road layers in the 'OSM Downloads' group to gray."""
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(GROUP_NAME)
        if not group:
            return

        road_keywords = ["road", "roads", "highway", "street", "path", "trail"]
        gray_color = "#888888"

        for tree_layer in group.findLayers():
            layer = tree_layer.layer()
            if layer is None:
                continue
            name_lower = layer.name().lower()
            if any(kw in name_lower for kw in road_keywords):
                style = {"color": gray_color, "weight": 1, "opacity": 0.8}
                self._style_line(layer, style)
                layer.triggerRepaint()

        QgsMessageLog.logMessage(
            "Set all road layers to gray", "OSM Bulk Downloader", Qgis.Info
        )

    def set_zoom_dependent_visibility(self, layer, min_scale, max_scale):
        """Set minimum/maximum scale denominators for zoom-dependent visibility."""
        layer.setMinimumScale(max_scale)
        layer.setMaximumScale(min_scale)
        layer.setScaleBasedVisibility(True)

    def get_plugin_layers(self):
        """Return list of currently loaded plugin layer IDs."""
        return list(self._plugin_layers)

    def get_valid_plugin_layers(self):
        """Return list of valid QgsVectorLayer objects in the OSM Downloads group."""
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(GROUP_NAME)
        if not group:
            return []
        layers = []
        for tree_layer in group.findLayers():
            layer = tree_layer.layer()
            if layer and layer.isValid():
                layers.append(layer)
        return layers
