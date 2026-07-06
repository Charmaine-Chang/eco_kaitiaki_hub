"""Repository layer for authentication and user management queries."""

from PF_LU_APP.db import get_cursor
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER


def fetch_user_by_username(username):
    """Fetch user by username (case-insensitive)."""
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_user_by_email(email):
    """Fetch user by email."""
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_user_by_id(user_id):
    """Fetch user by ID."""
    cursor = get_cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    return row


def check_email_exists(email, exclude_user_id=None):
    """Check if email is already registered."""
    cursor = get_cursor()
    if exclude_user_id:
        cursor.execute("SELECT user_id FROM users WHERE email = %s AND user_id != %s", (email, exclude_user_id))
    else:
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def create_user(username, first_name, last_name, email, password_hash,
                phone='', emergency_contact='', status='Active'):
    """Insert a new user."""
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO users (username, first_name, last_name, email, password_hash,
                           phone, emergency_contact, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (username, first_name, last_name, email, password_hash,
          phone, emergency_contact, status))
    cursor.close()


def update_user_profile(user_id, first_name, last_name, email, phone, emergency_contact):
    """Update user profile fields."""
    cursor = get_cursor()
    cursor.execute("""
        UPDATE users SET first_name=%s, last_name=%s, email=%s, phone=%s, emergency_contact=%s
        WHERE user_id=%s
    """, (first_name, last_name, email, phone, emergency_contact, user_id))
    cursor.close()


def update_user_password(user_id, password_hash):
    """Update user password hash."""
    cursor = get_cursor()
    cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (password_hash, user_id))
    cursor.close()


def update_profile_photo(user_id, photo_path):
    """Update or remove profile photo."""
    cursor = get_cursor()
    cursor.execute("UPDATE users SET profile_photo = %s WHERE user_id = %s", (photo_path, user_id))
    cursor.close()


def remove_profile_photo(user_id):
    """Remove profile photo."""
    cursor = get_cursor()
    cursor.execute("UPDATE users SET profile_photo = NULL WHERE user_id = %s", (user_id,))
    cursor.close()


# ── Group Membership ─────────────────────────────────────────────

def check_super_admin_membership(user_id):
    """Check if user is a super admin."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT 1 FROM group_membership
        WHERE user_id = %s AND role_id = %s AND membership_status = 'active'
    """, (user_id, ROLE_SUPER_ADMIN))
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def fetch_user_memberships(user_id):
    """Fetch all active memberships for a user."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT gm.group_id, g.group_name, gm.role_id, r.role_name
        FROM group_membership gm
        JOIN groups g ON gm.group_id = g.group_id
        JOIN roles r ON gm.role_id = r.role_id
        WHERE gm.user_id = %s AND gm.membership_status = 'active' AND g.status = 'active'
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_membership(user_id, group_id):
    """Fetch a specific membership."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT gm.group_id, g.group_name, gm.role_id
        FROM group_membership gm
        JOIN groups g ON gm.group_id = g.group_id
        WHERE gm.user_id = %s AND gm.group_id = %s
        AND gm.membership_status = 'active' AND g.status = 'active'
    """, (user_id, group_id))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_all_memberships_with_details(user_id):
    """Fetch all memberships with group details (for my_groups page)."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT g.group_id, g.group_name, g.description, g.geographic_area,
               g.visibility, g.status, g.branding_image, g.primary_color,
               gm.membership_status, r.role_name
        FROM groups g
        JOIN group_membership gm ON g.group_id = gm.group_id
        JOIN roles r ON gm.role_id = r.role_id
        WHERE gm.user_id = %s
        ORDER BY g.group_name ASC
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_pending_group_applications(user_id):
    """Fetch groups created by user that are still pending."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT group_id, group_name, description, geographic_area,
               visibility, status, created_at
        FROM groups
        WHERE created_by = %s AND status = 'pending'
        ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_group_color(group_id):
    """Get group primary color."""
    cursor = get_cursor()
    cursor.execute("SELECT primary_color FROM groups WHERE group_id = %s", (group_id,))
    row = cursor.fetchone()
    cursor.close()
    return row['primary_color'] if row else None


# ── Group Application ────────────────────────────────────────────

def check_group_name_exists(group_name):
    """Check if a group name already exists."""
    cursor = get_cursor()
    cursor.execute("SELECT group_id FROM groups WHERE LOWER(group_name) = LOWER(%s)", (group_name,))
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def create_group_application(group_name, description, geographic_area,
                             visibility, created_by):
    """Submit a new group application."""
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO groups (group_name, description, geographic_area, visibility, created_by, status)
        VALUES (%s, %s, %s, %s, %s, 'pending')
    """, (group_name, description, geographic_area, visibility, created_by))
    cursor.close()


# ── Join Group ───────────────────────────────────────────────────

def fetch_group_visibility(group_id):
    """Get group visibility setting."""
    cursor = get_cursor()
    cursor.execute("SELECT visibility FROM groups WHERE group_id = %s AND status = 'active'", (group_id,))
    row = cursor.fetchone()
    cursor.close()
    return row['visibility'] if row else None


def fetch_group_basic(group_id):
    """Get basic group info (name, color)."""
    cursor = get_cursor()
    cursor.execute("SELECT group_name, primary_color FROM groups WHERE group_id = %s", (group_id,))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_membership_status(user_id, group_id):
    """Check membership status for a user in a group."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT membership_status FROM group_membership WHERE user_id = %s AND group_id = %s",
        (user_id, group_id),
    )
    row = cursor.fetchone()
    cursor.close()
    return row['membership_status'] if row else None


def create_membership(user_id, group_id, role_id, status='active'):
    """Create a new group membership."""
    cursor = get_cursor()
    cursor.execute(
        "INSERT INTO group_membership (user_id, group_id, role_id, membership_status) VALUES (%s, %s, %s, %s)",
        (user_id, group_id, role_id, status),
    )
    cursor.close()


def update_membership_status(user_id, group_id, role_id, status):
    """Update an existing membership (e.g. rejected → pending)."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE group_membership SET membership_status = %s, role_id = %s WHERE user_id = %s AND group_id = %s",
        (status, role_id, user_id, group_id),
    )
    cursor.close()


# ── Coordinator Application ──────────────────────────────────────

def fetch_user_role_in_group(user_id, group_id):
    """Get user's role in a specific group."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT role_id FROM group_membership WHERE user_id = %s AND group_id = %s",
        (user_id, group_id),
    )
    row = cursor.fetchone()
    cursor.close()
    return row['role_id'] if row else None


def create_role_upgrade_request(user_id, group_id, requested_role_id):
    """Submit a role upgrade request."""
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO role_upgrade_requests (user_id, group_id, requested_role_id, status)
        VALUES (%s, %s, %s, 'pending')
        ON CONFLICT (user_id, group_id, requested_role_id, status) DO NOTHING
    """, (user_id, group_id, requested_role_id))
    cursor.close()
