"""Repository layer for dashboard queries.

Consolidates SQL from admin/dashboard.py and operators/dashboard.py.
"""

from PF_LU_APP.db import get_cursor
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR


# ── User & Group Info ─────────────────────────────────────────────

def fetch_user_by_id(user_id):
    """Get user record."""
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_group_boundary(group_id):
    """Get group boundary geojson and coordinates."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT boundary_geojson, latitude, longitude FROM `groups` WHERE group_id = %s",
        (group_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_all_group_boundaries():
    """Get boundaries for all active groups (map view)."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT group_name, boundary_geojson, latitude, longitude
        FROM `groups`
        WHERE status = 'active' AND boundary_geojson IS NOT NULL
    """)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_group_info(group_id):
    """Get group name and visibility."""
    cursor = get_cursor()
    cursor.execute("SELECT group_name, visibility FROM `groups` WHERE group_id = %s", (group_id,))
    row = cursor.fetchone()
    cursor.close()
    return row


# ── Pending Approvals ────────────────────────────────────────────

def fetch_pending_groups():
    """Fetch all pending group applications."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT g.*, u.first_name, u.last_name
        FROM `groups` g
        JOIN users u ON g.created_by = u.user_id
        WHERE g.status = 'pending'
        ORDER BY g.created_at DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_pending_members(group_id=None):
    """Fetch pending membership requests, optionally scoped to a group."""
    cursor = get_cursor()
    query = """
        SELECT gm.membership_id, u.first_name, u.last_name, u.username,
               gm.joined_at, r.role_name, g.group_name, gm.group_id
        FROM group_membership gm
        JOIN users u ON gm.user_id = u.user_id
        JOIN roles r ON gm.role_id = r.role_id
        JOIN `groups` g ON gm.group_id = g.group_id
        WHERE gm.membership_status = 'pending'
    """
    params = []
    if group_id:
        query += " AND gm.group_id = %s"
        params.append(group_id)
    query += " ORDER BY gm.joined_at DESC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_pending_upgrades(group_id=None):
    """Fetch pending role upgrade requests, optionally scoped to a group."""
    cursor = get_cursor()
    query = """
        SELECT rur.request_id, u.first_name, u.last_name, u.username,
               rur.created_at, g.group_name, rur.user_id, rur.group_id
        FROM role_upgrade_requests rur
        JOIN users u ON rur.user_id = u.user_id
        JOIN `groups` g ON rur.group_id = g.group_id
        WHERE rur.status = 'pending'
    """
    params = []
    if group_id:
        query += " AND rur.group_id = %s"
        params.append(group_id)
    query += " ORDER BY rur.created_at DESC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    return rows


# ── Dashboard Stats ──────────────────────────────────────────────

def fetch_admin_stats(group_id=None):
    """Fetch admin dashboard statistics."""
    cursor = get_cursor()
    stats = {}

    if group_id:
        cursor.execute("SELECT COUNT(*) as count FROM traps WHERE line_id IN (SELECT line_id FROM `lines` WHERE group_id = %s) AND status = 'active'", (group_id,))
        stats['total_traps'] = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM bait_stations WHERE line_id IN (SELECT line_id FROM `lines` WHERE group_id = %s) AND status = 'active'", (group_id,))
        stats['active_stations'] = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM `lines` WHERE group_id = %s AND status = 'active'", (group_id,))
        stats['active_lines'] = cursor.fetchone()['count']
    else:
        cursor.execute("SELECT COUNT(*) as count FROM traps WHERE status = 'active'")
        stats['total_traps'] = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM bait_stations WHERE status = 'active'")
        stats['active_stations'] = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM `groups` WHERE status = 'active'")
        stats['total_groups'] = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM users")
        stats['total_users'] = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM `groups` WHERE status = 'pending'")
        stats['pending_tasks'] = cursor.fetchone()['count']

    cursor.close()
    return stats


def fetch_recent_activity(group_id=None, limit=10):
    """Fetch recent catch activity."""
    cursor = get_cursor()
    query = """
        SELECT 'catch' as type, tc.`date` as timestamp, u.username,
               t.trap_code, s.species_name, g.group_name
        FROM trap_catches tc
        JOIN users u ON tc.recorded_by = u.user_id
        JOIN traps t ON tc.trap_code = t.trap_code
        JOIN `lines` l ON t.line_id = l.line_id
        JOIN `groups` g ON l.group_id = g.group_id
        LEFT JOIN species s ON tc.species_id = s.species_id
        WHERE 1=1
    """
    params = []
    if group_id:
        query += " AND g.group_id = %s"
        params.append(group_id)
    query += f" ORDER BY tc.`date` DESC LIMIT {limit}"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    return rows


# ── Group Approvals ──────────────────────────────────────────────

def approve_group(group_id):
    """Activate a group and assign creator as coordinator."""
    cursor = get_cursor()
    cursor.execute("SELECT created_by, group_name FROM `groups` WHERE group_id = %s", (group_id,))
    group = cursor.fetchone()
    if not group:
        cursor.close()
        return None

    cursor.execute("UPDATE `groups` SET status = 'active' WHERE group_id = %s", (group_id,))

    cursor.execute(
        "SELECT 1 FROM group_membership WHERE user_id = %s AND group_id = %s",
        (group['created_by'], group_id),
    )
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            "UPDATE group_membership SET role_id = %s, membership_status = 'active' WHERE user_id = %s AND group_id = %s",
            (ROLE_COORDINATOR, group['created_by'], group_id),
        )
    else:
        cursor.execute(
            "INSERT INTO group_membership (user_id, role_id, group_id, membership_status) VALUES (%s, %s, %s, 'active')",
            (group['created_by'], ROLE_COORDINATOR, group_id),
        )
    cursor.close()
    return group


def reject_group(group_id):
    """Reject a group application."""
    cursor = get_cursor()
    cursor.execute("UPDATE `groups` SET status = 'rejected' WHERE group_id = %s", (group_id,))
    cursor.close()


# ── Role Upgrade Approvals ───────────────────────────────────────

def fetch_upgrade_request(request_id):
    """Fetch a role upgrade request."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT user_id, group_id, requested_role_id FROM role_upgrade_requests WHERE request_id = %s",
        (request_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def approve_upgrade(request_id, user_id, group_id, role_id):
    """Approve a role upgrade request."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE group_membership SET role_id = %s WHERE user_id = %s AND group_id = %s",
        (role_id, user_id, group_id),
    )
    cursor.execute(
        "UPDATE role_upgrade_requests SET status = 'approved', updated_at = CURRENT_TIMESTAMP WHERE request_id = %s",
        (request_id,),
    )
    cursor.close()


def reject_upgrade(request_id):
    """Reject a role upgrade request."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE role_upgrade_requests SET status = 'rejected', updated_at = CURRENT_TIMESTAMP WHERE request_id = %s",
        (request_id,),
    )
    cursor.close()


# ── Operator Dashboard ───────────────────────────────────────────

def fetch_operator_lines(user_id, group_id, is_super_admin=False, is_coordinator=False):
    """Fetch lines visible to the operator."""
    cursor = get_cursor()
    if is_super_admin or is_coordinator:
        cursor.execute("""
            SELECT l.line_id, l.line_name, l.status, l.line_type,
                CASE WHEN l.line_type = 'bait_station'
                    THEN (SELECT COUNT(*) FROM bait_stations WHERE line_id = l.line_id AND (status = 'active' OR status IS NULL))
                    ELSE (SELECT COUNT(*) FROM traps WHERE line_id = l.line_id AND (status = 'active' OR status IS NULL))
                END as equipment_count,
                TRUE as is_assigned
            FROM `lines` l
            WHERE l.group_id = %s AND l.status = 'active'
            ORDER BY l.line_name ASC
        """, (group_id,))
    else:
        cursor.execute("""
            SELECT l.line_id, l.line_name, l.status, l.line_type,
                CASE WHEN l.line_type = 'bait_station'
                    THEN (SELECT COUNT(*) FROM bait_stations WHERE line_id = l.line_id AND (status = 'active' OR status IS NULL))
                    ELSE (SELECT COUNT(*) FROM traps WHERE line_id = l.line_id AND (status = 'active' OR status IS NULL))
                END as equipment_count,
                TRUE as is_assigned
            FROM `lines` l
            JOIN operator_lines ol ON l.line_id = ol.line_id
            WHERE ol.user_id = %s AND l.status = 'active'
            ORDER BY l.line_name ASC
        """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_equipment_map_data(group_id, line_id=None):
    """Fetch trap and bait station map data for the dashboard."""
    cursor = get_cursor()

    trap_query = """
        SELECT t.trap_code AS code, tt.trap_type_name AS type,
               t.latitude, t.longitude, es.equipment_status_name AS status,
               (SELECT MAX(tc.`date`) FROM trap_catches tc WHERE tc.trap_code = t.trap_code) AS last_check
        FROM traps t
        JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
        JOIN `lines` l ON t.line_id = l.line_id
        LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
        WHERE (t.status = 'active' OR t.status IS NULL) AND l.group_id = %s
    """
    trap_params = [group_id]
    if line_id:
        trap_query += " AND t.line_id = %s"
        trap_params.append(line_id)
    cursor.execute(trap_query, tuple(trap_params))
    traps = cursor.fetchall()

    bs_query = """
        SELECT b.bait_station_code AS code, bt.bait_station_type_name AS type,
               b.latitude, b.longitude, es.equipment_status_name AS status,
               (SELECT MAX(bsr.`date`) FROM bait_station_records bsr WHERE bsr.bait_station_code = b.bait_station_code) AS last_check
        FROM bait_stations b
        JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
        JOIN `lines` l ON b.line_id = l.line_id
        LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
        WHERE (b.status = 'active' OR b.status IS NULL) AND l.group_id = %s
    """
    bs_params = [group_id]
    if line_id:
        bs_query += " AND b.line_id = %s"
        bs_params.append(line_id)
    cursor.execute(bs_query, tuple(bs_params))
    stations = cursor.fetchall()

    cursor.close()
    return list(traps) + list(stations)


def fetch_line_equipment(line_id):
    """Fetch traps and bait stations for a specific line."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT b.bait_station_code as code, bt.bait_station_type_name as type,
               b.latitude, b.longitude, es.equipment_status_name as status, 'bait_station' as item_type
        FROM bait_stations b
        LEFT JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
        LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
        WHERE b.line_id = %s AND (b.status = 'active' OR b.status IS NULL)
        ORDER BY b.bait_station_code ASC
    """, (line_id,))
    stations = cursor.fetchall()

    cursor.execute("""
        SELECT t.trap_code as code, tt.trap_type_name as type,
               t.latitude, t.longitude, es.equipment_status_name as status, 'trap' as item_type
        FROM traps t
        LEFT JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
        LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
        WHERE t.line_id = %s AND (t.status = 'active' OR t.status IS NULL)
        ORDER BY t.trap_code ASC
    """, (line_id,))
    traps = cursor.fetchall()

    cursor.close()
    return list(stations) + list(traps)


def fetch_line_health(line_id):
    """Fetch line health metrics (checked counts, last check dates)."""
    cursor = get_cursor()

    cursor.execute("""
        SELECT COUNT(DISTINCT bait_station_code) as checked_count
        FROM bait_station_records
        WHERE date >= CURRENT_DATE - INTERVAL 7 DAY
        AND bait_station_code IN (SELECT bait_station_code FROM bait_stations WHERE line_id = %s)
    """, (line_id,))
    checked_stations = cursor.fetchone()['checked_count']

    cursor.execute("""
        SELECT COUNT(DISTINCT trap_code) as checked_count
        FROM trap_catches
        WHERE date >= CURRENT_DATE - INTERVAL 7 DAY
        AND trap_code IN (SELECT trap_code FROM traps WHERE line_id = %s)
    """, (line_id,))
    checked_traps = cursor.fetchone()['checked_count']

    cursor.execute("""
        SELECT bsr.`date`, CONCAT(COALESCE(u.first_name, u.username), ' ', COALESCE(u.last_name, '')) as operator
        FROM bait_station_records bsr
        JOIN users u ON bsr.recorded_by = u.user_id
        WHERE bsr.bait_station_code IN (SELECT bait_station_code FROM bait_stations WHERE line_id = %s)
        ORDER BY bsr.`date` DESC LIMIT 1
    """, (line_id,))
    last_station_check = cursor.fetchone()

    cursor.execute("""
        SELECT tc.`date`, CONCAT(COALESCE(u.first_name, u.username), ' ', COALESCE(u.last_name, '')) as operator
        FROM trap_catches tc
        JOIN users u ON tc.recorded_by = u.user_id
        WHERE tc.trap_code IN (SELECT trap_code FROM traps WHERE line_id = %s)
        ORDER BY tc.`date` DESC LIMIT 1
    """, (line_id,))
    last_trap_check = cursor.fetchone()

    cursor.close()
    return {
        'checked_stations': checked_stations,
        'checked_traps': checked_traps,
        'last_station_check': last_station_check,
        'last_trap_check': last_trap_check,
    }


def fetch_line_recent_activity(line_id, line_type, limit=5):
    """Fetch recent activity for a specific line."""
    cursor = get_cursor()
    if line_type == 'bait_station':
        cursor.execute("""
            SELECT 'bait' as type, bsr.`date`, u.username, b.bait_station_code as code,
                   'Checked' as species_name, l.line_name
            FROM bait_station_records bsr
            JOIN users u ON bsr.recorded_by = u.user_id
            JOIN bait_stations b ON bsr.bait_station_code = b.bait_station_code
            JOIN `lines` l ON b.line_id = l.line_id
            WHERE l.line_id = %s
            ORDER BY bsr.`date` DESC LIMIT %s
        """, (line_id, limit))
    else:
        cursor.execute("""
            SELECT 'catch' as type, tc.`date`, u.username, t.trap_code as code,
                   s.species_name, l.line_name
            FROM trap_catches tc
            JOIN users u ON tc.recorded_by = u.user_id
            JOIN traps t ON tc.trap_code = t.trap_code
            JOIN `lines` l ON t.line_id = l.line_id
            JOIN species s ON tc.species_id = s.species_id
            WHERE l.line_id = %s
            ORDER BY tc.`date` DESC LIMIT %s
        """, (line_id, limit))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_line_operators(line_id):
    """Fetch operators assigned to a line."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT u.user_id, u.first_name, u.last_name, u.username
        FROM operator_lines ol
        JOIN users u ON ol.user_id = u.user_id
        WHERE ol.line_id = %s
        ORDER BY u.first_name ASC
    """, (line_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows
