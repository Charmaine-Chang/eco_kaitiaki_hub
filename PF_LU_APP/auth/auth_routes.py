import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from PF_LU_APP import bcrypt
from ..db import get_db, get_cursor, get_cursor_context
import re
import psycopg2
from ..validators import is_valid_email
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER
from PF_LU_APP.shared.decorators import login_required
from werkzeug.utils import secure_filename
from .auth_validators import validate_password_complexity

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.after_app_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@auth_bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['password_confirm']
        email = request.form['email']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        contact_information = request.form.get('contact_information', '')
        emergency_contact = request.form.get('emergency_contact', '')

        # Helper: re-render with all non-password fields preserved
        def redisplay(message):
            flash(message, "danger")
            return render_template('auth/register.html', form_data={
                'username': username,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'contact_information': contact_information,
                'emergency_contact': emergency_contact,
            })

        if not is_valid_email(email):
            return redisplay("Invalid email format! Please enter a valid email (e.g., user@example.com).")

        if password != confirm_password:
            return redisplay("Passwords do not match.")

        is_valid, error_msg = validate_password_complexity(password)
        if not is_valid:
            return redisplay(error_msg)

        from .auth_service import register_user
        success, error_msg = register_user(
            username, first_name, last_name, email, password, contact_information, emergency_contact
        )
        if not success:
            return redisplay(error_msg)

        flash("Registration successful! Please login.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form_data={})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect them to their appropriate dashboard
    if 'user_id' in session:
        role_id = session.get('role_id')
        if role_id in (ROLE_SUPER_ADMIN, ROLE_COORDINATOR):
            return redirect(url_for('admin.admin_dashboard'))
        elif role_id == ROLE_OPERATOR:
            return redirect(url_for('operator.operator_dashboard'))
        elif role_id == ROLE_OBSERVER:
            return redirect(url_for('observer.observer_dashboard'))
        else:
            return redirect(url_for('main.home'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            with get_cursor_context() as cur:
                cur.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
                user = cur.fetchone()

                if user and bcrypt.check_password_hash(user['password_hash'], password):
                    if user['status'] == 'Inactive':
                        flash('Your account is currently inactive. Please contact an Administrator', 'danger')
                        return render_template('auth/login.html', prefilled_username=username)

                    session.permanent = False
                    session['user_id'] = user['user_id']
                    session['username'] = user['username']
                    
                    # Check if user is Super Admin
                    cur.execute(f"""
                        SELECT 1 FROM group_membership 
                        WHERE user_id = %s AND role_id = {ROLE_SUPER_ADMIN} AND membership_status = 'active'
                    """, (user['user_id'],))
                    is_super_admin = cur.fetchone() is not None
                    session['is_super_admin'] = is_super_admin
                    
                    # Fetch active memberships
                    cur.execute("""
                        SELECT gm.group_id, g.group_name, gm.role_id, r.role_name
                        FROM group_membership gm
                        JOIN groups g ON gm.group_id = g.group_id
                        JOIN roles r ON gm.role_id = r.role_id
                        WHERE gm.user_id = %s AND gm.membership_status = 'active'
                        AND g.status = 'active'
                    """, (user['user_id'],))
                    memberships = cur.fetchall()

                    if is_super_admin:
                        # Super admins can choose a group or go straight to dashboard
                        # For now, let's just let them go home or choose a group context
                        if len(memberships) > 1:
                            return redirect(url_for('auth.select_group'))
                        elif len(memberships) == 1:
                            session['current_group_id'] = memberships[0]['group_id']
                            session['current_group_name'] = memberships[0]['group_name']
                            session['role_id'] = memberships[0]['role_id']
                        else:
                            session['role_id'] = 1 # Fallback to Super Admin role
                        return redirect(url_for('admin.admin_dashboard'))

                    if len(memberships) > 1:
                        return redirect(url_for('auth.select_group'))
                    elif len(memberships) == 1:
                        m = memberships[0]
                        session['current_group_id'] = m['group_id']
                        session['current_group_name'] = m['group_name']
                        session['role_id'] = m['role_id']
                        
                        # Fetch branding
                        try:
                            cur.execute("SELECT primary_color FROM groups WHERE group_id = %s", (m['group_id'],))
                            g_data = cur.fetchone()
                            if g_data and g_data['primary_color']:
                                session['current_group_color'] = g_data['primary_color']
                            else:
                                session.pop('current_group_color', None)
                        except psycopg2.DatabaseError as e:
                            current_app.logger.error(f"Branding fetch error: {e}")
                            session.pop('current_group_color', None)
                        
                        # Redirect based on role
                        if m['role_id'] in (ROLE_SUPER_ADMIN, ROLE_COORDINATOR): return redirect(url_for('admin.admin_dashboard'))
                        if m['role_id'] == ROLE_OPERATOR: return redirect(url_for('operator.operator_dashboard'))
                        return redirect(url_for('observer.observer_dashboard'))
                    
                    # No groups? Just go home
                    return redirect(url_for('main.home'))

                flash('Login was unsuccessful. Incorrect username or password.', 'danger')
        except psycopg2.DatabaseError as e:
            current_app.logger.error(f"Login database error: {e}")
            flash('An error occurred during login. Please try again.', 'danger')
        except Exception as e:
            current_app.logger.exception(f"Login unexpected error: {e}")
            flash('An unexpected error occurred.', 'danger')

        return render_template('auth/login.html', prefilled_username=username)

    return render_template('auth/login.html')

@auth_bp.route('/select-group', methods=['GET', 'POST'])
@login_required
def select_group():
    if request.method == 'POST':
        group_id = request.form.get('group_id')
        
        try:
            with get_cursor_context() as cur:
                # Verify membership
                cur.execute("""
                    SELECT gm.group_id, g.group_name, gm.role_id
                    FROM group_membership gm
                    JOIN groups g ON gm.group_id = g.group_id
                    WHERE gm.user_id = %s AND gm.group_id = %s 
                    AND gm.membership_status = 'active' AND g.status = 'active'
                """, (session['user_id'], group_id))
                membership = cur.fetchone()
                
                if membership:
                    session['current_group_id'] = membership['group_id']
                    session['current_group_name'] = membership['group_name']
                    session['role_id'] = membership['role_id']
                    
                    # Fetch group branding if exists (color)
                    try:
                        cur.execute("SELECT primary_color FROM groups WHERE group_id = %s", (group_id,))
                        g_data = cur.fetchone()
                        if g_data and g_data['primary_color']:
                            session['current_group_color'] = g_data['primary_color']
                        else:
                            session.pop('current_group_color', None)
                    except psycopg2.DatabaseError as e:
                        current_app.logger.error(f"Branding fetch error (column might be missing): {e}")
                        session.pop('current_group_color', None)
                        
                    # Redirect based on role
                    if membership['role_id'] in (ROLE_SUPER_ADMIN, ROLE_COORDINATOR): return redirect(url_for('admin.admin_dashboard'))
                    if membership['role_id'] == ROLE_OPERATOR: return redirect(url_for('operator.operator_dashboard'))
                    return redirect(url_for('observer.observer_dashboard'))
                
                flash("Invalid group selection.", "danger")
        except psycopg2.DatabaseError as e:
            current_app.logger.error(f"Select group post error: {e}")
            flash("An error occurred.", "danger")
        
    # GET: Fetch all active groups for selection
    try:
        with get_cursor_context() as cur:
            cur.execute("""
                SELECT gm.group_id, g.group_name, g.description, r.role_name, gm.role_id
                FROM group_membership gm
                JOIN groups g ON gm.group_id = g.group_id
                JOIN roles r ON gm.role_id = r.role_id
                WHERE gm.user_id = %s AND gm.membership_status = 'active' AND g.status = 'active'
                ORDER BY CASE WHEN g.group_name = 'System Management' THEN 0 ELSE 1 END, g.group_name ASC
            """, (session['user_id'],))
            memberships = cur.fetchall()
    except psycopg2.DatabaseError as e:
        current_app.logger.error(f"Select group get error: {e}")
        memberships = []
        flash("Could not fetch groups.", "danger")
    
    return render_template('auth/select_group.html', memberships=memberships)

@auth_bp.route('/enter-group/<int:group_id>', methods=['POST'])
@login_required
def enter_group(group_id):
    try:
        with get_cursor_context() as cur:
            cur.execute("""
                SELECT gm.group_id, g.group_name, gm.role_id, g.primary_color
                FROM group_membership gm
                JOIN groups g ON gm.group_id = g.group_id
                WHERE gm.user_id = %s AND gm.group_id = %s 
                AND gm.membership_status = 'active' AND g.status = 'active'
            """, (session['user_id'], group_id))
            membership = cur.fetchone()
            
            if membership:
                session['current_group_id'] = membership['group_id']
                session['current_group_name'] = membership['group_name']
                session['role_id'] = membership['role_id']
                if membership['primary_color']:
                    session['current_group_color'] = membership['primary_color']
                else:
                    session.pop('current_group_color', None)
                
                if membership['role_id'] in (ROLE_SUPER_ADMIN, ROLE_COORDINATOR): return redirect(url_for('admin.admin_dashboard'))
                if membership['role_id'] == ROLE_OPERATOR: return redirect(url_for('operator.operator_dashboard'))
                return redirect(url_for('observer.observer_dashboard'))
    except psycopg2.DatabaseError as e:
        current_app.logger.error(f"Enter group error: {e}")
        
    flash("Unauthorized or invalid group.", "danger")
    return redirect(url_for('auth.my_groups'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('auth.login'))

ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def _allowed_photo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    try:
        with get_cursor_context() as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
            user = cur.fetchone()
            if not user:
                flash("User not found.", "danger")
                return redirect(url_for('auth.login'))

            if request.method == 'POST':
                action = request.form.get('action')

                #  UPDATE PROFILE
                if action == 'update_profile':
                    first_name = request.form.get('first_name')
                    last_name = request.form.get('last_name')
                    email = request.form.get('email')
                    phone = request.form.get('phone')
                    emergency_contact = request.form.get('emergency_contact')

                    if not first_name or not last_name or not email or not phone or not emergency_contact:
                        flash("Please fill in all required fields!", "danger")
                        return redirect(url_for('auth.profile'))

                    if not is_valid_email(email):
                        flash("Invalid email format!", "danger")
                        return redirect(url_for('auth.profile'))

                    try:
                        cur.execute("""
                            UPDATE users
                            SET first_name=%s, last_name=%s, email=%s, phone=%s, emergency_contact=%s
                            WHERE user_id=%s
                        """, (first_name, last_name, email, phone, emergency_contact, session['user_id']))
                        get_db().commit()
                        flash("Profile updated successfully!", "success")
                    except psycopg2.IntegrityError as e:
                        get_db().rollback()
                        current_app.logger.error(f"Profile update integrity error: {e}")
                        flash("Email already in use!", "danger")
                    
                    return redirect(url_for('auth.profile'))

                #  UPDATE PROFILE PHOTO
                elif action == 'update_photo':
                    if 'profile_photo' in request.files:
                        file = request.files['profile_photo']
                        if file and file.filename:
                            secured_filename = secure_filename(file.filename)
                            if not secured_filename or not _allowed_photo(secured_filename):
                                flash("Invalid file type. Allowed: png, jpg, jpeg, gif, webp", "danger")
                                return redirect(url_for('auth.profile'))
                            
                            ext = secured_filename.rsplit(".", 1)[1].lower()
                            unique_name = f"user_{session['user_id']}_{uuid.uuid4().hex}.{ext}"
                            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                            os.makedirs(upload_dir, exist_ok=True)
                            file.save(os.path.join(upload_dir, unique_name))
                            
                            cur.execute("UPDATE users SET profile_photo = %s WHERE user_id = %s",
                                        (f"/static/uploads/profiles/{unique_name}", session['user_id']))
                            get_db().commit()
                            flash("Profile photo updated!", "success")
                            return redirect(url_for('auth.profile'))

                    if request.form.get('remove_photo'):
                        cur.execute("UPDATE users SET profile_photo = NULL WHERE user_id = %s",
                                    (session['user_id'],))
                        get_db().commit()
                        flash("Profile photo removed.", "info")
                        return redirect(url_for('auth.profile'))

                # CHANGE PASSWORD
                elif action == 'change_password':
                    current_password = request.form.get('current_password')
                    new_password = request.form.get('new_password')
                    confirm_password = request.form.get('confirm_password')

                    from .auth_service import update_password
                    success, error_msg = update_password(
                        session['user_id'], user['password_hash'], current_password, new_password, confirm_password
                    )
                    
                    if not success:
                        flash(error_msg, "danger")
                    else:
                        flash("Password updated successfully!", "success")
                        
                    return redirect(url_for('auth.profile'))
    except psycopg2.DatabaseError as e:
        current_app.logger.error(f"Profile error: {e}")
        flash("An error occurred loading your profile.", "danger")
        return redirect(url_for('main.home'))

    return render_template('auth/profile.html', user=user)


@auth_bp.route('/my-groups')
@login_required
def my_groups():
    try:
        with get_cursor_context() as cur:
            # Groups the user is an active member of
            cur.execute("""
                SELECT g.group_id, g.group_name, g.description, g.geographic_area,
                       g.visibility, g.status, g.branding_image, g.primary_color,
                       gm.membership_status, r.role_name
                FROM groups g
                JOIN group_membership gm ON g.group_id = gm.group_id
                JOIN roles r ON gm.role_id = r.role_id
                WHERE gm.user_id = %s
                ORDER BY g.group_name ASC
            """, (session['user_id'],))
            memberships = cur.fetchall()

            # Groups applied for by this user that are still pending
            cur.execute("""
                SELECT group_id, group_name, description, geographic_area,
                       visibility, status, created_at
                FROM groups
                WHERE created_by = %s AND status = 'pending'
                ORDER BY created_at DESC
            """, (session['user_id'],))
            pending_applications = cur.fetchall()
    except psycopg2.DatabaseError as e:
        current_app.logger.error(f"My groups error: {e}")
        memberships = []
        pending_applications = []
        flash("An error occurred fetching your groups.", "danger")

    return render_template('auth/my_groups.html',
                           memberships=memberships,
                           pending_applications=pending_applications)


@auth_bp.route('/apply-group', methods=['GET', 'POST'])
@login_required
def apply_group():
    if request.method == 'POST':
        group_name   = request.form.get('group_name', '').strip()
        mission      = request.form.get('mission', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        geographic_area = request.form.get('geographic_area', '').strip()
        visibility   = request.form.get('visibility', 'public')

        if visibility not in ('public', 'private'):
            visibility = 'public'

        # Validation
        if not group_name:
            flash("Group name is required.", "danger")
            return render_template('auth/apply_group.html', form_data=request.form)

        if not contact_email:
            flash("Contact email is required.", "danger")
            return render_template('auth/apply_group.html', form_data=request.form)
        
        if not is_valid_email(contact_email):
            flash("Invalid contact email format!", "danger")
            return render_template('auth/apply_group.html', form_data=request.form)

        try:
            with get_cursor_context() as cur:
                # Compose description to store mission + contact email
                description = ""
                if mission:
                    description += f"Mission: {mission}\n\n"
                description += f"Contact Email: {contact_email}"

                cur.execute("""
                    INSERT INTO groups
                        (group_name, description, geographic_area, visibility, created_by, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                """, (group_name, description, geographic_area, visibility, session['user_id']))
                get_db().commit()
                
                flash(f'Your application to create "{group_name}" has been submitted and is pending review.',
                      "success")
                return redirect(url_for('auth.my_groups'))
        except psycopg2.IntegrityError as e:
            get_db().rollback()
            current_app.logger.error(f"Apply group integrity error: {e}")
            flash(f'A group named "{group_name}" may already exist. Please choose a different name.',
                  "danger")
            return render_template('auth/apply_group.html', form_data=request.form)
        except psycopg2.DatabaseError as e:
            get_db().rollback()
            current_app.logger.error(f"Apply group error: {e}")
            flash("An error occurred during application submission.", "danger")

    return render_template('auth/apply_group.html', form_data={})


@auth_bp.route('/join-group/<int:group_id>', methods=['POST'])
@login_required
def join_group(group_id):
    try:
        with get_cursor_context() as cur:
            # Check group exists and is active
            cur.execute("SELECT group_id, group_name, visibility FROM groups WHERE group_id = %s AND status = 'active'",
                        (group_id,))
            group = cur.fetchone()
            if not group:
                flash("Group not found or is not active.", "danger")
                return redirect(url_for('main.home'))

            if group['group_name'] == 'System Management':
                flash("You cannot request to join this group.", "danger")
                return redirect(url_for('main.home'))

            # Check already a member
            cur.execute("SELECT membership_id FROM group_membership WHERE user_id = %s AND group_id = %s",
                        (session['user_id'], group_id))
            if cur.fetchone():
                flash(f'You are already a member (or have a pending request) for "{group["group_name"]}".', "info")
                return redirect(url_for('main.home'))

            # Determine status based on visibility
            visibility = group.get('visibility', 'public').lower()
            membership_status = 'active' if visibility == 'public' else 'pending'

            # Insert membership as Observer (role_id=ROLE_OBSERVER)
            cur.execute(f"""
                INSERT INTO group_membership (user_id, role_id, group_id, membership_status)
                VALUES (%s, {ROLE_OBSERVER}, %s, %s)
            """, (session['user_id'], group_id, membership_status))
            get_db().commit()

            if membership_status == 'active':
                flash(f'You have successfully joined "{group["group_name"]}" as an Observer!', "success")
            else:
                flash(f'Your request to join "{group["group_name"]}" has been submitted and is pending approval by the Group Coordinator.', "success")
            
            return redirect(url_for('main.home'))
    except psycopg2.DatabaseError as e:
        current_app.logger.error(f"Join group error: {e}")
        flash("An error occurred trying to join the group.", "danger")
        return redirect(url_for('main.home'))

@auth_bp.route('/apply_coordinator/<int:group_id>', methods=['POST'])
@login_required
def apply_coordinator(group_id):
    user_id = session['user_id']
    
    try:
        with get_cursor_context() as cur:
            # Check if they are already a member
            cur.execute("SELECT role_id FROM group_membership WHERE user_id = %s AND group_id = %s", (user_id, group_id))
            membership = cur.fetchone()
            
            if not membership:
                flash("You are not a member of this group.", "danger")
                return redirect(url_for('auth.my_groups'))
            
            if membership['role_id'] in (ROLE_SUPER_ADMIN, ROLE_COORDINATOR):
                flash("You are already a Coordinator or Admin.", "info")
                return redirect(url_for('operator.operator_dashboard'))
            
            # Create request
            cur.execute("""
                INSERT INTO role_upgrade_requests (user_id, group_id, requested_role_id, status)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, group_id, requested_role_id, status) DO NOTHING
            """, (user_id, group_id, 2, 'pending'))
            
            get_db().commit()
            flash("Success! Your application to become a Group Coordinator has been submitted and is now awaiting review.", "success")
            
    except psycopg2.DatabaseError as e:
        current_app.logger.error(f"Error applying for coordinator: {e}")
        flash("It looks like you have already applied or an error occurred. Please check your status later.", "warning")
        
    return redirect(url_for('operator.operator_dashboard'))
