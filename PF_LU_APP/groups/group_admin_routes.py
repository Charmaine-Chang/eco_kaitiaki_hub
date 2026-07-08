from flask import render_template, request, redirect, url_for, flash, session, current_app
from PF_LU_APP.db import get_db, get_cursor, get_cursor_context
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required
import os
import werkzeug.utils
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR

@admin_bp.route('/manage_groups')
@roles_required(ROLE_SUPER_ADMIN)
def manage_groups():
    try:
        with get_cursor_context() as cursor:
            cursor.execute(f"""
                SELECT g.*, u.username as creator_username,
                       (SELECT u2.username FROM group_membership gm 
                         JOIN users u2 ON gm.user_id = u2.user_id 
                         WHERE gm.group_id = g.group_id AND gm.role_id = {ROLE_COORDINATOR} AND gm.membership_status = 'active'
                         LIMIT 1) as coordinator_username
                FROM `groups` g
                LEFT JOIN users u ON g.created_by = u.user_id 
                ORDER BY g.created_at DESC
            """)
            groups = cursor.fetchall()
    except Exception as e:
        current_app.logger.exception(f"Error fetching groups: {e}")
        groups = []
        
    return render_template('admin/list_groups.html', groups=groups)

def is_valid_geojson_polygon(geojson_str):
    if not geojson_str:
        return True
    try:
        import json
        data = json.loads(geojson_str)
        if data.get('type') != 'Polygon':
            return False
        coords = data.get('coordinates')
        if not coords or not isinstance(coords, list) or len(coords) == 0:
            return False
        ring = coords[0]
        if not isinstance(ring, list) or len(ring) < 4:
            return False
        first_pt = ring[0]
        last_pt = ring[-1]
        if not isinstance(first_pt, list) or len(first_pt) < 2 or not isinstance(last_pt, list) or len(last_pt) < 2:
            return False
        # Check if closed
        if first_pt[0] != last_pt[0] or first_pt[1] != last_pt[1]:
            return False
        return True
    except Exception:
        return False

@admin_bp.route('/edit_group/<int:group_id>', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def edit_group(group_id):
    conn = get_db()
    is_super = session.get('is_super_admin', False)

    # Scoping check for Group Coordinators
    if not is_super and int(group_id) != int(session.get('current_group_id', 0)):
        flash("Access denied: You can only edit settings for your own group.", "danger")
        return redirect(url_for('admin.admin_dashboard'))

    if request.method == 'POST':
        visibility = request.form.get('visibility')
        boundary_geojson = request.form.get('boundary_geojson')
        original_boundary_geojson = request.form.get('original_boundary_geojson')

        try:
            with get_cursor_context() as cursor:
                # Concurrency check: verify if another user has updated the boundary in the meantime
                cursor.execute("SELECT boundary_geojson FROM `groups` WHERE group_id = %s", (group_id,))
                current_group = cursor.fetchone()
                if not current_group:
                    flash("Group not found.", "danger")
                    return redirect(url_for('admin.manage_groups'))

                db_boundary = current_group['boundary_geojson']
                db_boundary_norm = (db_boundary.strip() if db_boundary else "")
                original_boundary_norm = (original_boundary_geojson.strip() if original_boundary_geojson else "")

                if db_boundary_norm != original_boundary_norm:
                    flash("Save failed: The boundary has been modified by another coordinator since you loaded this page. Please reload and try again.", "danger")
                    return redirect(url_for('admin.edit_group', group_id=group_id))

                # Validate boundary geojson if provided
                if boundary_geojson and not is_valid_geojson_polygon(boundary_geojson):
                    flash("Invalid area: The polygon must be closed.", "danger")
                    return redirect(url_for('admin.edit_group', group_id=group_id))

                if not is_super:
                    # Coordinator — can update visibility, geographic_area, region, latitude, longitude, boundary_geojson
                    geographic_area = request.form.get('geographic_area')
                    region = request.form.get('region')
                    latitude = request.form.get('latitude')
                    longitude = request.form.get('longitude')
                    
                    try:
                        latitude = float(latitude) if latitude else None
                    except (ValueError, TypeError):
                        latitude = None
                        
                    try:
                        longitude = float(longitude) if longitude else None
                    except (ValueError, TypeError):
                        longitude = None

                    try:
                        cursor.execute("""
                            UPDATE `groups`
                            SET visibility = %s, geographic_area = %s, region = %s,
                                latitude = %s, longitude = %s, boundary_geojson = %s
                            WHERE group_id = %s
                        """, (visibility, geographic_area, region, latitude, longitude, boundary_geojson or None, group_id))
                        conn.commit()
                        flash("Group settings updated successfully.", "success")
                    except Exception as e:
                        conn.rollback()
                        current_app.logger.exception(f"Error updating group settings: {e}")
                        flash(f"Error updating group: {str(e)}", "danger")
                        
                    return redirect(url_for('admin.edit_group', group_id=group_id))

                # Super admin — full edit
                group_name = request.form.get('group_name')
                if not group_name:
                    flash("Group name is required.", "danger")
                    return redirect(url_for('admin.edit_group', group_id=group_id))
                
                description = request.form.get('description')
                geographic_area = request.form.get('geographic_area')
                region = request.form.get('region')
                primary_color = request.form.get('primary_color', '#1a5e20')
                status = request.form.get('status')
                coordinator_id = request.form.get('coordinator_id')
                
                # Handle coordinates: convert empty strings to None
                latitude = request.form.get('latitude')
                longitude = request.form.get('longitude')
                try:
                    latitude = float(latitude) if latitude else None
                except (ValueError, TypeError):
                    latitude = None
                    
                try:
                    longitude = float(longitude) if longitude else None
                except (ValueError, TypeError):
                    longitude = None

                branding_image = request.form.get('branding_image_url') # Fallback to URL
                
                # Handle file upload
                if 'branding_file' in request.files:
                    file = request.files['branding_file']
                    if file and file.filename:
                        filename = werkzeug.utils.secure_filename(f"group_{group_id}_{file.filename}")
                        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'groups')
                        os.makedirs(upload_dir, exist_ok=True)
                        file.save(os.path.join(upload_dir, filename))
                        branding_image = filename # Store only the filename

                # Fallback for 'rejected' status if enum doesn't support it
                if status == 'rejected':
                    status = 'inactive' # Safe fallback to prevent DB crash

                try:
                    cursor.execute("""
                        UPDATE `groups`
                        SET group_name = %s, description = %s, geographic_area = %s, region = %s,
                            branding_image = %s, visibility = %s, status = %s,
                            primary_color = %s, latitude = %s, longitude = %s, boundary_geojson = %s
                        WHERE group_id = %s
                    """, (group_name, description, geographic_area, region,
                          branding_image, visibility, status,
                          primary_color, latitude, longitude, boundary_geojson or None, group_id))
                    conn.commit()

                    # Handle Coordinator Update
                    if coordinator_id:
                        # 1. Demote any existing coordinators to 'Operator' or just remove role
                        cursor.execute(f"UPDATE group_membership SET role_id = {ROLE_OPERATOR} WHERE group_id = %s AND role_id = {ROLE_COORDINATOR}", (group_id,))
                        
                        # 2. Assign/Promote new coordinator
                        cursor.execute("SELECT membership_id FROM group_membership WHERE user_id = %s AND group_id = %s", (coordinator_id, group_id))
                        existing = cursor.fetchone()
                        if existing:
                            cursor.execute(f"UPDATE group_membership SET role_id = {ROLE_COORDINATOR}, membership_status = 'active' WHERE membership_id = %s", (existing['membership_id'],))
                        else:
                            cursor.execute(f"INSERT INTO group_membership (user_id, group_id, role_id, membership_status) VALUES (%s, %s, {ROLE_COORDINATOR}, 'active')", (coordinator_id, group_id))
                        conn.commit()

                    flash("Group details updated successfully.", "success")
                    return redirect(url_for('admin.manage_groups'))
                except Exception as e:
                    conn.rollback()
                    current_app.logger.exception(f"Error updating group: {e}")
                    flash(f"Error updating group: {str(e)}", "danger")
                    return redirect(url_for('admin.edit_group', group_id=group_id))
        except Exception as outer_e:
            current_app.logger.error(f"Error in edit_group POST: {outer_e}")
            flash("An unexpected error occurred.", "danger")
            return redirect(url_for('admin.edit_group', group_id=group_id))

    try:
        with get_cursor_context() as cursor:
            cursor.execute("SELECT * FROM `groups` WHERE group_id = %s", (group_id,))
            group = cursor.fetchone()
            
            # Fetch current coordinator
            cursor.execute(f"""
                SELECT u.user_id, u.username 
                FROM group_membership gm 
                JOIN users u ON gm.user_id = u.user_id 
                WHERE gm.group_id = %s AND gm.role_id = {ROLE_COORDINATOR} AND gm.membership_status = 'active'
                LIMIT 1
            """, (group_id,))
            current_coordinator = cursor.fetchone()

            # Fetch all users for dropdown
            cursor.execute("SELECT user_id, username, first_name, last_name FROM users WHERE status = 'Active' ORDER BY username")
            users = cursor.fetchall()
            
            if not group:
                flash("Group not found.", "danger")
                return redirect(url_for('admin.manage_groups'))
                
            return render_template('admin/edit_group.html', group=group, users=users, current_coordinator=current_coordinator)
    except Exception as get_err:
        current_app.logger.error(f"Error loading edit group: {get_err}")
        flash("An error occurred loading the group.", "danger")
        return redirect(url_for('admin.manage_groups'))

@admin_bp.route('/approve_member/<int:membership_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def approve_member(membership_id):
    current_group_id = session.get('current_group_id')
    is_super_admin = session.get('is_super_admin')
    
    if not current_group_id and not is_super_admin:
        flash("No group context selected.", "danger")
        return redirect(url_for('admin.admin_dashboard'))
        
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            # Get group visibility
            if current_group_id:
                cursor.execute("SELECT visibility FROM `groups` WHERE group_id = %s", (current_group_id,))
                group = cursor.fetchone()
            else:
                cursor.execute("""
                    SELECT g.visibility, g.group_id 
                    FROM `groups` g
                    JOIN group_membership gm ON g.group_id = gm.group_id
                    WHERE gm.membership_id = %s
                """, (membership_id,))
                group = cursor.fetchone()
            
            is_coordinator = (session.get('role_id') == ROLE_COORDINATOR)
                
            if group and group['visibility'] == 'private' and not is_coordinator:
                flash("Only Group Coordinators can approve members for private groups.", "danger")
                return redirect(url_for('admin.admin_dashboard'))

            # Get role name for the flash message
            cursor.execute("""
                SELECT r.role_name 
                FROM group_membership gm 
                JOIN roles r ON gm.role_id = r.role_id 
                WHERE gm.membership_id = %s
            """, (membership_id,))
            role = cursor.fetchone()
            role_name = role['role_name'] if role else "Member"

            if current_group_id:
                cursor.execute("UPDATE group_membership SET membership_status = 'active' WHERE membership_id = %s AND group_id = %s", 
                               (membership_id, current_group_id))
            else:
                cursor.execute("UPDATE group_membership SET membership_status = 'active' WHERE membership_id = %s", 
                               (membership_id,))
            conn.commit()
            flash(f"Member approved as {role_name}.", "success")
    except Exception as e:
        current_app.logger.exception(f"Error approving member: {e}")
        flash("An error occurred.", "danger")
        
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/reject_member/<int:membership_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def reject_member(membership_id):
    current_group_id = session.get('current_group_id')
    is_super_admin = session.get('is_super_admin')
    
    if not current_group_id and not is_super_admin:
        flash("No group context selected.", "danger")
        return redirect(url_for('admin.admin_dashboard'))
        
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            # Get group visibility
            if current_group_id:
                cursor.execute("SELECT visibility FROM `groups` WHERE group_id = %s", (current_group_id,))
                group = cursor.fetchone()
            else:
                cursor.execute("""
                    SELECT g.visibility, g.group_id 
                    FROM `groups` g
                    JOIN group_membership gm ON g.group_id = gm.group_id
                    WHERE gm.membership_id = %s
                """, (membership_id,))
                group = cursor.fetchone()
            
            is_coordinator = (session.get('role_id') == ROLE_COORDINATOR)
                
            if group and group['visibility'] == 'private' and not is_coordinator:
                flash("Only Group Coordinators can reject members for private groups.", "danger")
                return redirect(url_for('admin.admin_dashboard'))

            if current_group_id:
                cursor.execute("DELETE FROM group_membership WHERE membership_id = %s AND group_id = %s", 
                               (membership_id, current_group_id))
            else:
                cursor.execute("DELETE FROM group_membership WHERE membership_id = %s", 
                               (membership_id,))
            conn.commit()
            flash("Member join request rejected.", "success")
    except Exception as e:
        current_app.logger.exception(f"Error rejecting member: {e}")
        flash("An error occurred.", "danger")
        
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/group_settings', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def group_settings():
    if not session.get('current_group_id'):
        flash("Unauthorized access.", "danger")
        return redirect(url_for('admin.admin_dashboard'))
    return redirect(url_for('admin.edit_group', group_id=session['current_group_id']))

@admin_bp.route('/groups/create', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN)
def create_group():
    db = get_db()

    if request.method == 'POST':
        group_name = request.form.get('group_name')
        description = request.form.get('description')
        visibility = request.form.get('visibility')
        branding_image = request.form.get('branding_image')
        coordinator_id = request.form.get('coordinator_id')

        if not group_name or not visibility or not coordinator_id:
            flash("Group Name, Visibility, and Coordinator are required.", "danger")
            return redirect(url_for('admin.create_group'))

        try:
            with get_cursor_context() as cursor:
                cursor.execute(
                    """
                    INSERT INTO `groups` (group_name, description, visibility, created_by, status, branding_image)
                    VALUES (%s, %s, %s, %s, 'active', %s)
                    """,
                    (group_name, description, visibility.lower(), session['user_id'], branding_image),
                )
                new_group_id = cursor.lastrowid

                cursor.execute(
                    """
                    INSERT INTO group_membership (user_id, group_id, role_id, membership_status)
                    VALUES (%s, %s, 2, 'active')
                    """,
                    (coordinator_id, new_group_id),
                )

                db.commit()
                flash(f"Group '{group_name}' created successfully and is now active.", "success")
                return redirect(url_for('admin.admin_dashboard'))
        except Exception as e:
            db.rollback()
            current_app.logger.exception(f"Error creating group: {e}")
            flash(f"An error occurred: {str(e)}", "danger")

    try:
        with get_cursor_context() as cursor:
            cursor.execute(
                "SELECT user_id, username, first_name, last_name FROM users WHERE status = 'Active' ORDER BY username"
            )
            users = cursor.fetchall()
    except Exception as e:
        current_app.logger.exception(f"Error fetching users for group creation: {e}")
        users = []

    return render_template('admin/create_group.html', users=users)

@admin_bp.route('/delete_group/<int:group_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN)
def delete_group(group_id):
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            # Check if group exists
            cursor.execute("SELECT group_name FROM `groups` WHERE group_id = %s", (group_id,))
            group = cursor.fetchone()
            
            if not group:
                flash("Group not found.", "danger")
                return redirect(url_for('admin.manage_groups'))
                
            # Delete the group (cascading deletes will handle lines, traps, memberships, etc.)
            cursor.execute("DELETE FROM `groups` WHERE group_id = %s", (group_id,))
            conn.commit()
            
            flash(f"Group '{group['group_name']}' and all its associated data have been permanently deleted.", "success")
    except Exception as e:
        current_app.logger.exception(f"Error deleting group: {e}")
        flash(f"Error deleting group: {str(e)}", "danger")
        
    return redirect(url_for('admin.manage_groups'))
