from flask import render_template, request, redirect, url_for, flash, session, current_app, jsonify
from PF_LU_APP.db import get_db, get_cursor_context
from PF_LU_APP.validators import validate_location_within_boundary
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.roles.operator import operator_bp
from PF_LU_APP.shared.permissions import get_equipment_status_id
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER
from PF_LU_APP.traps.trap_repository import (
    fetch_inventory_for_group,
    fetch_trap_details_simple,
    fetch_equipment_for_status_update,
    update_equipment_status as repo_update_status,
    fetch_trap_types,
    fetch_trap_details_scoped,
    update_trap_full,
    fetch_storage_areas_scoped,
)
from PF_LU_APP.traps.status_repository import (
    fetch_equipment_statuses,
)
from PF_LU_APP.traps.line_repository import (
    fetch_lines_for_group,
    fetch_line_group_id,
    fetch_lines_scoped,
)
from PF_LU_APP.traps.bait_station_repository import (
    fetch_bait_station_details_simple,
    fetch_bait_station_types,
    fetch_bait_station_details_scoped,
    update_bait_station_full,
)


@operator_bp.route('/inventory')
@roles_required(ROLE_OPERATOR)
def view_inventory():
    group_id = session.get('current_group_id')
    if not group_id:
        flash("Please select a group first.", "warning")
        return redirect(url_for('main.home'))

    search_query = request.args.get('search', '').strip()
    line_filter = request.args.get('line_id')

    try:
        with get_cursor_context() as cursor:

            # Fetch all active lines in this group
            cursor.execute("""
                SELECT DISTINCT l.line_id, l.line_name
                FROM `lines` l
                WHERE l.group_id = %s AND l.status = 'active'
                ORDER BY l.line_name
            """, (group_id,))
            operator_lines = cursor.fetchall()

            page = request.args.get('page', 1, type=int)
            per_page = 20
            offset = (page - 1) * per_page

            # Base Trap Query
            trap_select = """
                SELECT t.trap_code as code, tt.trap_type_name as type, l.line_name, l.line_id,
                       t.latitude, t.longitude, 'trap' as equip_type, t.status,
                       es.equipment_status_name as equipment_status_name
                FROM traps t
                JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
                JOIN `lines` l ON t.line_id = l.line_id
                LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
                WHERE l.group_id = %s
            """
            
            # Base Bait Station Query
            bs_select = """
                SELECT b.bait_station_code as code, bt.bait_station_type_name as type, l.line_name, l.line_id,
                       b.latitude, b.longitude, 'bait_station' as equip_type, b.status,
                       es.equipment_status_name as equipment_status_name
                FROM bait_stations b
                JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
                JOIN `lines` l ON b.line_id = l.line_id
                LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
                WHERE l.group_id = %s
            """

            where_clauses = ""
            params = [group_id, group_id]

            if search_query:
                where_clauses += " AND code LIKE %s"
                params.append(f'%{search_query}%')
            if line_filter:
                where_clauses += " AND line_id = %s"
                params.append(line_filter)

            # 1. Get Total Count
            count_query = f"""
                SELECT COUNT(*) as total FROM (
                    {trap_select}
                    UNION ALL
                    {bs_select}
                ) as combined
                WHERE 1=1 {where_clauses}
            """
            cursor.execute(count_query, tuple(params))
            total_items = cursor.fetchone()['total']
            total_pages = (total_items + per_page - 1) // per_page

            # 2. Get Paginated Data
            paginated_query = f"""
                SELECT * FROM (
                    {trap_select}
                    UNION ALL
                    {bs_select}
                ) as combined
                WHERE 1=1 {where_clauses}
                ORDER BY code ASC
                LIMIT %s OFFSET %s
            """
            
            params.extend([per_page, offset])
            cursor.execute(paginated_query, tuple(params))
            inventory = cursor.fetchall()

            cursor.execute("SELECT equipment_status_name FROM equipment_status ORDER BY equipment_status_name")
            equipment_statuses = cursor.fetchall()

            return render_template(
                'operator/inventory.html',
                inventory=inventory,
                all_lines=operator_lines,
                equipment_statuses=equipment_statuses,
                search_query=search_query,
                line_filter=line_filter,
                page=page,
                total_pages=total_pages
            )
    except Exception as e:
        current_app.logger.exception(f"Operator inventory error: {e}")
        flash("Error loading inventory.", "danger")
        return redirect(url_for('operator.operator_dashboard'))


@operator_bp.route('/inventory/update_status', methods=['POST'])
@roles_required(ROLE_OPERATOR)
def update_equipment_status():
    group_id = session.get('current_group_id')
    user_id = session.get('user_id')
    if not group_id:
        flash("Please select a group first.", "warning")
        return redirect(url_for('main.home'))

    equip_type = request.form.get('equip_type')
    code = request.form.get('code')
    equipment_status = request.form.get('equipment_status')

    if equip_type not in ('trap', 'bait_station') or not code or not equipment_status:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({'status': 'error', 'message': "Invalid equipment status update request."}), 400
        flash("Invalid equipment status update request.", "danger")
        return redirect(url_for('operator.view_inventory'))

    try:
        conn = get_db()
        with get_cursor_context() as cursor:

            # Verify the equipment belongs to the group
            if equip_type == 'trap':
                cursor.execute("""
                    SELECT t.trap_code, t.status AS current_status, es.equipment_status_name AS current_status_name
                    FROM traps t
                    LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
                    JOIN `lines` l ON t.line_id = l.line_id
                    WHERE t.trap_code = %s AND l.group_id = %s
                """, (code, group_id))
            else:
                cursor.execute("""
                    SELECT b.bait_station_code, b.status AS current_status, es.equipment_status_name AS current_status_name
                    FROM bait_stations b
                    LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
                    JOIN `lines` l ON b.line_id = l.line_id
                    WHERE b.bait_station_code = %s AND l.group_id = %s
                """, (code, group_id))

            item = cursor.fetchone()
            if not item:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                    return jsonify({'status': 'error', 'message': "Access denied or equipment not found."}), 403
                flash("Access denied or equipment not found.", "danger")
                return redirect(url_for('operator.view_inventory'))

            old_status_name = item['current_status_name'] if item['current_status_name'] else item['current_status']

            if old_status_name == 'Retired' or item['current_status'] == 'inactive':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                    return jsonify({'status': 'error', 'message': "The item is no longer in service."}), 400
                flash("The item is no longer in service.", "danger")
                return redirect(url_for('operator.view_inventory'))
            latitude = request.form.get('latitude', '').strip()
            longitude = request.form.get('longitude', '').strip()
            latitude_val = None
            longitude_val = None

            if equipment_status == 'Deployed':
                if not latitude or not longitude:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                        return jsonify({'status': 'error', 'message': "Coordinates are required when setting equipment to Deployed."}), 400
                    flash("Coordinates are required when setting equipment to Deployed.", "danger")
                    return redirect(url_for('operator.view_inventory'))
                try:
                    latitude_val = float(latitude)
                    longitude_val = float(longitude)
                except ValueError:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                        return jsonify({'status': 'error', 'message': "Coordinates must be valid numbers."}), 400
                    flash("Coordinates must be valid numbers.", "danger")
                    return redirect(url_for('operator.view_inventory'))
                if latitude_val == 0 and longitude_val == 0:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                        return jsonify({'status': 'error', 'message': "Coordinates cannot be 0,0 when deploying equipment."}), 400
                    flash("Coordinates cannot be 0,0 when deploying equipment.", "danger")
                    return redirect(url_for('operator.view_inventory'))
            elif old_status_name == 'Deployed' and equipment_status != 'Deployed':
                latitude_val = 0
                longitude_val = 0
            elif latitude or longitude:
                if not latitude or not longitude:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                        return jsonify({'status': 'error', 'message': "Please provide both latitude and longitude."}), 400
                    flash("Please provide both latitude and longitude.", "danger")
                    return redirect(url_for('operator.view_inventory'))
                try:
                    latitude_val = float(latitude)
                    longitude_val = float(longitude)
                except ValueError:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                        return jsonify({'status': 'error', 'message': "Coordinates must be valid numbers."}), 400
                    flash("Coordinates must be valid numbers.", "danger")
                    return redirect(url_for('operator.view_inventory'))

            status_value = 'inactive' if equipment_status == 'Retired' else 'active'
            status_id = get_equipment_status_id(cursor, equipment_status)
            table_name = 'traps' if equip_type == 'trap' else 'bait_stations'
            code_column = 'trap_code' if equip_type == 'trap' else 'bait_station_code'

            update_sql = f"UPDATE {table_name} SET status = %s, equipment_status_id = %s"
            update_params = [status_value, status_id]
            if latitude_val is not None and longitude_val is not None:
                update_sql += ", latitude = %s, longitude = %s"
                update_params.extend([latitude_val, longitude_val])
            update_sql += f" WHERE {code_column} = %s"
            update_params.append(code)

            cursor.execute(update_sql, tuple(update_params))
            conn.commit()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                return jsonify({'status': 'success', 'message': f"{'Trap' if equip_type == 'trap' else 'Bait station'} status updated to {equipment_status}."}), 200

            flash(f"{'Trap' if equip_type == 'trap' else 'Bait station'} status updated to {equipment_status}.", "success")
    except Exception as e:
        current_app.logger.exception(f"Error updating equipment status as operator: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({'status': 'error', 'message': "Unable to update equipment status."}), 500
        flash("Unable to update equipment status.", "danger")
    return redirect(url_for('operator.view_inventory'))


