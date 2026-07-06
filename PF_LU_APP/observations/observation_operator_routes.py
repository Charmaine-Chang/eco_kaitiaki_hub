from flask import render_template, session, redirect, url_for, request, flash, current_app
from PF_LU_APP.db import get_cursor_context, get_db
from PF_LU_APP.roles.operator import operator_bp
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR
from PF_LU_APP.shared.decorators import roles_required

@operator_bp.route('/add_observation', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)
def add_observation():
    try:
        with get_cursor_context() as cursor:
            cursor.execute("SELECT line_id, line_name FROM lines WHERE status = 'active' ORDER BY line_name ASC")
            active_lines = cursor.fetchall()
    except Exception as e:
        current_app.logger.exception(f"Error fetching lines: {e}")
        active_lines = []

    if request.method == 'POST':
        observation_type = request.form.get('observation_type')
        observation_description = request.form.get('observation_description')
        observation_line = request.form.get('observation_line')
        observation_date = request.form.get('observation_date')

        if not all([observation_type, observation_description, observation_line, observation_date]):
            flash('Please fill in all required fields.', 'danger')
        else:
            try:
                with get_cursor_context() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO observation_notes (observation_type, description, related_line_id, user_id, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (observation_type, observation_description, observation_line, session['user_id'], observation_date)
                    )
                    get_db().commit()
                flash('Incidental observation saved successfully!', 'success')
                return redirect(url_for('operator.operator_dashboard'))
            except Exception as e:
                flash(f'Error saving observation: {e}', 'danger')

    return render_template('operator/add_observation.html', active_lines=active_lines)

@operator_bp.route('/incidental_observation', methods=['GET'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)
def incidental_observation_menu():
    return render_template('operator/incidental_observation_menu.html')

@operator_bp.route('/view_observations', methods=['GET'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)
def view_observations():
    try:
        with get_cursor_context() as cursor:
            cursor.execute('''
                SELECT n.note_id, n.observation_type, n.description,
                       l.line_name AS related_line, u.username AS added_by, n.created_at
                FROM observation_notes n
                LEFT JOIN users u ON n.user_id = u.user_id
                LEFT JOIN lines l ON n.related_line_id = l.line_id
                ORDER BY n.created_at DESC
            ''')
            observations = cursor.fetchall()
        return render_template('operator/view_observations.html', observations=observations)
    except Exception as e:
        current_app.logger.exception(f"Error viewing observations: {e}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('operator.operator_dashboard'))

@operator_bp.route('/edit_observation/<int:note_id>', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)
def edit_observation(note_id):
    try:
        with get_cursor_context() as cursor:
            cursor.execute("SELECT * FROM observation_notes WHERE note_id = %s", (note_id,))
            note = cursor.fetchone()

            if not note:
                flash("Observation note not found.", "danger")
                return redirect(url_for('operator.operator_dashboard'))

            if note['user_id'] != session.get('user_id') and session.get('role_id') != ROLE_SUPER_ADMIN:
                flash("You do not have permission to edit this note.", "danger")
                return redirect(url_for('operator.operator_dashboard'))

            cursor.execute("SELECT line_id, line_name FROM lines WHERE status = 'active' ORDER BY line_name ASC")
            active_lines = cursor.fetchall()

            if request.method == 'POST':
                observation_type = request.form.get('observation_type')
                observation_description = request.form.get('observation_description')
                observation_line = request.form.get('observation_line')
                observation_date = request.form.get('observation_date')

                if not all([observation_type, observation_description, observation_line, observation_date]):
                    flash("Please fill in all required fields.", "danger")
                else:
                    cursor.execute("""
                        UPDATE observation_notes
                        SET observation_type = %s, description = %s, related_line_id = %s, created_at = %s
                        WHERE note_id = %s
                    """, (observation_type, observation_description, observation_line, observation_date, note_id))
                    get_db().commit()
                    flash("Observation note updated successfully!", "success")
                    return redirect(url_for('operator.operator_dashboard'))

        return render_template('operator/edit_observation.html', note=note, active_lines=active_lines)
    except Exception as e:
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('operator.operator_dashboard'))

@operator_bp.route('/delete_observation/<int:note_id>', methods=['POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def delete_observation(note_id):
    try:
        with get_cursor_context() as cursor:
            cursor.execute("SELECT user_id FROM observation_notes WHERE note_id = %s", (note_id,))
            note = cursor.fetchone()

            if not note:
                flash("Observation note not found.", "danger")
                return redirect(url_for('operator.operator_dashboard'))

            if note['user_id'] != session.get('user_id') and session.get('role_id') != ROLE_SUPER_ADMIN:
                flash("You do not have permission to delete this note.", "danger")
                return redirect(url_for('operator.operator_dashboard'))

            cursor.execute("DELETE FROM observation_notes WHERE note_id = %s", (note_id,))
            get_db().commit()
            flash("Observation note deleted successfully.", "success")
    except Exception as e:
        flash(f"An error occurred: {str(e)}", "danger")

    return redirect(url_for('operator.view_observations'))
