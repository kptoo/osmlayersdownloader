# OSM Bulk Downloader — QGIS Plugin

An ARTographer-style dark-themed QGIS plugin for bulk-downloading OpenStreetMap data for lake and golf course mapping.

---

## Features

- **Dark-themed dockable panel** — right-side dock with a professional dark UI
- **Location search** — type any place name and press 🔍 to search via Nominatim; or use 🌐 to use the current map extent
- **Padding control** — add a percentage buffer around the search area
- **27 feature types** (checkbox selection with colour indicators):
  - Water Bodies & Lakes, Rivers, Streams, Bays, Coastlines
  - Golf Courses, Parks/Reserves, Protected Areas
  - Major Roads, Residential Roads, Local Roads, Paths/Trails, Railways
  - Buildings, Mountain Peaks, Cities, Places
  - Beaches, Islands, Residential Areas, State/Country Boundaries
  - Airports, Runways, Ski Resorts, Ski Runs, Ski Lifts
- **One-click bulk download** ("Generate Map") — downloads all checked layers in a background thread
- **Progress bar + activity log** — real-time feedback in the Activity tab
- **Per-feature auto-styling** — each layer gets its own colour/line-width/fill
- **Label toggle** — enable/disable labels globally across all layers
- **Tool buttons**:
  - *City Roads* — download all road types at once
  - *Grab 1 Layer* — download only the single checked layer
  - *Gray Roads* — set all road layers to gray
  - *Tiny Polys* — remove tiny polygon artefacts from water/golf layers
  - *Lets Golf* — download golf courses for the current extent
  - *Smooth Lake / Smooth River* — dissolve/merge water features
  - *Set Frame* — draw an 11×14 inch red frame on the canvas
  - *Clear Map* — remove all OSM Download layers
  - *Abort* — cancel a running download
- **SVG export** — export all layers to a single SVG file (A4/A3/Letter/Tabloid)
- **QGIS layer group** — all layers are added under an "OSM Downloads" group

---

## Installation

### From ZIP (recommended)

1. Download or clone this repository.
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the downloaded ZIP and click **Install Plugin**.
4. Enable the plugin under **Installed** plugins.

### Manual

1. Copy the `osmlayersdownloader/` folder to your QGIS plugins directory:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS/Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
2. Restart QGIS and enable the plugin in **Plugins → Manage and Install Plugins**.

---

## Requirements

- QGIS 3.16+
- Python `requests` library (install via OSGeo4W Shell or system Python):
  ```
  pip install requests
  ```

---

## Usage

1. Open the panel: **Web → OSM Bulk Downloader → OSM Bulk Downloader**
2. Type a place name (e.g. "Turkeyfoot Lake") and click 🔍 **or** navigate the QGIS map canvas to your area and click 🌐
3. Tick the feature types you want in the **Options** section
4. (Optional) Adjust the padding percentage
5. Click **Generate Map** — layers will appear in QGIS as they download
6. Use **Export** (Export tab) to save an SVG

---

## File Structure

```
osmlayersdownloader/
├── __init__.py              — QGIS plugin entry point
├── metadata.txt             — Plugin metadata
├── icon.png                 — Toolbar icon
├── osm_bulk_downloader.py   — Main plugin class (toolbar/menu)
├── osm_downloader_dialog.py — OSMDownloaderDock (main dark panel)
├── worker.py                — QThread download worker
├── layer_manager.py         — Layer loading, styling, grouping
├── osm_api.py               — Overpass + Nominatim API handler
├── feature_configs.py       — All 27 feature type configs
├── frame_builder.py         — 11×14 inch frame geometry builder
├── style_editor_dialog.py   — Advanced layer style editor dialog
├── svg_exporter.py          — SVG export engine
└── README.md
```

---

## Credits

Built on top of the OpenStreetMap Overpass API and Nominatim geocoding service.
Inspired by the ARTographer mapping workflow for lake and golf course cartography.
