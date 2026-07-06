"""Repository layer for all catch-related database queries.

This module consolidates all SQL queries that were previously duplicated across
admin/catches.py, operators/catches.py, observer/routes.py, and shared/queries.py.
"""

from PF_LU_APP.db import get_cursor
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER


def _build_catches_where(session, extra_conditions=None):
    """Build a WHERE clause and params for catch queries based on user role.

    Returns:
        (where_str, params)
    """
    where_clause = ['1=1']
    params = []

    is_super_admin = session.get('is_super_admin')
    role_id = session.get('role_id')
    current_group_id = session.get('current_group_id')

    if is_super_admin:
        pass
    elif role_id in (ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER):
        where_clause.append('l.group_id = %s')
        params.append(current_group_id)
    else:
        where_clause.append('t.line_id IN (SELECT line_id FROM operator_lines WHERE user_id = %s)')
        params.append(session.get('user_id'))

    if extra_conditions:
        for condition, param in extra_conditions:
            where_clause.append(condition)
            params.append(param)

    return " AND ".join(where_clause), tuple(params)


# ── Catch List ────────────────────────────────────────────────────

def fetch_catches(session, line_filter=None, species_filter=None,
                  start_date=None, end_date=None, include_updated_at=False):
    """Fetch catch records with filters for the catch list view.

    Returns:
        (catches, all_lines, all_species, line, map_data)
    """
    cursor = get_cursor()
    current_group_id = session.get('current_group_id')
    is_super_admin = session.get('is_super_admin')

    if is_super_admin:
        cursor.execute("SELECT line_id, line_name FROM lines WHERE status = 'active' ORDER BY line_name ASC")
    else:
        cursor.execute("SELECT line_id, line_name FROM lines WHERE status = 'active' AND group_id = %s ORDER BY line_name ASC", (current_group_id,))
    all_lines = cursor.fetchall()

    cursor.execute("SELECT * FROM species ORDER BY species_name ASC")
    all_species = cursor.fetchall()

    line = None
    if line_filter:
        cursor.execute("SELECT line_name FROM lines WHERE line_id = %s", (line_filter,))
        line = cursor.fetchone()

    extra = []
    if line_filter:
        extra.append(('t.line_id = %s', line_filter))
    if species_filter:
        extra.append(('tc.species_id = %s', species_filter))
    if start_date:
        extra.append(('DATE(tc.date) >= %s', start_date))
    if end_date:
        extra.append(('DATE(tc.date) <= %s', f"{end_date} 23:59:59"))

    where_str, params = _build_catches_where(session, extra)

    updated_col = ", tc.updated_at" if include_updated_at else ""
    query = f"""
        SELECT tc.catches_id, tc.trap_code, tc.date, s.species_name, tc.sex, tc.maturity,
               ts.status_name as trap_status, tc.rebaited, b.bait_type_name,
               cond.trap_condition_name as trap_condition, tc.strikes, tc.note,
               COALESCE(u.first_name, '') || ' ' || COALESCE(u.last_name, '') as recorded_by_name,
               tc.recorded_by, l.line_name, t.latitude, t.longitude{updated_col},
               t.status AS trap_overall_status, es_t.equipment_status_name AS trap_equipment_status
        FROM trap_catches tc
        JOIN traps t ON tc.trap_code = t.trap_code
        LEFT JOIN equipment_status es_t ON t.equipment_status_id = es_t.equipment_status_id
        JOIN lines l ON t.line_id = l.line_id
        JOIN species s ON tc.species_id = s.species_id
        JOIN trap_status ts ON tc.trap_status_id = ts.trap_status_id
        LEFT JOIN bait_type b ON tc.bait_type_id = b.bait_type_id
        JOIN trap_condition cond ON tc.trap_condition_id = cond.trap_condition_id
        JOIN users u ON tc.recorded_by = u.user_id
        WHERE {where_str}
        ORDER BY tc.date DESC
    """
    cursor.execute(query, params)
    catches = cursor.fetchall()

    map_data = []
    for c in catches:
        if c.get('latitude') and c.get('longitude'):
            map_data.append({
                'catches_id': c['catches_id'],
                'trap_code': c['trap_code'],
                'species': c['species_name'],
                'sex': c['sex'] or 'N/A',
                'maturity': c['maturity'] or 'N/A',
                'status': c['trap_status'] or '',
                'date': c['date'].strftime('%Y-%m-%d %H:%M') if c['date'] else 'N/A',
                'lat': float(c['latitude']),
                'lng': float(c['longitude']),
            })

    cursor.close()
    return catches, all_lines, all_species, line, map_data


def fetch_catches_kpis(session):
    """Calculate KPI stats for the catch list view."""
    cursor = get_cursor()
    current_group_id = session.get('current_group_id')
    is_super_admin = session.get('is_super_admin')
    role_id = session.get('role_id')

    stats = {'total_catches': 0, 'active_traps': 0, 'maintenance_required': 0}

    if is_super_admin:
        cursor.execute("SELECT COUNT(*) as count FROM traps WHERE status = 'active'")
    elif role_id == ROLE_COORDINATOR:
        cursor.execute("SELECT COUNT(*) as count FROM traps WHERE status = 'active' AND line_id IN (SELECT line_id FROM lines WHERE group_id = %s)", (current_group_id,))
    else:
        cursor.execute("SELECT COUNT(*) as count FROM traps WHERE status = 'active' AND line_id IN (SELECT line_id FROM operator_lines WHERE user_id = %s)", (session.get('user_id'),))
    stats['active_traps'] = cursor.fetchone()['count']

    maint_query = """
        SELECT COUNT(DISTINCT t.trap_code) as count
        FROM traps t
        JOIN trap_catches tc ON t.trap_code = tc.trap_code
        WHERE tc.trap_condition_id IN (SELECT trap_condition_id FROM trap_condition WHERE trap_condition_name != 'Good')
        AND tc.date = (SELECT MAX(date) FROM trap_catches WHERE trap_code = t.trap_code)
    """
    maint_params = []
    if is_super_admin:
        pass
    elif role_id == ROLE_COORDINATOR:
        maint_query += " AND t.line_id IN (SELECT line_id FROM lines WHERE group_id = %s)"
        maint_params.append(current_group_id)
    else:
        maint_query += " AND t.line_id IN (SELECT line_id FROM operator_lines WHERE user_id = %s)"
        maint_params.append(session.get('user_id'))
    cursor.execute(maint_query, tuple(maint_params))
    stats['maintenance_required'] = cursor.fetchone()['count']

    cursor.close()
    return stats


# ── CSV Export ────────────────────────────────────────────────────

def fetch_catches_for_csv(session, line_filter=None, species_filter=None,
                          start_date=None, end_date=None):
    """Fetch catch records for CSV export."""
    cursor = get_cursor()

    extra = []
    if line_filter:
        extra.append(('t.line_id = %s', line_filter))
    if species_filter:
        extra.append(('tc.species_id = %s', species_filter))
    if start_date:
        extra.append(('DATE(tc.date) >= %s', start_date))
    if end_date:
        extra.append(('DATE(tc.date) <= %s', end_date))

    where_str, params = _build_catches_where(session, extra)

    query = f"""
        SELECT tc.catches_id, tc.trap_code, tc.date, s.species_name, tc.sex, tc.maturity,
               ts.status_name as trap_status, tc.rebaited, b.bait_type_name,
               cond.trap_condition_name as trap_condition, tc.strikes, tc.note,
               u.first_name || ' ' || u.last_name as recorded_by_name, l.line_name
        FROM trap_catches tc
        JOIN traps t ON tc.trap_code = t.trap_code
        JOIN lines l ON t.line_id = l.line_id
        JOIN species s ON tc.species_id = s.species_id
        JOIN trap_status ts ON tc.trap_status_id = ts.trap_status_id
        LEFT JOIN bait_type b ON tc.bait_type_id = b.bait_type_id
        JOIN trap_condition cond ON tc.trap_condition_id = cond.trap_condition_id
        JOIN users u ON tc.recorded_by = u.user_id
        WHERE {where_str}
        ORDER BY tc.date DESC
    """
    cursor.execute(query, params)
    catches = cursor.fetchall()
    cursor.close()
    return catches


# ── Single Catch Record ──────────────────────────────────────────

def fetch_catch_by_id(catches_id):
    """Fetch a single catch record with line info."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT tc.*, t.line_id, l.line_name, tc.updated_at
        FROM trap_catches tc
        JOIN traps t ON tc.trap_code = t.trap_code
        JOIN lines l ON t.line_id = l.line_id
        WHERE tc.catches_id = %s
    """, (catches_id,))
    catch = cursor.fetchone()
    cursor.close()
    return catch


def fetch_catch_owner(catches_id):
    """Fetch the recorded_by user and group for a catch record."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT tc.recorded_by, tc.bait_type_id, tc.bait_amount, t.line_id
        FROM trap_catches tc
        JOIN traps t ON tc.trap_code = t.trap_code
        WHERE tc.catches_id = %s
    """, (catches_id,))
    record = cursor.fetchone()
    cursor.close()
    return record


def fetch_catch_group(catches_id):
    """Fetch which group a catch record belongs to."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT l.group_id
        FROM trap_catches tc
        JOIN traps t ON tc.trap_code = t.trap_code
        JOIN lines l ON t.line_id = l.line_id
        WHERE tc.catches_id = %s
    """, (catches_id,))
    row = cursor.fetchone()
    cursor.close()
    return row


def update_catch(catches_id, date, species_id, sex, maturity, trap_status_id,
                 rebaited, bait_type_id, trap_condition_id, strikes, note,
                 bait_amount=None):
    """Update a catch record."""
    cursor = get_cursor()
    cursor.execute("""
        UPDATE trap_catches
        SET date = %s, species_id = %s, sex = %s, maturity = %s,
            trap_status_id = %s, rebaited = %s, bait_type_id = %s,
            trap_condition_id = %s, strikes = %s, note = %s,
            bait_amount = %s, updated_at = CURRENT_TIMESTAMP
        WHERE catches_id = %s
    """, (date, species_id, sex, maturity, trap_status_id, rebaited,
          bait_type_id, trap_condition_id, strikes, note, bait_amount, catches_id))
    cursor.close()


def insert_catch(trap_code, date, recorded_by, species_id, sex, maturity,
                 trap_status_id, rebaited, bait_type_id, bait_amount,
                 trap_condition_id, strikes, note):
    """Insert a new catch record."""
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO trap_catches (trap_code, date, recorded_by, species_id, sex, maturity,
                                  trap_status_id, rebaited, bait_type_id, bait_amount,
                                  trap_condition_id, strikes, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (trap_code, date, recorded_by, species_id, sex, maturity,
          trap_status_id, rebaited, bait_type_id, bait_amount,
          trap_condition_id, strikes, note))
    cursor.close()


# ── Form Data ────────────────────────────────────────────────────

def fetch_catch_form_data(trap_code=None, line_id=None):
    """Fetch dropdown data for the catch form."""
    cursor = get_cursor()
    trap = None
    traps = []
    line = None

    if trap_code:
        cursor.execute("SELECT * FROM traps WHERE trap_code = %s", (trap_code,))
        trap = cursor.fetchone()
    elif line_id:
        cursor.execute("SELECT line_name FROM lines WHERE line_id = %s", (line_id,))
        line = cursor.fetchone()
        cursor.execute("SELECT * FROM traps WHERE line_id = %s AND status = 'active' ORDER BY trap_code", (line_id,))
        traps = cursor.fetchall()

    cursor.execute("SELECT * FROM species ORDER BY species_name")
    species = cursor.fetchall()
    cursor.execute("SELECT * FROM trap_status ORDER BY status_name")
    statuses = cursor.fetchall()
    cursor.execute("SELECT * FROM bait_type ORDER BY bait_type_name")
    baits = cursor.fetchall()
    cursor.execute("SELECT * FROM trap_condition ORDER BY trap_condition_name")
    conditions = cursor.fetchall()
    cursor.close()

    return trap, traps, line, species, statuses, baits, conditions
