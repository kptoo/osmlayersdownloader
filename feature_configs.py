"""
Feature Configurations - Defines all available OSM features
"""


def get_all_features():
    """Get all available feature configurations"""
    return [
        {
            'id': 1,
            'name': 'bays',
            'display': 'Bays',
            'filters': [
                'way["natural"="bay"]',
                'relation["natural"="bay"]'
            ],
            'style': {'color': '#4682B4', 'weight': 1, 'fillColor': '#87CEEB', 'fillOpacity': 0.4},
            'create_labels': True  # Water body - keep labels
        },
        {
            'id': 2,
            'name': 'water_bodies',
            'display': 'Water Bodies & Lakes',
            'filters': [
                # Exclude river polygons - they're often badly mapped
                'way["natural"="water"]["water"!="river"]',
                'relation["natural"="water"]["water"!="river"]',
                # Untagged natural=water (usually lakes, not rivers)
                'way["natural"="water"][!"water"]',
                'relation["natural"="water"][!"water"]',
                # Specific water types (not rivers)
                'way["water"="lake"]',
                'relation["water"="lake"]',
                'way["water"="reservoir"]',
                'relation["water"="reservoir"]',
                'way["water"="pond"]',
                'relation["water"="pond"]',
                'way["water"="basin"]',
                'relation["water"="basin"]',
                'way["landuse"="reservoir"]',
                'relation["landuse"="reservoir"]'
            ],
            'style': {'color': '#4682B4', 'weight': 1, 'fillColor': '#87CEEB', 'fillOpacity': 0.6},
            'create_labels': True  # Water body - keep labels
        },
        {
            'id': 3,
            'name': 'rivers',
            'display': 'Rivers',
            'filters': [
                'way["waterway"="river"]',
                'relation["waterway"="river"]'
            ],
            'style': {'color': '#4682B4', 'weight': 2, 'opacity': 1.0},
            'create_labels': False  # No labels for rivers
        },
        {
            'id': 4,
            'name': 'roads_major',
            'display': 'Major Roads',
            'filters': [
                'way["highway"~"motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link"]'
            ],
            'style': {'color': '#FFD700', 'weight': 3, 'opacity': 1.0},
            'create_labels': False  # No labels for roads
        },
        {
            'id': 5,
            'name': 'roads_residential',
            'display': 'Residential Roads',
            'filters': [
                'way["highway"="residential"]',
                'way["highway"="living_street"]'
            ],
            'style': {'color': '#FF0000', 'weight': 1, 'opacity': 0.8},
            'create_labels': False  # No labels for roads
        },
        {
            'id': 6,
            'name': 'railways',
            'display': 'Railways',
            'filters': [
                'way["railway"~"rail|light_rail|subway|tram"]'
            ],
            'style': {'color': '#000000', 'weight': 2, 'opacity': 0.8, 'dashArray': '5,5'},
            'create_labels': False  # No labels for railways
        },
        {
            'id': 7,
            'name': 'protected_areas',
            'display': 'Protected areas',
            'filters': [
                'way["boundary"="protected_area"]',
                'relation["boundary"="protected_area"]',
                'way["leisure"="nature_reserve"]',
                'relation["leisure"="nature_reserve"]'
            ],
            'style': {'color': '#228B22', 'weight': 1, 'fillColor': '#90EE90', 'fillOpacity': 0.3},
            'create_labels': False  # No labels
        },
        {
            'id': 8,
            'name': 'cities',
            'display': 'Cities',
            'filters': [
                'node["place"~"city|town"]'
            ],
            'style': {'color': '#FF0000', 'weight': 1},
            'create_labels': False  # No labels for cities
        },
        {
            'id': 9,
            'name': 'coastlines',
            'display': 'Coastlines',
            'filters': [
                'way["natural"="coastline"]'
            ],
            'style': {'color': '#000080', 'weight': 2, 'opacity': 1.0},
            'create_labels': False
        },
        {
            'id': 10,
            'name': 'streams',
            'display': 'Streams',
            'filters': [
                'way["waterway"="stream"]',
                'way["waterway"="canal"]'
            ],
            'style': {'color': '#4682B4', 'weight': 1, 'opacity': 1.0},
            'create_labels': False  # No labels for streams
        },
        {
            'id': 11,
            'name': 'roads_local',
            'display': 'Local Roads',
            'filters': [
                'way["highway"~"unclassified|tertiary|tertiary_link"]'
            ],
            'style': {'color': '#FFF8DC', 'weight': 2, 'opacity': 0.9},
            'create_labels': False  # No labels for roads
        },
        {
            'id': 12,
            'name': 'paths_trails',
            'display': 'Paths/Trails',
            'filters': [
                'way["highway"~"path|footway|cycleway|bridleway|track"]'
            ],
            'style': {'color': '#CD853F', 'weight': 1, 'opacity': 0.7, 'dashArray': '2,2'},
            'create_labels': False
        },
        {
            'id': 13,
            'name': 'parks_reserves',
            'display': 'Parks/reserves',
            'filters': [
                'way["leisure"="park"]',
                'relation["leisure"="park"]',
                'way["landuse"="recreation_ground"]',
                'relation["landuse"="recreation_ground"]'
            ],
            'style': {'color': '#228B22', 'weight': 1, 'fillColor': '#90EE90', 'fillOpacity': 0.4},
            'create_labels': False  # No labels
        },
        {
            'id': 14,
            'name': 'mountain_peaks',
            'display': 'Mountain peaks',
            'filters': [
                'node["natural"="peak"]'
            ],
            'style': {'color': '#8B4513', 'weight': 1},
            'create_labels': False  # No labels
        },
        {
            'id': 15,
            'name': 'buildings',
            'display': 'Buildings',
            'filters': [
                'way["building"]',
                'relation["building"]'
            ],
            'style': {'color': '#696969', 'weight': 1, 'fillColor': '#D3D3D3', 'fillOpacity': 0.5},
            'create_labels': False
        },
        {
            'id': 16,
            'name': 'golf_courses',
            'display': 'Golf Courses',
            'filters': [
                'way["leisure"="golf_course"]',
                'relation["leisure"="golf_course"]'
            ],
            'style': {'color': '#90EE90', 'weight': 1, 'fillColor': '#228B22', 'fillOpacity': 0.3},
            'create_labels': False  # No labels
        },
        {
            'id': 17,
            'name': 'ski_resorts',
            'display': 'Ski Resorts',
            'filters': [
                'way["landuse"="winter_sports"]',
                'relation["landuse"="winter_sports"]',
                'way["leisure"="ski_resort"]',
                'relation["leisure"="ski_resort"]',
                'way["site"="piste"]',
                'relation["site"="piste"]'
            ],
            'style': {'color': '#0066CC', 'weight': 1, 'fillColor': '#ADD8E6', 'fillOpacity': 0.3},
            'create_labels': False  # No labels
        },
        {
            'id': 18,
            'name': 'ski_runs',
            'display': 'Ski Runs/Pistes',
            'filters': [
                'way["piste:type"="downhill"]',
                'way["piste:type"="nordic"]',
                'way["piste:type"="skitour"]'
            ],
            'style': {'color': '#0000FF', 'weight': 2, 'opacity': 0.8},
            'create_labels': False  # No labels
        },
        {
            'id': 19,
            'name': 'ski_lifts',
            'display': 'Ski Lifts',
            'filters': [
                'way["aerialway"~"cable_car|gondola|chair_lift|drag_lift|t-bar|j-bar|platter|rope_tow"]'
            ],
            'style': {'color': '#FF0000', 'weight': 2, 'opacity': 0.8, 'dashArray': '5,3'},
            'create_labels': False  # No labels
        },
        {
            'id': 20,
            'name': 'airports',
            'display': 'Airports',
            'filters': [
                'way["aeroway"="aerodrome"]',
                'relation["aeroway"="aerodrome"]',
                'node["aeroway"="aerodrome"]'
            ],
            'style': {'color': '#8B008B', 'weight': 1, 'fillColor': '#DDA0DD', 'fillOpacity': 0.3},
            'create_labels': False  # No labels
        },
        {
            'id': 21,
            'name': 'runways',
            'display': 'Airport Runways',
            'filters': [
                'way["aeroway"="runway"]'
            ],
            'style': {'color': '#696969', 'weight': 3, 'opacity': 1.0},
            'create_labels': False  # No labels
        }
    ]
