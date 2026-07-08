"""Repository layer for bait station management queries."""

from PF_LU_APP.db import get_cursor


def fetch_bait_station_details(station_code):
    """Get full bait station details with status and storage area."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT b.*, es.equipment_status_name, sa.storage_area_id, sa.storage_area_name
        FROM bait_stations b
        LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
        LEFT JOIN storage_area sa ON b.storage_area_id = sa.storage_area_id
        WHERE b.bait_station_code = %s
    """, (station_code,))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_bait_station_details_simple(station_code, group_id):
    """Get bait station details scoped to a group."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT b.*, es.equipment_status_name
        FROM bait_stations b
        LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
        JOIN `lines` l ON b.line_id = l.line_id
        WHERE b.bait_station_code = %s AND l.group_id = %s
    """, (station_code, group_id))
    row = cursor.fetchone()
    cursor.close()
    return row


def check_bait_station_code_exists(station_code):
    """Check if a bait station code already exists."""
    cursor = get_cursor()
    cursor.execute("SELECT bait_station_code FROM bait_stations WHERE bait_station_code = %s", (station_code,))
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def insert_bait_station(station_code, station_type_id, line_id, latitude, longitude,
                        storage_area_id=None, equipment_status_id=None, status='active'):
    """Create a new bait station."""
    cursor = get_cursor()
    cursor.execute(
        """INSERT INTO bait_stations
           (bait_station_code, bait_station_type_id, line_id, latitude, longitude,
            storage_area_id, equipment_status_id, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (station_code, station_type_id, line_id, latitude, longitude,
         storage_area_id, equipment_status_id, status),
    )
    cursor.close()


def update_bait_station(station_code, station_type_id, line_id, latitude, longitude,
                        equipment_status_id, status, storage_area_id=None):
    """Update a bait station record."""
    cursor = get_cursor()
    cursor.execute(
        """UPDATE bait_stations
           SET bait_station_type_id = %s, line_id = %s, storage_area_id = %s,
               latitude = %s, longitude = %s, equipment_status_id = %s, status = %s
           WHERE bait_station_code = %s""",
        (station_type_id, line_id, storage_area_id, latitude, longitude,
         equipment_status_id, status, station_code),
    )
    cursor.close()


def retire_bait_station(station_code, retired_status_id):
    """Set a bait station to inactive and retired."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE bait_stations SET status = 'inactive', equipment_status_id = %s WHERE bait_station_code = %s",
        (retired_status_id, station_code),
    )
    cursor.close()


def reactivate_bait_station(station_code):
    """Set a bait station back to active."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE bait_stations SET status = 'active' WHERE bait_station_code = %s",
        (station_code,),
    )
    cursor.close()


def fetch_retired_bait_stations(group_id=None):
    """Fetch retired bait stations."""
    cursor = get_cursor()
    query = """
        SELECT b.bait_station_code, bt.bait_station_type_name, l.line_name, l.group_id,
               b.latitude, b.longitude, b.status
        FROM bait_stations b
        JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
        JOIN `lines` l ON b.line_id = l.line_id
        WHERE b.status = 'inactive'
    """
    params = []
    if group_id:
        query += " AND l.group_id = %s"
        params.append(group_id)
    query += " ORDER BY l.line_name, b.bait_station_code"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_bait_station_types():
    """Get all bait station types."""
    cursor = get_cursor()
    cursor.execute("SELECT * FROM bait_station_type ORDER BY bait_station_type_name")
    rows = cursor.fetchall()
    cursor.close()
    return rows


def ensure_bait_station_type(type_name):
    """Get or create a bait station type, returning its ID."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT bait_station_type_id FROM bait_station_type WHERE bait_station_type_name = %s",
        (type_name,),
    )
    row = cursor.fetchone()
    if row:
        cursor.close()
        return row['bait_station_type_id']
    cursor.execute(
        "INSERT INTO bait_station_type (bait_station_type_name) VALUES (%s)",
        (type_name,),
    )
    result = cursor.lastrowid
    cursor.close()
    return result


def fetch_bait_station_details_scoped(cursor, bait_station_code, group_id, is_super_admin=False):
    """Fetch bait station details scoped to a group, or all if is_super_admin is True."""
    if is_super_admin:
        cursor.execute("""
            SELECT b.*, es.equipment_status_name, sa.storage_area_id, sa.storage_area_name
            FROM bait_stations b
            LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
            LEFT JOIN `lines` l ON b.line_id = l.line_id
            LEFT JOIN storage_area sa ON b.storage_area_id = sa.storage_area_id
            WHERE b.bait_station_code = %s
        """, (bait_station_code,))
    else:
        cursor.execute("""
            SELECT b.*, es.equipment_status_name, sa.storage_area_id, sa.storage_area_name
            FROM bait_stations b
            LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
            LEFT JOIN `lines` l ON b.line_id = l.line_id
            LEFT JOIN storage_area sa ON b.storage_area_id = sa.storage_area_id
            WHERE b.bait_station_code = %s AND ((l.group_id = %s) OR (sa.group_id = %s))
        """, (bait_station_code, group_id, group_id))
    return cursor.fetchone()


def update_bait_station_full(cursor, bait_station_code, bait_station_type_id, line_id, storage_area_id, latitude, longitude, equipment_status_id, status):
    """Perform full update for a bait station."""
    cursor.execute("""
        UPDATE bait_stations
        SET bait_station_type_id = %s, line_id = %s, storage_area_id = %s,
            latitude = %s, longitude = %s, equipment_status_id = %s, status = %s
        WHERE bait_station_code = %s
    """, (bait_station_type_id, line_id, storage_area_id, latitude, longitude, equipment_status_id, status, bait_station_code))
