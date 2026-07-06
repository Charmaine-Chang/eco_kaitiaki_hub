import csv
import io
import json
from flask import Blueprint, render_template, session, redirect, url_for, request, make_response, flash, current_app
from PF_LU_APP.db import get_cursor_context
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER, EquipmentStatus
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.shared.utils import resolve_date_preset
from PF_LU_APP.catches.catch_repository import (
    fetch_catches, fetch_catches_kpis,
    fetch_catches_for_csv,
)
from PF_LU_APP.catches.analytics_repository import (
    fetch_species_distribution, fetch_data_graphs, fetch_trend_analytics,
)

from PF_LU_APP.roles.observer import observer_bp

@observer_bp.route('/lines', methods=['GET'])
@roles_required(ROLE_OBSERVER)
def view_lines():
    # Initialize all variables required by the template
    lines = []
    traps = []
    bait_stations = []
    operators = []
    available_operators = []
    selected_line_id = request.args.get('line_id')
    selected_line_type = 'trap'
    is_selected_line_assigned = False

    # Metrics and Activity (Required by view_lines.html)
    stats = {'total_active_lines': 0, 'total_equipment': 0, 'last_sync': None}
    recent_activity = []
    status_breakdown = {'functional': 0, 'maintenance': 0}
    
    # Selected Line KPIs
    line_kpis = {
        'health_score': 0, 
        'last_check_date': None, 
        'last_check_by': None,
        'maintenance_count': 0
    }

    try:
        with get_cursor_context() as cursor:
            current_group_id = session.get('current_group_id')
            # 1. Fetch Lines with Equipment Counts
            query = """
                SELECT l.*, g.group_name,
                       (SELECT COUNT(*) FROM traps t WHERE t.line_id = l.line_id AND (t.status = 'active' OR t.status IS NULL)) as trap_count,
                       (SELECT COUNT(*) FROM bait_stations b WHERE b.line_id = l.line_id AND (b.status = 'active' OR b.status IS NULL)) as station_count,
                       (SELECT STRING_AGG(u.first_name || ' ' || u.last_name, ', ' ORDER BY u.first_name)
                        FROM operator_lines ol2
                        JOIN users u ON ol2.user_id = u.user_id
                        WHERE ol2.line_id = l.line_id) AS operator_names
                FROM lines l
                JOIN groups g ON l.group_id = g.group_id
                WHERE l.status = 'active'
            """
            params = []
            if current_group_id:
                query += " AND l.group_id = %s"
                params.append(current_group_id)
            query += " ORDER BY g.group_name ASC, l.line_name ASC"
            cursor.execute(query, tuple(params))
            lines = cursor.fetchall()
            
            # Calculate Global Stats
            stats['total_active_lines'] = len(lines)
            stats['total_equipment'] = sum((l['trap_count'] or 0) + (l['station_count'] or 0) for l in lines)

            if not selected_line_id:
                # Global Activity for Observers (all groups)
                cursor.execute("""
                    SELECT 'catch' as type, tc.date, u.username, t.trap_code as code, 
                           s.species_name, l.line_name
                    FROM trap_catches tc
                    JOIN users u ON tc.recorded_by = u.user_id
                    JOIN traps t ON tc.trap_code = t.trap_code
                    JOIN lines l ON t.line_id = l.line_id
                    JOIN species s ON tc.species_id = s.species_id
                    ORDER BY tc.date DESC LIMIT 5
                """)
                recent_activity = cursor.fetchall()
                if recent_activity:
                    stats['last_sync'] = recent_activity[0]['date']

            if selected_line_id:
                # Validate selected_line_id is numeric to avoid DB errors
                if not str(selected_line_id).isdigit():
                    flash("Invalid line ID format.", "warning")
                    return redirect(url_for('observer.view_lines'))

                # Find selected line details
                selected_line = next((l for l in lines if str(l['line_id']) == str(selected_line_id)), None)
                if selected_line:
                    selected_line_type = str(selected_line.get('line_type') or 'trap').strip().lower()

                    # 2. Fetch Equipment and Calculate KPIs
                    # Fetch both bait stations and traps to allow mixed lines
                    cursor.execute("""
                        SELECT b.bait_station_code as code, bt.bait_station_type_name as type, b.latitude, b.longitude, es.equipment_status_name as status, 'bait_station' as item_type
                        FROM bait_stations b
                        LEFT JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
                        LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
                        WHERE b.line_id = %s AND (b.status = 'active' OR b.status IS NULL)
                        ORDER BY b.bait_station_code ASC
                    """, (selected_line_id,))
                    bait_stations = cursor.fetchall()

                    cursor.execute("""
                        SELECT t.trap_code as code, tt.trap_type_name as type, t.latitude, t.longitude, es.equipment_status_name as status, 'trap' as item_type
                        FROM traps t
                        LEFT JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
                        LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
                        WHERE t.line_id = %s AND (t.status = 'active' OR t.status IS NULL)
                        ORDER BY t.trap_code ASC
                    """, (selected_line_id,))
                    traps = cursor.fetchall()

                    for s in bait_stations:
                        if s['status'] and s['status'].lower() in EquipmentStatus.healthy_states(): status_breakdown['functional'] += 1
                        else: status_breakdown['maintenance'] += 1

                    for t in traps:
                        if t['status'] and t['status'].lower() in EquipmentStatus.healthy_states(): status_breakdown['functional'] += 1
                        else: status_breakdown['maintenance'] += 1

                    # Line Health: % checked in 7 days (combined)
                    cursor.execute("""
                        SELECT COUNT(DISTINCT bait_station_code) as checked_count
                        FROM bait_station_records
                        WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                        AND bait_station_code IN (SELECT bait_station_code FROM bait_stations WHERE line_id = %s)
                    """, (selected_line_id,))
                    checked_stations = cursor.fetchone()['checked_count'] or 0

                    cursor.execute("""
                        SELECT COUNT(DISTINCT trap_code) as checked_count
                        FROM trap_catches
                        WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                        AND trap_code IN (SELECT trap_code FROM traps WHERE line_id = %s)
                    """, (selected_line_id,))
                    checked_traps = cursor.fetchone()['checked_count'] or 0

                    total_nodes = len(bait_stations) + len(traps)
                    total_checked = checked_stations + checked_traps
                    line_kpis['health_score'] = int((total_checked / total_nodes * 100)) if total_nodes > 0 else 0

                    # Last check: most recent check between bait stations and traps
                    cursor.execute("""
                        SELECT bsr.date, COALESCE(u.first_name, u.username) || ' ' || COALESCE(u.last_name, '') as operator
                        FROM bait_station_records bsr
                        JOIN users u ON bsr.recorded_by = u.user_id
                        WHERE bsr.bait_station_code IN (SELECT bait_station_code FROM bait_stations WHERE line_id = %s)
                        ORDER BY bsr.date DESC LIMIT 1
                    """, (selected_line_id,))
                    last_station = cursor.fetchone()

                    cursor.execute("""
                        SELECT tc.date, COALESCE(u.first_name, u.username) || ' ' || COALESCE(u.last_name, '') as operator
                        FROM trap_catches tc
                        JOIN users u ON tc.recorded_by = u.user_id
                        WHERE tc.trap_code IN (SELECT trap_code FROM traps WHERE line_id = %s)
                        ORDER BY tc.date DESC LIMIT 1
                    """, (selected_line_id,))
                    last_trap = cursor.fetchone()

                    last = None
                    if last_station and last_trap:
                        last = last_station if last_station['date'] >= last_trap['date'] else last_trap
                    elif last_station:
                        last = last_station
                    elif last_trap:
                        last = last_trap

                    if last:
                        line_kpis['last_check_date'] = last['date']
                        line_kpis['last_check_by'] = str(last['operator']).strip() if last['operator'] else "Unknown"

                    line_kpis['maintenance_count'] = status_breakdown['maintenance']
                    combined_equip = sorted(list(traps) + list(bait_stations), key=lambda x: x['code'])

                    # 3. Fetch Assigned Operators
                    cursor.execute("""
                        SELECT u.user_id, u.first_name, u.last_name, u.username
                        FROM operator_lines ol
                        JOIN users u ON ol.user_id = u.user_id
                        WHERE ol.line_id = %s
                        ORDER BY u.first_name ASC
                    """, (selected_line_id,))
                    operators = cursor.fetchall()

                    # 4. Recent Activity for this Line
                    if selected_line_type == 'bait_station':
                        cursor.execute("""
                            SELECT 'bait' as type, bsr.date, u.username, b.bait_station_code as code, 
                                   'Checked' as species_name, l.line_name
                            FROM bait_station_records bsr
                            JOIN users u ON bsr.recorded_by = u.user_id
                            JOIN bait_stations b ON bsr.bait_station_code = b.bait_station_code
                            JOIN lines l ON b.line_id = l.line_id
                            WHERE l.line_id = %s
                            ORDER BY bsr.date DESC LIMIT 5
                        """, (selected_line_id,))
                    else:
                        cursor.execute("""
                            SELECT 'catch' as type, tc.date, u.username, t.trap_code as code, 
                                   s.species_name, l.line_name
                            FROM trap_catches tc
                            JOIN users u ON tc.recorded_by = u.user_id
                            JOIN traps t ON tc.trap_code = t.trap_code
                            JOIN lines l ON t.line_id = l.line_id
                            JOIN species s ON tc.species_id = s.species_id
                            WHERE l.line_id = %s
                            ORDER BY tc.date DESC LIMIT 5
                        """, (selected_line_id,))
                    recent_activity = cursor.fetchall()

            boundary_geojson = None
            group_latitude = None
            group_longitude = None
            current_group_id = session.get('current_group_id')
            if not current_group_id and selected_line_id:
                cursor.execute("SELECT group_id FROM lines WHERE line_id = %s", (selected_line_id,))
                ln = cursor.fetchone()
                if ln:
                    current_group_id = ln['group_id']

            if current_group_id:
                cursor.execute("SELECT boundary_geojson, latitude, longitude FROM groups WHERE group_id = %s", (current_group_id,))
                grp = cursor.fetchone()
                if grp:
                    boundary_geojson = grp.get('boundary_geojson')
                    group_latitude = grp.get('latitude')
                    group_longitude = grp.get('longitude')

        return render_template('admin/list_lines.html',
                               lines=lines, 
                               traps=traps, 
                               bait_stations=bait_stations,
                               combined_equip=combined_equip if 'combined_equip' in locals() else [],
                               selected_line_type=selected_line_type, 
                               selected_line_id=selected_line_id,
                               operators=operators, 
                               available_operators=available_operators,
                               is_selected_line_assigned=is_selected_line_assigned,
                               stats=stats,
                               recent_activity=recent_activity,
                               status_breakdown=status_breakdown,
                               line_kpis=line_kpis,
                               boundary_geojson=boundary_geojson,
                               group_latitude=group_latitude,
                               group_longitude=group_longitude)
    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.exception(f"Error viewing lines: {e}")
        flash(f"An error occurred while loading line details: {str(e)}", "danger")
        if selected_line_id:
            return redirect(url_for('observer.view_lines'))
        return redirect(url_for('observer.observer_dashboard'))

