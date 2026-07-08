import logging
import re
import json

def is_valid_email(email):
    """
    Validates email format using a robust regex.
    Criteria:
    - Standard user@domain format
    - Allowed characters in user part: letters, numbers, dots, underscores, dashes, pluses
    - Domain must have at least one dot and a valid TLD (2+ chars)
    """
    if not email:
        return False
    
    # Robust email regex
    # ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    return bool(re.match(email_regex, email.strip()))

def point_in_polygon(x, y, poly_coords):
    """
    Ray casting point-in-polygon algorithm.
    poly_coords: nested coordinate list representing the polygon (from GeoJSON).
    x: longitude, y: latitude.
    """
    if not poly_coords or len(poly_coords) < 1:
        return False
    ring = poly_coords[0]
    n = len(ring)
    if n < 3:
        return False
    inside = False
    p1x, p1y = ring[0]
    for i in range(1, n + 1):
        p2x, p2y = ring[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def is_point_inside_geojson(lat, lng, geojson_str):
    """
    Checks if a point (lat, lng) is inside the polygon/multipolygon GeoJSON string.
    """
    if not geojson_str:
        return True
    try:
        geo = json.loads(geojson_str)
        geom_type = geo.get('type')
        coords = geo.get('coordinates')
        if geom_type == 'Polygon':
            return point_in_polygon(lng, lat, coords)
        elif geom_type == 'MultiPolygon':
            for poly in coords:
                if point_in_polygon(lng, lat, poly):
                    return True
            return False
    except Exception as e:
        logging.exception(f"Error checking point in GeoJSON: {e}")
    return True

def validate_location_within_boundary(cursor, group_id, lat, lng):
    """
    Queries group's boundary_geojson and checks if the given (lat, lng) is inside it.
    Returns True if inside or if no boundary is defined, False otherwise.
    """
    if not group_id:
        return True
    try:
        cursor.execute("SELECT boundary_geojson FROM `groups` WHERE group_id = %s", (group_id,))
        row = cursor.fetchone()
    except Exception as e:
        # Column might not exist; consider no boundary defined
        logging.exception(f"Warning: could not read group boundary_geojson: {e}")
        return True
    if not row or not row.get('boundary_geojson'):
        return True
    return is_point_inside_geojson(lat, lng, row.get('boundary_geojson'))
