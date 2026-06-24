"""
OSM Bulk Downloader - Main Plugin File
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDockWidget
from qgis.core import QgsProject
import os.path

from .osm_downloader_dialog import OSMDownloaderDock


class OSMBulkDownloader:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = '&OSM Bulk Downloader'
        self.toolbar = self.iface.addToolBar('OSM Bulk Downloader')
        self.toolbar.setObjectName('OSMBulkDownloader')
        self.dockwidget = None

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                   add_to_menu=True, add_to_toolbar=True,
                   status_tip=None, whats_this=None, parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.toolbar.addAction(action)
        if add_to_menu:
            self.iface.addPluginToWebMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        if not os.path.exists(icon_path):
            icon_path = ''
        self.add_action(
            icon_path,
            text='OSM Bulk Downloader',
            callback=self.run,
            parent=self.iface.mainWindow())

    def unload(self):
        for action in self.actions:
            self.iface.removePluginWebMenu('&OSM Bulk Downloader', action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar
        if self.dockwidget:
            self.iface.removeDockWidget(self.dockwidget)

    def run(self):
        if self.dockwidget is None:
            self.dockwidget = OSMDownloaderDock(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
        self.dockwidget.show()
