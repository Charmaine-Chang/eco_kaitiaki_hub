import psycopg2
from PF_LU_APP.db import get_db, get_cursor_context
from PF_LU_APP import bcrypt

def register_user(username, first_name, last_name, email, password, contact_information, emergency_contact):
    """
    Registers a new user in the database.
    Returns (True, None) on success.
    Returns (False, error_message) on failure (e.g. unique constraint violation).
    """
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    try:
        with get_cursor_context() as cur:
            cur.execute("""
                INSERT INTO users (username, first_name, last_name, email, password_hash, phone, emergency_contact, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (username, first_name, last_name, email, password_hash, contact_information, emergency_contact, 'Active'))
            get_db().commit()
            return True, None
    except psycopg2.IntegrityError as e:
        get_db().rollback()
        error_msg = str(e).lower()
        if 'email' in error_msg:
            return False, "Email already registered! Please supply a different email address."
        elif 'username' in error_msg:
            return False, "Username already taken! Please supply a different username."
        else:
            return False, "An account with this information already exists."

def update_password(user_id, current_hash, current_password, new_password, confirm_password):
    """
    Validates and updates user password.
    Returns (True, None) on success, or (False, error_msg) on failure.
    """
    if not bcrypt.check_password_hash(current_hash, current_password):
        return False, "Current password is incorrect"
        
    if current_password == new_password:
        return False, "New password must be different from current password"
        
    if new_password != confirm_password:
        return False, "New passwords do not match"
        
    from .auth_validators import validate_password_complexity
    is_valid, error_msg = validate_password_complexity(new_password)
    if not is_valid:
        return False, error_msg
        
    new_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
    try:
        with get_cursor_context() as cur:
            cur.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (new_hash, user_id))
            get_db().commit()
        return True, None
    except psycopg2.DatabaseError as e:
        get_db().rollback()
        return False, "An error occurred while updating the database."
