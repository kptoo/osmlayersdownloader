"""
OSM Downloader Dock — ARTographer-style dark-themed dockable panel.

Provides:
  - Location search (Nominatim) + manual extent mode
  - Padding control
  - Checkbox grid for all 21+ feature types with colour indicators
  - Coloured tool buttons (City Roads, Grab 1 Layer, Gray Roads, etc.)
  - QTabWidget: Activity | Settings | Export | Access
  - Activity tab: progress bar + log + Copy for Josh
  - Export tab: paper size / orientation / output path
  - Generate Map / Export / Abort / Clear Map actions
"""

import json
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QDoubleSpinBox,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QTabWidget,
    QScrollArea,
    QComboBox,
    QFileDialog,
    QSizePolicy,
    QSpacerItem,
    QApplication,
)
from qgis.core import (
    QgsProject,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsVectorLayer,
    QgsFeature,
    QgsFillSymbol,
    QgsSingleSymbolRenderer,
    QgsWkbTypes,
    Qgis,
)

from .feature_configs import get_all_features
from .worker import DownloadWorker
from .layer_manager import LayerManager
from .frame_builder import FrameBuilder
from .svg_exporter import SVGExporter

# ---------------------------------------------------------------------------
# Dark-theme stylesheet
# ---------------------------------------------------------------------------
DARK_STYLE = """
QDockWidget {
    background-color: #1a1a2e;
    color: #ffffff;
}
QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QGroupBox {
    border: 1px solid #444;
    border-radius: 4px;
    margin-top: 8px;
    color: #cccccc;
    padding: 4px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    color: #aaaaaa;
    padding: 0 4px;
}
QCheckBox {
    color: #e0e0e0;
    spacing: 5px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #666;
    border-radius: 2px;
    background-color: #2d2d44;
}
QCheckBox::indicator:checked {
    background-color: #4CAF50;
    border-color: #4CAF50;
}
QLineEdit {
    background-color: #2d2d44;
    color: #ffffff;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 3px;
}
QDoubleSpinBox, QSpinBox {
    background-color: #2d2d44;
    color: #ffffff;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 2px;
}
QComboBox {
    background-color: #2d2d44;
    color: #ffffff;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 2px;
}
QComboBox QAbstractItemView {
    background-color: #2d2d44;
    color: #ffffff;
    selection-background-color: #3a3a5c;
}
QProgressBar {
    border: 1px solid #555;
    border-radius: 3px;
    background: #2d2d44;
    text-align: center;
    color: #ffffff;
}
QProgressBar::chunk {
    background-color: #4CAF50;
    border-radius: 2px;
}
QTextEdit {
    background-color: #0d0d1a;
    color: #88ff88;
    font-family: monospace;
    font-size: 11px;
    border: 1px solid #333;
    border-radius: 3px;
}
QScrollArea {
    border: none;
    background-color: #1a1a2e;
}
QTabWidget::pane {
    border: 1px solid #444;
    background-color: #1a1a2e;
}
QTabBar::tab {
    background-color: #2d2d44;
    color: #cccccc;
    padding: 5px 10px;
    border: 1px solid #444;
    border-bottom: none;
}
QTabBar::tab:selected {
    background-color: #3a3a5c;
    color: #ffffff;
}
QPushButton {
    border-radius: 3px;
    padding: 4px 8px;
    color: #ffffff;
    font-weight: bold;
    border: none;
}
"""


def _btn(label, bg_color, min_height=26):
    """Helper: create a styled QPushButton with the given background colour."""
    b = QPushButton(label)
    b.setStyleSheet(
        f"background-color: {bg_color}; color: #ffffff; border-radius: 3px; "
        f"padding: 3px 6px; font-weight: bold;"
    )
    b.setMinimumHeight(min_height)
    return b


def _color_swatch(hex_color):
    """Return a 14x14 QLabel coloured with hex_color."""
    lbl = QLabel()
    lbl.setFixedSize(14, 14)
    lbl.setStyleSheet(
        f"background-color: {hex_color}; border: 1px solid #666; border-radius: 2px;"
    )
    return lbl


# ---------------------------------------------------------------------------
# Main dock widget
# ---------------------------------------------------------------------------

class OSMDownloaderDock(QDockWidget):
    """Dark-themed dockable panel for the OSM Bulk Downloader plugin."""

    def __init__(self, iface, parent=None):
        super().__init__("OSM Bulk Downloader", parent)
        self.iface = iface
        self.setObjectName("OSMBulkDownloaderDock")

        self._worker = None
        self._layer_manager = LayerManager(iface)
        self._all_features = get_all_features()

        # dict: feature_name -> QCheckBox
        self._feature_checkboxes = {}
        self._labels_enabled = True
        self._current_bbox = None
        self._base_map_on = True

        self._build_ui()
        self.setStyleSheet(DARK_STYLE)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        container = QWidget()
        container.setObjectName("osmDockContainer")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        # Location section
        main_layout.addWidget(self._build_location_section())

        # Padding section
        main_layout.addWidget(self._build_padding_section())

        # Options (feature checkboxes)
        main_layout.addWidget(self._build_options_section())

        # Tools buttons
        main_layout.addWidget(self._build_tools_section())

        # Tab widget (Activity / Settings / Export / Access)
        self._tabs = self._build_tabs()
        main_layout.addWidget(self._tabs)

        # Bottom action buttons
        main_layout.addWidget(self._build_bottom_buttons())

        self.setWidget(container)

    # ---- Location -------------------------------------------------------

    def _build_location_section(self):
        grp = QGroupBox("Location")
        layout = QVBoxLayout(grp)
        layout.setSpacing(3)

        row = QHBoxLayout()
        self._location_edit = QLineEdit()
        self._location_edit.setPlaceholderText("e.g. turkeyfoot lake")
        self._location_edit.returnPressed.connect(self._on_search)
        row.addWidget(self._location_edit)

        search_btn = _btn("\U0001f50d", "#3a3a5c", 28)
        search_btn.setFixedWidth(32)
        search_btn.setToolTip("Search location via Nominatim")
        search_btn.clicked.connect(self._on_search)
        row.addWidget(search_btn)

        extent_btn = _btn("\U0001f30d", "#3a3a5c", 28)
        extent_btn.setFixedWidth(32)
        extent_btn.setToolTip("Use current map extent")
        extent_btn.clicked.connect(self._on_use_extent)
        row.addWidget(extent_btn)

        layout.addLayout(row)
        return grp

    # ---- Padding --------------------------------------------------------

    def _build_padding_section(self):
        grp = QGroupBox("Padding")
        layout = QHBoxLayout(grp)
        layout.setSpacing(6)

        self._padding_spin = QDoubleSpinBox()
        self._padding_spin.setRange(0, 100)
        self._padding_spin.setValue(0)
        self._padding_spin.setSuffix("%")
        self._padding_spin.setFixedWidth(70)
        layout.addWidget(self._padding_spin)

        self._manual_chk = QCheckBox("Manual")
        self._manual_chk.setChecked(False)
        layout.addWidget(self._manual_chk)

        self._water_chk = QCheckBox("Water")
        self._water_chk.setChecked(False)
        layout.addWidget(self._water_chk)

        layout.addStretch()
        return grp

    # ---- Feature checkboxes ---------------------------------------------

    def _build_options_section(self):
        grp = QGroupBox("Options")
        outer = QVBoxLayout(grp)

        # Global toggles row
        toggle_row = QHBoxLayout()
        self._base_map_chk = QCheckBox("base map")
        self._base_map_chk.setChecked(True)
        self._abbreviate_chk = QCheckBox("Abbreviate")
        self._abbreviate_chk.setChecked(False)
        self._gray_roads_chk = QCheckBox("Gray roads")
        self._gray_roads_chk.setChecked(False)
        self._labels_chk = QCheckBox("Enable labels")
        self._labels_chk.setChecked(True)
        self._labels_chk.stateChanged.connect(self._on_labels_toggled)
        for w in (self._base_map_chk, self._abbreviate_chk,
                  self._gray_roads_chk, self._labels_chk):
            toggle_row.addWidget(w)
        toggle_row.addStretch()
        outer.addLayout(toggle_row)

        # Scrollable 2-column grid of feature checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(260)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(3)
        grid.setContentsMargins(2, 2, 2, 2)

        features = self._all_features
        # Default checked features
        default_on = {
            "water_bodies",
            "golf_courses",
            "roads_major",
            "roads_residential",
            "roads_local",
            "paths_trails",
            "rivers",
            "streams",
        }

        for i, feat in enumerate(features):
            grid_row = i // 2
            col_base = (i % 2) * 3  # each feature: swatch(0), checkbox(1), spacer(2)

            style = feat.get("style", {})
            swatch_color = (
                style.get("fillColor")
                or style.get("color")
                or "#888888"
            )
            swatch = _color_swatch(swatch_color)

            chk = QCheckBox(feat["display"])
            chk.setChecked(feat["name"] in default_on)
            self._feature_checkboxes[feat["name"]] = chk

            grid.addWidget(swatch, grid_row, col_base, Qt.AlignVCenter)
            grid.addWidget(chk, grid_row, col_base + 1, Qt.AlignVCenter)
            if i % 2 == 0:
                grid.addItem(QSpacerItem(8, 1), grid_row, col_base + 2)

        scroll.setWidget(grid_widget)
        outer.addWidget(scroll)

        # Select all / none buttons
        sel_row = QHBoxLayout()
        all_btn = _btn("All", "#3a3a5c")
        none_btn = _btn("None", "#3a3a5c")
        all_btn.clicked.connect(self._select_all_features)
        none_btn.clicked.connect(self._select_no_features)
        sel_row.addWidget(all_btn)
        sel_row.addWidget(none_btn)
        sel_row.addStretch()
        outer.addLayout(sel_row)

        return grp

    # ---- Tool buttons ---------------------------------------------------

    def _build_tools_section(self):
        grp = QGroupBox("Tools")
        grid = QGridLayout(grp)
        grid.setSpacing(4)

        GRAY   = "#555555"
        ORANGE = "#FF6600"
        CYAN   = "#00AAAA"
        GREEN  = "#00AA00"
        BLUE   = "#3399FF"
        RED    = "#CC0000"

        # (label, color, slot_or_None)
        tool_defs = [
            # row 0
            ("City Roads",    GRAY,   self._on_city_roads),
            ("Grab 1 Layer",  GRAY,   self._on_grab_one_layer),
            ("Gray Roads",    GRAY,   self._on_gray_roads),
            # row 1
            ("Tiny Polys",    ORANGE, self._on_tiny_polys),
            ("Custom Pins",   CYAN,   self._on_custom_pins),
            ("Lets Golf",     GREEN,  self._on_lets_golf),
            # row 2
            ("Smooth Lake",   BLUE,   self._on_smooth_lake),
            ("Smooth River",  BLUE,   self._on_smooth_river),
            ("Set Frame",     GRAY,   self._on_set_frame),
            # row 3
            ("Clear Map",     RED,    self._on_clear_map),
            ("Abort",         RED,    self._on_abort),
        ]

        for idx, (label, color, slot) in enumerate(tool_defs):
            r, c = divmod(idx, 3)
            b = _btn(label, color)
            if slot:
                b.clicked.connect(slot)
            grid.addWidget(b, r, c)

        # Base Map toggle (spans last cell of row 3)
        self._base_map_btn = _btn("x Base Map", GREEN)
        self._base_map_btn.clicked.connect(self._on_toggle_base_map)
        grid.addWidget(self._base_map_btn, 3, 2)

        return grp

    # ---- Tabs -----------------------------------------------------------

    def _build_tabs(self):
        tabs = QTabWidget()

        # Activity tab
        activity_widget = QWidget()
        al = QVBoxLayout(activity_widget)
        al.setSpacing(4)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        al.addWidget(self._progress_bar)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMinimumHeight(120)
        al.addWidget(self._log_edit)

        copy_btn = _btn("Copy for Josh", "#444466")
        copy_btn.clicked.connect(self._on_copy_log)
        al.addWidget(copy_btn)

        tabs.addTab(activity_widget, "Activity")

        # Settings tab
        tabs.addTab(self._build_settings_tab(), "Settings")

        # Export tab
        tabs.addTab(self._build_export_tab(), "Export")

        # Access tab
        access_widget = QWidget()
        access_layout = QVBoxLayout(access_widget)
        access_layout.addWidget(QLabel("API access settings (Overpass / Nominatim)"))
        self._overpass_url_edit = QLineEdit("https://overpass-api.de/api/interpreter")
        access_layout.addWidget(QLabel("Overpass URL:"))
        access_layout.addWidget(self._overpass_url_edit)
        self._nominatim_url_edit = QLineEdit("https://nominatim.openstreetmap.org/search")
        access_layout.addWidget(QLabel("Nominatim URL:"))
        access_layout.addWidget(self._nominatim_url_edit)
        access_layout.addStretch()
        tabs.addTab(access_widget, "Access")

        return tabs

    def _build_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(6)

        frame_grp = QGroupBox("Frame / Paper")
        fl = QVBoxLayout(frame_grp)
        orient_row = QHBoxLayout()
        orient_row.addWidget(QLabel("Orientation:"))
        self._orientation_combo = QComboBox()
        self._orientation_combo.addItems(["portrait", "landscape"])
        orient_row.addWidget(self._orientation_combo)
        fl.addLayout(orient_row)
        layout.addWidget(frame_grp)

        zoom_grp = QGroupBox("Zoom Visibility")
        zl = QVBoxLayout(zoom_grp)
        self._zoom_vis_chk = QCheckBox("Enable zoom-dependent visibility")
        self._zoom_vis_chk.setChecked(False)
        zl.addWidget(self._zoom_vis_chk)
        layout.addWidget(zoom_grp)

        layout.addStretch()
        return widget

    def _build_export_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(6)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Paper:"))
        self._paper_combo = QComboBox()
        self._paper_combo.addItems(["A4", "A3", "Letter", "Tabloid"])
        size_row.addWidget(self._paper_combo)
        layout.addLayout(size_row)

        orient_row = QHBoxLayout()
        orient_row.addWidget(QLabel("Orientation:"))
        self._export_orientation_combo = QComboBox()
        self._export_orientation_combo.addItems(["auto", "portrait", "landscape"])
        orient_row.addWidget(self._export_orientation_combo)
        layout.addLayout(orient_row)

        path_row = QHBoxLayout()
        self._export_path_edit = QLineEdit()
        self._export_path_edit.setPlaceholderText("Output SVG path...")
        path_row.addWidget(self._export_path_edit)
        browse_btn = _btn("...", "#3a3a5c")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._on_browse_export_path)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        layout.addStretch()
        return widget

    # ---- Bottom buttons -------------------------------------------------

    def _build_bottom_buttons(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(6)

        self._export_btn = _btn("Export", "#3399FF", 34)
        self._export_btn.clicked.connect(self._on_export)
        layout.addWidget(self._export_btn)

        self._generate_btn = _btn("Generate Map", "#00AA00", 34)
        self._generate_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._generate_btn.clicked.connect(self._on_generate_map)
        layout.addWidget(self._generate_btn)

        return widget

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, msg):
        """Append a message to the activity log."""
        self._log_edit.append(msg)
        QgsMessageLog.logMessage(msg, "OSM Bulk Downloader", Qgis.Info)

    def _get_selected_features(self):
        """Return list of feature config dicts that are currently checked."""
        return [
            feat
            for feat in self._all_features
            if self._feature_checkboxes.get(feat["name"], QCheckBox()).isChecked()
        ]

    def _get_bbox(self):
        """
        Return (south, west, north, east) bbox.
        Uses the location search result if available, otherwise current canvas extent.
        Applies padding percentage.
        """
        if self._current_bbox:
            south, west, north, east = self._current_bbox
        else:
            south, west, north, east = self._canvas_bbox()

        padding_pct = self._padding_spin.value() / 100.0
        if padding_pct > 0:
            lat_pad = (north - south) * padding_pct
            lon_pad = (east - west) * padding_pct
            south -= lat_pad
            west -= lon_pad
            north += lat_pad
            east += lon_pad

        return (south, west, north, east)

    def _canvas_bbox(self):
        """Return current QGIS canvas extent as (south, west, north, east) in WGS84."""
        canvas = self.iface.mapCanvas()
        extent = canvas.extent()
        canvas_crs = canvas.mapSettings().destinationCrs()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

        if canvas_crs != wgs84:
            transform = QgsCoordinateTransform(
                canvas_crs, wgs84, QgsProject.instance()
            )
            extent = transform.transformBoundingBox(extent)

        return (
            extent.yMinimum(),
            extent.xMinimum(),
            extent.yMaximum(),
            extent.xMaximum(),
        )

    def _set_worker_running(self, running):
        self._generate_btn.setEnabled(not running)
        self._export_btn.setEnabled(not running)

    # ------------------------------------------------------------------
    # Slot implementations
    # ------------------------------------------------------------------

    def _on_search(self):
        """Search for a place name using Nominatim."""
        place = self._location_edit.text().strip()
        if not place:
            self._log("Warning: Please enter a place name.")
            return

        self._log("Searching for '{}'...".format(place))
        QApplication.processEvents()

        from .osm_api import OSMAPIHandler
        api = OSMAPIHandler()
        bbox = api.search_place(place)

        if bbox:
            self._current_bbox = bbox
            south, west, north, east = bbox
            self._log(
                "Found: {} -- bbox [{:.4f}, {:.4f}, {:.4f}, {:.4f}]".format(
                    place, south, west, north, east
                )
            )
            try:
                wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
                canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
                rect = QgsRectangle(west, south, east, north)
                if canvas_crs != wgs84:
                    transform = QgsCoordinateTransform(
                        wgs84, canvas_crs, QgsProject.instance()
                    )
                    rect = transform.transformBoundingBox(rect)
                self.iface.mapCanvas().setExtent(rect)
                self.iface.mapCanvas().refresh()
            except Exception as e:
                self._log("Warning: Could not zoom to extent: {}".format(e))
        else:
            self._log("No results found for '{}'".format(place))

    def _on_use_extent(self):
        """Set the current canvas extent as the working bbox."""
        self._current_bbox = None
        south, west, north, east = self._canvas_bbox()
        self._log(
            "Using current extent: [{:.4f}, {:.4f}, {:.4f}, {:.4f}]".format(
                south, west, north, east
            )
        )

    def _on_generate_map(self):
        """Start bulk download of all selected features."""
        if self._worker and self._worker.isRunning():
            self._log("Warning: A download is already in progress.")
            return

        selected = self._get_selected_features()
        if not selected:
            self._log("Warning: No features selected -- tick at least one checkbox.")
            return

        bbox = self._get_bbox()
        south, west, north, east = bbox
        if south >= north or west >= east:
            self._log("Invalid bbox -- please search a location or navigate the map.")
            return

        self._log(
            "Generating map -- bbox [{:.4f}, {:.4f}, {:.4f}, {:.4f}]".format(
                south, west, north, east
            )
        )
        self._log("  {} feature type(s) selected.".format(len(selected)))
        self._progress_bar.setValue(0)
        self._tabs.setCurrentIndex(0)  # show Activity tab

        self._worker = DownloadWorker(bbox, selected)
        self._worker.progress.connect(self._progress_bar.setValue)
        self._worker.log.connect(self._log)
        self._worker.layer_ready.connect(self._on_layer_ready)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)

        self._set_worker_running(True)
        self._worker.start()

    def _on_layer_ready(self, geojson_str, config):
        """Called from worker thread via Qt signal when a layer is downloaded."""
        layer_name = config.get("display", config.get("name", "OSM Layer"))

        layer = self._layer_manager.load_geojson_as_layer(
            geojson_str, layer_name, config
        )

        if layer and self._labels_chk.isChecked() and config.get("create_labels"):
            self._layer_manager.apply_labels(layer)

        if layer and self._zoom_vis_chk.isChecked():
            self._layer_manager.set_zoom_dependent_visibility(layer, 1000, 500000)

        if self.iface:
            self.iface.mapCanvas().refresh()

    def _on_worker_finished(self):
        self._set_worker_running(False)
        if self._gray_roads_chk.isChecked():
            self._layer_manager.gray_all_roads()
        self._log("Done.")

    def _on_worker_error(self, msg):
        self._log("Error: {}".format(msg))
        self._set_worker_running(False)

    def _on_abort(self):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
        else:
            self._log("No download running.")

    def _on_clear_map(self):
        self._layer_manager.remove_all_plugin_layers()
        self._log("All OSM Download layers removed.")
        if self.iface:
            self.iface.mapCanvas().refresh()

    def _on_gray_roads(self):
        self._layer_manager.gray_all_roads()
        if self.iface:
            self.iface.mapCanvas().refresh()
        self._log("Road layers set to gray.")

    def _on_lets_golf(self):
        """Download only golf courses for the current extent."""
        golf_features = [f for f in self._all_features if f["name"] == "golf_courses"]
        if not golf_features:
            self._log("Golf course feature config not found.")
            return
        if self._worker and self._worker.isRunning():
            self._log("Warning: A download is already running.")
            return
        bbox = self._get_bbox()
        self._log("Downloading golf courses...")
        self._progress_bar.setValue(0)
        self._tabs.setCurrentIndex(0)
        self._worker = DownloadWorker(bbox, golf_features)
        self._worker.progress.connect(self._progress_bar.setValue)
        self._worker.log.connect(self._log)
        self._worker.layer_ready.connect(self._on_layer_ready)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._set_worker_running(True)
        self._worker.start()

    def _on_smooth_lake(self):
        """Dissolve/merge water body polygons."""
        self._dissolve_layer_by_keyword("water", "Smooth Lake")

    def _on_smooth_river(self):
        """Dissolve/merge river line features."""
        self._dissolve_layer_by_keyword("river", "Smooth River")

    def _dissolve_layer_by_keyword(self, keyword, action_name):
        """Find a plugin layer by keyword and run the QGIS dissolve algorithm."""
        try:
            import processing
        except ImportError:
            self._log("{} failed: 'processing' module not available.".format(action_name))
            return

        layers = self._layer_manager.get_valid_plugin_layers()
        target = next(
            (l for l in layers if keyword.lower() in l.name().lower()), None
        )
        if not target:
            self._log("No layer found containing '{}'.".format(keyword))
            return

        try:
            result = processing.run(
                "native:dissolve",
                {"INPUT": target, "FIELD": [], "OUTPUT": "memory:"},
            )
            dissolved = result["OUTPUT"]
            dissolved.setName(target.name() + " (dissolved)")

            style_config = {
                "style": {
                    "color": "#4682B4",
                    "fillColor": "#87CEEB",
                    "fillOpacity": 0.6,
                    "weight": 1,
                }
            }
            self._layer_manager.apply_style(dissolved, style_config)
            QgsProject.instance().addMapLayer(dissolved, False)
            group = self._layer_manager._get_or_create_group()
            group.addLayer(dissolved)
            self._log("{} complete.".format(action_name))
            if self.iface:
                self.iface.mapCanvas().refresh()
        except Exception as e:
            self._log("{} failed: {}".format(action_name, e))

    def _on_tiny_polys(self):
        """Remove very small polygons from water/golf layers."""
        layers = self._layer_manager.get_valid_plugin_layers()
        removed_total = 0

        for layer in layers:
            name = layer.name().lower()
            if "water" not in name and "golf" not in name:
                continue
            if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
                continue

            ids_to_delete = []
            for feat in layer.getFeatures():
                geom = feat.geometry()
                if geom and geom.area() < 1e-8:
                    ids_to_delete.append(feat.id())

            if ids_to_delete:
                layer.startEditing()
                layer.deleteFeatures(ids_to_delete)
                layer.commitChanges()
                removed_total += len(ids_to_delete)

        self._log("Tiny Polys: removed {} tiny polygon(s).".format(removed_total))
        if self.iface:
            self.iface.mapCanvas().refresh()

    def _on_grab_one_layer(self):
        """Download only the single currently-checked layer (if exactly one checked)."""
        selected = self._get_selected_features()
        if len(selected) == 1:
            if self._worker and self._worker.isRunning():
                self._log("Warning: A download is already running.")
                return
            bbox = self._get_bbox()
            self._log("Grabbing single layer: {}".format(selected[0]["display"]))
            self._progress_bar.setValue(0)
            self._tabs.setCurrentIndex(0)
            self._worker = DownloadWorker(bbox, selected)
            self._worker.progress.connect(self._progress_bar.setValue)
            self._worker.log.connect(self._log)
            self._worker.layer_ready.connect(self._on_layer_ready)
            self._worker.finished.connect(self._on_worker_finished)
            self._worker.error.connect(self._on_worker_error)
            self._set_worker_running(True)
            self._worker.start()
        elif len(selected) == 0:
            self._log("Warning: No features selected.")
        else:
            self._log(
                "Grab 1 Layer: {} features checked -- please select exactly ONE "
                "or use Generate Map.".format(len(selected))
            )

    def _on_city_roads(self):
        """Download major + residential + local roads."""
        road_names = {"roads_major", "roads_residential", "roads_local"}
        road_features = [f for f in self._all_features if f["name"] in road_names]
        if not road_features:
            self._log("Road feature configs not found.")
            return
        if self._worker and self._worker.isRunning():
            self._log("Warning: A download is already running.")
            return
        bbox = self._get_bbox()
        self._log("Downloading city roads...")
        self._progress_bar.setValue(0)
        self._tabs.setCurrentIndex(0)
        self._worker = DownloadWorker(bbox, road_features)
        self._worker.progress.connect(self._progress_bar.setValue)
        self._worker.log.connect(self._log)
        self._worker.layer_ready.connect(self._on_layer_ready)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._set_worker_running(True)
        self._worker.start()

    def _on_custom_pins(self):
        self._log("Custom Pins: not yet implemented.")

    def _on_set_frame(self):
        """Draw an 11x14 inch frame rectangle on the canvas centred on the bbox."""
        try:
            bbox = self._get_bbox()
            orientation = self._orientation_combo.currentText()
            frame_geom = FrameBuilder.create_frame_geometry(bbox, orientation)

            if not frame_geom or frame_geom.isEmpty():
                self._log("Could not create frame geometry.")
                return

            frame_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "Frame", "memory")
            pr = frame_layer.dataProvider()
            feat = QgsFeature()
            feat.setGeometry(frame_geom)
            pr.addFeature(feat)
            frame_layer.updateExtents()

            symbol = QgsFillSymbol.createSimple({
                "color": "0,0,0,0",
                "outline_color": "#FF0000",
                "outline_width": "1.5",
                "style": "no",
                "outline_style": "solid",
            })
            frame_layer.setRenderer(QgsSingleSymbolRenderer(symbol))

            QgsProject.instance().addMapLayer(frame_layer, False)
            group = self._layer_manager._get_or_create_group()
            group.addLayer(frame_layer)

            if self.iface:
                self.iface.mapCanvas().refresh()
            self._log("Frame set ({}).".format(orientation))
        except Exception as e:
            self._log("Set Frame failed: {}".format(e))

    def _on_toggle_base_map(self):
        self._base_map_on = not self._base_map_on
        if self._base_map_on:
            self._base_map_btn.setStyleSheet(
                "background-color: #00AA00; color: #ffffff; border-radius: 3px; "
                "padding: 3px 6px; font-weight: bold;"
            )
            self._base_map_btn.setText("x Base Map")
            self._log("Base map enabled.")
        else:
            self._base_map_btn.setStyleSheet(
                "background-color: #CC0000; color: #ffffff; border-radius: 3px; "
                "padding: 3px 6px; font-weight: bold;"
            )
            self._base_map_btn.setText("x Base Map")
            self._log("Base map disabled.")

    def _on_labels_toggled(self, state):
        """Enable/disable labels on all plugin layers."""
        enabled = (state == Qt.Checked)
        self._labels_enabled = enabled
        layers = self._layer_manager.get_valid_plugin_layers()
        for layer in layers:
            if enabled:
                self._layer_manager.apply_labels(layer)
            else:
                self._layer_manager.disable_labels(layer)
        if self.iface:
            self.iface.mapCanvas().refresh()

    def _on_copy_log(self):
        """Copy the activity log text to the clipboard."""
        text = self._log_edit.toPlainText()
        QApplication.clipboard().setText(text)
        self._log("Log copied to clipboard.")

    def _on_browse_export_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save SVG", "", "SVG Files (*.svg)"
        )
        if path:
            if not path.endswith(".svg"):
                path += ".svg"
            self._export_path_edit.setText(path)

    def _on_export(self):
        """Export all plugin layers to SVG."""
        output_path = self._export_path_edit.text().strip()
        if not output_path:
            self._on_browse_export_path()
            output_path = self._export_path_edit.text().strip()
        if not output_path:
            self._log("Warning: No output path specified.")
            return

        layers = self._layer_manager.get_valid_plugin_layers()
        if not layers:
            self._log("Warning: No plugin layers to export.")
            return

        bbox = self._get_bbox()
        paper = self._paper_combo.currentText()
        orientation = self._export_orientation_combo.currentText()

        self._log("Exporting {} layer(s) to SVG...".format(len(layers)))
        try:
            exporter = SVGExporter(bbox, paper_size=paper, orientation=orientation)
            exporter.export_layers_to_svg(layers, output_path)
            self._log("SVG saved: {}".format(output_path))
        except Exception as e:
            self._log("Export failed: {}".format(e))

    # ---- Feature selection helpers --------------------------------------

    def _select_all_features(self):
        for chk in self._feature_checkboxes.values():
            chk.setChecked(True)

    def _select_no_features(self):
        for chk in self._feature_checkboxes.values():
            chk.setChecked(False)
