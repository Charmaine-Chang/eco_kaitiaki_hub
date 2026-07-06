from flask import render_template, request, redirect, url_for, flash, session, json, current_app
from PF_LU_APP.db import get_db, get_cursor, get_cursor_context
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR
from PF_LU_APP.catches.catch_repository import (
    fetch_catches, fetch_catches_kpis,
    fetch_catch_by_id, fetch_catch_group, update_catch,
    fetch_catch_form_data,
)
from PF_LU_APP.catches.analytics_repository import (
    fetch_species_distribution,
)
from PF_LU_APP.catches.validation_repository import (
    fetch_trap_status_by_catch,
)

@admin_bp.route('/edit_catch/<int:catches_id>', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def edit_catch(catches_id):
    try:
        conn = get_db()
        trap_status_row = fetch_trap_status_by_catch(catches_id)
        is_retired = False
        if trap_status_row:
            is_retired = (trap_status_row['status'] == 'inactive' or trap_status_row['equipment_status_name'] == 'Retired')

        if not session.get('is_super_admin') and session.get('role_id') == ROLE_COORDINATOR:
            current_group_id = session.get('current_group_id')
            record = fetch_catch_group(catches_id)
            if record and record['group_id'] != current_group_id:
                flash("You do not have permission to edit records from other groups.", "danger")
                return redirect(url_for('admin.view_catches'))

        if request.method == 'POST':
            if is_retired:
                flash("Cannot modify records associated with a retired item.", "warning")
                return redirect(url_for('admin.edit_catch', catches_id=catches_id))

            update_catch(
                catches_id,
                request.form.get('date'),
                request.form.get('species_id'),
                request.form.get('sex'),
                request.form.get('maturity'),
                request.form.get('trap_status_id'),
                'rebaited' in request.form,
                request.form.get('bait_type_id') or None,
                request.form.get('trap_condition_id'),
                request.form.get('strikes') or 0,
                request.form.get('note'),
            )
            conn.commit()
            flash("Catch record updated successfully!", "success")
            return redirect(url_for('admin.view_catches'))

        catch = fetch_catch_by_id(catches_id)
        if not catch:
            flash("Catch record not found.", "danger")
            return redirect(url_for('admin.view_catches'))

        with get_cursor_context() as cursor:
            cursor.execute("SELECT * FROM species ORDER BY species_name")
            all_species = cursor.fetchall()
            cursor.execute("SELECT * FROM trap_status ORDER BY status_name")
            all_statuses = cursor.fetchall()
            cursor.execute("SELECT * FROM bait_type ORDER BY bait_type_name")
            all_baits = cursor.fetchall()
            cursor.execute("SELECT * FROM trap_condition ORDER BY trap_condition_name")
            all_conditions = cursor.fetchall()

        return render_template(
            'operator/edit_catch.html',
            catch=catch,
            all_species=all_species,
            all_statuses=all_statuses,
            all_baits=all_baits,
            all_conditions=all_conditions,
            is_retired=is_retired,
        )

    except Exception as e:
        current_app.logger.exception(f"Error editing catch (admin): {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        flash("An error occurred while accessing the record.", "danger")
        return redirect(url_for('admin.view_catches'))

@admin_bp.route('/catches', defaults={'line_id': None}, methods=['GET'])
@admin_bp.route('/operator/<int:line_id>', methods=['GET'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def view_catches(line_id):
    try:
        line_filter = request.args.get('line_filter')
        if line_filter is None and line_id:
            line_filter = str(line_id)
        species_filter = request.args.get('species_filter')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        catches, all_lines, all_species, line, map_data = fetch_catches(
            session, line_filter, species_filter, start_date, end_date
        )
        stats = fetch_catches_kpis(session)
        stats['total_catches'] = len(catches)
        species_distribution = fetch_species_distribution(session)
        
        return render_template('operator/catch_list.html', 
                               line=line, 
                               catches=catches, 
                               line_id=line_id,
                               all_lines=all_lines,
                               all_species=all_species,
                               line_filter=line_filter,
                               species_filter=species_filter,
                               start_date=start_date,
                               end_date=end_date,
                               stats=stats,
                               map_data=json.dumps(map_data),
                               species_distribution=json.dumps([dict(row) for row in species_distribution]))
    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.exception(f"Error viewing catches: {e}")
        flash(f"Could not load catch records: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))
