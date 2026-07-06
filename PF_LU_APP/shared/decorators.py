from functools import wraps
from flask import session, flash, redirect, url_for
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER

def login_required(f):
    """Decorator to require that a user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    """Decorator to require that a user has one of the specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for('auth.login'))
            
            role_id = session.get('role_id')
            if role_id not in roles:
                flash("You do not have permission to access this page.", "danger")
                
                # Smart redirect based on existing role
                if role_id == ROLE_OPERATOR:
                    return redirect(url_for('operator.operator_dashboard'))
                elif role_id == ROLE_OBSERVER:
                    return redirect(url_for('observer.observer_dashboard'))
                elif role_id in (ROLE_SUPER_ADMIN, ROLE_COORDINATOR):
                    return redirect(url_for('admin.admin_dashboard'))
                return redirect(url_for('main.home'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
