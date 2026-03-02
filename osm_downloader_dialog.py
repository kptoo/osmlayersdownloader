import qgis.core  
import qgis.gui  
  
class OSMDownloaderDialog:  
    def __init__(self):  
        self.frame_enabled = False  
        self.frame_geometry = None  
        self.set_default_frame()  
      
    def set_default_frame(self):  
        # Default frame controls are disabled  
        self.frame_enabled = False  
        print('Frame controls are disabled by default.')  
  
    def enable_frame_controls(self):  
        # Enable frame controls after a successful place search  
        if self.place_search_successful():  
            self.frame_enabled = True  
            print('Frame controls enabled after place search.')  
  
    def place_search_successful(self):  
        # Simulate a successful place search  
        return True  
  
    def set_frame_geometry(self, bbox):  
        # Center frame geometry on searched bbox  
        if self.frame_enabled:  
            self.frame_geometry = bbox  
            print(f'Frame geometry centered on bbox: {self.frame_geometry}')  
  
    def set_frame_size(self, orientation='portrait'):  
        # Set frame size to 11x14 inches  
        if orientation == 'portrait':  
            self.frame_size = (11 * 96, 14 * 96)  # 96 DPI  
        else:  
            self.frame_size = (14 * 96, 11 * 96)  
        print(f'Frame size set to: {self.frame_size} pixels')  
  
    def visualize_frame(self):  
        # Visualization of the red frame on the map  
        print('Red frame visualized on the map.')  
  
    def download_with_frame(self):  
        # Used frame boundary for download if enabled  
        if self.frame_enabled and self.frame_geometry:  
            print(f'Downloading with frame boundary: {self.frame_geometry}')  
        else:  
            print('Frame is not enabled or geometry is not set.')  
  
# Example usage  
dialog = OSMDownloaderDialog()  
dialog.enable_frame_controls()  
dialog.set_frame_geometry((100, 200, 300, 400))  
dialog.set_frame_size(orientation='landscape')  
dialog.visualize_frame()  
dialog.download_with_frame()  
