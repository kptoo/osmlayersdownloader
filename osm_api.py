"""
OSM API Handler - Handles communication with OpenStreetMap APIs
"""

import requests
import json
import time
from typing import Dict, List, Tuple, Optional
from qgis.core import QgsMessageLog, Qgis


class OSMAPIHandler:
    def __init__(self):
        self.overpass_url = "https://overpass-api.de/api/interpreter"
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"
        
    def log(self, message, level=Qgis.Info):
        """Log message to QGIS"""
        QgsMessageLog.logMessage(message, 'OSM Bulk Downloader', level)
        
    def search_place(self, place_name: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Search for a place using Nominatim and get its bounding box
        Returns: (south, west, north, east) or None
        """
        self.log(f"Searching for '{place_name}'...")
        
        params = {
            'q': place_name,
            'format': 'json',
            'limit': 1,
            'polygon_geojson': 1
        }
        
        headers = {
            'User-Agent': 'QGIS OSM Bulk Downloader Plugin/1.0'
        }
        
        try:
            response = requests.get(self.nominatim_url, params=params, headers=headers)
            response.raise_for_status()
            results = response.json()
            
            if not results:
                self.log(f"No results found for '{place_name}'", Qgis.Warning)
                return None
            
            result = results[0]
            bbox = result.get('boundingbox')
            
            if bbox:
                # Nominatim returns [south, north, west, east]
                south, north, west, east = map(float, bbox)
                self.log(f"Found: {result['display_name']}")
                return (south, west, north, east)
            else:
                self.log("No bounding box found for this location", Qgis.Warning)
                return None
                
        except Exception as e:
            self.log(f"Error searching for place: {e}", Qgis.Critical)
            return None
    
    def query_overpass(self, query: str) -> Optional[Dict]:
        """Execute an Overpass API query"""
        try:
            response = requests.post(
                self.overpass_url,
                data={'data': query},
                timeout=180
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.log(f"Error querying Overpass API: {e}", Qgis.Critical)
            return None
    
    def build_query(self, bbox: Tuple[float, float, float, float], 
                   osm_filters: List[str]) -> str:
        """Build an Overpass QL query"""
        south, west, north, east = bbox
        bbox_str = f"{south},{west},{north},{east}"
        
        # Build the query parts
        query_parts = []
        for filter_str in osm_filters:
            query_parts.append(f"  {filter_str}({bbox_str});")
        
        query = f"""
[out:json][timeout:180];
(
{chr(10).join(query_parts)}
);
out geom;
>;
out skel qt;
"""
        return query
    
    def download_feature(self, bbox: Tuple[float, float, float, float],
                        feature_config: Dict) -> Optional[Dict]:
        """Download a specific feature type and return GeoJSON"""
        feature_name = feature_config['name']
        self.log(f"Downloading {feature_name}...")
        
        query = self.build_query(bbox, feature_config['filters'])
        
        # Query the API
        data = self.query_overpass(query)
        
        if data is None:
            self.log(f"Failed to download {feature_name}", Qgis.Warning)
            return None
        
        # Check if this is a water feature
        is_water_feature = feature_name == 'water_bodies_lakes'
        
        # Convert to GeoJSON
        geojson = self.osm_to_geojson(data, include_points=is_water_feature, 
                                     feature_name=feature_name)
        
        # Apply styling if configured
        if 'style' in feature_config:
            for feature in geojson['features']:
                feature['properties']['_style'] = feature_config['style']
        
        feature_count = len(geojson['features'])
        self.log(f"✓ Downloaded {feature_count} features for {feature_name}")
        
        return geojson
    
    def osm_to_geojson(self, osm_data: Dict, include_points: bool = False, 
                      feature_name: str = '') -> Dict:
        """Convert OSM JSON to GeoJSON"""
        features = []
        
        # Create a lookup for nodes
        nodes = {}
        for element in osm_data.get('elements', []):
            if element['type'] == 'node':
                nodes[element['id']] = element
        
        for element in osm_data.get('elements', []):
            feature = self.element_to_feature(element, nodes, include_points, feature_name)
            if feature:
                features.append(feature)
        
        return {
            'type': 'FeatureCollection',
            'features': features
        }
    
    def element_to_feature(self, element: Dict, nodes: Dict, include_points: bool = False, 
                          feature_name: str = '') -> Optional[Dict]:
        """Convert an OSM element to a GeoJSON feature"""
        if element['type'] == 'node':
            if not include_points:
                return None
                
            if 'lat' not in element or 'lon' not in element:
                return None
            
            # Only include nodes that have tags
            if not element.get('tags'):
                return None
            
            return {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [element['lon'], element['lat']]
                },
                'properties': element.get('tags', {})
            }
        
        elif element['type'] == 'way':
            if 'geometry' not in element:
                return None
            
            coords = [[pt['lon'], pt['lat']] for pt in element['geometry']]
            
            if not coords:
                return None
            
            # Check if it's a closed way
            is_closed = (len(coords) > 2 and 
                        coords[0][0] == coords[-1][0] and 
                        coords[0][1] == coords[-1][1])
            
            # Check if this is a road feature
            is_road = 'roads' in feature_name or 'trails' in feature_name
            
            if is_road:
                geometry = {
                    'type': 'LineString',
                    'coordinates': coords
                }
            else:
                tags = element.get('tags', {})
                is_area = (is_closed and (
                    tags.get('area') == 'yes' or
                    'building' in tags or
                    'landuse' in tags or
                    'natural' in tags or
                    'leisure' in tags or
                    'amenity' in tags
                ))
                
                geometry = {
                    'type': 'Polygon' if is_area else 'LineString',
                    'coordinates': [coords] if is_area else coords
                }
            
            return {
                'type': 'Feature',
                'geometry': geometry,
                'properties': element.get('tags', {})
            }
        
        elif element['type'] == 'relation':
            if 'members' not in element:
                return None
            
            tags = element.get('tags', {})
            if tags.get('type') not in ['multipolygon', 'boundary']:
                return None
            
            # Collect outer and inner ways
            outer_ways = []
            inner_ways = []
            
            for member in element['members']:
                if member['type'] != 'way' or 'geometry' not in member:
                    continue
                
                coords = [[pt['lon'], pt['lat']] for pt in member['geometry']]
                if not coords:
                    continue
                
                if member['role'] == 'outer':
                    outer_ways.append(coords)
                elif member['role'] == 'inner':
                    inner_ways.append(coords)
                else:
                    outer_ways.append(coords)
            
            if not outer_ways:
                return None
            
            # Simple case: single outer way
            if len(outer_ways) == 1 and len(inner_ways) == 0:
                coords = outer_ways[0]
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                
                return {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Polygon',
                        'coordinates': [coords]
                    },
                    'properties': tags
                }
            
            # Complex multipolygons with holes
            if len(outer_ways) == 1:
                coords = outer_ways[0]
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                
                all_coords = [coords]
                for inner in inner_ways:
                    if inner[0] != inner[-1]:
                        inner.append(inner[0])
                    all_coords.append(inner)
                
                return {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Polygon',
                        'coordinates': all_coords
                    },
                    'properties': tags
                }
            
            # Multiple outer ways - MultiPolygon
            polygons = []
            for outer in outer_ways:
                if outer[0] != outer[-1]:
                    outer.append(outer[0])
                polygons.append([outer])
            
            return {
                'type': 'Feature',
                'geometry': {
                    'type': 'MultiPolygon',
                    'coordinates': polygons
                },
                'properties': tags
            }
        
        return None
    
    def calculate_centroid(self, geometry: Dict) -> Optional[List[float]]:
        """Calculate centroid of a geometry"""
        geom_type = geometry.get('type')
        coords = geometry.get('coordinates')
        
        if not coords:
            return None
        
        if geom_type == 'Point':
            return coords
        elif geom_type == 'LineString':
            mid_idx = len(coords) // 2
            return coords[mid_idx]
        elif geom_type == 'Polygon':
            ring = coords[0]
            x_sum = sum(pt[0] for pt in ring)
            y_sum = sum(pt[1] for pt in ring)
            n = len(ring)
            return [x_sum / n, y_sum / n]
        elif geom_type == 'MultiPolygon':
            if coords and coords[0] and coords[0][0]:
                ring = coords[0][0]
                x_sum = sum(pt[0] for pt in ring)
                y_sum = sum(pt[1] for pt in ring)
                n = len(ring)
                return [x_sum / n, y_sum / n]
        
        return None
    
    def create_labels_geojson(self, geojson: Dict) -> Dict:
        """Create label points from features"""
        label_features = []
        
        for feature in geojson.get('features', []):
            # Only create labels for features with names
            if not feature.get('properties', {}).get('name'):
                continue
            
            geometry = feature.get('geometry', {})
            geom_type = geometry.get('type')
            coords = geometry.get('coordinates')
            
            if not coords:
                continue
            
            # Calculate label position based on geometry type
            label_pos = None
            
            if geom_type == 'Point':
                label_pos = coords
            elif geom_type == 'LineString':
                # Use midpoint for lines (roads)
                mid_idx = len(coords) // 2
                label_pos = coords[mid_idx]
            elif geom_type == 'Polygon':
                # Calculate centroid of outer ring
                ring = coords[0]
                x_sum = sum(pt[0] for pt in ring)
                y_sum = sum(pt[1] for pt in ring)
                n = len(ring)
                label_pos = [x_sum / n, y_sum / n]
            elif geom_type == 'MultiPolygon':
                # Use centroid of first polygon
                if coords and coords[0] and coords[0][0]:
                    ring = coords[0][0]
                    x_sum = sum(pt[0] for pt in ring)
                    y_sum = sum(pt[1] for pt in ring)
                    n = len(ring)
                    label_pos = [x_sum / n, y_sum / n]
            
            if label_pos:
                label_feature = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': label_pos
                    },
                    'properties': feature.get('properties', {})
                }
                label_features.append(label_feature)
        
        return {
            'type': 'FeatureCollection',
            'features': label_features
        }
