"""Repository layer for trap validations when recording/updating catches."""

from PF_LU_APP.db import get_cursor


def fetch_trap_status(trap_code):
    """Check if a trap is active and not retired."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT t.status, es.equipment_status_name
        FROM traps t
        LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
        WHERE t.trap_code = %s
    """, (trap_code,))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_trap_status_by_catch(catches_id):
    """Check if the trap associated with a catch is active and not retired."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT t.status, es.equipment_status_name
        FROM traps t
        LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
        WHERE t.trap_code = (SELECT trap_code FROM trap_catches WHERE catches_id = %s)
    """, (catches_id,))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_trap_line(trap_code):
    """Get the line_id for a trap."""
    cursor = get_cursor()
    cursor.execute("SELECT line_id FROM traps WHERE trap_code = %s", (trap_code,))
    row = cursor.fetchone()
    cursor.close()
    return row
