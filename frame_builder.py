"""
Frame builder for restricting downloads to a specific frame size.
Supports 11x14 inch frames in portrait and landscape orientations.
"""

from qgis.core import QgsGeometry, QgsPointXY, QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject
import math


class FrameBuilder:
    """Build frame geometry for restricting feature downloads"""
    
    # Frame dimensions in inches
    FRAME_WIDTH_INCHES = 11
    FRAME_HEIGHT_INCHES = 14
    
    @staticmethod
    def meters_per_degree_at_lat(lat):
        """
        Calculate meters per degree longitude at given latitude.
        
        Args:
            lat: Latitude in degrees
            
        Returns:
            float: Meters per degree longitude
        """
        # Simplified formula: cos(latitude) * ~111000 meters per degree
        return math.cos(math.radians(lat)) * 111000
    
    @staticmethod
    def inches_to_meters(inches):
        """
        Convert inches to meters (1 inch = 0.0254 meters).
        
        Args:
            inches: Distance in inches
            
        Returns:
            float: Distance in meters
        """
        return inches * 0.0254
    
    @classmethod
    def create_frame_geometry(cls, bbox, orientation="portrait"):
        """
        Create a frame polygon (11x14 inches) centered on bbox center.
        
        Args:
            bbox: Tuple of (south, west, north, east) in degrees WGS84
            orientation: "portrait" (11w x 14h) or "landscape" (14w x 11h)
        
        Returns:
            QgsGeometry: Rectangle polygon in WGS84 (EPSG:4326)
            
        Raises:
            ValueError: If bbox is invalid
        """
        if not bbox or len(bbox) != 4:
            raise ValueError("bbox must be a tuple of (south, west, north, east)")
        
        south, west, north, east = bbox
        
        # Validate bbox
        if south >= north or west >= east:
            raise ValueError("Invalid bbox: south >= north or west >= east")
        
        # Calculate center
        center_lat = (north + south) / 2
        center_lon = (west + east) / 2
        
        # Get frame dimensions based on orientation
        if orientation.lower() == "landscape":
            frame_width_inches = cls.FRAME_HEIGHT_INCHES  # 14
            frame_height_inches = cls.FRAME_WIDTH_INCHES   # 11
        else:  # portrait (default)
            frame_width_inches = cls.FRAME_WIDTH_INCHES    # 11
            frame_height_inches = cls.FRAME_HEIGHT_INCHES  # 14
        
        # Convert inches to meters
        frame_width_m = cls.inches_to_meters(frame_width_inches)
        frame_height_m = cls.inches_to_meters(frame_height_inches)
        
        # Convert meters to degrees
        # Latitude: ~111,000 meters per degree (constant)
        frame_height_deg = frame_height_m / 111000
        
        # Longitude: depends on latitude
        meters_per_deg_lon = cls.meters_per_degree_at_lat(center_lat)
        frame_width_deg = frame_width_m / meters_per_deg_lon
        
        # Calculate frame corners
        frame_north = center_lat + (frame_height_deg / 2)
        frame_south = center_lat - (frame_height_deg / 2)
        frame_east = center_lon + (frame_width_deg / 2)
        frame_west = center_lon - (frame_width_deg / 2)
        
        # Create rectangle polygon (closed ring)
        points = [
            QgsPointXY(frame_west, frame_south),   # SW
            QgsPointXY(frame_east, frame_south),   # SE
            QgsPointXY(frame_east, frame_north),   # NE
            QgsPointXY(frame_west, frame_north),   # NW
            QgsPointXY(frame_west, frame_south),   # Close polygon
        ]
        
        # Create geometry from polyline and polygonize
        geom = QgsGeometry.fromPolylineXY(points)
        
        # Convert to polygon
        if geom.isMultipart():
            polygons = geom.asMultiPolygon()
            if polygons:
                return QgsGeometry.fromPolygonXY(polygons[0])
        else:
            return QgsGeometry.fromPolygonXY([points])
    
    @staticmethod
    def get_frame_bbox(frame_geometry):
        """
        Extract bbox (south, west, north, east) from frame geometry.
        
        Args:
            frame_geometry: QgsGeometry polygon
        
        Returns:
            Tuple: (south, west, north, east) in degrees
        """
        bbox = frame_geometry.boundingBox()
        return (bbox.yMinimum(), bbox.xMinimum(), bbox.yMaximum(), bbox.xMaximum())
    
    @staticmethod
    def get_frame_dimensions_degrees(bbox, center_lat, orientation="portrait"):
        """
        Get frame dimensions in degrees for a given latitude.
        
        Args:
            bbox: Tuple of (south, west, north, east)
            center_lat: Center latitude in degrees
            orientation: "portrait" or "landscape"
        
        Returns:
            Dict with width_deg, height_deg, width_inches, height_inches
        """
        frame_width_inches = 14 if orientation.lower() == "landscape" else 11
        frame_height_inches = 11 if orientation.lower() == "landscape" else 14
        
        frame_width_m = FrameBuilder.inches_to_meters(frame_width_inches)
        frame_height_m = FrameBuilder.inches_to_meters(frame_height_inches)
        
        frame_height_deg = frame_height_m / 111000
        frame_width_deg = frame_width_m / FrameBuilder.meters_per_degree_at_lat(center_lat)
        
        return {
            'width_deg': frame_width_deg,
            'height_deg': frame_height_deg,
            'width_inches': frame_width_inches,
            'height_inches': frame_height_inches,
        }
