from flask import render_template, request, redirect, url_for, flash, session, current_app
from PF_LU_APP.db import get_db, get_cursor_context
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR

@admin_bp.route('/storage_areas', methods=['GET'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def view_storage_areas():
    group_id = session.get('current_group_id')
    if not group_id and not session.get('is_super_admin'):
        flash("Please select a group first.", "warning")
        return redirect(url_for('main.home'))
    
    search_query = request.args.get('search', '').strip()
    
    try:
        with get_cursor_context() as cursor:
            # Fetch all storage areas for the current group (or all if super admin)
            if session.get('is_super_admin') and not group_id:
                query = """
                    SELECT sa.storage_area_id, sa.storage_area_name, 
                           COUNT(DISTINCT ii.item_id) as item_count,
                           COUNT(DISTINCT t.trap_code) as trap_count,
                           COUNT(DISTINCT b.bait_station_code) as bait_station_count
                    FROM storage_area sa
                    LEFT JOIN inventory_items ii ON sa.storage_area_id = ii.storage_area_id
                    LEFT JOIN traps t ON sa.storage_area_id = t.storage_area_id
                    LEFT JOIN bait_stations b ON sa.storage_area_id = b.storage_area_id
                """
                params = []
                if search_query:
                    query += " WHERE sa.storage_area_name ILIKE %s"
                    params.append(f'%{search_query}%')
            else:
                query = """
                    SELECT sa.storage_area_id, sa.storage_area_name, 
                           COUNT(DISTINCT ii.item_id) as item_count,
                           COUNT(DISTINCT t.trap_code) as trap_count,
                           COUNT(DISTINCT b.bait_station_code) as bait_station_count
                    FROM storage_area sa
                    LEFT JOIN inventory_items ii ON sa.storage_area_id = ii.storage_area_id
                    LEFT JOIN traps t ON sa.storage_area_id = t.storage_area_id
                    LEFT JOIN bait_stations b ON sa.storage_area_id = b.storage_area_id
                    WHERE sa.group_id = %s
                """
                params = [group_id]
                if search_query:
                    query += " AND sa.storage_area_name ILIKE %s"
                    params.append(f'%{search_query}%')
            
            query += " GROUP BY sa.storage_area_id, sa.storage_area_name ORDER BY sa.storage_area_name ASC"
            cursor.execute(query, tuple(params))
            storage_areas = cursor.fetchall()
            
        return render_template('admin/list_storage.html',
                               storage_areas=storage_areas,
                               search_query=search_query)
    except Exception as e:
        current_app.logger.exception(f"Error viewing storage areas: {e}")
        flash("Error loading storage areas.", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/storage_areas/create', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def create_storage_area():
    group_id = session.get('current_group_id')
    if not group_id:
        flash("Please select a group first.", "warning")
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        storage_area_name = request.form.get('storage_area_name', '').strip()
        
        # Validation: Check if name is provided
        if not storage_area_name:
            flash("Storage area name is required.", "danger")
            return redirect(url_for('admin.create_storage_area'))
        
        if len(storage_area_name) > 50:
            flash("Storage area name must be 50 characters or less.", "danger")
            return redirect(url_for('admin.create_storage_area'))
        
        try:
            conn = get_db()
            with get_cursor_context() as cursor:
                # Check if a storage area with this name already exists in this group
                cursor.execute(
                    "SELECT storage_area_id FROM storage_area WHERE group_id = %s AND LOWER(storage_area_name) = LOWER(%s)",
                    (group_id, storage_area_name)
                )
                existing = cursor.fetchone()
                
                if existing:
                    flash("A storage area with this name already exists in your group.", "warning")
                    return redirect(url_for('admin.create_storage_area'))
                
                # Create the storage area
                cursor.execute(
                    "INSERT INTO storage_area (group_id, storage_area_name) VALUES (%s, %s) RETURNING storage_area_id",
                    (group_id, storage_area_name)
                )
                new_area = cursor.fetchone()
                conn.commit()
                
            flash(f"Storage area '{storage_area_name}' created successfully!", "success")
            return redirect(url_for('admin.view_storage_areas'))
            
        except Exception as e:
            current_app.logger.exception(f"Error creating storage area: {e}")
            flash("An error occurred while creating the storage area.", "danger")
            return redirect(url_for('admin.create_storage_area'))
    
    return render_template('admin/create_storage.html')


@admin_bp.route('/storage_areas/<int:storage_area_id>/edit', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def edit_storage_area(storage_area_id):
    group_id = session.get('current_group_id')
    if not group_id and not session.get('is_super_admin'):
        flash("Please select a group first.", "warning")
        return redirect(url_for('main.home'))
    
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            # Verify storage area belongs to current group
            cursor.execute(
                "SELECT storage_area_id, storage_area_name, group_id FROM storage_area WHERE storage_area_id = %s",
                (storage_area_id,)
            )
            storage_area = cursor.fetchone()
            
            if not storage_area or (str(storage_area['group_id']) != str(group_id) and not session.get('is_super_admin')):
                flash("Storage area not found or access denied.", "danger")
                return redirect(url_for('admin.view_storage_areas'))
            
            if request.method == 'POST':
                storage_area_name = request.form.get('storage_area_name', '').strip()
                
                # Validation
                if not storage_area_name:
                    flash("Storage area name is required.", "danger")
                    return redirect(url_for('admin.edit_storage_area', storage_area_id=storage_area_id))
                
                if len(storage_area_name) > 50:
                    flash("Storage area name must be 50 characters or less.", "danger")
                    return redirect(url_for('admin.edit_storage_area', storage_area_id=storage_area_id))
                
                # Check if another storage area has this name
                cursor.execute(
                    "SELECT storage_area_id FROM storage_area WHERE group_id = %s AND LOWER(storage_area_name) = LOWER(%s) AND storage_area_id != %s",
                    (storage_area['group_id'], storage_area_name, storage_area_id)
                )
                existing = cursor.fetchone()
                
                if existing:
                    flash("A storage area with this name already exists in your group.", "warning")
                    return redirect(url_for('admin.edit_storage_area', storage_area_id=storage_area_id))
                
                # Update the storage area
                cursor.execute(
                    "UPDATE storage_area SET storage_area_name = %s WHERE storage_area_id = %s",
                    (storage_area_name, storage_area_id)
                )
                conn.commit()
                
                flash(f"Storage area updated successfully!", "success")
                return redirect(url_for('admin.view_storage_areas'))
            
            # Get related items count
            cursor.execute(
                "SELECT COUNT(*) as count FROM inventory_items WHERE storage_area_id = %s",
                (storage_area_id,)
            )
            item_count = cursor.fetchone()['count']
            
        return render_template('admin/edit_storage.html',
                               storage_area=storage_area,
                               item_count=item_count)
    
    except Exception as e:
        current_app.logger.exception(f"Error editing storage area: {e}")
        flash("An error occurred while editing the storage area.", "danger")
        return redirect(url_for('admin.view_storage_areas'))


@admin_bp.route('/storage_areas/<int:storage_area_id>/delete', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def delete_storage_area(storage_area_id):
    group_id = session.get('current_group_id')
    if not group_id and not session.get('is_super_admin'):
        flash("Please select a group first.", "warning")
        return redirect(url_for('main.home'))
    
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            # Verify storage area belongs to current group
            cursor.execute(
                "SELECT storage_area_id, storage_area_name, group_id FROM storage_area WHERE storage_area_id = %s",
                (storage_area_id,)
            )
            storage_area = cursor.fetchone()
            
            if not storage_area or (str(storage_area['group_id']) != str(group_id) and not session.get('is_super_admin')):
                flash("Storage area not found or access denied.", "danger")
                return redirect(url_for('admin.view_storage_areas'))
            
            # Check if storage area has any items assigned
            cursor.execute(
                "SELECT COUNT(*) as count FROM inventory_items WHERE storage_area_id = %s",
                (storage_area_id,)
            )
            item_count = cursor.fetchone()['count']
            
            if item_count > 0:
                flash(f"Cannot delete storage area with {item_count} assigned item(s). Please reassign or remove items first.", "warning")
                return redirect(url_for('admin.view_storage_areas'))
            
            # Delete the storage area
            cursor.execute("DELETE FROM storage_area WHERE storage_area_id = %s", (storage_area_id,))
            conn.commit()
            
            flash(f"Storage area '{storage_area['storage_area_name']}' deleted successfully!", "success")
    
    except Exception as e:
        current_app.logger.exception(f"Error deleting storage area: {e}")
        flash("An error occurred while deleting the storage area.", "danger")
    
    return redirect(url_for('admin.view_storage_areas'))
