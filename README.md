# OSM Bulk Downloader - QGIS Plugin

Download and import OpenStreetMap features in bulk directly into QGIS.

## Features

- **Download various OSM features**: Golf courses, water bodies, rivers, beaches, roads, boundaries, and more
- **Dockable interface**: Integrates seamlessly with QGIS layer panel
- **Automatic styling**: Each feature type comes with predefined colors and styles
- **Label generation**: Automatically creates labels for named features
- **Quick selection**: Preset buttons for common feature groups (Water, Roads, Boundaries)
- **Multi-threaded**: Downloads happen in background without blocking QGIS

## Installation

### Method 1: Manual Installation

1. Download or clone this repository
2. Copy the `osm_bulk_downloader` folder to your QGIS plugins directory:
   - **Windows**: `C:\Users\{username}\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Mac**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

3. Restart QGIS
4. Enable the plugin:
   - Go to `Plugins > Manage and Install Plugins`
   - Find "OSM Bulk Downloader" in the list
   - Check the box to enable it

### Method 2: From ZIP

1. Create a ZIP file of the `osm_bulk_downloader` folder
2. In QGIS: `Plugins > Manage and Install Plugins > Install from ZIP`
3. Select the ZIP file and click "Install Plugin"

## Usage

1. **Open the plugin**: 
   - Click the plugin icon in the toolbar, or
   - Go to `Web > OSM Bulk Downloader`
   
2. **Search for a location**:
   - Enter a place name (e.g., "Stow, Ohio", "Manhattan, New York", "Paris, France")
   - Click "Search"
   - The plugin will find the location and show its bounding box

3. **Select features**:
   - Use the quick select buttons (All, Water, Roads, Boundaries, None), or
   - Manually select individual features from the list

4. **Download**:
   - Click "Download & Add to QGIS"
   - Watch the progress in the log window
   - Layers will be automatically added to your QGIS project with styling

## Available Features

### Water Features
- Water Bodies & Lakes
- Rivers & Streams
- Bays
- Beaches

### Infrastructure
- Roads (Residential, Local, Major)
- Trails & Paths

### Land Use
- Golf Courses
- Residential Areas
- Islands

### Administrative Boundaries
- City Boundaries
- State/Province Boundaries
- Country Boundaries

## Styling

Each feature type has predefined styling:
- **Roads**: Varying widths (thin=residential, medium=local, thick=major highways)
- **Water**: Blue colors with transparency
- **Boundaries**: Dashed lines in red/orange tones
- **Labels**: Automatically generated for named features

You can modify styles after import using QGIS's standard styling tools.

## Requirements

- QGIS 3.0 or higher
- Internet connection (for accessing OpenStreetMap APIs)
- Python packages: `requests` (usually included with QGIS)

## Tips

- **Large areas**: For very large regions, be selective with features (especially roads) to avoid long download times
- **API limits**: The plugin includes automatic delays between requests to respect OSM API limits
- **Re-download**: You can search for the same location multiple times and add different feature sets
- **Layer management**: Layers are added as temporary GeoJSON layers. Save them if you want to keep them permanently

## Troubleshooting

**Plugin doesn't appear in menu**:
- Make sure it's enabled in Plugin Manager
- Check the QGIS Python console for error messages

**"Place not found"**:
- Try different search terms (add country/state)
- Use more specific location names

**No features downloaded**:
- The location might not have those features in OpenStreetMap
- Try a different area or different feature types

**Download is slow**:
- This is normal for large areas or many features
- The plugin respects API rate limits with 2-second delays

## Credits

- OpenStreetMap contributors for the data
- Overpass API for data retrieval
- Nominatim for geocoding

## License

This plugin is released under the GNU General Public License v3.0

## Support

For issues, feature requests, or contributions, please visit the GitHub repository.
