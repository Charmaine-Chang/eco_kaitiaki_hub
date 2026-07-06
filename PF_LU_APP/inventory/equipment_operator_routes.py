from flask import render_template, request, redirect, url_for, flash, session, current_app
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


@operator_bp.route('/edit_trap/<string:trap_code>', methods=['GET', 'POST'])
@roles_required(ROLE_OPERATOR)
def edit_trap(trap_code):
    conn = get_db()
    try:
        with get_cursor_context() as cursor:
            trap = fetch_trap_details_scoped(cursor, trap_code, session.get('current_group_id'))

            if not trap:
                flash("Trap not found or access denied.", "danger")
                return redirect(url_for('operator.view_lines'))

            is_retired = (trap.get('status') == 'inactive' or trap.get('equipment_status_name') == 'Retired')

            if request.method == 'POST':
                if is_retired:
                    flash("The item is no longer in service.", "danger")
                    return redirect(url_for('operator.view_lines'))

                trap_type_id = request.form.get('trap_type_id')
                line_id = request.form.get('line_id')
                storage_area_id = request.form.get('storage_area_id')
                latitude = request.form.get('latitude')
                longitude = request.form.get('longitude')
                equipment_status_name = request.form.get('equipment_status')

                if not trap_type_id or not equipment_status_name or not (line_id or storage_area_id):
                    flash("Please fill out all required fields and choose either a line or a storage area.", "danger")
                    return redirect(url_for('operator.edit_trap', trap_code=trap_code))

                if line_id and storage_area_id:
                    flash("Please select either a line or a storage area, not both.", "danger")
                    return redirect(url_for('operator.edit_trap', trap_code=trap_code))

                if equipment_status_name == 'In Storage' and not storage_area_id:
                    flash("Please select a storage location when moving a trap into storage.", "danger")
                    return redirect(url_for('operator.edit_trap', trap_code=trap_code))

                if equipment_status_name == 'In Storage' and line_id:
                    flash("When moving a trap into storage, clear the line selection and choose a storage area.", "danger")
                    return redirect(url_for('operator.edit_trap', trap_code=trap_code))

                l_id = None
                sa_id = None
                lat = None
                lng = None

                if line_id:
                    cursor.execute("SELECT group_id FROM lines WHERE line_id = %s", (line_id,))
                    new_line = cursor.fetchone()
                    if not new_line or str(new_line['group_id']) != str(session.get('current_group_id')):
                        flash("Unauthorized line assignment.", "danger")
                        return redirect(url_for('operator.edit_trap', trap_code=trap_code))
                    try:
                        l_id = int(line_id)
                        lat = float(latitude)
                        lng = float(longitude)
                    except (ValueError, TypeError):
                        flash("Valid line coordinates and trap type are required.", "danger")
                        return redirect(url_for('operator.edit_trap', trap_code=trap_code))

                if storage_area_id:
                    cursor.execute("SELECT group_id FROM storage_area WHERE storage_area_id = %s", (storage_area_id,))
                    storage_area = cursor.fetchone()
                    if not storage_area or str(storage_area['group_id']) != str(session.get('current_group_id')):
                        flash("Unauthorized storage assignment.", "danger")
                        return redirect(url_for('operator.edit_trap', trap_code=trap_code))
                    try:
                        sa_id = int(storage_area_id)
                    except (ValueError, TypeError):
                        flash("Invalid storage area selected.", "danger")
                        return redirect(url_for('operator.edit_trap', trap_code=trap_code))

                try:
                    t_type_id = int(trap_type_id)
                except (ValueError, TypeError):
                    flash("Invalid trap type selected.", "danger")
                    return redirect(url_for('operator.edit_trap', trap_code=trap_code))

                if l_id is not None:
                    if not validate_location_within_boundary(cursor, session.get('current_group_id'), lat, lng):
                        flash("Cannot update trap: coordinates are outside the group boundary.", "danger")
                        return redirect(url_for('operator.edit_trap', trap_code=trap_code))

                item_status = 'inactive' if equipment_status_name == 'Retired' else 'active'
                equipment_status_id = get_equipment_status_id(cursor, equipment_status_name)
                update_trap_full(cursor, trap_code, t_type_id, l_id, sa_id, lat, lng, equipment_status_id, item_status)
                conn.commit()
                flash("Trap updated successfully!", "success")
                return redirect(url_for('operator.view_lines'))

            lines = fetch_lines_scoped(cursor, session.get('current_group_id'))
            storage_areas = fetch_storage_areas_scoped(cursor, session.get('current_group_id'))
            cursor.execute('SELECT * FROM trap_type ORDER BY trap_type_name ASC')
            trap_types = cursor.fetchall()
            for status_name in ['Active', 'In Storage', 'Under Repair', 'Retired']:
                get_equipment_status_id(cursor, status_name)
            cursor.execute('SELECT * FROM equipment_status ORDER BY equipment_status_name ASC')
            equipment_statuses = cursor.fetchall()

            return render_template(
                'admin/edit_trap.html',
                trap=trap,
                lines=lines,
                storage_areas=storage_areas,
                trap_types=trap_types,
                equipment_statuses=equipment_statuses,
                form_action=url_for('operator.edit_trap', trap_code=trap_code),
                back_url=url_for('operator.view_lines', line_id=trap.get('line_id')),
                is_retired=is_retired
            )
    except Exception as e:
        current_app.logger.exception(f"Error editing trap as operator: {e}")
        flash("An error occurred while updating the trap.", "danger")
        return redirect(url_for('operator.view_lines'))


@operator_bp.route('/edit_bait_station/<string:bait_station_code>', methods=['GET', 'POST'])
@roles_required(ROLE_OPERATOR)
def edit_bait_station(bait_station_code):
    conn = get_db()
    try:
        with get_cursor_context() as cursor:
            bait_station = fetch_bait_station_details_scoped(cursor, bait_station_code, session.get('current_group_id'))

            if not bait_station:
                flash("Bait station not found or access denied.", "danger")
                return redirect(url_for('operator.view_lines'))

            is_retired = (bait_station.get('status') == 'inactive' or bait_station.get('equipment_status_name') == 'Retired')

            if request.method == 'POST':
                if is_retired:
                    flash("The item is no longer in service.", "danger")
                    return redirect(url_for('operator.view_lines'))

                bait_station_type_id = request.form.get('bait_station_type_id')
                line_id = request.form.get('line_id')
                storage_area_id = request.form.get('storage_area_id')
                latitude = request.form.get('latitude')
                longitude = request.form.get('longitude')
                equipment_status_name = request.form.get('equipment_status')

                if not bait_station_type_id or not equipment_status_name or not (line_id or storage_area_id):
                    flash("Please fill out all required fields and choose either a line or a storage area.", "danger")
                    return redirect(url_for('operator.edit_bait_station', bait_station_code=bait_station_code))

                if line_id and storage_area_id:
                    flash("Please select either a line or a storage area, not both.", "danger")
                    return redirect(url_for('operator.edit_bait_station', bait_station_code=bait_station_code))

                if equipment_status_name == 'In Storage' and not storage_area_id:
                    flash("Please select a storage location when moving a bait station into storage.", "danger")
                    return redirect(url_for('operator.edit_bait_station', bait_station_code=bait_station_code))

                if equipment_status_name == 'In Storage' and line_id:
                    flash("When moving a bait station into storage, clear the line selection and choose a storage area.", "danger")
                    return redirect(url_for('operator.edit_bait_station', bait_station_code=bait_station_code))

                l_id = None
                sa_id = None
                lat = None
                lng = None

                if line_id:
                    cursor.execute("SELECT group_id FROM lines WHERE line_id = %s", (line_id,))
                    new_line = cursor.fetchone()
                    if not new_line or str(new_line['group_id']) != str(session.get('current_group_id')):
                        flash("Unauthorized line assignment.", "danger")
                        return redirect(url_for('operator.edit_bait_station', bait_station_code=bait_station_code))
                    try:
                        l_id = int(line_id)
                        lat = float(latitude)
                        lng = float(longitude)
                    except (ValueError, TypeError):
                        flash("Valid line coordinates and bait station type are required.", "danger")
                        return redirect(url_for('operator.edit_bait_station', bait_station_code=bait_station_code))

                if storage_area_id:
                    cursor.execute("SELECT group_id FROM storage_area WHERE storage_area_id = %s", (storage_area_id,))
                    storage_area = cursor.fetchone()
                    if not storage_area or str(storage_area['group_id']) != str(session.get('current_group_id')):
                        flash("Unauthorized storage assignment.", "danger")
                        return redirect(url_for('operator.edit_bait_station', bait_station_code=bait_station_code))
                    try:
                        sa_id = int(storage_area_id)
                    except (ValueError, TypeError):
                        flash("Invalid storage area selected.", "danger")
                        return redirect(url_for('operator.edit_bait_station', bait_station_code=bait_station_code))

                try:
                    bs_type_id = int(bait_station_type_id)
                except (ValueError, TypeError):
                    flash("Invalid bait station type selected.", "danger")
                    return redirect(url_for('operator.edit_bait_station', bait_station_code=bait_station_code))

                if l_id is not None:
                    if not validate_location_within_boundary(cursor, session.get('current_group_id'), lat, lng):
                        flash("Cannot update bait station: coordinates are outside the group boundary.", "danger")
                        return redirect(url_for('operator.edit_bait_station', bait_station_code=bait_station_code))

                item_status = 'inactive' if equipment_status_name == 'Retired' else 'active'
                equipment_status_id = get_equipment_status_id(cursor, equipment_status_name)
                update_bait_station_full(cursor, bait_station_code, bs_type_id, l_id, sa_id, lat, lng, equipment_status_id, item_status)
                conn.commit()
                flash("Bait station updated successfully!", "success")
                return redirect(url_for('operator.view_lines'))

            lines = fetch_lines_scoped(cursor, session.get('current_group_id'))
            storage_areas = fetch_storage_areas_scoped(cursor, session.get('current_group_id'))
            cursor.execute('SELECT * FROM bait_station_type ORDER BY bait_station_type_name ASC')
            bait_station_types = cursor.fetchall()
            for status_name in ['Active', 'In Storage', 'Under Repair', 'Retired']:
                get_equipment_status_id(cursor, status_name)
            cursor.execute('SELECT * FROM equipment_status ORDER BY equipment_status_name ASC')
            equipment_statuses = cursor.fetchall()

            return render_template(
                'admin/edit_bait_station.html',
                bait_station=bait_station,
                lines=lines,
                storage_areas=storage_areas,
                bait_station_types=bait_station_types,
                equipment_statuses=equipment_statuses,
                form_action=url_for('operator.edit_bait_station', bait_station_code=bait_station_code),
                back_url=url_for('operator.view_lines', line_id=bait_station.get('line_id')),
                is_retired=is_retired
            )
    except Exception as e:
        current_app.logger.exception(f"Error editing bait station as operator: {e}")
        flash("An error occurred while updating the bait station.", "danger")
        return redirect(url_for('operator.view_lines'))


@operator_bp.route('/action_retire_trap/<string:trap_code>', methods=['POST'])
@roles_required(ROLE_OPERATOR)
def action_retire_trap(trap_code):
    conn = get_db()
    try:
        with get_cursor_context() as cursor:
            cursor.execute("""
                SELECT l.group_id
                FROM traps t
                JOIN lines l ON t.line_id = l.line_id
                WHERE t.trap_code = %s
            """, (trap_code,))
            res = cursor.fetchone()
            if not res or str(res['group_id']) != str(session.get('current_group_id')):
                flash("Access denied.", "danger")
                return redirect(url_for('operator.view_lines'))

            retired_status_id = get_equipment_status_id(cursor, 'Retired')
            cursor.execute("UPDATE traps SET status = 'inactive', equipment_status_id = %s WHERE trap_code = %s", (retired_status_id, trap_code))
            conn.commit()
            flash(f"Trap {trap_code} was successfully retired.", "success")
    except Exception as e:
        current_app.logger.exception(f"Error retiring trap as operator: {e}")
        flash(f"Error retiring trap: {e}", "danger")
    return redirect(url_for('operator.view_lines'))


@operator_bp.route('/action_retire_bait_station/<string:bait_station_code>', methods=['POST'])
@roles_required(ROLE_OPERATOR)
def action_retire_bait_station(bait_station_code):
    conn = get_db()
    try:
        with get_cursor_context() as cursor:
            cursor.execute("""
                SELECT l.group_id
                FROM bait_stations b
                JOIN lines l ON b.line_id = l.line_id
                WHERE b.bait_station_code = %s
            """, (bait_station_code,))
            res = cursor.fetchone()
            if not res or str(res['group_id']) != str(session.get('current_group_id')):
                flash("Access denied.", "danger")
                return redirect(url_for('operator.view_lines'))

            retired_status_id = get_equipment_status_id(cursor, 'Retired')
            cursor.execute("UPDATE bait_stations SET status = 'inactive', equipment_status_id = %s WHERE bait_station_code = %s", (retired_status_id, bait_station_code))
            conn.commit()
            flash(f"Bait station {bait_station_code} was successfully retired.", "success")
    except Exception as e:
        current_app.logger.exception(f"Error retiring bait station as operator: {e}")
        flash(f"Error retiring bait station: {e}", "danger")
    return redirect(url_for('operator.view_lines'))
