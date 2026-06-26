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
        # Servers ordered by what works - mail.ru first, then overpass-api.de
        self.overpass_servers = [
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass-api.de/api/interpreter",
            "https://overpass.osm.ch/api/interpreter",
        ]
        self.overpass_url = self.overpass_servers[0]
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"

    def log(self, message, level=Qgis.Info):
        """Log message to QGIS"""
        QgsMessageLog.logMessage(message, 'OSM Bulk Downloader', level)

    def search_place(self, place_name: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Search for a place using Nominatim and return its bounding box.
        Returns: (south, west, north, east) or None
        Use search_place_full() to also get the boundary polygon.
        """
        result = self.search_place_full(place_name)
        if result:
            return result['bbox']
        return None

    def search_place_full(self, place_name: str) -> Optional[Dict]:
        """
        Search for a place using Nominatim.

        Returns a dict with:
          'bbox'     : (south, west, north, east)
          'display'  : display name string
          'geojson'  : GeoJSON geometry dict of the place boundary (or None)

        Returns None if the place is not found.
        """
        self.log(f"Searching for '{place_name}'...")

        params = {
            'q': place_name,
            'format': 'json',
            'limit': 1,
            'polygon_geojson': 1,   # ask Nominatim to return the boundary shape
        }
        headers = {'User-Agent': 'QGIS OSM Bulk Downloader Plugin/2.0'}

        try:
            response = requests.get(
                self.nominatim_url,
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            results = response.json()

            if not results:
                self.log(f"No results found for '{place_name}'", Qgis.Warning)
                return None

            result   = results[0]
            bbox_raw = result.get('boundingbox')
            geojson  = result.get('geojson')          # boundary polygon / multipolygon

            if not bbox_raw:
                self.log("No bounding box found for this location", Qgis.Warning)
                return None

            # Nominatim returns [south, north, west, east]
            south, north, west, east = map(float, bbox_raw)
            self.log(f"Found: {result['display_name']}")

            return {
                'bbox'   : (south, west, north, east),
                'display': result['display_name'],
                'geojson': geojson,   # may be None for simple node results
            }

        except Exception as e:
            self.log(f"Error searching for place: {e}", Qgis.Critical)
            return None

    def query_overpass(self, query: str) -> Optional[Dict]:
        """Execute an Overpass API query with automatic server fallback."""
        headers = {
            'User-Agent': 'QGIS OSM Bulk Downloader Plugin/2.0',
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        for server_url in self.overpass_servers:
            try:
                self.log(f"Querying: {server_url}")
                response = requests.post(
                    server_url,
                    data={'data': query},
                    headers=headers,
                    timeout=180
                )
                response.raise_for_status()
                data = response.json()
                self.log(f"✓ Got response from {server_url}")
                return data
            except requests.exceptions.Timeout:
                self.log(f"Timeout on {server_url} — trying next...", Qgis.Warning)
                continue
            except requests.exceptions.ConnectionError as e:
                self.log(f"Connection error on {server_url}: {e} — trying next...", Qgis.Warning)
                continue
            except Exception as e:
                self.log(f"Server {server_url} failed: {e} — trying next...", Qgis.Warning)
                continue

        self.log("All Overpass servers failed.", Qgis.Critical)
        return None

    def build_query(self, bbox: Tuple[float, float, float, float],
                    osm_filters: List[str]) -> str:
        """Build an Overpass QL query"""
        south, west, north, east = bbox
        bbox_str = f"{south},{west},{north},{east}"

        query_parts = []
        for filter_str in osm_filters:
            query_parts.append(f"  {filter_str}({bbox_str});")

        query = f"""[out:json][timeout:180];
(
{chr(10).join(query_parts)}
);
out geom;
"""
        return query

    def download_feature(self, bbox: Tuple[float, float, float, float],
                         feature_config: Dict) -> Optional[Dict]:
        """Download a specific feature type and return GeoJSON"""
        feature_name = feature_config['name']
        self.log(f"Downloading {feature_name}...")

        query = self.build_query(bbox, feature_config['filters'])
        data  = self.query_overpass(query)

        if data is None:
            self.log(f"Failed to download {feature_name}", Qgis.Warning)
            return None

        elements = data.get('elements', [])
        self.log(f"Raw elements received: {len(elements)} for {feature_name}")

        if not elements:
            self.log(f"No elements found for {feature_name}", Qgis.Warning)
            return {'type': 'FeatureCollection', 'features': []}

        is_water_feature = 'water' in feature_name
        is_point_feature = feature_name in ('cities', 'mountain_peaks', 'places')

        geojson = self.osm_to_geojson(
            data,
            include_points=(is_water_feature or is_point_feature),
            feature_name=feature_name
        )

        if 'style' in feature_config:
            for feature in geojson['features']:
                feature['properties']['_style'] = feature_config['style']

        feature_count = len(geojson['features'])
        self.log(f"✓ Converted {feature_count} features for {feature_name}")

        return geojson

    def osm_to_geojson(self, osm_data: Dict, include_points: bool = False,
                       feature_name: str = '') -> Dict:
        """Convert OSM JSON to GeoJSON"""
        features = []

        nodes = {}
        for element in osm_data.get('elements', []):
            if element['type'] == 'node':
                nodes[element['id']] = element

        for element in osm_data.get('elements', []):
            feature = self.element_to_feature(
                element, nodes, include_points, feature_name
            )
            if feature:
                features.append(feature)

        return {
            'type': 'FeatureCollection',
            'features': features
        }

    def element_to_feature(self, element: Dict, nodes: Dict,
                            include_points: bool = False,
                            feature_name: str = '') -> Optional[Dict]:
        """Convert an OSM element to a GeoJSON feature"""

        if element['type'] == 'node':
            if not include_points:
                return None
            if 'lat' not in element or 'lon' not in element:
                return None
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

            is_closed = (
                len(coords) > 2 and
                coords[0][0] == coords[-1][0] and
                coords[0][1] == coords[-1][1]
            )

            is_road = any(x in feature_name for x in
                          ['roads', 'trails', 'paths', 'railways',
                           'streams', 'rivers', 'coastlines'])

            if is_road:
                geometry = {'type': 'LineString', 'coordinates': coords}
            else:
                tags    = element.get('tags', {})
                is_area = (is_closed and (
                    tags.get('area') == 'yes' or
                    'building' in tags or
                    'landuse'  in tags or
                    'natural'  in tags or
                    'leisure'  in tags or
                    'amenity'  in tags or
                    'boundary' in tags
                ))
                if is_area:
                    geometry = {'type': 'Polygon', 'coordinates': [coords]}
                else:
                    geometry = {'type': 'LineString', 'coordinates': coords}

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

            outer_segments = []
            inner_segments = []

            for member in element['members']:
                if member['type'] != 'way' or 'geometry' not in member:
                    continue
                coords = [[pt['lon'], pt['lat']] for pt in member['geometry']]
                if not coords:
                    continue
                if member['role'] == 'outer':
                    outer_segments.append(coords)
                elif member['role'] == 'inner':
                    inner_segments.append(coords)
                else:
                    outer_segments.append(coords)

            if not outer_segments:
                return None

            outer_rings = self._stitch_segments(outer_segments)
            inner_rings = self._stitch_segments(inner_segments)

            if not outer_rings:
                return None

            if len(outer_rings) == 1 and len(inner_rings) == 0:
                return {
                    'type': 'Feature',
                    'geometry': {'type': 'Polygon', 'coordinates': [outer_rings[0]]},
                    'properties': tags
                }

            if len(outer_rings) == 1:
                return {
                    'type': 'Feature',
                    'geometry': {'type': 'Polygon', 'coordinates': [outer_rings[0]] + inner_rings},
                    'properties': tags
                }

            polygons = [[outer] for outer in outer_rings]
            for inner in inner_rings:
                placed = False
                for poly in polygons:
                    if self._point_in_ring(inner[0], poly[0]):
                        poly.append(inner)
                        placed = True
                        break
                if not placed:
                    polygons[0].append(inner)

            return {
                'type': 'Feature',
                'geometry': {'type': 'MultiPolygon', 'coordinates': polygons},
                'properties': tags
            }

        return None

    # ------------------------------------------------------------------
    # Ring-stitching helpers
    # ------------------------------------------------------------------

    def _coords_match(self, a, b, tol=1e-8) -> bool:
        return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol

    def _stitch_segments(self, segments: List[List]) -> List[List]:
        """
        Assemble a list of way-segment coordinate lists into one or more
        closed rings by chaining them end-to-end.
        """
        if not segments:
            return []

        remaining = [list(seg) for seg in segments]
        rings = []

        while remaining:
            chain   = remaining.pop(0)
            changed = True
            while changed:
                changed = False
                if len(chain) > 2 and self._coords_match(chain[0], chain[-1]):
                    break
                for i, seg in enumerate(remaining):
                    if self._coords_match(chain[-1], seg[0]):
                        chain.extend(seg[1:]); remaining.pop(i); changed = True; break
                    if self._coords_match(chain[-1], seg[-1]):
                        chain.extend(list(reversed(seg))[1:]); remaining.pop(i); changed = True; break
                    if self._coords_match(chain[0], seg[0]):
                        chain = list(reversed(seg)) + chain[1:]; remaining.pop(i); changed = True; break
                    if self._coords_match(chain[0], seg[-1]):
                        chain = seg + chain[1:]; remaining.pop(i); changed = True; break

            if not self._coords_match(chain[0], chain[-1]):
                chain.append(chain[0])
            rings.append(chain)

        return rings

    def _point_in_ring(self, point, ring) -> bool:
        """Ray-casting point-in-polygon test."""
        px, py  = point[0], point[1]
        inside  = False
        n       = len(ring)
        j       = n - 1
        for i in range(n):
            xi, yi = ring[i][0], ring[i][1]
            xj, yj = ring[j][0], ring[j][1]
            if ((yi > py) != (yj > py)) and (
                px < (xj - xi) * (py - yi) / (yj - yi + 1e-15) + xi
            ):
                inside = not inside
            j = i
        return inside

    # ------------------------------------------------------------------
    # Centroid / label helpers
    # ------------------------------------------------------------------

    def calculate_centroid(self, geometry: Dict) -> Optional[List[float]]:
        geom_type = geometry.get('type')
        coords    = geometry.get('coordinates')
        if not coords:
            return None
        if geom_type == 'Point':
            return coords
        elif geom_type == 'LineString':
            return coords[len(coords) // 2]
        elif geom_type == 'Polygon':
            ring  = coords[0]
            return [sum(p[0] for p in ring) / len(ring),
                    sum(p[1] for p in ring) / len(ring)]
        elif geom_type == 'MultiPolygon':
            if coords and coords[0] and coords[0][0]:
                ring = coords[0][0]
                return [sum(p[0] for p in ring) / len(ring),
                        sum(p[1] for p in ring) / len(ring)]
        return None

    def create_labels_geojson(self, geojson: Dict) -> Dict:
        label_features = []
        for feature in geojson.get('features', []):
            if not feature.get('properties', {}).get('name'):
                continue
            geometry  = feature.get('geometry', {})
            geom_type = geometry.get('type')
            coords    = geometry.get('coordinates')
            if not coords:
                continue
            label_pos = None
            if geom_type == 'Point':
                label_pos = coords
            elif geom_type == 'LineString':
                label_pos = coords[len(coords) // 2]
            elif geom_type == 'Polygon':
                ring      = coords[0]
                label_pos = [sum(p[0] for p in ring) / len(ring),
                             sum(p[1] for p in ring) / len(ring)]
            elif geom_type == 'MultiPolygon':
                if coords and coords[0] and coords[0][0]:
                    ring      = coords[0][0]
                    label_pos = [sum(p[0] for p in ring) / len(ring),
                                 sum(p[1] for p in ring) / len(ring)]
            if label_pos:
                label_features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'Point', 'coordinates': label_pos},
                    'properties': feature.get('properties', {})
                })
        return {'type': 'FeatureCollection', 'features': label_features}
