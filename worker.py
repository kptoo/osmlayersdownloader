"""
Download Worker - QThread-based non-blocking download worker
"""

import json
from qgis.PyQt.QtCore import QThread, pyqtSignal
from qgis.core import QgsMessageLog, Qgis

from .osm_api import OSMAPIHandler


class DownloadWorker(QThread):
    """QThread worker for downloading OSM features without blocking the QGIS UI."""

    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    layer_ready = pyqtSignal(str, dict)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, bbox, feature_configs, parent=None):
        super().__init__(parent)
        self.bbox = bbox
        self.feature_configs = feature_configs
        self._abort = False
        self._api = OSMAPIHandler()

    def abort(self):
        self._abort = True
        self.log.emit("⚠ Abort requested — stopping after current feature…")
        QgsMessageLog.logMessage(
            "Download aborted by user", "OSM Bulk Downloader", Qgis.Warning
        )

    def run(self):
        total = len(self.feature_configs)
        if total == 0:
            self.log.emit("⚠ No features selected.")
            self.finished.emit()
            return

        try:
            for idx, config in enumerate(self.feature_configs):
                if self._abort:
                    self.log.emit("✗ Download aborted.")
                    break

                display_name = config.get("display", config.get("name", "unknown"))
                self.log.emit(f"Downloading {display_name}…")
                QgsMessageLog.logMessage(
                    f"Downloading {display_name}", "OSM Bulk Downloader", Qgis.Info
                )

                try:
                    geojson = self._api.download_feature(self.bbox, config)
                except Exception as exc:
                    msg = f"✗ Error downloading {display_name}: {exc}"
                    self.log.emit(msg)
                    QgsMessageLog.logMessage(msg, "OSM Bulk Downloader", Qgis.Warning)
                    geojson = None

                if geojson is not None:
                    feature_count = len(geojson.get("features", []))
                    if feature_count == 0:
                        self.log.emit(f"  (no features found for {display_name})")
                    else:
                        self.log.emit(f"✓ {feature_count} features loaded — {display_name}")
                        geojson_str = json.dumps(geojson)
                        self.layer_ready.emit(geojson_str, config)
                else:
                    self.log.emit(f"✗ Failed to download {display_name}")

                pct = int((idx + 1) / total * 100)
                self.progress.emit(pct)

            if not self._abort:
                self.log.emit("✓ All layers downloaded.")
                self.progress.emit(100)

        except Exception as exc:
            msg = f"Unexpected error in download worker: {exc}"
            QgsMessageLog.logMessage(msg, "OSM Bulk Downloader", Qgis.Critical)
            self.error.emit(msg)

        finally:
            self.finished.emit()
