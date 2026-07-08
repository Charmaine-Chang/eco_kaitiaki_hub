"""Repository layer for trap management queries."""

from PF_LU_APP.db import get_cursor, get_db


# ── Trap Queries ──────────────────────────────────────────────────

def fetch_trap_details(trap_code):
    """Get full trap details with status and storage area."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT t.*, es.equipment_status_name, sa.storage_area_id, sa.storage_area_name
        FROM traps t
        LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
        LEFT JOIN storage_area sa ON t.storage_area_id = sa.storage_area_id
        WHERE t.trap_code = %s
    """, (trap_code,))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_trap_details_simple(trap_code, group_id):
    """Get trap details scoped to a group."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT t.*, es.equipment_status_name
        FROM traps t
        LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
        JOIN `lines` l ON t.line_id = l.line_id
        WHERE t.trap_code = %s AND l.group_id = %s
    """, (trap_code, group_id))
    row = cursor.fetchone()
    cursor.close()
    return row


def check_trap_code_exists(trap_code):
    """Check if a trap code already exists."""
    cursor = get_cursor()
    cursor.execute("SELECT trap_code FROM traps WHERE trap_code = %s", (trap_code,))
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def insert_trap(trap_code, trap_type_id, line_id, latitude, longitude,
                storage_area_id=None, equipment_status_id=None, status='active'):
    """Create a new trap."""
    cursor = get_cursor()
    cursor.execute(
        """INSERT INTO traps (trap_code, trap_type_id, line_id, latitude, longitude,
                              storage_area_id, equipment_status_id, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (trap_code, trap_type_id, line_id, latitude, longitude,
         storage_area_id, equipment_status_id, status),
    )
    cursor.close()


def update_trap(trap_code, trap_type_id, line_id, latitude, longitude,
                equipment_status_id, status, storage_area_id=None):
    """Update a trap record."""
    cursor = get_cursor()
    cursor.execute(
        """UPDATE traps
           SET trap_type_id = %s, line_id = %s, storage_area_id = %s,
               latitude = %s, longitude = %s, equipment_status_id = %s, status = %s
           WHERE trap_code = %s""",
        (trap_type_id, line_id, storage_area_id, latitude, longitude,
         equipment_status_id, status, trap_code),
    )
    cursor.close()


def retire_trap(trap_code, retired_status_id):
    """Set a trap to inactive and retired."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE traps SET status = 'inactive', equipment_status_id = %s WHERE trap_code = %s",
        (retired_status_id, trap_code),
    )
    cursor.close()


def reactivate_trap(trap_code):
    """Set a trap back to active."""
    cursor = get_cursor()
    cursor.execute("UPDATE traps SET status = 'active' WHERE trap_code = %s", (trap_code,))
    cursor.close()


def fetch_retired_traps(group_id=None):
    """Fetch retired traps."""
    cursor = get_cursor()
    query = """
        SELECT t.trap_code, tt.trap_type_name, l.line_name, l.group_id,
               t.latitude, t.longitude, t.status
        FROM traps t
        JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
        JOIN `lines` l ON t.line_id = l.line_id
        WHERE t.status = 'inactive'
    """
    params = []
    if group_id:
        query += " AND l.group_id = %s"
        params.append(group_id)
    query += " ORDER BY l.line_name, t.trap_code"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_trap_types():
    """Get all trap types."""
    cursor = get_cursor()
    cursor.execute("SELECT * FROM trap_type ORDER BY trap_type_name")
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_trap_details_scoped(cursor, trap_code, group_id, is_super_admin=False):
    """Fetch trap details scoped to a group, or all if is_super_admin is True."""
    if is_super_admin:
        cursor.execute("""
            SELECT t.*, es.equipment_status_name, sa.storage_area_id, sa.storage_area_name
            FROM traps t
            LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
            LEFT JOIN `lines` l ON t.line_id = l.line_id
            LEFT JOIN storage_area sa ON t.storage_area_id = sa.storage_area_id
            WHERE t.trap_code = %s
        """, (trap_code,))
    else:
        cursor.execute("""
            SELECT t.*, es.equipment_status_name, sa.storage_area_id, sa.storage_area_name
            FROM traps t
            LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
            LEFT JOIN `lines` l ON t.line_id = l.line_id
            LEFT JOIN storage_area sa ON t.storage_area_id = sa.storage_area_id
            WHERE t.trap_code = %s AND ((l.group_id = %s) OR (sa.group_id = %s))
        """, (trap_code, group_id, group_id))
    return cursor.fetchone()


def update_trap_full(cursor, trap_code, trap_type_id, line_id, storage_area_id, latitude, longitude, equipment_status_id, status):
    """Perform full update for a trap."""
    cursor.execute("""
        UPDATE traps
        SET trap_type_id = %s, line_id = %s, storage_area_id = %s,
            latitude = %s, longitude = %s, equipment_status_id = %s, status = %s
        WHERE trap_code = %s
    """, (trap_type_id, line_id, storage_area_id, latitude, longitude, equipment_status_id, status, trap_code))


# ── Inventory View ────────────────────────────────────────────────

def fetch_inventory_for_group(group_id):
    """Fetch all equipment (traps + bait stations) for a group."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT t.trap_code as code, tt.trap_type_name as type, l.line_name, l.line_id,
               t.latitude, t.longitude, 'trap' as equip_type, t.status, es.equipment_status_name
        FROM traps t
        JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
        JOIN `lines` l ON t.line_id = l.line_id
        LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
        WHERE l.group_id = %s
        ORDER BY l.line_name, t.trap_code
    """, (group_id,))
    traps = cursor.fetchall()

    cursor.execute("""
        SELECT b.bait_station_code as code, bt.bait_station_type_name as type, l.line_name, l.line_id,
               b.latitude, b.longitude, 'bait_station' as equip_type, b.status, es.equipment_status_name
        FROM bait_stations b
        JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
        JOIN `lines` l ON b.line_id = l.line_id
        LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
        WHERE l.group_id = %s
        ORDER BY l.line_name, b.bait_station_code
    """, (group_id,))
    stations = cursor.fetchall()
    cursor.close()

    return list(traps) + list(stations)


def update_equipment_status(table, code, status, equipment_status_id,
                            latitude=None, longitude=None):
    """Update status and location for a trap or bait station."""
    cursor = get_cursor()
    if table == 'traps':
        cursor.execute(
            "UPDATE traps SET status = %s, equipment_status_id = %s, latitude = %s, longitude = %s WHERE trap_code = %s",
            (status, equipment_status_id, latitude, longitude, code),
        )
    else:
        cursor.execute(
            "UPDATE bait_stations SET status = %s, equipment_status_id = %s, latitude = %s, longitude = %s WHERE bait_station_code = %s",
            (status, equipment_status_id, latitude, longitude, code),
        )
    cursor.close()


def fetch_equipment_for_status_update(code, group_id):
    """Fetch equipment details for status update validation."""
    cursor = get_cursor()
    # Try trap first
    cursor.execute("""
        SELECT t.trap_code as code, t.status, es.equipment_status_name, 'traps' as table_name
        FROM traps t
        LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
        JOIN `lines` l ON t.line_id = l.line_id
        WHERE t.trap_code = %s AND l.group_id = %s
    """, (code, group_id))
    row = cursor.fetchone()
    if row:
        cursor.close()
        return row
    # Try bait station
    cursor.execute("""
        SELECT b.bait_station_code as code, b.status, es.equipment_status_name, 'bait_stations' as table_name
        FROM bait_stations b
        LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
        JOIN `lines` l ON b.line_id = l.line_id
        WHERE b.bait_station_code = %s AND l.group_id = %s
    """, (code, group_id))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_storage_areas(group_id):
    """Get storage areas for a group."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT storage_area_id, storage_area_name FROM storage_area WHERE group_id = %s ORDER BY storage_area_name",
        (group_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_storage_areas_scoped(cursor, group_id, is_super_admin=False):
    """Get storage areas scoped by group_id or all if is_super_admin."""
    if is_super_admin:
        cursor.execute("SELECT storage_area_id, storage_area_name FROM storage_area ORDER BY storage_area_name ASC")
    else:
        cursor.execute("SELECT storage_area_id, storage_area_name FROM storage_area WHERE group_id = %s ORDER BY storage_area_name ASC", (group_id,))
    return cursor.fetchall()
