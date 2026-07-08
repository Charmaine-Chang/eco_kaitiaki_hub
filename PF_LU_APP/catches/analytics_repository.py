"""Repository layer for catches analytics and trends queries."""

from PF_LU_APP.db import get_cursor
from PF_LU_APP.constants import ROLE_COORDINATOR, TrapCondition, EquipmentStatus



def _normalise_id_list(value):
    if not value:
        return []
    values = value if isinstance(value, (list, tuple)) else [value]
    return [str(v).strip() for v in values if str(v).strip().isdigit()]


def _normalise_id(value):
    if not value:
        return None
    value = str(value).strip()
    return value if value.isdigit() else None


def _flag_anomalies(rows):
    if not rows:
        return rows
    average = sum(row['count'] for row in rows) / len(rows)
    threshold = max(3, average * 2)
    for row in rows:
        row['is_anomaly'] = row['count'] >= threshold
    return rows


def fetch_data_graphs(session, line_id=None, start_date=None, end_date=None,
                      species_id=None, record_type='all', operator_id=None):
    """Execute all queries for the data graphs dashboard."""
    cursor = get_cursor()
    current_group_id = session.get('current_group_id')
    is_super_admin = session.get('is_super_admin')
    line_ids = _normalise_id_list(line_id)
    species_id = _normalise_id(species_id)
    operator_id = _normalise_id(operator_id)
    if record_type not in ('all', 'trap', 'bait'):
        record_type = 'all'

    if is_super_admin:
        cursor.execute("SELECT line_id, line_name FROM `lines` WHERE status = 'active' ORDER BY line_name ASC")
    else:
        cursor.execute("SELECT line_id, line_name FROM `lines` WHERE status = 'active' AND group_id = %s ORDER BY line_name ASC", (current_group_id,))
    lines = cursor.fetchall()

    cursor.execute("SELECT species_id, species_name FROM species ORDER BY species_name ASC")
    species = cursor.fetchall()

    from PF_LU_APP.constants import ROLE_OPERATOR
    if is_super_admin:
        cursor.execute(f"""
            SELECT DISTINCT u.user_id,
                   COALESCE(NULLIF(TRIM(CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, ''))), ''), u.username) as operator_name
            FROM users u
            JOIN group_membership gm ON u.user_id = gm.user_id
            WHERE gm.role_id = {ROLE_OPERATOR} AND gm.membership_status = 'active'
            ORDER BY operator_name ASC
        """)
    else:
        cursor.execute(f"""
            SELECT DISTINCT u.user_id,
                   COALESCE(NULLIF(TRIM(CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, ''))), ''), u.username) as operator_name
            FROM group_membership gm
            JOIN users u ON gm.user_id = u.user_id
            WHERE gm.group_id = %s AND gm.membership_status = 'active' AND gm.role_id = {ROLE_OPERATOR}
            ORDER BY operator_name ASC
        """, (current_group_id,))
    operators = cursor.fetchall()

    def activity_conditions(date_column, species_column):
        conditions = ['1=1']
        params = []
        if not is_super_admin:
            conditions.append('l.group_id = %s')
            params.append(current_group_id)
        if line_ids:
            placeholders = ', '.join(['%s'] * len(line_ids))
            conditions.append(f"l.line_id IN ({placeholders})")
            params.extend(line_ids)
        if start_date:
            conditions.append(f"{date_column} >= %s")
            params.append(start_date)
        if end_date:
            conditions.append(f"{date_column} <= %s")
            params.append(f"{end_date} 23:59:59")
        if species_id:
            conditions.append(f"{species_column} = %s")
            params.append(species_id)
        return " AND ".join(conditions), params

    activity_selects = []
    activity_params = []

    trap_cond_in = ", ".join([f"'{s}'" for s in TrapCondition.healthy_states()])
    equip_stat_in = ", ".join([f"'{s}'" for s in EquipmentStatus.healthy_states()])

    if record_type in ('all', 'trap'):
        trap_where, trap_params = activity_conditions('tc.`date`', 'tc.species_id')
        activity_selects.append(f"""
            SELECT 'trap' as record_type,
                   tc.`date` as record_date,
                   tc.recorded_by,
                   COALESCE(NULLIF(TRIM(CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, ''))), ''), u.username) as operator_name,
                   s.species_id,
                   COALESCE(s.species_name, 'Unspecified') as species_name,
                   l.line_id,
                   l.line_name,
                   g.group_name,
                   t.trap_code as equipment_code,
                   'Trap' as equipment_type,
                   t.latitude,
                   t.longitude,
                   0.0 as bait_added,
                   CASE
                       WHEN LOWER(COALESCE(cond.trap_condition_name, '')) NOT IN ('', {trap_cond_in})
                         OR LOWER(COALESCE(es.equipment_status_name, '')) NOT IN ('', {equip_stat_in})
                       THEN 1 ELSE 0
                   END as maintenance_count
            FROM trap_catches tc
            JOIN traps t ON tc.trap_code = t.trap_code
            JOIN `lines` l ON t.line_id = l.line_id
            JOIN `groups` g ON l.group_id = g.group_id
            JOIN users u ON tc.recorded_by = u.user_id
            LEFT JOIN species s ON tc.species_id = s.species_id
            LEFT JOIN trap_condition cond ON tc.trap_condition_id = cond.trap_condition_id
            LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
            WHERE {trap_where}
        """)
        activity_params.extend(trap_params)

    if record_type in ('all', 'bait'):
        bait_where, bait_params = activity_conditions('bsr.`date`', 'bsr.target_species_id')
        activity_selects.append(f"""
            SELECT 'bait' as record_type,
                   bsr.`date` as record_date,
                   bsr.recorded_by,
                   COALESCE(NULLIF(TRIM(CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, ''))), ''), u.username) as operator_name,
                   s.species_id,
                   COALESCE(s.species_name, 'Unspecified') as species_name,
                   l.line_id,
                   l.line_name,
                   g.group_name,
                   bs.bait_station_code as equipment_code,
                   'Bait Station' as equipment_type,
                   bs.latitude,
                   bs.longitude,
                   COALESCE(bsr.bait_added, 0) as bait_added,
                   CASE
                       WHEN LOWER(COALESCE(bsr.notes, '')) LIKE '%%maintenance%%'
                         OR LOWER(COALESCE(bsr.notes, '')) LIKE '%%repair%%'
                         OR LOWER(COALESCE(bsr.notes, '')) LIKE '%%damage%%'
                         OR LOWER(COALESCE(es.equipment_status_name, '')) NOT IN ('', {equip_stat_in})
                       THEN 1 ELSE 0
                   END as maintenance_count
            FROM bait_station_records bsr
            JOIN bait_stations bs ON bsr.bait_station_code = bs.bait_station_code
            JOIN `lines` l ON bs.line_id = l.line_id
            JOIN `groups` g ON l.group_id = g.group_id
            JOIN users u ON bsr.recorded_by = u.user_id
            LEFT JOIN species s ON bsr.target_species_id = s.species_id
            LEFT JOIN equipment_status es ON bs.equipment_status_id = es.equipment_status_id
            WHERE {bait_where}
        """)
        activity_params.extend(bait_params)

    activity_sql = "\nUNION ALL\n".join(activity_selects)

    def fetch_activity(query, params=()):
        cursor.execute(f"WITH activity AS ({activity_sql}) {query}", tuple(activity_params) + tuple(params))
        return cursor.fetchall()

    species_data = [dict(row) for row in fetch_activity("""
        SELECT species_name, COUNT(*) as count
        FROM activity
        GROUP BY species_name
        ORDER BY count DESC, species_name ASC
    """)]

    lines_data = [dict(row) for row in fetch_activity("""
        SELECT line_id, line_name, COUNT(*) as count, COALESCE(SUM(maintenance_count), 0) as maintenance_count
        FROM activity
        GROUP BY line_id, line_name
        ORDER BY count DESC, line_name ASC
    """)]

    dates_data = [dict(row) for row in fetch_activity("""
        SELECT DATE_FORMAT(record_date, '%Y-%m-%d') as catch_date, COUNT(*) as count
        FROM activity
        GROUP BY DATE(record_date)
        ORDER BY DATE(record_date)
    """)]

    map_rows = fetch_activity("""
        SELECT record_date as date, record_type, species_name, equipment_code, latitude, longitude
        FROM activity
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY record_date DESC
    """)
    map_data = []
    for row in map_rows:
        r = dict(row)
        if r.get('date'):
            r['date'] = r['date'].strftime('%Y-%m-%d %H:%M')
        map_data.append(r)

    seasonal_data = [dict(row) for row in fetch_activity("""
        SELECT
            CASE
                WHEN EXTRACT(MONTH FROM record_date) IN (9, 10, 11) THEN 'Spring'
                WHEN EXTRACT(MONTH FROM record_date) IN (12, 1, 2) THEN 'Summer'
                WHEN EXTRACT(MONTH FROM record_date) IN (3, 4, 5) THEN 'Autumn'
                ELSE 'Winter'
            END as season,
            COUNT(*) as count
        FROM activity
        GROUP BY season
    """)]

    recent_catches = fetch_activity("""
        SELECT record_date as date, record_type, species_name, equipment_code,
               equipment_type, line_name, group_name, operator_name
        FROM activity
        ORDER BY record_date DESC
        LIMIT 10
    """)

    record_counts = {
        row['record_type']: row['count']
        for row in fetch_activity("""
            SELECT record_type, COUNT(*) as count
            FROM activity
            GROUP BY record_type
        """)
    }
    total_trap_records = record_counts.get('trap', 0)
    total_bait_records = record_counts.get('bait', 0)
    total_catches = total_trap_records
    total_records = total_trap_records + total_bait_records
    total_bait_consumed = fetch_activity("SELECT COALESCE(SUM(bait_added), 0) as total FROM activity")[0]['total']
    maintenance_issues = fetch_activity("SELECT COALESCE(SUM(maintenance_count), 0) as count FROM activity")[0]['count']

    active_line_ids = [str(line['line_id']) for line in lines if not line_ids or str(line['line_id']) in line_ids]
    active_lines_count = len(active_line_ids)

    equipment_scope = ['1=1']
    equipment_params = []
    if not is_super_admin:
        equipment_scope.append('l.group_id = %s')
        equipment_params.append(current_group_id)
    if line_ids:
        placeholders = ', '.join(['%s'] * len(line_ids))
        equipment_scope.append(f"l.line_id IN ({placeholders})")
        equipment_params.extend(line_ids)
    equipment_where = " AND ".join(equipment_scope)
    cursor.execute(f"""
        SELECT COUNT(*) as count
        FROM traps t
        JOIN `lines` l ON t.line_id = l.line_id
        WHERE t.status = 'active' AND {equipment_where}
    """, tuple(equipment_params))
    active_traps_count = cursor.fetchone()['count']
    cursor.execute(f"""
        SELECT COUNT(*) as count
        FROM bait_stations bs
        JOIN `lines` l ON bs.line_id = l.line_id
        WHERE bs.status = 'active' AND {equipment_where}
    """, tuple(equipment_params))
    active_stations_count = cursor.fetchone()['count']

    operator_stats = [dict(row) for row in fetch_activity("""
        SELECT recorded_by as user_id, operator_name,
               COUNT(*) as activity_count,
               COALESCE(SUM(CASE WHEN record_type = 'trap' THEN 1 ELSE 0 END), 0) as trap_records,
               COALESCE(SUM(CASE WHEN record_type = 'bait' THEN 1 ELSE 0 END), 0) as bait_records,
               COUNT(DISTINCT line_id) as lines_touched,
               MAX(record_date) as last_activity
        FROM activity
        GROUP BY recorded_by, operator_name
        ORDER BY activity_count DESC, operator_name ASC
    """)]

    station_hotspots = [dict(row) for row in fetch_activity("""
        SELECT equipment_code, equipment_type, line_name,
               COUNT(*) as count, COALESCE(SUM(maintenance_count), 0) as maintenance_count
        FROM activity
        GROUP BY equipment_code, equipment_type, line_name
        ORDER BY count DESC, equipment_code ASC
        LIMIT 10
    """)]

    line_hotspots = _flag_anomalies(lines_data[:10])
    station_hotspots = _flag_anomalies(station_hotspots)

    selected_operator_detail = None
    if operator_id:
        matching_operator = next((op for op in operator_stats if str(op['user_id']) == operator_id), None)
        if matching_operator:
            selected_operator_detail = dict(matching_operator)
            selected_operator_detail['line_breakdown'] = [dict(row) for row in fetch_activity("""
                SELECT line_name, COUNT(*) as count
                FROM activity
                WHERE recorded_by = %s
                GROUP BY line_name
                ORDER BY count DESC, line_name ASC
                LIMIT 5
            """, (operator_id,))]
            selected_operator_detail['species_breakdown'] = [dict(row) for row in fetch_activity("""
                SELECT species_name, COUNT(*) as count
                FROM activity
                WHERE recorded_by = %s
                GROUP BY species_name
                ORDER BY count DESC, species_name ASC
                LIMIT 5
            """, (operator_id,))]

    hotspot = "N/A"
    if lines_data:
        most_active = max(lines_data, key=lambda x: x['count'])
        hotspot = most_active['line_name']

    success_rate = (total_catches / total_records * 100) if total_records > 0 else 0

    cursor.close()

    return {
        'species_data': species_data,
        'lines_data': lines_data,
        'dates_data': dates_data,
        'map_data': map_data,
        'seasonal_data': seasonal_data,
        'recent_catches': recent_catches,
        'operator_stats': operator_stats,
        'selected_operator_detail': selected_operator_detail,
        'line_hotspots': line_hotspots,
        'station_hotspots': station_hotspots,
        'species': species,
        'operators': operators,
        'kpis': {
            'total_catches': total_catches,
            'active_lines': active_lines_count,
            'active_traps': active_traps_count,
            'active_stations': active_stations_count,
            'total_trap_records': total_trap_records,
            'total_bait_records': total_bait_records,
            'total_bait_consumed': total_bait_consumed,
            'maintenance_issues': maintenance_issues,
            'success_rate': round(success_rate, 1),
            'hotspot': hotspot,
        },
        'lines': lines,
    }


def fetch_trend_analytics(session, interval='month', line_id=None, start_date=None, end_date=None):
    """Fetch time-based trend data for catches, bait consumption, and station checks."""
    cursor = get_cursor()
    current_group_id = session.get('current_group_id')
    is_super_admin = session.get('is_super_admin')

    if interval not in ('day', 'week', 'month', 'year'):
        interval = 'month'

    group_filter_trap = ''
    group_filter_bait = ''
    group_filter_station = ''
    group_params_trap = []
    group_params_bait = []
    group_params_station = []

    if not is_super_admin and current_group_id:
        group_filter_trap = 'AND l.group_id = %s '
        group_filter_bait = 'AND l.group_id = %s '
        group_filter_station = 'AND l.group_id = %s '
        group_params_trap = [current_group_id]
        group_params_bait = [current_group_id]
        group_params_station = [current_group_id]

    if line_id:
        group_filter_trap += 'AND t.line_id = %s '
        group_filter_bait += 'AND bs.line_id = %s '
        group_filter_station += 'AND bs.line_id = %s '
        group_params_trap.append(line_id)
        group_params_bait.append(line_id)
        group_params_station.append(line_id)

    if start_date:
        group_filter_trap += 'AND tc.`date` >= %s '
        group_filter_bait += 'AND bsr.`date` >= %s '
        group_filter_station += 'AND bsr.`date` >= %s '
        group_params_trap.append(start_date)
        group_params_bait.append(start_date)
        group_params_station.append(start_date)

    if end_date:
        group_filter_trap += 'AND tc.`date` <= %s '
        group_filter_bait += 'AND bsr.`date` <= %s '
        group_filter_station += 'AND bsr.`date` <= %s '
        group_params_trap.append(f"{end_date} 23:59:59")
        group_params_bait.append(f"{end_date} 23:59:59")
        group_params_station.append(f"{end_date} 23:59:59")

    # Date format for display labels (MySQL format strings)
    fmt_map = {
        'day': '%Y-%m-%d',
        'week': '%x-%v',
        'month': '%Y-%m',
        'year': '%Y',
    }
    date_fmt = fmt_map[interval]

    # Catches trend (trap records with a real catch / non-empty species)
    cursor.execute(f"""
        SELECT DATE_FORMAT(tc.`date`, '{date_fmt}') as period,
               COUNT(*) as count
        FROM trap_catches tc
        JOIN traps t ON tc.trap_code = t.trap_code
        JOIN `lines` l ON t.line_id = l.line_id
        WHERE tc.`date` IS NOT NULL
          {group_filter_trap}
        GROUP BY DATE_FORMAT(tc.`date`, '{date_fmt}')
        ORDER BY DATE_FORMAT(tc.`date`, '{date_fmt}')
    """, tuple(group_params_trap))
    catches_trend = [dict(row) for row in cursor.fetchall()]

    # Bait consumption trend
    cursor.execute(f"""
        SELECT DATE_FORMAT(bsr.`date`, '{date_fmt}') as period,
               COALESCE(SUM(bsr.bait_added), 0) as total_bait
        FROM bait_station_records bsr
        JOIN bait_stations bs ON bsr.bait_station_code = bs.bait_station_code
        JOIN `lines` l ON bs.line_id = l.line_id
        WHERE bsr.`date` IS NOT NULL
          {group_filter_bait}
        GROUP BY DATE_FORMAT(bsr.`date`, '{date_fmt}')
        ORDER BY DATE_FORMAT(bsr.`date`, '{date_fmt}')
    """, tuple(group_params_bait))
    bait_trend = [dict(row) for row in cursor.fetchall()]

    # Station checks trend (number of bait station check visits)
    cursor.execute(f"""
        SELECT DATE_FORMAT(bsr.`date`, '{date_fmt}') as period,
               COUNT(*) as count
        FROM bait_station_records bsr
        JOIN bait_stations bs ON bsr.bait_station_code = bs.bait_station_code
        JOIN `lines` l ON bs.line_id = l.line_id
        WHERE bsr.`date` IS NOT NULL
          {group_filter_station}
        GROUP BY DATE_FORMAT(bsr.`date`, '{date_fmt}')
        ORDER BY DATE_FORMAT(bsr.`date`, '{date_fmt}')
    """, tuple(group_params_station))
    station_trend = [dict(row) for row in cursor.fetchall()]

    # Seasonal comparison – Southern Hemisphere seasons
    seasonal_sql_trap = f"""
        SELECT
            CASE
                WHEN EXTRACT(MONTH FROM tc.`date`) IN (9, 10, 11) THEN 'Spring'
                WHEN EXTRACT(MONTH FROM tc.`date`) IN (12, 1, 2) THEN 'Summer'
                WHEN EXTRACT(MONTH FROM tc.`date`) IN (3, 4, 5) THEN 'Autumn'
                ELSE 'Winter'
            END as season,
            COUNT(*) as catches,
            0 as bait_consumed,
            0 as station_checks
        FROM trap_catches tc
        JOIN traps t ON tc.trap_code = t.trap_code
        JOIN `lines` l ON t.line_id = l.line_id
        WHERE tc.`date` IS NOT NULL {group_filter_trap}
        GROUP BY season
    """

    seasonal_sql_bait = f"""
        SELECT
            CASE
                WHEN EXTRACT(MONTH FROM bsr.`date`) IN (9, 10, 11) THEN 'Spring'
                WHEN EXTRACT(MONTH FROM bsr.`date`) IN (12, 1, 2) THEN 'Summer'
                WHEN EXTRACT(MONTH FROM bsr.`date`) IN (3, 4, 5) THEN 'Autumn'
                ELSE 'Winter'
            END as season,
            0 as catches,
            COALESCE(SUM(bsr.bait_added), 0) as bait_consumed,
            COUNT(*) as station_checks
        FROM bait_station_records bsr
        JOIN bait_stations bs ON bsr.bait_station_code = bs.bait_station_code
        JOIN `lines` l ON bs.line_id = l.line_id
        WHERE bsr.`date` IS NOT NULL {group_filter_bait}
        GROUP BY season
    """

    cursor.execute(seasonal_sql_trap, tuple(group_params_trap))
    trap_seasonal = {row['season']: dict(row) for row in cursor.fetchall()}

    cursor.execute(seasonal_sql_bait, tuple(group_params_bait))
    bait_seasonal = {row['season']: dict(row) for row in cursor.fetchall()}

    season_order = ['Spring', 'Summer', 'Autumn', 'Winter']
    seasonal_data = []
    for season in season_order:
        t = trap_seasonal.get(season, {'catches': 0})
        b = bait_seasonal.get(season, {'bait_consumed': 0, 'station_checks': 0})
        seasonal_data.append({
            'season': season,
            'catches': t.get('catches', 0),
            'bait_consumed': float(b.get('bait_consumed', 0)),
            'station_checks': b.get('station_checks', 0),
        })

    # Simple summary KPIs
    total_catches = sum(r['count'] for r in catches_trend)
    total_bait = sum(float(r['total_bait']) for r in bait_trend)
    total_checks = sum(r['count'] for r in station_trend)

    cursor.close()

    return {
        'catches_trend': catches_trend,
        'bait_trend': bait_trend,
        'station_trend': station_trend,
        'seasonal_data': seasonal_data,
        'interval': interval,
        'kpis': {
            'total_catches': total_catches,
            'total_bait_consumed': round(total_bait, 1),
            'total_station_checks': total_checks,
        },
    }


def fetch_species_distribution(session):
    """Get species distribution counts."""
    cursor = get_cursor()
    current_group_id = session.get('current_group_id')
    is_super_admin = session.get('is_super_admin')
    role_id = session.get('role_id')

    dist_query = """
        SELECT s.species_name, COUNT(*) as count
        FROM trap_catches tc
        JOIN species s ON tc.species_id = s.species_id
        JOIN traps t ON tc.trap_code = t.trap_code
        WHERE 1=1
    """
    dist_params = []
    if is_super_admin:
        pass
    elif role_id == ROLE_COORDINATOR:
        dist_query += " AND t.line_id IN (SELECT line_id FROM `lines` WHERE group_id = %s)"
        dist_params.append(current_group_id)
    else:
        dist_query += " AND t.line_id IN (SELECT line_id FROM operator_lines WHERE user_id = %s)"
        dist_params.append(session.get('user_id'))
    dist_query += " GROUP BY s.species_name ORDER BY count DESC"
    cursor.execute(dist_query, tuple(dist_params))
    result = cursor.fetchall()
    cursor.close()
    return result
