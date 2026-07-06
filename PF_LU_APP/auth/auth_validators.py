import re

def validate_password_complexity(password):
    """
    Validates that a password meets complexity requirements.
    Returns (True, None) if valid, or (False, error_message) if invalid.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain an uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain a lowercase letter."
    if not re.search(r'[0-9]', password):
        return False, "Password must contain a number."
    return True, None
