from flask import render_template, request, redirect, url_for, flash, session, current_app
from PF_LU_APP.db import get_db, get_cursor, get_cursor_context
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER

@admin_bp.route('/')
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def admin_dashboard():
    # Ensure variables used later are always defined to avoid UnboundLocalError
    all_groups_boundaries = None

    try:
        with get_cursor_context() as cursor:
            # Fetch basic user info
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
            user = cursor.fetchone()
            
            current_group_id = session.get('current_group_id')
            role_id = session.get('role_id')
            
            # Determine if we show global system-wide data or group-scoped data
            is_global_view = not current_group_id
            is_private = False
            if current_group_id:
                cursor.execute("SELECT group_name, visibility FROM `groups` WHERE group_id = %s", (current_group_id,))
                _cg = cursor.fetchone()
                if _cg:
                    is_private = _cg['visibility'] == 'private'
                    if _cg['group_name'] == 'System Management':
                        is_global_view = True

            pending_groups = []
            if is_global_view and session.get('is_super_admin'):
                cursor.execute("""
                    SELECT g.*, u.first_name, u.last_name 
                    FROM `groups` g 
                    JOIN users u ON g.created_by = u.user_id 
                    WHERE g.status = 'pending'
                """)
                pending_groups = cursor.fetchall()
                
            pending_members = []
            pending_upgrades = []

            if is_global_view and session.get('is_super_admin'):
                cursor.execute("""
                    SELECT gm.membership_id, u.first_name, u.last_name, u.username, gm.joined_at, r.role_name, g.group_name
                    FROM group_membership gm
                    JOIN users u ON gm.user_id = u.user_id
                    JOIN roles r ON gm.role_id = r.role_id
                    JOIN `groups` g ON gm.group_id = g.group_id
                    WHERE gm.membership_status = 'pending'
                """)
                pending_members = cursor.fetchall()
                
                # Fetch pending role upgrade requests
                cursor.execute("""
                    SELECT rur.request_id, u.first_name, u.last_name, u.username, rur.created_at, g.group_name, rur.user_id
                    FROM role_upgrade_requests rur
                    JOIN users u ON rur.user_id = u.user_id
                    JOIN `groups` g ON rur.group_id = g.group_id
                    WHERE rur.status = 'pending'
                """)
                pending_upgrades = cursor.fetchall()
            else:
                can_view_pending = False
                if current_group_id:
                    if role_id == ROLE_COORDINATOR: # Coordinator
                        can_view_pending = True
                    elif session.get('is_super_admin') and not is_private: # Super Admin + Public Group
                        can_view_pending = True

                if can_view_pending:
                    cursor.execute("""
                        SELECT gm.membership_id, u.first_name, u.last_name, u.username, gm.joined_at, r.role_name, g.group_name
                        FROM group_membership gm
                        JOIN users u ON gm.user_id = u.user_id
                        JOIN roles r ON gm.role_id = r.role_id
                        JOIN `groups` g ON gm.group_id = g.group_id
                        WHERE gm.group_id = %s AND gm.membership_status = 'pending'
                    """, (current_group_id,))
                    pending_members = cursor.fetchall()
                    
                    # Fetch pending role upgrade requests
                    cursor.execute("""
                        SELECT rur.request_id, u.first_name, u.last_name, u.username, rur.created_at, g.group_name, rur.user_id
                        FROM role_upgrade_requests rur
                        JOIN users u ON rur.user_id = u.user_id
                        JOIN `groups` g ON rur.group_id = g.group_id
                        WHERE rur.group_id = %s AND rur.status = 'pending'
                    """, (current_group_id,))
                    pending_upgrades = cursor.fetchall()
        
            # Fetch groups to enter/switch
            if session.get('is_super_admin'):
                cursor.execute("""
                    SELECT g.group_id, g.group_name, gm.role_id
                    FROM `groups` g
                    LEFT JOIN group_membership gm ON g.group_id = gm.group_id AND gm.user_id = %s AND gm.membership_status = 'active'
                    WHERE g.status = 'active'
                    ORDER BY g.group_name
                """, (session['user_id'],))
                user_groups = cursor.fetchall()
            else:
                cursor.execute("""
                    SELECT g.group_id, g.group_name, gm.role_id
                    FROM `groups` g 
                    JOIN group_membership gm ON g.group_id = gm.group_id 
                    WHERE gm.user_id = %s AND g.status = 'active' AND gm.membership_status = 'active'
                    ORDER BY g.group_name
                """, (session['user_id'],))
                user_groups = cursor.fetchall()

            # ── QUICK STATS ───────────────────────────────────────────
            stats = {}
            stats.setdefault('pending_tasks', 0)
            if is_global_view:
                cursor.execute("SELECT COUNT(*) as count FROM traps WHERE status = 'active'")
                stats['total_traps'] = cursor.fetchone()['count']
                cursor.execute("SELECT COUNT(*) as count FROM bait_stations WHERE status = 'active'")
                stats['active_bait_stations'] = cursor.fetchone()['count']
                cursor.execute("SELECT COUNT(*) as count FROM `groups` WHERE status = 'active'")
                stats['total_groups'] = cursor.fetchone()['count']
                cursor.execute("SELECT COUNT(*) as count FROM users")
                stats['total_users'] = cursor.fetchone()['count']
                cursor.execute("SELECT COUNT(*) as count FROM `groups` WHERE status = 'pending'")
                stats['pending_tasks'] = cursor.fetchone()['count']
                cursor.execute("SELECT COUNT(*) as count FROM `lines` WHERE status = 'active'")
                stats['total_active_lines'] = cursor.fetchone()['count']
            else:
                if current_group_id:
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM traps 
                        WHERE line_id IN (SELECT line_id FROM `lines` WHERE group_id = %s) AND status = 'active'
                    """, (current_group_id,))
                    stats['total_traps'] = cursor.fetchone()['count']
                    cursor.execute("""
                        SELECT COUNT(*) as count FROM bait_stations 
                        WHERE line_id IN (SELECT line_id FROM `lines` WHERE group_id = %s) AND status = 'active'
                    """, (current_group_id,))
                    stats['active_bait_stations'] = cursor.fetchone()['count']
                    cursor.execute("SELECT COUNT(*) as count FROM `lines` WHERE group_id = %s AND status = 'active'", (current_group_id,))
                    stats['total_active_lines'] = cursor.fetchone()['count']
                else:
                    stats['total_traps'] = 0
                    stats['active_bait_stations'] = 0
                    stats['total_active_lines'] = 0

            low_stock_alerts = []
            try:
                from PF_LU_APP.inventory.utils import fetch_low_stock_alerts
                from PF_LU_APP.inventory.inventory_repository import find_alternative_stock
                if session.get('is_super_admin') and not current_group_id:
                    low_stock_alerts = fetch_low_stock_alerts(cursor, all_groups=True)
                elif current_group_id:
                    low_stock_alerts = fetch_low_stock_alerts(cursor, group_id=current_group_id)
                # Attach alternative stock counts
                for alert in low_stock_alerts:
                    item_cat = alert.get('item_category', 'bait')
                    alternatives = find_alternative_stock(
                        alert['group_id'], alert['item_name'], item_cat,
                        alert['item_id'], alert.get('storage_area_id'),
                    )
                    alert['alternative_count'] = len(alternatives)
            except Exception as alert_err:
                current_app.logger.error(f"Error fetching low stock alerts: {alert_err}")
                low_stock_alerts = []

            # ── RECENT ACTIVITY ───────────────────────────────────────
            recent_activity = []
            try:
                act_query = """
                    SELECT 'catch' as type, tc.`date` as timestamp, u.username, t.trap_code, s.species_name, g.group_name
                    FROM trap_catches tc
                    JOIN users u ON tc.recorded_by = u.user_id
                    JOIN traps t ON tc.trap_code = t.trap_code
                    JOIN `lines` l ON t.line_id = l.line_id
                    JOIN `groups` g ON l.group_id = g.group_id
                    LEFT JOIN species s ON tc.species_id = s.species_id
                    WHERE 1=1
                """
                act_params = []
                if not session.get('is_super_admin'):
                    act_query += " AND g.group_id = %s"
                    act_params.append(current_group_id)
                act_query += " ORDER BY tc.`date` DESC LIMIT 10"
                cursor.execute(act_query, tuple(act_params))
                recent_activity = cursor.fetchall()
            except Exception as act_err:
                current_app.logger.error(f"Error fetching recent activity: {act_err}")
                recent_activity = []

            # Fetch group boundary for the map (defensive for older DB schemas)
            boundary_geojson = None
            group_latitude = None
            group_longitude = None
            if current_group_id:
                try:
                    cursor.execute("SELECT boundary_geojson, latitude, longitude FROM `groups` WHERE group_id = %s", (current_group_id,))
                    grp = cursor.fetchone()
                    if grp:
                        boundary_geojson = grp.get('boundary_geojson')
                        group_latitude = grp.get('latitude')
                        group_longitude = grp.get('longitude')
                except Exception as e:
                    current_app.logger.exception(f"Warning: could not read group boundary_geojson: {e}")
                    try:
                        get_db().rollback()
                    except Exception:
                        pass

            # Fetch all groups' boundaries for System Management overview map (defensive for older DB schemas)
            all_groups_boundaries = None
            if is_global_view:
                try:
                    cursor.execute("""
                        SELECT group_name, boundary_geojson, latitude, longitude
                        FROM `groups`
                        WHERE status = 'active' AND boundary_geojson IS NOT NULL
                    """)
                    all_groups_boundaries = cursor.fetchall()
                except Exception as e:
                    current_app.logger.exception(f"Warning: could not read group boundary_geojson: {e}")
                    try:
                        get_db().rollback()
                    except Exception:
                        pass

    except Exception as e:
        current_app.logger.exception(f"Error fetching dashboard info: {e}")
        try:
            get_db().rollback()
        except:
            pass
        user = {}
        pending_groups = []
        pending_members = []
        user_groups = []
        pending_upgrades = []
        stats = {}
        # Ensure all expected stat keys are present to avoid template errors
        default_keys = ['total_traps', 'total_groups', 'total_users', 'pending_tasks', 'total_active_lines', 'active_bait_stations']
        for key in default_keys:
            stats.setdefault(key, 0)
        recent_activity = []
        low_stock_alerts = []

    # Update pending tasks count with pending groups, members, upgrades and low stock alerts
    if stats is not None:
        stats['pending_tasks'] = (
            len(pending_groups) +
            len(pending_members) +
            len(pending_upgrades) +
            len(low_stock_alerts)
        )

    template = 'dashboards/admin_dashboard.html' if session.get('is_super_admin') else 'dashboards/coordinator_dashboard.html'
    return render_template(template, 
                           user=user, 
                           pending_groups=pending_groups, 
                           pending_members=pending_members,
                           pending_upgrades=pending_upgrades,
                           user_groups=user_groups,
                           stats=stats,
                           recent_activity=recent_activity,
                           low_stock_alerts=low_stock_alerts,
                           boundary_geojson=boundary_geojson,
                           group_latitude=group_latitude,
                           group_longitude=group_longitude,
                           all_groups_boundaries=all_groups_boundaries)

@admin_bp.route('/approve_group/<int:group_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN)
def approve_group(group_id):
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            cursor.execute("SELECT created_by, group_name FROM `groups` WHERE group_id = %s", (group_id,))
            group = cursor.fetchone()
            
            if group:
                cursor.execute("UPDATE `groups` SET status = 'active' WHERE group_id = %s", (group_id,))
                
                # Ensure the creator is an active coordinator for the group
                cursor.execute("SELECT 1 FROM group_membership WHERE user_id = %s AND group_id = %s", (group['created_by'], group_id))
                if not cursor.fetchone():
                    cursor.execute(f"""
                        INSERT INTO group_membership (user_id, role_id, group_id, membership_status)
                        VALUES (%s, {ROLE_COORDINATOR}, %s, 'active')
                    """, (group['created_by'], group_id))
                else:
                    cursor.execute(f"""
                        UPDATE group_membership 
                        SET role_id = {ROLE_COORDINATOR}, membership_status = 'active' 
                        WHERE user_id = %s AND group_id = %s
                    """, (group['created_by'], group_id))
                
                conn.commit()
                flash(f"Group '{group['group_name']}' approved successfully.", "success")
    except Exception as e:
        current_app.logger.exception(f"Error approving group: {e}")
        try:
            conn.rollback()
        except:
            pass
        flash("An error occurred.", "danger")
        
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/reject_group/<int:group_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN)
def reject_group(group_id):
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            # Mark as rejected or delete
            cursor.execute("UPDATE `groups` SET status = 'rejected' WHERE group_id = %s", (group_id,))
            conn.commit()
            flash("Group application rejected.", "success")
    except Exception as e:
        current_app.logger.exception(f"Error rejecting group: {e}")
        try:
            conn.rollback()
        except:
            pass
        flash("An error occurred.", "danger")
        
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/approve_upgrade/<int:request_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def approve_upgrade(request_id):
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            # Fetch request details
            cursor.execute("SELECT user_id, group_id, requested_role_id FROM role_upgrade_requests WHERE request_id = %s", (request_id,))
            req = cursor.fetchone()
            
            if req:
                # Update membership
                cursor.execute("""
                    UPDATE group_membership 
                    SET role_id = %s 
                    WHERE user_id = %s AND group_id = %s
                """, (req['requested_role_id'], req['user_id'], req['group_id']))
                
                # Mark request as approved
                cursor.execute("UPDATE role_upgrade_requests SET status = 'approved', updated_at = CURRENT_TIMESTAMP WHERE request_id = %s", (request_id,))
                
                conn.commit()
                flash("Role upgrade approved successfully!", "success")
    except Exception as e:
        current_app.logger.exception(f"Error approving upgrade: {e}")
        try:
            conn.rollback()
        except:
            pass
        flash("An error occurred.", "danger")
        
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/reject_upgrade/<int:request_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def reject_upgrade(request_id):
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            # Mark request as rejected
            cursor.execute("UPDATE role_upgrade_requests SET status = 'rejected', updated_at = CURRENT_TIMESTAMP WHERE request_id = %s", (request_id,))
            
            conn.commit()
            flash("Role upgrade application rejected.", "warning")
    except Exception as e:
        current_app.logger.exception(f"Error rejecting upgrade: {e}")
        try:
            conn.rollback()
        except:
            pass
        flash("An error occurred.", "danger")
        
    return redirect(url_for('admin.admin_dashboard'))
