from flask import request, redirect, url_for, flash, current_app
from PF_LU_APP.db import get_db, get_cursor, get_cursor_context
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR

@admin_bp.route('/assign_operator_to_line', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def assign_operator_to_line():
    line_id = request.form.get('line_id')
    user_id = request.form.get('user_id')
    redirect_line_id = request.form.get('redirect_line_id') or line_id
    if not line_id or not user_id:
        flash("Please select both a line and an operator.", "warning")
        return redirect(url_for('admin.view_lines', line_id=redirect_line_id))
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            cursor.execute("SELECT 1 FROM operator_lines WHERE line_id = %s AND user_id = %s", (line_id, user_id))
            if cursor.fetchone():
                flash("Operator is already assigned to this line.", "warning")
            else:
                cursor.execute("INSERT INTO operator_lines (line_id, user_id) VALUES (%s, %s)", (line_id, user_id))
                conn.commit()
                flash("Operator successfully assigned to the line!", "success")
    except Exception as e:
        current_app.logger.exception(f"Error assigning operator: {e}")
        flash("An error occurred while assigning the operator.", "danger")
    return redirect(url_for('admin.view_lines', line_id=redirect_line_id))

@admin_bp.route('/remove_operator/<int:line_id>/<int:user_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def remove_operator(line_id, user_id):
    redirect_line_id = request.form.get('redirect_line_id') or line_id
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            cursor.execute("DELETE FROM operator_lines WHERE line_id = %s AND user_id = %s", (line_id, user_id))
            conn.commit()
            flash("Operator removed from line successfully.", "success")
    except Exception as e:
        current_app.logger.exception(f"Error removing operator: {e}")
        flash("An error occurred while removing the operator.", "danger")
    return redirect(url_for('admin.view_lines', line_id=redirect_line_id))
