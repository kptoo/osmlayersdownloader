"""
OSM Bulk Downloader QGIS Plugin
"""

def classFactory(iface):
    from .osm_bulk_downloader import OSMBulkDownloader
    return OSMBulkDownloader(iface)
