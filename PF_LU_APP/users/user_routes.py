from flask import render_template, request, redirect, url_for, flash, session, current_app
from PF_LU_APP.db import get_db, get_cursor, get_cursor_context
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required

@admin_bp.route('/users')
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def admin_users():
    current_group_id = session.get('current_group_id')
    users = []
    
    try:
        with get_cursor_context() as cursor:
            if not current_group_id:
                flash("Please enter a group context first (Home → Enter Group) to manage members.", "warning")
                return redirect(url_for('admin.admin_dashboard'))

            # Fetch users in current group
            cursor.execute("""
                SELECT u.user_id, u.username, u.first_name, u.last_name, u.email, u.status,
                       r.role_name, gm.membership_status
                FROM users u
                JOIN group_membership gm ON u.user_id = gm.user_id
                JOIN roles r ON gm.role_id = r.role_id
                WHERE gm.group_id = %s
                ORDER BY u.username
            """, (current_group_id,))
            users = cursor.fetchall()
            
            # Pre-calculate active members for the dashboard
            active_count = sum(1 for u in users if u['status'] == 'Active')
            
            # Fetch potential members (users not in this group)
            cursor.execute("""
                SELECT user_id, username, first_name, last_name, email
                FROM users
                WHERE user_id NOT IN (
                    SELECT user_id FROM group_membership WHERE group_id = %s
                ) AND status = 'Active'
                ORDER BY username
            """, (current_group_id,))
            potential_members = cursor.fetchall()

            # Fetch roles for the template stats and modal
            cursor.execute(f"SELECT role_id, role_name FROM roles WHERE role_id > {ROLE_SUPER_ADMIN}")
            roles = cursor.fetchall()
            
    except Exception as e:
        current_app.logger.exception(f"Error fetching group users: {e}")
        roles = []
        potential_members = []
        active_count = 0
        
    return render_template('admin/list_users.html', 
                           users=users, 
                           roles=roles, 
                           potential_members=potential_members,
                           active_count=active_count)

@admin_bp.route('/global_users')
@roles_required(ROLE_SUPER_ADMIN)
def global_users():
    try:
        with get_cursor_context() as cursor:
            cursor.execute("""
                SELECT u.user_id, u.username, u.first_name, u.last_name, u.email, u.status, u.created_at
                FROM users u
                ORDER BY u.username
            """)
            users = cursor.fetchall()
    except Exception as e:
        current_app.logger.exception(f"Error fetching global users: {e}")
        users = []
        
    return render_template('admin/list_users_global.html', users=users)

@admin_bp.route('/assign_to_group', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def assign_to_group():
    user_id = request.form.get('user_id')
    group_id = request.form.get('group_id')
    role_id = request.form.get('role_id')
    
    # ── Self-assignment protection ──
    if str(user_id) == str(session.get('user_id')):
        flash("You cannot assign yourself to a group.", "danger")
        return redirect(url_for('admin.admin_users'))

    # Permission check: Coordinators can only assign to their CURRENT group
    is_super_admin = session.get('is_super_admin')
    current_group_id = session.get('current_group_id')
    
    if not is_super_admin:
        if not current_group_id or str(group_id) != str(current_group_id):
            flash("You can only assign users to your currently active group.", "danger")
            return redirect(url_for('admin.admin_users'))
        
        # Coordinators cannot assign Super Admin or Coordinator roles
        role_id_int = int(role_id) if role_id else 0
        if role_id_int <= ROLE_COORDINATOR:  # super_admin=1 or coordinator=2
            flash("You can only assign Operator or Observer roles.", "danger")
            return redirect(url_for('admin.admin_users'))
    else:
        # Super admin: cannot assign Super Admin role
        role_id_int = int(role_id) if role_id else 0
        if role_id_int == ROLE_SUPER_ADMIN:
            flash("Super Admin role cannot be assigned to other users.", "danger")
            return redirect(url_for('admin.admin_users'))
    
    # Protect Super Admin accounts from assignment
    try:
        with get_cursor_context() as c:
            c.execute(f"SELECT 1 FROM group_membership WHERE user_id = %s AND role_id = {ROLE_SUPER_ADMIN} AND membership_status = 'active'", (user_id,))
            if c.fetchone():
                flash("Super Admin accounts cannot be assigned to groups.", "danger")
                return redirect(url_for('admin.admin_users'))
    except Exception:
        pass

    if not user_id or not group_id or not role_id:
        flash("Missing required fields.", "danger")
        return redirect(url_for('admin.admin_users'))
        
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            cursor.execute("SELECT 1 FROM group_membership WHERE user_id = %s AND group_id = %s", (user_id, group_id))
            if cursor.fetchone():
                cursor.execute("""
                    UPDATE group_membership 
                    SET role_id = %s, membership_status = 'active' 
                    WHERE user_id = %s AND group_id = %s
                """, (role_id, user_id, group_id))
                msg = "Updated existing membership."
            else:
                cursor.execute("""
                    INSERT INTO group_membership (user_id, group_id, role_id, membership_status)
                    VALUES (%s, %s, %s, 'active')
                """, (user_id, group_id, role_id))
                msg = "Assigned user to group successfully."
                
            conn.commit()
            flash(msg, "success")
    except Exception as e:
        current_app.logger.exception(f"Error assigning user to group: {e}")
        flash("Could not assign user to group.", "danger")
        
    return redirect(url_for('admin.user_detail', user_id=user_id))

@admin_bp.route('/users/<int:user_id>', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def user_detail(user_id):
    db = get_db()
    current_group_id = session.get('current_group_id')

    if request.method == 'POST':
        try:
            with get_cursor_context() as cur:
                # ── Protect Super Admin accounts from modification ──
                cur.execute(f"SELECT 1 FROM group_membership WHERE user_id = %s AND role_id = {ROLE_SUPER_ADMIN} AND membership_status = 'active'", (user_id,))
                if cur.fetchone():
                    flash("Super Admin accounts cannot be modified.", "danger")
                    return redirect(url_for('admin.user_detail', user_id=user_id))

                new_role_id = request.form.get('role_id')
                if new_role_id and current_group_id:
                    # ── Self-role-change protection ──
                    if int(user_id) == int(session.get('user_id')):
                        flash("You cannot change your own role.", "danger")
                    else:
                        cur.execute("SELECT role_id FROM group_membership WHERE user_id = %s AND group_id = %s", (user_id, current_group_id))
                        current_role = cur.fetchone()
                        
                        if current_role and str(current_role['role_id']) != str(new_role_id):
                            new_role_int = int(new_role_id)
                            
                            if session.get('is_super_admin'):
                                # Super admin: can assign any role EXCEPT super admin (1)
                                if new_role_int == ROLE_SUPER_ADMIN:
                                    flash("Super Admin role cannot be assigned to other users.", "danger")
                                else:
                                    cur.execute("UPDATE group_membership SET role_id = %s WHERE user_id = %s AND group_id = %s",
                                                (new_role_id, user_id, current_group_id))
                                    db.commit()
                                    flash('Group role updated successfully.', 'success')
                            else:
                                # Coordinator: can only assign operator (3) or observer (4)
                                if new_role_int <= ROLE_COORDINATOR:  # super_admin=1 or coordinator=2
                                    flash("You can only assign Operator or Observer roles.", "danger")
                                else:
                                    cur.execute("UPDATE group_membership SET role_id = %s WHERE user_id = %s AND group_id = %s",
                                                (new_role_id, user_id, current_group_id))
                                    db.commit()
                                    flash('Group role updated successfully.', 'success')
                        
                if session.get('is_super_admin'):
                    new_status = request.form.get('status')
                    if user_id == session.get('user_id'):
                        if new_status and new_status != 'Active':
                            flash('For security reasons, you cannot change your own status.', 'warning')
                    else:
                        if new_status in ['Active', 'Inactive', 'Suspended']:
                            cur.execute("UPDATE users SET status = %s WHERE user_id = %s", (new_status, user_id))
                            db.commit()
                            flash('Global user status updated successfully.', 'success')
        except Exception as e:
            db.rollback()
            current_app.logger.exception(f"Error updating user detail: {e}")
            flash(f"Error updating user: {str(e)}", "danger")
            return redirect(url_for('admin.user_detail', user_id=user_id))
                    
        return redirect(url_for('admin.user_detail', user_id=user_id))

    try:
        with get_cursor_context() as cur:
            cur.execute("""
                SELECT username, first_name, last_name, email, phone, emergency_contact, status, user_id, created_at
                FROM users
                WHERE user_id = %s
            """, (user_id,))
            user_info = cur.fetchone()
            
            if not user_info:
                flash("User not found.", "danger")
                return redirect(url_for('admin.admin_users'))

            membership = None
            if current_group_id:
                cur.execute("""
                    SELECT r.role_name, gm.role_id, gm.membership_status
                    FROM group_membership gm
                    JOIN roles r ON gm.role_id = r.role_id
                    WHERE gm.user_id = %s AND gm.group_id = %s
                """, (user_id, current_group_id))
                membership = cur.fetchone()

            # Check if target user is a Super Admin
            cur.execute(f"SELECT 1 FROM group_membership WHERE user_id = %s AND role_id = {ROLE_SUPER_ADMIN} AND membership_status = 'active'", (user_id,))
            is_super_admin_user = cur.fetchone() is not None

            if session.get('is_super_admin'):
                cur.execute("SELECT role_id, role_name FROM roles ORDER BY role_id")
            else:
                # Coordinators cannot assign Super Admin or Coordinator roles
                cur.execute(f"SELECT role_id, role_name FROM roles WHERE role_id > {ROLE_COORDINATOR} ORDER BY role_id")
            roles = cur.fetchall()
            
            all_groups = []
            user_memberships = []
            if session.get('is_super_admin'):
                cur.execute("SELECT group_id, group_name FROM `groups` WHERE status = 'active' ORDER BY group_name")
                all_groups = cur.fetchall()
                
                cur.execute("""
                    SELECT gm.group_id, g.group_name, r.role_name, gm.membership_status, gm.role_id, gm.joined_at
                    FROM group_membership gm
                    JOIN `groups` g ON gm.group_id = g.group_id
                    JOIN roles r ON gm.role_id = r.role_id
                    WHERE gm.user_id = %s
                    ORDER BY g.group_name
                """, (user_id,))
                user_memberships = cur.fetchall()
            elif current_group_id:
                cur.execute("""
                    SELECT gm.group_id, g.group_name, r.role_name, gm.membership_status, gm.role_id, gm.joined_at
                    FROM group_membership gm
                    JOIN `groups` g ON gm.group_id = g.group_id
                    JOIN roles r ON gm.role_id = r.role_id
                    WHERE gm.user_id = %s AND gm.group_id = %s
                    ORDER BY g.group_name
                """, (user_id, current_group_id))
                user_memberships = cur.fetchall()

            current_group_name = None
            if current_group_id:
                cur.execute("SELECT group_name FROM `groups` WHERE group_id = %s", (current_group_id,))
                res = cur.fetchone()
                if res:
                    current_group_name = res['group_name']

            return render_template('admin/user_detail.html', 
                                   user=user_info, 
                                   membership=membership, 
                                   roles=roles, 
                                   all_groups=all_groups,
                                   user_memberships=user_memberships,
                                   current_group_name=current_group_name,
                                   is_super_admin_user=is_super_admin_user)
    except Exception as e:
        current_app.logger.exception(f"Error fetching user detail: {e}")
        flash("An error occurred loading user detail.", "danger")
        return redirect(url_for('admin.admin_users'))

@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN)
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    conn = get_db()
    
    try:
        with get_cursor_context() as cursor:
            cursor.execute("SELECT username FROM users WHERE user_id = %s", (user_id,))
            target = cursor.fetchone()

            if not target:
                flash('User not found.', 'danger')
                return redirect(url_for('admin.admin_users'))

            # Protect Super Admin accounts from deletion
            cursor.execute(f"""
                SELECT 1 FROM group_membership 
                WHERE user_id = %s AND role_id = {ROLE_SUPER_ADMIN} AND membership_status = 'active'
            """, (user_id,))
            if cursor.fetchone():
                flash('Super Admin accounts cannot be deleted.', 'danger')
                return redirect(url_for('admin.user_detail', user_id=user_id))

            cursor.execute("DELETE FROM operator_lines WHERE user_id = %s", (user_id,))
            cursor.execute("UPDATE trap_catches SET recorded_by = NULL WHERE recorded_by = %s", (user_id,))
            cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            conn.commit()
            flash(f"User '{target['username']}' has been permanently deleted.", 'success')
    except Exception as e:
        conn.rollback()
        current_app.logger.exception(f"Error deleting user: {e}")
        flash(f'Error deleting user: {str(e)}', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/user/<int:user_id>/remove_from_group/<int:group_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN)
def remove_member_from_group(user_id, group_id):
    if user_id == session.get('user_id'):
        flash("You cannot remove yourself from a group.", "danger")
        return redirect(url_for('admin.user_detail', user_id=user_id))

    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            # Check if this membership exists and get group name for flash message
            cursor.execute("""
                SELECT g.group_name 
                FROM group_membership gm
                JOIN `groups` g ON gm.group_id = g.group_id
                WHERE gm.user_id = %s AND gm.group_id = %s
            """, (user_id, group_id))
            membership = cursor.fetchone()
            
            if not membership:
                flash("Membership not found.", "danger")
                return redirect(url_for('admin.user_detail', user_id=user_id))

            # Protect Super Admin accounts from membership deletion
            cursor.execute(f"""
                SELECT 1 FROM group_membership 
                WHERE user_id = %s AND role_id = {ROLE_SUPER_ADMIN} AND membership_status = 'active'
            """, (user_id,))
            if cursor.fetchone():
                flash("Super Admin memberships cannot be removed.", "danger")
                return redirect(url_for('admin.user_detail', user_id=user_id))

            # Delete the group membership
            cursor.execute("DELETE FROM group_membership WHERE user_id = %s AND group_id = %s", (user_id, group_id))
            
            # Clean up operator lines for this user within this group
            cursor.execute("""
                DELETE FROM operator_lines 
                WHERE user_id = %s AND line_id IN (
                    SELECT line_id FROM `lines` WHERE group_id = %s
                )
            """, (user_id, group_id))

            conn.commit()
            flash(f"User has been successfully removed from '{membership['group_name']}'.", "success")
    except Exception as e:
        conn.rollback()
        current_app.logger.exception(f"Error removing user from group: {e}")
        flash(f"Error removing user from group: {str(e)}", "danger")

    return redirect(url_for('admin.user_detail', user_id=user_id))
