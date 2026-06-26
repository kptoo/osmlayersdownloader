"""
Layer Manager - Loading, styling and managing downloaded OSM layers in QGIS
"""

import json
import tempfile
import os
import time

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
    QgsStyle,
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QSizeF

GROUP_NAME = "OSM Downloads"

# ---------------------------------------------------------------------------
# QGIS built-in style names used as defaults for specific feature categories
# ---------------------------------------------------------------------------
TOPO_WATER_STYLE    = "topo water"       # for water bodies, lakes, bays
TOPO_ROAD_STYLE     = "topo road"        # for all road types and paths/trails
TOPO_HYDRO_STYLE    = "topo hydrology"   # for rivers and streams/canals

# Feature-name keywords that map to each topo style
_WATER_KEYWORDS  = ('water_bodies', 'bays', 'lakes')
_ROAD_KEYWORDS   = ('roads_major', 'roads_residential', 'roads_local',
                    'paths_trails', 'ski_runs', 'ski_lifts', 'runways')
_HYDRO_KEYWORDS  = ('rivers', 'streams')


def _feature_topo_style(feature_name: str):
    """
    Return the QGIS built-in style name for a given feature config name,
    or None if no topo style applies.
    """
    n = feature_name.lower()
    if any(k in n for k in _WATER_KEYWORDS):
        return TOPO_WATER_STYLE
    if any(k in n for k in _ROAD_KEYWORDS):
        return TOPO_ROAD_STYLE
    if any(k in n for k in _HYDRO_KEYWORDS):
        return TOPO_HYDRO_STYLE
    return None


class LayerManager:
    """Manages loading, styling, and grouping of OSM feature layers in QGIS."""

    def __init__(self, iface=None):
        self.iface = iface
        self._plugin_layers = []

    def _get_or_create_group(self):
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(GROUP_NAME)
        if group is None:
            group = root.insertGroup(0, GROUP_NAME)
        return group

    def load_geojson_as_layer(self, geojson_str, layer_name, style_config):
        """
        Create a QGIS vector layer from a GeoJSON string, apply styling,
        add it to the 'OSM Downloads' group and return the layer.
        """
        tmp = None
        tmp_path = None

        try:
            # Write GeoJSON to a temp file
            tmp = tempfile.NamedTemporaryFile(
                suffix=".geojson", mode="w", encoding="utf-8", delete=False
            )
            tmp_path = tmp.name
            tmp.write(geojson_str)
            tmp.flush()
            tmp.close()
            tmp = None  # Mark as closed

            layer = QgsVectorLayer(tmp_path, layer_name, "ogr")

            if not layer.isValid():
                QgsMessageLog.logMessage(
                    f"Failed to create layer '{layer_name}'",
                    "OSM Bulk Downloader", Qgis.Warning,
                )
                return None

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
                "OSM Bulk Downloader", Qgis.Critical,
            )
            return None

        finally:
            # Close temp file handle if still open
            if tmp is not None:
                try:
                    tmp.close()
                except Exception:
                    pass

            # Try to delete temp file — on Windows QGIS may hold it open briefly
            if tmp_path and os.path.exists(tmp_path):
                for attempt in range(5):
                    try:
                        os.unlink(tmp_path)
                        break
                    except (OSError, PermissionError):
                        if attempt < 4:
                            time.sleep(0.2)
                        else:
                            pass  # Give up silently — OS will clean it up

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def apply_style(self, layer, style_config):
        """
        Apply styling to a layer.

        Priority:
          1. Try to apply the QGIS built-in topo style that matches the
             feature category (topo water / topo road / topo hydrology).
          2. Fall back to the colour/weight values in style_config if the
             built-in style is not found or cannot be applied.
        """
        feature_name = style_config.get("name", "")
        topo_style   = _feature_topo_style(feature_name)

        if topo_style and self._apply_builtin_style(layer, topo_style):
            QgsMessageLog.logMessage(
                f"Applied built-in style '{topo_style}' to '{layer.name()}'",
                "OSM Bulk Downloader", Qgis.Info,
            )
            return

        # --- Fallback: manual colour/weight styling ---
        style    = style_config.get("style", {})
        if not style:
            return

        geom_type = layer.geometryType()

        try:
            if geom_type == QgsWkbTypes.PointGeometry:
                self._style_point(layer, style)
            elif geom_type == QgsWkbTypes.LineGeometry:
                self._style_line(layer, style)
            elif geom_type == QgsWkbTypes.PolygonGeometry:
                self._style_polygon(layer, style)
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Style error on '{layer.name()}': {exc}",
                "OSM Bulk Downloader", Qgis.Warning,
            )

    def _apply_builtin_style(self, layer, style_name: str) -> bool:
        """
        Look up a symbol by name in the QGIS default style library and apply
        it to the layer.  Returns True on success, False if not found.

        The QGIS built-in styles (topo water, topo road, topo hydrology) are
        stored as named symbols in QgsStyle.defaultStyle().  This method
        searches fill symbols (for polygons), line symbols (for lines), and
        marker symbols (for points) in that order.
        """
        try:
            default_style = QgsStyle.defaultStyle()
            geom_type     = layer.geometryType()

            if geom_type == QgsWkbTypes.PolygonGeometry:
                symbol = default_style.symbol(style_name)           # fill symbol
                if symbol is None:
                    # Some QGIS versions store them case-sensitively
                    for name in default_style.symbolNames():
                        if name.lower() == style_name.lower():
                            symbol = default_style.symbol(name)
                            break
                if symbol:
                    layer.setRenderer(QgsSingleSymbolRenderer(symbol.clone()))
                    layer.triggerRepaint()
                    return True

            elif geom_type == QgsWkbTypes.LineGeometry:
                symbol = default_style.symbol(style_name)
                if symbol is None:
                    for name in default_style.symbolNames():
                        if name.lower() == style_name.lower():
                            symbol = default_style.symbol(name)
                            break
                if symbol:
                    layer.setRenderer(QgsSingleSymbolRenderer(symbol.clone()))
                    layer.triggerRepaint()
                    return True

            elif geom_type == QgsWkbTypes.PointGeometry:
                symbol = default_style.symbol(style_name)
                if symbol is None:
                    for name in default_style.symbolNames():
                        if name.lower() == style_name.lower():
                            symbol = default_style.symbol(name)
                            break
                if symbol:
                    layer.setRenderer(QgsSingleSymbolRenderer(symbol.clone()))
                    layer.triggerRepaint()
                    return True

        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Could not apply built-in style '{style_name}' to "
                f"'{layer.name()}': {exc}",
                "OSM Bulk Downloader", Qgis.Warning,
            )

        return False

    def _style_point(self, layer, style):
        color_str = style.get("color", "#FF0000")
        symbol = QgsMarkerSymbol.createSimple(
            {"color": color_str, "size": "3", "outline_style": "no"}
        )
        symbol.setOpacity(style.get("opacity", 1.0))
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    def _style_line(self, layer, style):
        color_str = style.get("color", "#000000")
        weight    = style.get("weight", 1)
        symbol = QgsLineSymbol.createSimple(
            {"color": color_str, "width": str(weight), "capstyle": "round"}
        )
        symbol.setOpacity(style.get("opacity", 1.0))
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    def _style_polygon(self, layer, style):
        stroke_color  = style.get("color", "#000000")
        fill_color    = style.get("fillColor", "#CCCCCC")
        weight        = style.get("weight", 0.5)
        fill_opacity  = style.get("fillOpacity", 0.5)
        fill_qcolor   = QColor(fill_color)
        fill_qcolor.setAlphaF(fill_opacity)
        symbol = QgsFillSymbol.createSimple({
            "color":         fill_qcolor.name(QColor.HexArgb),
            "outline_color": stroke_color,
            "outline_width": str(weight),
            "style":         "solid",
            "outline_style": "solid",
        })
        symbol.setOpacity(style.get("opacity", 1.0))
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def apply_labels(self, layer, field="name", font_size=10):
        """Enable simple text labels on field for the given layer."""
        settings = QgsPalLayerSettings()
        settings.fieldName = field
        settings.enabled = True
        text_format = QgsTextFormat()
        text_format.setSize(font_size)
        text_format.setColor(QColor("#333333"))
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
            for tree_layer in group.findLayers():
                QgsProject.instance().removeMapLayer(tree_layer.layerId())
            root.removeChildNode(group)
        self._plugin_layers.clear()
        QgsMessageLog.logMessage(
            "Removed all OSM Downloads layers",
            "OSM Bulk Downloader", Qgis.Info
        )

    def gray_all_roads(self):
        """Set all road layers in the OSM Downloads group to gray."""
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(GROUP_NAME)
        if not group:
            return
        road_keywords = ["road", "roads", "highway", "street", "path", "trail"]
        for tree_layer in group.findLayers():
            layer = tree_layer.layer()
            if layer is None:
                continue
            if any(kw in layer.name().lower() for kw in road_keywords):
                self._style_line(layer, {"color": "#888888", "weight": 1, "opacity": 0.8})
                layer.triggerRepaint()
        QgsMessageLog.logMessage(
            "Set all road layers to gray",
            "OSM Bulk Downloader", Qgis.Info
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
        return [
            tl.layer() for tl in group.findLayers()
            if tl.layer() and tl.layer().isValid()
        ]
