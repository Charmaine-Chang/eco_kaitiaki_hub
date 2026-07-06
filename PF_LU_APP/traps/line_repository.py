"""Repository layer for line management queries."""

from PF_LU_APP.db import get_cursor


def fetch_lines_for_group(group_id):
    """Get active lines for a group."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT line_id, line_name FROM lines WHERE group_id = %s AND status = 'active' ORDER BY line_name",
        (group_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_all_active_lines():
    """Get all active lines (super admin view)."""
    cursor = get_cursor()
    cursor.execute("SELECT line_id, line_name FROM lines WHERE status = 'active' ORDER BY line_name ASC")
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_line_by_id(line_id):
    """Get a single line record."""
    cursor = get_cursor()
    cursor.execute("SELECT * FROM lines WHERE line_id = %s", (line_id,))
    row = cursor.fetchone()
    cursor.close()
    return row


def check_line_name_exists(line_name, group_id, exclude_line_id=None):
    """Check if a line name already exists in the group."""
    cursor = get_cursor()
    if exclude_line_id:
        cursor.execute(
            "SELECT line_id FROM lines WHERE line_name ILIKE %s AND line_id != %s AND group_id = %s",
            (line_name, exclude_line_id, group_id),
        )
    else:
        cursor.execute(
            "SELECT line_id FROM lines WHERE line_name ILIKE %s AND group_id = %s",
            (line_name, group_id),
        )
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def insert_line(line_name, line_type, status, group_id):
    """Create a new line."""
    cursor = get_cursor()
    cursor.execute(
        "INSERT INTO lines (line_name, line_type, status, group_id) VALUES (%s, %s, %s, %s)",
        (line_name, line_type, status, group_id),
    )
    cursor.close()


def update_line(line_id, line_name, line_type, status):
    """Update a line record."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE lines SET line_name = %s, line_type = %s, status = %s WHERE line_id = %s",
        (line_name, line_type, status, line_id),
    )
    cursor.close()


def deactivate_line(line_id):
    """Set a line to inactive."""
    cursor = get_cursor()
    cursor.execute("UPDATE lines SET status = 'inactive' WHERE line_id = %s", (line_id,))
    cursor.close()


def reactivate_line(line_id):
    """Set a line back to active."""
    cursor = get_cursor()
    cursor.execute("UPDATE lines SET status = 'active' WHERE line_id = %s", (line_id,))
    cursor.close()


def fetch_line_group_id(line_id):
    """Get the group_id for a line."""
    cursor = get_cursor()
    cursor.execute("SELECT group_id FROM lines WHERE line_id = %s", (line_id,))
    row = cursor.fetchone()
    cursor.close()
    return row['group_id'] if row else None


def fetch_lines_with_equipment(session):
    """Fetch all lines with equipment counts for the admin view."""
    cursor = get_cursor()
    current_group_id = session.get('current_group_id')
    is_super_admin = session.get('is_super_admin')

    if is_super_admin:
        cursor.execute("""
            SELECT l.*, g.group_name,
                (SELECT COUNT(*) FROM traps t WHERE t.line_id = l.line_id) as trap_count,
                (SELECT COUNT(*) FROM bait_stations b WHERE b.line_id = l.line_id) as bait_station_count,
                (SELECT COUNT(*) FROM operator_lines ol WHERE ol.line_id = l.line_id) as assigned_count,
                COALESCE(
                    (SELECT STRING_AGG(CONCAT(u.first_name, ' ', u.last_name), ', ')
                     FROM operator_lines ol JOIN users u ON ol.user_id = u.user_id
                      WHERE ol.line_id = l.line_id),
                    'Unassigned'
                ) as operator_names
            FROM lines l JOIN groups g ON l.group_id = g.group_id
            WHERE l.status = 'active'
            ORDER BY g.group_name, l.line_name
        """)
    else:
        cursor.execute("""
            SELECT l.*, g.group_name,
                (SELECT COUNT(*) FROM traps t WHERE t.line_id = l.line_id) as trap_count,
                (SELECT COUNT(*) FROM bait_stations b WHERE b.line_id = l.line_id) as bait_station_count,
                (SELECT COUNT(*) FROM operator_lines ol WHERE ol.line_id = l.line_id) as assigned_count,
                COALESCE(
                    (SELECT STRING_AGG(CONCAT(u.first_name, ' ', u.last_name), ', ')
                     FROM operator_lines ol JOIN users u ON ol.user_id = u.user_id
                     WHERE ol.line_id = l.line_id),
                    'Unassigned'
                ) as operator_names
            FROM lines l JOIN groups g ON l.group_id = g.group_id
            WHERE l.group_id = %s AND l.status = 'active'
            ORDER BY l.line_name
        """, (current_group_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_lines_scoped(cursor, group_id, is_super_admin=False):
    """Get active lines scoped by group_id or all if is_super_admin."""
    if is_super_admin:
        cursor.execute("SELECT line_id, line_name FROM lines WHERE status = 'active' ORDER BY line_name ASC")
    else:
        cursor.execute("SELECT line_id, line_name FROM lines WHERE group_id = %s AND status = 'active' ORDER BY line_name ASC", (group_id,))
    return cursor.fetchall()
