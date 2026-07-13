"""Admin routes for line management: view, create, edit, retire, restore, and retired assets view."""

from flask import render_template, request, redirect, url_for, flash, session, current_app
from PF_LU_APP.db import get_db, get_cursor, get_cursor_context
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.shared.permissions import get_equipment_status_id
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, EquipmentStatus, ROLE_OPERATOR, ROLE_OBSERVER


@admin_bp.route('/lines')
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def view_lines():

    view_all = request.args.get('view_all') == 'true' and session.get('is_super_admin')
    current_group_id = session.get('current_group_id')
    selected_line_id = request.args.get('line_id')

    if not current_group_id and not view_all:
        flash("Please enter a group context first (Home → Enter Group).", "info")
        return redirect(url_for('admin.admin_dashboard'))

    lines = []
    traps = []
    bait_stations = []
    operators = []
    available_operators = []
    selected_line_type = 'trap'
    is_selected_line_assigned = False
    boundary_geojson = None
    group_latitude = None
    group_longitude = None

    stats = {'total_active_lines': 0, 'total_equipment': 0, 'last_sync': None}
    recent_activity = []
    status_breakdown = {'functional': 0, 'maintenance': 0}

    line_kpis = {
        'health_score': 0,
        'last_check_date': None,
        'last_check_by': None,
        'maintenance_count': 0
    }

    try:
        with get_cursor_context() as cursor:

            is_global_view = False
            if current_group_id:
                cursor.execute("SELECT group_name FROM `groups` WHERE group_id = %s", (current_group_id,))
                g_res = cursor.fetchone()
                if g_res and g_res['group_name'] == 'System Management':
                    is_global_view = True

            query = """
                SELECT l.*, g.group_name,
                       (SELECT COUNT(*) FROM traps t WHERE t.line_id = l.line_id AND (t.status = 'active' OR t.status IS NULL)) as trap_count,
                       (SELECT COUNT(*) FROM bait_stations b WHERE b.line_id = l.line_id AND (b.status = 'active' OR b.status IS NULL)) as station_count,
                       (SELECT GROUP_CONCAT(CONCAT(u.first_name, ' ', u.last_name) ORDER BY u.first_name SEPARATOR ', ')
                        FROM operator_lines ol2
                        JOIN users u ON ol2.user_id = u.user_id
                        WHERE ol2.line_id = l.line_id) AS operator_names,
                       EXISTS (SELECT 1 FROM operator_lines ol3 WHERE ol3.line_id = l.line_id AND ol3.user_id = %s) AS is_assigned
                FROM `lines` l
                JOIN `groups` g ON l.group_id = g.group_id
            """
            params = [session.get('user_id')]

            if view_all or is_global_view:
                query += " WHERE l.status = 'active' ORDER BY g.group_name ASC, l.line_name ASC"
            else:
                query += " WHERE l.group_id = %s AND l.status = 'active' ORDER BY l.line_name ASC"
                params.append(current_group_id)

            cursor.execute(query, params)
            lines = cursor.fetchall()
            stats['total_active_lines'] = len(lines)

            if not selected_line_id:
                if is_global_view or not current_group_id:
                    cursor.execute("SELECT COUNT(*) as count FROM `lines` WHERE status = 'active'")
                    stats['total_active_lines'] = cursor.fetchone()['count']

                    cursor.execute("""
                        SELECT
                            (SELECT COUNT(*) FROM traps WHERE status = 'active') +
                            (SELECT COUNT(*) FROM bait_stations WHERE status = 'active')
                        as count
                    """)
                    stats['total_equipment'] = cursor.fetchone()['count']

                    cursor.execute("""
                        SELECT 'catch' as type, tc.`date`, u.username, t.trap_code as code, s.species_name, s.species_color, l.line_name
                        FROM trap_catches tc
                        JOIN traps t ON tc.trap_code = t.trap_code
                        JOIN `lines` l ON t.line_id = l.line_id
                        JOIN users u ON tc.recorded_by = u.user_id
                        JOIN species s ON tc.species_id = s.species_id
                        ORDER BY tc.`date` DESC LIMIT 15
                    """)
                    recent_activity = cursor.fetchall()

                    if recent_activity:
                        stats['last_sync'] = recent_activity[0]['date']
                elif current_group_id:
                    cursor.execute("SELECT COUNT(*) as count FROM `lines` WHERE group_id = %s AND status = 'active'", (current_group_id,))
                    stats['total_active_lines'] = cursor.fetchone()['count']

                    cursor.execute("""
                        SELECT
                            (SELECT COUNT(*) FROM traps t JOIN `lines` l ON t.line_id = l.line_id WHERE l.group_id = %s AND t.status = 'active') +
                            (SELECT COUNT(*) FROM bait_stations b JOIN `lines` l ON b.line_id = l.line_id WHERE l.group_id = %s AND b.status = 'active')
                        as count
                    """, (current_group_id, current_group_id))
                    stats['total_equipment'] = cursor.fetchone()['count']

                    cursor.execute("""
                        SELECT 'catch' as type, tc.`date`, u.username, t.trap_code as code, s.species_name, s.species_color, l.line_name
                        FROM trap_catches tc
                        JOIN traps t ON tc.trap_code = t.trap_code
                        JOIN `lines` l ON t.line_id = l.line_id
                        JOIN users u ON tc.recorded_by = u.user_id
                        JOIN species s ON tc.species_id = s.species_id
                        WHERE l.group_id = %s
                        ORDER BY tc.`date` DESC LIMIT 15
                    """, (current_group_id,))
                    recent_activity = cursor.fetchall()

                    if recent_activity:
                        stats['last_sync'] = recent_activity[0]['date']

            selected_line_group_id = None
            if selected_line_id:
                for l in lines:
                    if str(l['line_id']) == str(selected_line_id):
                        selected_line_type = l.get('line_type', 'trap')
                        is_selected_line_assigned = bool(l.get('is_assigned'))
                        selected_line_group_id = l.get('group_id')
                        break

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
                    if s['status'] and s['status'].lower() in EquipmentStatus.healthy_states():
                        status_breakdown['functional'] += 1
                    else:
                        status_breakdown['maintenance'] += 1

                for t in traps:
                    if t['status'] and t['status'].lower() in EquipmentStatus.healthy_states():
                        status_breakdown['functional'] += 1
                    else:
                        status_breakdown['maintenance'] += 1

                cursor.execute("""
                    SELECT COUNT(DISTINCT bait_station_code) as checked_count
                    FROM bait_station_records
                    WHERE date >= CURRENT_DATE - INTERVAL 7 DAY
                    AND bait_station_code IN (SELECT bait_station_code FROM bait_stations WHERE line_id = %s)
                """, (selected_line_id,))
                checked_stations = cursor.fetchone()['checked_count'] or 0

                cursor.execute("""
                    SELECT COUNT(DISTINCT trap_code) as checked_count
                    FROM trap_catches
                    WHERE date >= CURRENT_DATE - INTERVAL 7 DAY
                    AND trap_code IN (SELECT trap_code FROM traps WHERE line_id = %s)
                """, (selected_line_id,))
                checked_traps = cursor.fetchone()['checked_count'] or 0

                total_nodes = len(bait_stations) + len(traps)
                total_checked = checked_stations + checked_traps
                line_kpis['health_score'] = int((total_checked / total_nodes * 100)) if total_nodes > 0 else 0

                cursor.execute("""
                    SELECT bsr.`date`, CONCAT(COALESCE(u.first_name, u.username), ' ', COALESCE(u.last_name, '')) as operator
                    FROM bait_station_records bsr
                    JOIN users u ON bsr.recorded_by = u.user_id
                    WHERE bsr.bait_station_code IN (SELECT bait_station_code FROM bait_stations WHERE line_id = %s)
                    ORDER BY bsr.`date` DESC LIMIT 1
                """, (selected_line_id,))
                last_station = cursor.fetchone()

                cursor.execute("""
                    SELECT tc.`date`, CONCAT(COALESCE(u.first_name, u.username), ' ', COALESCE(u.last_name, '')) as operator
                    FROM trap_catches tc
                    JOIN users u ON tc.recorded_by = u.user_id
                    WHERE tc.trap_code IN (SELECT trap_code FROM traps WHERE line_id = %s)
                    ORDER BY tc.`date` DESC LIMIT 1
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
                    line_kpis['last_check_by'] = last['operator'].strip()

                line_kpis['maintenance_count'] = status_breakdown['maintenance']
                combined_equip = sorted(list(traps) + list(bait_stations), key=lambda x: x['code'])

                cursor.execute("""
                    SELECT u.user_id, u.first_name, u.last_name, u.username
                    FROM operator_lines ol
                    JOIN users u ON ol.user_id = u.user_id
                    WHERE ol.line_id = %s
                    ORDER BY u.first_name ASC
                """, (selected_line_id,))
                operators = cursor.fetchall()

                if selected_line_group_id:
                    cursor.execute("""
                        SELECT u.user_id, u.first_name, u.last_name, u.username
                        FROM users u
                        JOIN group_membership gm ON u.user_id = gm.user_id
                        JOIN roles r ON gm.role_id = r.role_id
                        WHERE gm.group_id = %s AND gm.membership_status = 'active' AND u.status = 'Active' AND r.role_name = 'Operator'
                          AND NOT EXISTS (SELECT 1 FROM operator_lines ol WHERE ol.user_id = u.user_id AND ol.line_id = %s)
                        ORDER BY u.first_name ASC
                    """, (selected_line_group_id, selected_line_id))
                    available_operators = cursor.fetchall()

            boundary_geojson = None
            group_latitude = None
            group_longitude = None
            map_group_id = selected_line_group_id if (is_global_view and selected_line_id) else current_group_id
            if map_group_id:
                cursor.execute("SELECT boundary_geojson, latitude, longitude FROM `groups` WHERE group_id = %s", (map_group_id,))
                grp = cursor.fetchone()
                if grp:
                    boundary_geojson = grp.get('boundary_geojson')
                    group_latitude = grp.get('latitude')
                    group_longitude = grp.get('longitude')

    except Exception as e:
        current_app.logger.exception(f"Error viewing lines: {e}")
        flash("Could not load line details.", "danger")

    return render_template(
        'admin/list_lines.html',
        lines=lines,
        traps=traps,
        bait_stations=bait_stations,
        combined_equip=combined_equip if 'combined_equip' in locals() else [],
        selected_line_id=selected_line_id,
        selected_line_type=selected_line_type,
        operators=operators,
        available_operators=available_operators,
        is_selected_line_assigned=is_selected_line_assigned,
        stats=stats,
        recent_activity=recent_activity,
        status_breakdown=status_breakdown,
        line_kpis=line_kpis,
        boundary_geojson=boundary_geojson,
        group_latitude=group_latitude,
        group_longitude=group_longitude
    )


@admin_bp.route('/create_new_lines', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def create_new_lines():

    current_group_id = session.get('current_group_id')

    if request.method == 'POST':
        line_name = request.form.get('line_name')
        line_type = request.form.get('line_type')
        status = request.form.get('status')

        if not line_name or not line_type or not status:
            flash("Please fill out all required fields.", "danger")
            return redirect(url_for('admin.create_new_lines'))

        status = status.lower()

        try:
            conn = get_db()
            with get_cursor_context() as cursor:

                if not session.get('is_super_admin'):
                    cursor.execute('SELECT line_id FROM `lines` WHERE line_name LIKE %s AND group_id = %s', (line_name, current_group_id))
                else:
                    cursor.execute('SELECT line_id FROM `lines` WHERE line_name LIKE %s', (line_name,))

                if cursor.fetchone():
                    flash(f"A {line_type} line with the name '{line_name}' already exists.", "danger")
                    return redirect(url_for('admin.create_new_lines'))

                target_group_id = current_group_id if current_group_id else 1

                cursor.execute('INSERT INTO `lines` (line_name, line_type, status, group_id) VALUES (%s, %s, %s, %s)',
                               (line_name, line_type, status, target_group_id))
                conn.commit()

                flash(f"{line_type.replace('_', ' ').title()} line created successfully!", "success")
                return redirect(url_for('admin.create_new_lines'))

        except Exception as e:
            current_app.logger.exception(f"Database error: {e}")
            flash(f"An error occurred while creating the {line_type} line.", "danger")

    trap_lines = []
    try:
        with get_cursor_context() as cursor:
            if not session.get('is_super_admin'):
                cursor.execute('SELECT * FROM `lines` WHERE group_id = %s ORDER BY created_at DESC', (current_group_id,))
            else:
                cursor.execute('SELECT * FROM `lines` ORDER BY created_at DESC')
            trap_lines = cursor.fetchall()
    except Exception as e:
        current_app.logger.exception(f"Error fetching existing lines: {e}")

    return render_template('admin/create_line.html', trap_lines=trap_lines)


@admin_bp.route('/edit_line/<int:line_id>', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def edit_line(line_id):
    try:
        conn = get_db()
        with get_cursor_context() as cursor:

            current_group_id = session.get('current_group_id')
            is_super = session.get('is_super_admin')

            cursor.execute("SELECT * FROM `lines` WHERE line_id = %s", (line_id,))
            line = cursor.fetchone()

            if not line or (not is_super and str(line['group_id']) != str(current_group_id)):
                flash("Access denied or line not found.", "danger")
                return redirect(url_for('admin.view_lines'))

            if request.method == 'POST':
                line_name = request.form.get('line_name')
                line_type = request.form.get('line_type')
                status = request.form.get('status')

                if not line_name or not line_type or not status:
                    flash("Please fill out all required fields.", "danger")
                    return redirect(url_for('admin.edit_line', line_id=line_id))

                status = status.lower()
                valid_types = ['trap', 'bait_station']
                if line_type not in valid_types:
                    flash("Invalid line type submitted.", "danger")
                    return redirect(url_for('admin.edit_line', line_id=line_id))

                cursor.execute('SELECT line_id FROM `lines` WHERE line_name LIKE %s AND line_id != %s AND group_id = %s',
                               (line_name, line_id, line['group_id']))
                if cursor.fetchone():
                    flash(f"Another line with the name '{line_name}' already exists in this group.", "danger")
                    return redirect(url_for('admin.edit_line', line_id=line_id))

                cursor.execute(
                    'UPDATE `lines` SET line_name = %s, line_type = %s, status = %s WHERE line_id = %s',
                    (line_name, line_type, status, line_id),
                )

                if status == 'inactive':
                    cursor.execute("UPDATE traps SET status = 'inactive' WHERE line_id = %s", (line_id,))
                    cursor.execute("UPDATE bait_stations SET status = 'inactive' WHERE line_id = %s", (line_id,))

                conn.commit()
                flash("Line updated successfully!", "success")
                return redirect(url_for('admin.view_lines'))


            if not line:
                flash("Line not found.", "danger")
                return redirect(url_for('admin.view_lines'))

            return render_template('admin/edit_line.html', line=line)

    except Exception as e:
        current_app.logger.exception(f"Database error: {e}")
        flash("An error occurred while editing the line.", "danger")
        return redirect(url_for('admin.create_new_lines'))


@admin_bp.route('/action_retire_line/<int:line_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def action_retire_line(line_id):
    try:
        conn = get_db()
        with get_cursor_context() as cursor:

            cursor.execute("SELECT group_id FROM `lines` WHERE line_id = %s", (line_id,))
            line = cursor.fetchone()
            if not line or (not session.get('is_super_admin') and str(line['group_id']) != str(session.get('current_group_id'))):
                flash("Access denied.", "danger")
                return redirect(url_for('admin.view_lines'))

            retired_id = get_equipment_status_id(cursor, 'Retired')
            cursor.execute("UPDATE `lines` SET status = 'inactive' WHERE line_id = %s", (line_id,))
            cursor.execute("UPDATE traps SET status = 'inactive', equipment_status_id = %s WHERE line_id = %s", (retired_id, line_id))
            cursor.execute("UPDATE bait_stations SET status = 'inactive', equipment_status_id = %s WHERE line_id = %s", (retired_id, line_id))
            conn.commit()
            flash("Line and all its associated equipment were successfully retired.", "success")
    except Exception as e:
        flash(f"Error retiring line: {e}", "danger")
    return redirect(url_for('admin.view_lines'))


@admin_bp.route('/retired_assets')
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def retired_assets():

    group_id = session.get('current_group_id')
    is_super = session.get('is_super_admin')

    if not group_id and not is_super:
        flash("Please select a group first.", "info")
        return redirect(url_for('admin.admin_dashboard'))

    try:
        with get_cursor_context() as cursor:

            current_group_name = "Global View"
            if group_id:
                cursor.execute("SELECT group_name FROM `groups` WHERE group_id = %s", (group_id,))
                res = cursor.fetchone()
                if res:
                    current_group_name = res['group_name']

            line_query = """
                SELECT l.*,
                       (SELECT COUNT(*) FROM traps t WHERE t.line_id = l.line_id) as trap_count,
                       (SELECT COUNT(*) FROM bait_stations b WHERE b.line_id = l.line_id) as bait_station_count
                FROM `lines` l
                WHERE l.status = 'inactive'
            """
            line_params = []
            if not is_super or group_id:
                line_query += " AND l.group_id = %s"
                line_params.append(group_id)

            line_query += " ORDER BY l.line_name ASC"
            cursor.execute(line_query, tuple(line_params))
            retired_lines = cursor.fetchall()

            for line in retired_lines:
                equipment_info = []
                if line['trap_count'] > 0:
                    equipment_info.append(f"{line['trap_count']} traps")
                if line['bait_station_count'] > 0:
                    equipment_info.append(f"{line['bait_station_count']} bait stations")

                if equipment_info:
                    line['line_name'] = f"{line['line_name']} ({', '.join(equipment_info)})"
                else:
                    line['line_name'] = f"{line['line_name']} (No equipment)"

            trap_query = """
                SELECT t.trap_code, tt.trap_type_name, l.line_name, t.latitude, t.longitude
                FROM traps t
                JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
                JOIN `lines` l ON t.line_id = l.line_id
                WHERE (t.status = 'inactive' OR l.status = 'inactive')
            """
            trap_params = []
            if not is_super or group_id:
                trap_query += " AND l.group_id = %s"
                trap_params.append(group_id)

            trap_query += " ORDER BY t.trap_code ASC"
            cursor.execute(trap_query, tuple(trap_params))
            retired_traps = cursor.fetchall()

            bs_query = """
                SELECT b.bait_station_code, bt.bait_station_type_name, l.line_name, b.latitude, b.longitude
                FROM bait_stations b
                JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
                JOIN `lines` l ON b.line_id = l.line_id
                WHERE (b.status = 'inactive' OR l.status = 'inactive')
            """
            bs_params = []
            if not is_super or group_id:
                bs_query += " AND l.group_id = %s"
                bs_params.append(group_id)

            bs_query += " ORDER BY b.bait_station_code ASC"
            cursor.execute(bs_query, tuple(bs_params))
            retired_bait_stations = cursor.fetchall()

            return render_template('admin/list_retired.html',
                                   retired_lines=retired_lines,
                                   retired_traps=retired_traps,
                                   retired_bait_stations=retired_bait_stations,
                                   current_group_name=current_group_name)
    except Exception as e:
        current_app.logger.exception(f"Error fetching retired assets: {e}")
        flash("Error loading retired assets.", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/action_restore_line/<int:line_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def action_restore_line(line_id):
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            cursor.execute("UPDATE `lines` SET status = 'active' WHERE line_id = %s", (line_id,))
            conn.commit()
        flash("Line was successfully restored.", "success")
    except Exception as e:
        current_app.logger.exception(f"Error restoring line: {e}")
        flash("An error occurred while restoring the line.", "danger")
    return redirect(url_for('admin.retired_assets'))
