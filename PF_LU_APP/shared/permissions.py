"""Shared permission and access-control helpers."""

from flask import session, redirect, url_for, flash
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER

def get_equipment_status_id(cursor, status_name):
    """Resolve an equipment_status_name to its ID, creating the row if it doesn't exist."""
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
