from flask import render_template, session, redirect, url_for, request, flash, current_app
import json
from PF_LU_APP.db import get_cursor_context
from PF_LU_APP.roles.operator import operator_bp
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER, EquipmentStatus
from PF_LU_APP.shared.decorators import roles_required

@operator_bp.route('/')
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER)
def operator_dashboard():
    group_id = session.get('current_group_id')
    line_id = request.args.get('line_id', type=int)  # optional filter
    
    try:
        with get_cursor_context() as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
            user = cursor.fetchone()
        
            cursor.execute("""
                SELECT gm.group_id, g.group_name, gm.role_id
                FROM group_membership gm
                JOIN groups g ON gm.group_id = g.group_id
                WHERE gm.user_id = %s AND gm.membership_status = 'active' AND g.status = 'active'
            """, (session['user_id'],))
            memberships = cursor.fetchall()
        
            if not session.get('current_group_id') and len(memberships) == 1:
                session['current_group_id'] = memberships[0]['group_id']
                session['current_group_name'] = memberships[0]['group_name']
                session['role_id'] = memberships[0]['role_id']
                group_id = session.get('current_group_id')

            # ── Dashboard Query ──
            # Observers (4) and Coordinators (2) see ALL lines in the group.
            # Operators (3) see only assigned lines.
            if session.get('role_id') in (ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OBSERVER):
                cursor.execute("""
                    SELECT l.line_id, l.line_name, l.status, l.line_type,
                           CASE WHEN l.line_type = 'bait_station'
                                THEN (SELECT COUNT(*) FROM bait_stations WHERE line_id = l.line_id AND (status = 'active' OR status IS NULL))
                                ELSE (SELECT COUNT(*) FROM traps WHERE line_id = l.line_id AND (status = 'active' OR status IS NULL))
                           END as equipment_count,
                           TRUE as is_assigned
                    FROM lines l
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
                    FROM lines l
                    JOIN operator_lines ol ON l.line_id = ol.line_id
                    WHERE ol.user_id = %s AND l.status = 'active'
                    ORDER BY l.line_name ASC
                """, (session['user_id'],))
            assigned_lines = cursor.fetchall()

            # ---------- Gather map data for the Group Equipment Map ----------
            map_data = []
            centroid_lat = None
            centroid_lng = None
            all_lines = []

            if group_id:
                # Gather traps
                trap_sql = """
                    SELECT t.trap_code AS code,
                           tt.trap_type_name AS type,
                           t.latitude,
                           t.longitude,
                           es.equipment_status_name AS status,
                           (SELECT MAX(tc.date) FROM trap_catches tc WHERE tc.trap_code = t.trap_code) AS last_check
                    FROM traps t
                    JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
                    JOIN lines l ON t.line_id = l.line_id
                    LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
                    WHERE (t.status = 'active' OR t.status IS NULL)
                      AND l.group_id = %s
                """
                params = [group_id]
                if line_id:
                    trap_sql += " AND t.line_id = %s"
                    params.append(line_id)
                cursor.execute(trap_sql, tuple(params))
                traps = cursor.fetchall()

                # Gather bait stations
                bait_sql = """
                    SELECT b.bait_station_code AS code,
                           bt.bait_station_type_name AS type,
                           b.latitude,
                           b.longitude,
                           es.equipment_status_name AS status,
                           (SELECT MAX(bsr.date) FROM bait_station_records bsr WHERE bsr.bait_station_code = b.bait_station_code) AS last_check
                    FROM bait_stations b
                    JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
                    JOIN lines l ON b.line_id = l.line_id
                    LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
                    WHERE (b.status = 'active' OR b.status IS NULL)
                      AND l.group_id = %s
                """
                params = [group_id]
                if line_id:
                    bait_sql += " AND b.line_id = %s"
                    params.append(line_id)
                cursor.execute(bait_sql, tuple(params))
                bait_stations = cursor.fetchall()

                for t in traps:
                    map_data.append({
                        "code": t["code"],
                        "type": "trap",
                        "equipment_type": t["type"],
                        "lat": t["latitude"],
                        "lng": t["longitude"],
                        "last_check": t["last_check"].strftime('%Y-%m-%d') if t["last_check"] else None,
                        "status": t["status"]
                    })
                for b in bait_stations:
                    map_data.append({
                        "code": b["code"],
                        "type": "bait_station",
                        "equipment_type": b["type"],
                        "lat": b["latitude"],
                        "lng": b["longitude"],
                        "last_check": b["last_check"].strftime('%Y-%m-%d') if b["last_check"] else None,
                        "status": b["status"]
                    })

                if map_data:
                    lat_sum = sum(item["lat"] for item in map_data if item["lat"] is not None)
                    lng_sum = sum(item["lng"] for item in map_data if item["lng"] is not None)
                    count = len([item for item in map_data if item["lat"] is not None and item["lng"] is not None])
                    if count:
                        centroid_lat = lat_sum / count
                        centroid_lng = lng_sum / count

                # Gather all lines for filter dropdown
                cursor.execute(
                    """
                    SELECT line_id, line_name FROM lines
                    WHERE group_id = %s AND status = 'active'
                    ORDER BY line_name ASC
                    """,
                    (group_id,)
                )
                all_lines = cursor.fetchall()

                # Fetch group boundary
                cursor.execute("SELECT boundary_geojson FROM groups WHERE group_id = %s", (group_id,))
                g_row = cursor.fetchone()
                boundary_geojson = g_row['boundary_geojson'] if (g_row and g_row['boundary_geojson']) else None
            else:
                boundary_geojson = None

    except Exception as e:
        current_app.logger.exception(f"Error fetching dashboard data: {e}")
        user = {}
        assigned_lines = []
        map_data = []
        all_lines = []
        centroid_lat = None
        centroid_lng = None
        boundary_geojson = None

    return render_template(
        'dashboards/operator_dashboard.html',
        user=user,
        assigned_lines=assigned_lines,
        map_data=json.dumps(map_data),
        all_lines=all_lines,
        selected_line_id=line_id,
        center_lat=centroid_lat,
        center_lng=centroid_lng,
        current_group_boundary_geojson=boundary_geojson
    )

@operator_bp.route('/lines', methods=['GET'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER)
def view_lines():
    current_group_id = session.get('current_group_id')
    if not current_group_id:
        flash("Please select a group context first.", "info")
        return redirect(url_for('operator.operator_dashboard'))

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
            # 1. Fetch Lines with Equipment Counts
            cursor.execute("""
                SELECT l.*, g.group_name,
                       (SELECT COUNT(*) FROM traps t WHERE t.line_id = l.line_id AND (t.status = 'active' OR t.status IS NULL)) as trap_count,
                       (SELECT COUNT(*) FROM bait_stations b WHERE b.line_id = l.line_id AND (b.status = 'active' OR b.status IS NULL)) as station_count,
                       (SELECT STRING_AGG(u.first_name || ' ' || u.last_name, ', ') 
                        FROM operator_lines ol2 
                        JOIN users u ON ol2.user_id = u.user_id 
                        WHERE ol2.line_id = l.line_id) as operator_names,
                       EXISTS (SELECT 1 FROM operator_lines ol3 WHERE ol3.line_id = l.line_id AND ol3.user_id = %s) as is_assigned
                FROM lines l
                JOIN groups g ON l.group_id = g.group_id
                WHERE l.status = 'active' AND l.group_id = %s
                ORDER BY l.line_name ASC
            """, (session['user_id'], current_group_id))
            lines = cursor.fetchall()
        
            # Calculate Global Group Stats
            stats['total_active_lines'] = len(lines)
            stats['total_equipment'] = sum((l['trap_count'] or 0) + (l['station_count'] or 0) for l in lines)

            if not selected_line_id:
                # Global Activity for the group
                cursor.execute("""
                    SELECT 'catch' as type, tc.date, u.username, t.trap_code as code, 
                           s.species_name, l.line_name
                    FROM trap_catches tc
                    JOIN users u ON tc.recorded_by = u.user_id
                    JOIN traps t ON tc.trap_code = t.trap_code
                    JOIN lines l ON t.line_id = l.line_id
                    JOIN species s ON tc.species_id = s.species_id
                    WHERE l.group_id = %s
                    ORDER BY tc.date DESC LIMIT 5
                """, (current_group_id,))
                recent_activity = cursor.fetchall()
                if recent_activity:
                    stats['last_sync'] = recent_activity[0]['date']

            if selected_line_id:
                # Validate selected_line_id is numeric to avoid DB errors
                if not str(selected_line_id).isdigit():
                    flash("Invalid line ID format.", "warning")
                    return redirect(url_for('operator.view_lines'))

                # Find selected line details in the fetched list
                selected_line = next((l for l in lines if str(l['line_id']) == str(selected_line_id)), None)
                if selected_line:
                    is_selected_line_assigned = bool(selected_line.get('is_assigned'))
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
 
                    # 3. Fetch Assigned Operators
                    cursor.execute("""
                        SELECT u.user_id, u.first_name, u.last_name, u.username
                        FROM operator_lines ol
                        JOIN users u ON ol.user_id = u.user_id
                        WHERE ol.line_id = %s
                        ORDER BY u.first_name ASC
                    """, (selected_line_id,))
                    operators = cursor.fetchall()



            boundary_geojson = None
            group_latitude = None
            group_longitude = None
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
        # If we have a line_id, try going back to the general lines page to avoid infinite redirect
        if selected_line_id:
            return redirect(url_for('operator.view_lines'))
        return redirect(url_for('operator.operator_dashboard'))


