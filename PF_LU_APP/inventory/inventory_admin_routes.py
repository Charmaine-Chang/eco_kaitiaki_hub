from flask import render_template, request, redirect, url_for, flash, session, current_app, jsonify
from PF_LU_APP.db import get_db, get_cursor, get_cursor_context
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.shared.permissions import get_equipment_status_id
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER
from PF_LU_APP.inventory.utils import fetch_consumable_stock, log_inventory_action, format_location
from PF_LU_APP.inventory.inventory_repository import fetch_stored_equipment as repo_stored_equipment, merge_or_create_item

@admin_bp.route('/inventory')
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER)
def view_inventory():
    group_id = session.get('current_group_id')
    if not group_id and not session.get('is_super_admin'):
        flash("Please select a group first.", "warning")
        return redirect(url_for('main.home'))
        
    search_query = request.args.get('search', '').strip()
    line_filter = request.args.get('line_id')

    try:
        with get_cursor_context() as cursor:
            if group_id:
                cursor.execute("SELECT line_id, line_name FROM `lines` WHERE group_id = %s AND status = 'active' ORDER BY line_name", (group_id,))
            else:
                cursor.execute("SELECT line_id, line_name FROM `lines` WHERE status = 'active' ORDER BY line_name")
            all_lines = cursor.fetchall()

            page = request.args.get('page', 1, type=int)
            per_page = 20
            offset = (page - 1) * per_page

            trap_select = """
                SELECT t.trap_code as code, tt.trap_type_name as type, l.line_name, l.line_id, sa.storage_area_name, sa.storage_area_id, t.latitude, t.longitude,
                       'trap' as equip_type, t.status, es.equipment_status_name as equipment_status_name
                FROM traps t
                JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
                LEFT JOIN `lines` l ON t.line_id = l.line_id
                LEFT JOIN storage_area sa ON t.storage_area_id = sa.storage_area_id
                LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
            """
            
            bs_select = """
                SELECT b.bait_station_code as code, bt.bait_station_type_name as type, l.line_name, l.line_id, sa.storage_area_name, sa.storage_area_id, b.latitude, b.longitude,
                       'bait_station' as equip_type, b.status, es.equipment_status_name as equipment_status_name
                FROM bait_stations b
                JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
                LEFT JOIN `lines` l ON b.line_id = l.line_id
                LEFT JOIN storage_area sa ON b.storage_area_id = sa.storage_area_id
                LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
            """

            where_clauses = ""
            params = []

            if group_id:
                trap_select += " WHERE (l.group_id = %s OR sa.group_id = %s)"
                bs_select += " WHERE (l.group_id = %s OR sa.group_id = %s)"
                params.extend([group_id, group_id, group_id, group_id])
            else:
                trap_select += " WHERE 1=1"
                bs_select += " WHERE 1=1"

            if search_query:
                where_clauses += " AND code LIKE %s"
                params.append(f'%{search_query}%')
            if line_filter:
                where_clauses += " AND line_id = %s"
                params.append(line_filter)

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
            
            stored_inventory = repo_stored_equipment(group_id)

            cursor.execute("SELECT equipment_status_name FROM equipment_status ORDER BY equipment_status_name")
            equipment_statuses = cursor.fetchall()

            # Consumable stock (bait, toxins) for display on the inventory page
            consumables = fetch_consumable_stock(cursor, group_id)
            
        return render_template('admin/list_inventory.html', 
                               inventory=inventory, 
                               stored_inventory=stored_inventory,
                               consumables=consumables,
                               all_lines=all_lines, 
                               equipment_statuses=equipment_statuses,
                               search_query=search_query, 
                               line_filter=line_filter,
                               page=page,
                               total_pages=total_pages)
    except Exception as e:
        import traceback
        current_app.logger.exception(f"Inventory error: {e}")
        traceback.print_exc()
        flash("Error loading inventory.", "danger")
        return redirect(url_for('admin.view_lines'))

@admin_bp.route('/inventory/update_status', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def update_equipment_status():
    group_id = session.get('current_group_id')
    is_super_admin = session.get('is_super_admin')
    if not group_id and not is_super_admin:
        flash("Please select a group first.", "warning")
        return redirect(url_for('main.home'))

    equip_type = request.form.get('equip_type')
    code = request.form.get('code')
    equipment_status = request.form.get('equipment_status')

    if equip_type not in ('trap', 'bait_station') or not code or not equipment_status:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({'status': 'error', 'message': "Invalid equipment status update request."}), 400
        flash("Invalid equipment status update request.", "danger")
        return redirect(url_for('admin.view_inventory'))

    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            if equip_type == 'trap':
                if is_super_admin and not group_id:
                    cursor.execute(
                        """
                            SELECT t.trap_code, t.status AS current_status, es.equipment_status_name AS current_status_name
                            FROM traps t
                            LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
                            WHERE t.trap_code = %s
                        """,
                        (code,),
                    )
                else:
                    cursor.execute(
                        """
                            SELECT t.trap_code, t.status AS current_status, es.equipment_status_name AS current_status_name
                            FROM traps t
                            LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
                            LEFT JOIN `lines` l ON t.line_id = l.line_id
                            LEFT JOIN storage_area sa ON t.storage_area_id = sa.storage_area_id
                            WHERE t.trap_code = %s AND (l.group_id = %s OR sa.group_id = %s)
                        """,
                        (code, group_id, group_id),
                    )
            else:
                if is_super_admin and not group_id:
                    cursor.execute(
                        """
                            SELECT b.bait_station_code, b.status AS current_status, es.equipment_status_name AS current_status_name
                            FROM bait_stations b
                            LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
                            WHERE b.bait_station_code = %s
                        """,
                        (code,),
                    )
                else:
                    cursor.execute(
                        """
                            SELECT b.bait_station_code, b.status AS current_status, es.equipment_status_name AS current_status_name
                            FROM bait_stations b
                            LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
                            LEFT JOIN `lines` l ON b.line_id = l.line_id
                            LEFT JOIN storage_area sa ON b.storage_area_id = sa.storage_area_id
                            WHERE b.bait_station_code = %s AND (l.group_id = %s OR sa.group_id = %s)
                        """,
                        (code, group_id, group_id),
                    )

            item = cursor.fetchone()
            if not item:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                    return jsonify({'status': 'error', 'message': "Access denied."}), 403
                flash("Access denied.", "danger")
                return redirect(url_for('admin.view_inventory'))

            old_status_name = item['current_status_name'] if item['current_status_name'] else item['current_status']
            if old_status_name == 'Retired' or item['current_status'] == 'inactive':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                    return jsonify({'status': 'error', 'message': "The item is no longer in service."}), 400
                flash("The item is no longer in service.", "danger")
                return redirect(url_for('admin.view_inventory'))
                
            latitude = request.form.get('latitude', '').strip()
            longitude = request.form.get('longitude', '').strip()
            latitude_val = None
            longitude_val = None

            if equipment_status == 'Deployed':
                if not latitude or not longitude:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                        return jsonify({'status': 'error', 'message': "Coordinates are required when setting equipment to Deployed."}), 400
                    flash("Coordinates are required when setting equipment to Deployed.", "danger")
                    return redirect(url_for('admin.view_inventory'))
                try:
                    latitude_val = float(latitude)
                    longitude_val = float(longitude)
                except ValueError:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                        return jsonify({'status': 'error', 'message': "Coordinates must be valid numbers."}), 400
                    flash("Coordinates must be valid numbers.", "danger")
                    return redirect(url_for('admin.view_inventory'))
                if latitude_val == 0 and longitude_val == 0:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                        return jsonify({'status': 'error', 'message': "Coordinates cannot be 0,0 when deploying equipment. Please enter a valid location."}), 400
                    flash("Coordinates cannot be 0,0 when deploying equipment. Please enter a valid location.", "danger")
                    return redirect(url_for('admin.view_inventory'))
            elif old_status_name == 'Deployed' and equipment_status != 'Deployed':
                latitude_val = 0
                longitude_val = 0
            elif latitude or longitude:
                if not latitude or not longitude:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                        return jsonify({'status': 'error', 'message': "Please provide both latitude and longitude to update coordinates."}), 400
                    flash("Please provide both latitude and longitude to update coordinates.", "danger")
                    return redirect(url_for('admin.view_inventory'))
                try:
                    latitude_val = float(latitude)
                    longitude_val = float(longitude)
                except ValueError:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                        return jsonify({'status': 'error', 'message': "Coordinates must be valid numbers."}), 400
                    flash("Coordinates must be valid numbers.", "danger")
                    return redirect(url_for('admin.view_inventory'))

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
        current_app.logger.exception(f"Error updating equipment status: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({'status': 'error', 'message': "Unable to update equipment status."}), 500
        flash("Unable to update equipment status.", "danger")
    return redirect(url_for('admin.view_inventory'))

@admin_bp.route('/inventory/add', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def add_inventory_item():
    group_id = session.get('current_group_id')
    if not group_id:
        flash("Please select a group first.", "warning")
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        item_category = request.form.get('item_category')
        item_name = request.form.get('item_name')
        quantity = request.form.get('quantity')
        threshold = request.form.get('threshold')
        storage_area_id = request.form.get('storage_area_id')

        if not all([item_category, item_name, quantity, threshold]):
            flash("Please fill out all required fields.", "danger")
            return redirect(url_for('admin.add_inventory_item'))

        try:
            quantity = float(quantity)
            threshold = float(threshold)
        except ValueError:
            flash("Quantity and reorder point must be numeric.", "danger")
            return redirect(url_for('admin.add_inventory_item'))

        if quantity < 0 or threshold < 0:
            flash("Quantity and reorder point cannot be negative.", "danger")
            return redirect(url_for('admin.add_inventory_item'))

        # Validate storage area if provided
        storage_area_id_int = None
        storage_area_name = None
        if storage_area_id and storage_area_id.strip():
            try:
                storage_area_id_int = int(storage_area_id)
                # Verify storage area belongs to current group
                with get_cursor_context() as cursor:
                    cursor.execute(
                        "SELECT storage_area_name FROM storage_area WHERE storage_area_id = %s AND group_id = %s",
                        (storage_area_id_int, group_id)
                    )
                    row = cursor.fetchone()
                    if not row:
                        flash("Invalid storage area selected.", "danger")
                        return redirect(url_for('admin.add_inventory_item'))
                    storage_area_name = row['storage_area_name']
            except ValueError:
                flash("Invalid storage area selected.", "danger")
                return redirect(url_for('admin.add_inventory_item'))

        try:
            new_id, merged = merge_or_create_item(
                group_id, item_category, item_name, quantity,
                None, threshold, storage_area_id_int,
            )
            loc = format_location(storage_name=storage_area_name)
            with get_cursor_context() as cursor:
                if merged:
                    log_inventory_action(
                        cursor, group_id, session['user_id'], 'merge', new_id,
                        new_location=loc, details=f'Merged {quantity} into existing: {item_category}: {item_name}',
                    )
                    flash("Item merged with existing stock.", "success")
                else:
                    log_inventory_action(
                        cursor, group_id, session['user_id'], 'create', new_id,
                        new_location=loc, details=f'{item_category}: {item_name}, qty={quantity}',
                    )
                    flash("New inventory item saved successfully.", "success")
            get_db().commit()
            return redirect(url_for('admin.view_inventory'))
        except Exception as e:
            current_app.logger.exception(f"Error adding inventory item: {e}")
            flash("An error occurred while saving the inventory item.", "danger")
            return redirect(url_for('admin.add_inventory_item'))

    stored_items = []
    storage_areas = []
    try:
        with get_cursor_context() as cursor:
            cursor.execute(
                "SELECT item_id, item_category, item_name, quantity, threshold, storage_area_id "
                "FROM inventory_items "
                "WHERE group_id = %s "
                "ORDER BY item_category ASC, item_name ASC",
                (group_id,),
            )
            stored_items = cursor.fetchall()
            
            # Fetch storage areas for dropdown
            cursor.execute(
                "SELECT storage_area_id, storage_area_name FROM storage_area WHERE group_id = %s ORDER BY storage_area_name ASC",
                (group_id,)
            )
            storage_areas = cursor.fetchall()
    except Exception as e:
        current_app.logger.exception(f"Error loading inventory items: {e}")
        flash("Could not load storage inventory.", "warning")

    return render_template('admin/create_inventory_item.html', stored_items=stored_items, storage_areas=storage_areas)
