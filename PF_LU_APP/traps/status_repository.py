"""Repository layer for equipment status management queries."""

from PF_LU_APP.db import get_cursor


def get_equipment_status_id(cursor, status_name):
    """Resolve an equipment_status_name to its ID, creating the row if needed."""
    cursor.execute(
        "SELECT equipment_status_id FROM equipment_status WHERE LOWER(equipment_status_name) = LOWER(%s)",
        (status_name,),
    )
    row = cursor.fetchone()
    if row:
        return row['equipment_status_id']
    cursor.execute(
        "INSERT INTO equipment_status (equipment_status_name) VALUES (%s)",
        (status_name,),
    )
    return cursor.lastrowid


def fetch_equipment_statuses():
    """Get all equipment status names."""
    cursor = get_cursor()
    cursor.execute("SELECT equipment_status_name FROM equipment_status ORDER BY equipment_status_name")
    rows = cursor.fetchall()
    cursor.close()
    return rows


def deactivate_equipment_for_line(line_id, retired_status_id):
    """Deactivate all traps and bait stations on a line."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE traps SET status = 'inactive', equipment_status_id = %s WHERE line_id = %s",
        (retired_status_id, line_id),
    )
    cursor.execute(
        "UPDATE bait_stations SET status = 'inactive', equipment_status_id = %s WHERE line_id = %s",
        (retired_status_id, line_id),
    )
    cursor.close()
