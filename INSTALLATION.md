# Quick Installation Guide

## Install the Plugin

1. **Copy the plugin folder**:
   ```
   Copy the entire 'osm_bulk_downloader' folder to your QGIS plugins directory
   ```

2. **QGIS plugins directory location**:
   - **Windows**: `C:\Users\{username}\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Mac**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

3. **Restart QGIS**

4. **Enable the plugin**:
   - Open QGIS
   - Go to: `Plugins` → `Manage and Install Plugins`
   - Click on "Installed" tab
   - Find "OSM Bulk Downloader" in the list
   - Check the box next to it to enable

5. **Access the plugin**:
   - Click the plugin icon in the toolbar (looks like a map grid)
   - Or go to: `Web` → `OSM Bulk Downloader`
   - A dockable panel will appear on the right side

## First Use

1. **Enter a location**: Type a place name (e.g., "London, UK")
2. **Click Search**: The plugin will find the location
3. **Select features**: Choose what to download (use quick buttons or select individually)
4. **Click "Download & Add to QGIS"**: Wait for download to complete
5. **View your layers**: All downloaded features appear as layers in QGIS

## Folder Structure

```
osm_bulk_downloader/
├── __init__.py                    # Plugin initialization
├── metadata.txt                   # Plugin metadata
├── icon.png                       # Plugin icon
├── README.md                      # Full documentation
├── INSTALLATION.md                # This file
├── osm_bulk_downloader.py        # Main plugin class
├── osm_downloader_dialog.py      # UI dialog
├── osm_api.py                    # OSM API handler
└── feature_configs.py            # Feature definitions
```

## Troubleshooting

**Plugin doesn't show up**:
- Make sure you copied to the correct plugins folder
- Restart QGIS completely
- Check Plugin Manager → Installed tab

**"Module not found" error**:
- Make sure all files are in the `osm_bulk_downloader` folder
- Don't rename the folder

**Can't enable plugin**:
- Check Python console in QGIS for error messages
- Go to: `Plugins` → `Python Console`

## Need Help?

Check the README.md file for detailed documentation and usage instructions.
