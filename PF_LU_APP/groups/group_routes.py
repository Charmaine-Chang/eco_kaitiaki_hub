import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from PF_LU_APP.db import get_db, get_cursor
from PF_LU_APP.constants import ROLE_COORDINATOR, ROLE_SUPER_ADMIN, ROLE_OPERATOR

groups_bp = Blueprint('groups', __name__, url_prefix='/groups')


def _membership_for_group(user_id, group_id):
    """Active membership row for this user in group, or None."""
    cursor = get_cursor()
    cursor.execute(
        """
        SELECT role_id FROM group_membership
        WHERE user_id = %s AND group_id = %s AND membership_status = 'active'
        """,
        (user_id, group_id),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def _require_group_member(group_id):
    """Redirect if not logged in or not an active member of group_id. Returns role_id or None."""
    if 'user_id' not in session:
        flash('You must be logged in to view group updates.', 'warning')
        return None, redirect(url_for('auth.login'))
    if session.get('is_super_admin'):
        if int(session.get('current_group_id') or 0) != int(group_id):
            flash('Select a group context to view its updates.', 'warning')
            return None, redirect(url_for('main.home'))
        return session.get('role_id') or 1, None
    row = _membership_for_group(session['user_id'], group_id)
    if not row:
        flash('You do not have access to this group’s updates.', 'danger')
        return None, redirect(url_for('main.home'))
    return row['role_id'], None

@groups_bp.route('/apply', methods=['GET', 'POST'])
def apply_group():
    if 'user_id' not in session:
        flash("You must be logged in to apply to create a new group.", "warning")
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        group_name = request.form.get('group_name')
        description = request.form.get('description')
        geographic_area = request.form.get('geographic_area')
        visibility = request.form.get('visibility')
        branding_image = request.form.get('branding_image')
        
        if not group_name or not visibility:
            flash("Please provide a group name and select visibility.", "danger")
            return redirect(url_for('groups.apply_group'))
            
        try:
            conn = get_db()
            cursor = get_cursor()

            cursor.execute("SELECT 1 FROM `groups` WHERE LOWER(group_name) = LOWER(%s)", (group_name,))
            if cursor.fetchone():
                flash(f"A group named '{group_name}' already exists.", "danger")
                cursor.close()
                return redirect(url_for('groups.apply_group'))
                
            cursor.execute("""
                INSERT INTO `groups` (group_name, description, geographic_area, visibility, created_by, status, branding_image)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s)
            """, (group_name, description, geographic_area, visibility.lower(), session['user_id'], branding_image))
            conn.commit()
            cursor.close()
            
            flash("Your application to form a new group has been submitted and is pending Super Admin approval.", "success")
            return redirect(url_for('main.home'))
        except Exception as e:
            logging.exception(f"Error applying for group: {e}")
            flash("An error occurred while submitting your application.", "danger")
            
    return render_template('groups/apply.html')

@groups_bp.route('/<int:group_id>/join', methods=['POST'])
def join_group(group_id):
    if 'user_id' not in session:
        flash("You must be logged in to join a group.", "warning")
        return redirect(url_for('auth.login'))
        
    try:
        conn = get_db()
        cursor = get_cursor()
        
        cursor.execute("SELECT group_name, visibility FROM `groups` WHERE group_id = %s", (group_id,))
        group = cursor.fetchone()
        
        if not group:
            flash("Group not found.", "danger")
            return redirect(url_for('main.home'))
            
        if group['group_name'] == 'System Management':
            flash("You cannot request to join this group.", "danger")
            return redirect(url_for('main.home'))
            
        visibility = group['visibility']
        apply_coord = request.form.get('apply_coordinator') == 'on'
        
        # If applying as coordinator, always set to pending regardless of visibility
        if apply_coord:
            membership_status = 'pending'
            target_role = 2
        else:
            membership_status = 'active' if visibility == 'public' else 'pending'
            target_role = 4
        
        # Check if already applied or member
        cursor.execute("SELECT membership_status FROM group_membership WHERE user_id = %s AND group_id = %s", (session['user_id'], group_id))
        existing = cursor.fetchone()
        
        if existing:
            status = existing['membership_status']
            if status == 'active':
                flash("You are already a member of this group.", "info")
            elif status == 'pending':
                flash("You already have a pending request for this group.", "info")
            elif status == 'rejected':
                # Re-apply
                cursor.execute("""
                    UPDATE group_membership SET membership_status = %s, role_id = %s
                    WHERE user_id = %s AND group_id = %s
                """, (membership_status, target_role, session['user_id'], group_id))
                conn.commit()
                msg = "You have joined the group." if membership_status == 'active' else "Your request has been submitted."
                flash(msg, "success")
        else:
            # Insert with determined role and status
            cursor.execute("""
                INSERT INTO group_membership (user_id, group_id, role_id, membership_status)
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], group_id, target_role, membership_status))
            conn.commit()
            
            msg = "You have successfully joined the group!" if membership_status == 'active' else "Your request has been submitted for approval."
            flash(msg, "success")
            
        cursor.close()
    except Exception as e:
        logging.exception(f"Error joining group: {e}")
        flash("An error occurred while trying to join the group.", "danger")
        
    return redirect(url_for('main.home'))

@groups_bp.route('/<int:group_id>/enter', methods=['POST'])
def enter_group(group_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        is_super_admin = session.get('is_super_admin', False)

        cursor = get_cursor()

        # Super admin path: any group is accessible
        if is_super_admin:
            cursor.execute(
                "SELECT group_name, primary_color FROM `groups` WHERE group_id = %s",
                (group_id,),
            )
            row = cursor.fetchone()
            if not row:
                cursor.close()
                flash("Group not found.", "danger")
                return redirect(url_for('main.home'))

            resolved_role = session.get('role_id') or ROLE_SUPER_ADMIN
            if resolved_role != ROLE_SUPER_ADMIN:
                resolved_role = ROLE_SUPER_ADMIN
            cursor.close()

            session['current_group_id'] = group_id
            session['current_group_name'] = row['group_name']
            session['role_id'] = resolved_role
            if row['primary_color']:
                session['current_group_color'] = row['primary_color']
            else:
                session.pop('current_group_color', None)

            flash("Entered group context as Super Admin.", "success")
            return redirect(url_for('admin.admin_dashboard'))

        # Regular member path: must have active membership
        cursor.execute(
            "SELECT role_id, membership_status FROM group_membership "
            "WHERE user_id = %s AND group_id = %s",
            (session['user_id'], group_id),
        )
        membership = cursor.fetchone()

        if not membership or membership['membership_status'] != 'active':
            cursor.close()
            flash("You do not have active access to this group.", "danger")
            return redirect(url_for('main.home'))

        cursor.execute(
            "SELECT group_name, primary_color FROM `groups` WHERE group_id = %s",
            (group_id,),
        )
        group = cursor.fetchone()
        cursor.close()

        if not group:
            flash("Group not found.", "danger")
            return redirect(url_for('main.home'))

        session['current_group_id'] = group_id
        session['current_group_name'] = group['group_name']
        session['role_id'] = membership['role_id']
        if group['primary_color']:
            session['current_group_color'] = group['primary_color']
        else:
            session.pop('current_group_color', None)

        flash("Entered group context.", "success")

        # Redirect based on role in this group
        if session['role_id'] in (ROLE_SUPER_ADMIN, ROLE_COORDINATOR):
            return redirect(url_for('admin.admin_dashboard'))
        elif session['role_id'] == ROLE_OPERATOR:
            return redirect(url_for('operator.operator_dashboard'))
        else:
            return redirect(url_for('observer.observer_dashboard'))

    except Exception as e:
        logging.exception(f"Error entering group: {e}")
        flash("Could not enter group.", "danger")
        return redirect(url_for('main.home'))


@groups_bp.route('/<int:group_id>/updates/<int:update_id>')
def group_update_detail(group_id, update_id):
    role_id, err = _require_group_member(group_id)
    if err:
        return err
    try:
        cursor = get_cursor()
        cursor.execute(
            """
            SELECT gu.update_id, gu.group_id, gu.update_title, gu.update_content, gu.created_at,
                   u.username,
                   COALESCE(NULLIF(TRIM(CONCAT(u.first_name, ' ', u.last_name)), ''), u.username) AS author_display,
                   COALESCE(lc.like_count, 0) AS like_count
            FROM group_updates gu
            JOIN users u ON gu.user_id = u.user_id
            LEFT JOIN (SELECT update_id, COUNT(*) AS like_count FROM update_likes GROUP BY update_id) lc ON lc.update_id = gu.update_id
            WHERE gu.update_id = %s AND gu.group_id = %s AND gu.is_published = TRUE
            """,
            (update_id, group_id),
        )
        update_row = cursor.fetchone()
        if not update_row:
            cursor.close()
            flash('Update not found.', 'warning')
            return redirect(url_for('updates.updates_list', group_id=group_id))

        # Check if current user liked this update
        cursor.execute(
            "SELECT like_id FROM update_likes WHERE update_id = %s AND user_id = %s",
            (update_id, session['user_id']),
        )
        user_has_liked = cursor.fetchone() is not None

        cursor.execute(
            """
            SELECT c.comment_id, c.comment_content, c.created_at, c.user_id,
                   u.username,
                   COALESCE(NULLIF(TRIM(CONCAT(u.first_name, ' ', u.last_name)), ''), u.username) AS author_display
            FROM update_comments c
            JOIN users u ON c.user_id = u.user_id
            WHERE c.update_id = %s
            ORDER BY c.created_at ASC, c.comment_id ASC
            """,
            (update_id,),
        )
        comments = cursor.fetchall()

        cursor.execute(
            "SELECT * FROM group_update_images WHERE update_id = %s ORDER BY image_id ASC",
            (update_id,)
        )
        images = cursor.fetchall()

        cursor.close()
    except Exception as e:
        logging.exception(f'Error loading update: {e}')
        flash('Could not load this update.', 'danger')
        return redirect(url_for('updates.updates_list', group_id=group_id))

    can_delete_comments = role_id == ROLE_COORDINATOR or bool(session.get('is_super_admin'))
    return render_template(
        'groups/group_update_detail.html',
        group_id=group_id,
        update=update_row,
        comments=comments,
        member_role_id=role_id,
        can_delete_comments=can_delete_comments,
        user_has_liked=user_has_liked,
        images=images,
    )


@groups_bp.route('/<int:group_id>/updates/<int:update_id>/comments', methods=['POST'])
def add_group_update_comment(group_id, update_id):
    role_id, err = _require_group_member(group_id)
    if err:
        return err
    body = (request.form.get('comment_content') or '').strip()
    if not body:
        flash('Please enter a comment before submitting.', 'warning')
        return redirect(url_for('groups.group_update_detail', group_id=group_id, update_id=update_id))

    try:
        cursor = get_cursor()
        cursor.execute(
            """
            SELECT 1 FROM group_updates
            WHERE update_id = %s AND group_id = %s AND is_published = TRUE
            """,
            (update_id, group_id),
        )
        if not cursor.fetchone():
            cursor.close()
            flash('Update not found.', 'warning')
            return redirect(url_for('updates.updates_list', group_id=group_id))

        cursor.execute(
            """
            INSERT INTO update_comments (update_id, user_id, comment_content)
            VALUES (%s, %s, %s)
            """,
            (update_id, session['user_id'], body),
        )
        get_db().commit()
        cursor.close()
        flash('Your comment was posted.', 'success')
    except Exception as e:
        logging.exception(f'Error adding comment: {e}')
        get_db().rollback()
        flash('Could not save your comment.', 'danger')
    return redirect(url_for('groups.group_update_detail', group_id=group_id, update_id=update_id))


@groups_bp.route(
    '/<int:group_id>/updates/<int:update_id>/comments/<int:comment_id>/delete',
    methods=['POST'],
)
def delete_group_update_comment(group_id, update_id, comment_id):
    role_id, err = _require_group_member(group_id)
    if err:
        return err

    if role_id != ROLE_COORDINATOR and not session.get('is_super_admin'):
        flash('Access denied. Only Group Coordinators and Super Admins can remove comments.', 'danger')
        return redirect(url_for('groups.group_update_detail', group_id=group_id, update_id=update_id))

    try:
        cursor = get_cursor()
        cursor.execute(
            """
            DELETE c FROM update_comments c
            JOIN group_updates gu ON gu.update_id = c.update_id
            WHERE c.comment_id = %s
              AND c.update_id = %s
              AND gu.group_id = %s
            """,
            (comment_id, update_id, group_id),
        )
        deleted = cursor.rowcount > 0
        get_db().commit()
        cursor.close()
        if deleted:
            flash('Comment removed.', 'success')
        else:
            flash('Comment not found.', 'warning')
    except Exception as e:
        logging.exception(f'Error deleting comment: {e}')
        get_db().rollback()
        flash('Could not delete the comment.', 'danger')
    return redirect(url_for('groups.group_update_detail', group_id=group_id, update_id=update_id))
