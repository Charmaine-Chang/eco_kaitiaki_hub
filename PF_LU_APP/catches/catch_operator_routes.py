import csv
import io
import json
from flask import render_template, session, redirect, url_for, request, flash, make_response, current_app
from PF_LU_APP.db import get_db, get_cursor_context
from PF_LU_APP.roles.operator import operator_bp
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.shared.inventory import adjust_bait_inventory
from PF_LU_APP.shared.utils import resolve_date_preset
from PF_LU_APP.catches.catch_repository import (
    fetch_catches, fetch_catches_kpis,
    fetch_catches_for_csv,
    fetch_catch_by_id, fetch_catch_owner, fetch_catch_group,
    update_catch, insert_catch, fetch_catch_form_data,
)
from PF_LU_APP.catches.analytics_repository import (
    fetch_species_distribution, fetch_data_graphs, fetch_trend_analytics,
)
from PF_LU_APP.catches.validation_repository import (
    fetch_trap_status, fetch_trap_line,
)

@operator_bp.route('/add_catch', methods=['GET', 'POST'])
@operator_bp.route('/add_catch/<string:trap_code>', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)
def add_catch(trap_code=None):

        
    line_id = request.args.get('line_id')
    
    if not trap_code and request.method == 'POST':
        trap_code = request.form.get('trap_code')

    if trap_code:
        try:
            with get_cursor_context() as cursor:
                cursor.execute("""
                    SELECT t.status, es.equipment_status_name
                    FROM traps t
                    LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
                    WHERE t.trap_code = %s
                """, (trap_code,))
                trap_chk = cursor.fetchone()
                
                if not trap_chk:
                    flash("Trap not found.", "danger")
                    return redirect(url_for('operator.operator_dashboard'))
                if trap_chk['status'] == 'inactive' or trap_chk['equipment_status_name'] == 'Retired':
                    flash("The item is no longer in service.", "danger")
                    return redirect(url_for('operator.operator_dashboard'))
        except Exception as e:
            current_app.logger.exception(f"Error checking trap status in add_catch: {e}")

    if request.method == 'POST' and trap_code:
        date = request.form.get('date')
        species_id = request.form.get('species_id')
        sex = request.form.get('sex')
        if sex:
            sex = sex.capitalize()
        maturity = request.form.get('maturity')
        if maturity:
            maturity = maturity.capitalize()
        trap_status_id = request.form.get('trap_status_id')
        rebaited = 'rebaited' in request.form
        bait_type_id = request.form.get('bait_type_id') or None
        trap_condition_id = request.form.get('trap_condition_id')
        strikes = request.form.get('strikes') or 0
        note = request.form.get('note')

        if not all([date, species_id, sex, maturity, trap_status_id, trap_condition_id]):
            flash("Please fill in all required fields.", "danger")
        else:
            try:
                conn = get_db()
                with get_cursor_context() as cursor:
                    bait_amount = None
                    if bait_type_id:
                        raw_amt = request.form.get('bait_amount')
                        try:
                            bait_amount = float(raw_amt) if raw_amt else 1.0
                        except ValueError:
                            bait_amount = 1.0

                        if bait_amount <= 0:
                            flash("Please enter a valid positive quantity for the bait used.", "danger")
                            return redirect(url_for('operator.add_catch', trap_code=trap_code))

                        inventory_result = adjust_bait_inventory(
                            cursor,
                            session.get('current_group_id'),
                            bait_type_id,
                            -bait_amount,
                        )
                        if inventory_result is not True:
                            conn.rollback()
                            flash(
                                "Bait selected but inventory could not be reduced because stock is unavailable. Please verify inventory quantities.",
                                "danger",
                            )
                            return redirect(url_for('operator.add_catch', trap_code=trap_code))

                    cursor.execute("""
                        INSERT INTO trap_catches (trap_code, date, recorded_by, species_id, sex, maturity, 
                                                  trap_status_id, rebaited, bait_type_id, bait_amount, trap_condition_id, strikes, note)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (trap_code, date, session['user_id'], species_id, sex, maturity, 
                          trap_status_id, rebaited, bait_type_id, bait_amount, trap_condition_id, strikes, note))

                    conn.commit()
                    flash("Trap catch record saved successfully!", "success")

                with get_cursor_context() as curr:
                    curr.execute("SELECT line_id FROM traps WHERE trap_code = %s", (trap_code,))
                    trap_info = curr.fetchone()

                if trap_info:
                    line_id = trap_info['line_id']
                    if session.get('role_id') == ROLE_SUPER_ADMIN:
                        return redirect(url_for('admin.view_lines', line_id=line_id))
                    else:
                        return redirect(url_for('operator.view_lines', line_id=line_id))
                return redirect(url_for('operator.operator_dashboard'))
            except Exception as e:
                current_app.logger.exception(f"Error adding catch: {e}")
                flash("An error occurred while saving the record.", "danger")

    traps = []
    line = None
    trap = None
    species = []
    statuses = []
    baits = []
    conditions = []

    try:
        with get_cursor_context() as cursor:
            if trap_code:
                cursor.execute("SELECT * FROM traps WHERE trap_code = %s", (trap_code,))
                trap = cursor.fetchone()
                if not trap:
                    flash("Trap not found.", "danger")
                    return redirect(url_for('operator.operator_dashboard'))
                if not line_id and trap:
                    line_id = trap['line_id']
            elif line_id:
                cursor.execute("SELECT line_name FROM `lines` WHERE line_id = %s", (line_id,))
                line = cursor.fetchone()
                cursor.execute("SELECT * FROM traps WHERE line_id = %s AND status = 'active' ORDER BY trap_code", (line_id,))
                traps = cursor.fetchall()

            cursor.execute("SELECT * FROM species ORDER BY species_name")
            species = cursor.fetchall()
            cursor.execute("SELECT * FROM trap_status ORDER BY status_name")
            statuses = cursor.fetchall()
            cursor.execute("SELECT * FROM bait_type ORDER BY bait_type_name")
            baits = cursor.fetchall()
            cursor.execute("SELECT * FROM trap_condition ORDER BY trap_condition_name")
            conditions = cursor.fetchall()
    except Exception as e:
        current_app.logger.exception(f"Error loading catch form data: {e}")

    return render_template('operator/add_catch.html', trap_code=trap_code, trap=trap, line_id=line_id, line=line,
                           traps=traps, species=species, statuses=statuses, baits=baits, conditions=conditions)

@operator_bp.route('/view_catches', defaults={'line_id': None}, methods=['GET'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER)
def view_catches(line_id):

    
    try:
        line_filter = request.args.get('line_filter')
        if line_filter is None and line_id:
            line_filter = str(line_id)
        species_filter = request.args.get('species_filter')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        catches, all_lines, all_species, line, map_data = fetch_catches(
            session, line_filter, species_filter, start_date, end_date, include_updated_at=True
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
        current_app.logger.exception(f"Error viewing catches: {e}")
        flash(f"Could not load catch records: {str(e)}", "danger")
        return redirect(url_for('operator.operator_dashboard'))

@operator_bp.route('/edit_catch/<int:catches_id>', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)
def edit_catch(catches_id):

        
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            cursor.execute("""
                SELECT tc.recorded_by, tc.bait_type_id, tc.bait_amount, t.line_id 
                FROM trap_catches tc
                JOIN traps t ON tc.trap_code = t.trap_code
                WHERE tc.catches_id = %s
            """, (catches_id,))
            record = cursor.fetchone()
            
            if not record:
                flash("Catch record not found.", "danger")
                return redirect(url_for('operator.operator_dashboard'))

            # Check if the associated trap is retired
            cursor.execute("""
                SELECT t.status, es.equipment_status_name
                FROM traps t
                LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
                WHERE t.trap_code = (SELECT trap_code FROM trap_catches WHERE catches_id = %s)
            """, (catches_id,))
            trap_status_row = cursor.fetchone()
            is_retired = False
            if trap_status_row:
                is_retired = (trap_status_row['status'] == 'inactive' or trap_status_row['equipment_status_name'] == 'Retired')
                
            old_bait_type_id = str(record['bait_type_id']) if record['bait_type_id'] is not None else None

            # ── Permission Check ──
            role_id = session.get('role_id')
            current_group_id = session.get('current_group_id')
            
            # Scope Check: Find which group this record belongs to
            cursor.execute("""
                SELECT l.group_id 
                FROM trap_catches tc
                JOIN traps t ON tc.trap_code = t.trap_code
                JOIN `lines` l ON t.line_id = l.line_id
                WHERE tc.catches_id = %s
            """, (catches_id,))
            record_group = cursor.fetchone()
            
            # 1. Super Admin (Role 1) can edit anything
            if session.get('is_super_admin'):
                pass # Authorized
                
            # 2. Group Coordinator (Role 2) - Can edit if it belongs to their group
            elif role_id == ROLE_COORDINATOR:
                if not record_group or str(record_group['group_id']) != str(current_group_id):
                    flash("Access denied. You can only edit records within your own group.", "danger")
                    return redirect(url_for('admin.view_catches'))
                    
            # 3. Operator (Role 3) - Must be the one who recorded it
            else:
                if record['recorded_by'] != session.get('user_id'):
                    flash("You can only edit records that you created yourself.", "danger")
                    return redirect(url_for('operator.view_catches'))
            
            if request.method == 'POST':
                if is_retired:
                    flash("Cannot modify records associated with a retired item.", "warning")
                    return redirect(url_for('operator.edit_catch', catches_id=catches_id))

                date = request.form.get('date')
                species_id = request.form.get('species_id')
                sex = request.form.get('sex')
                if sex:
                    sex = sex.capitalize()
                maturity = request.form.get('maturity')
                if maturity:
                    maturity = maturity.capitalize()
                trap_status_id = request.form.get('trap_status_id')
                rebaited = 'rebaited' in request.form
                bait_type_id = request.form.get('bait_type_id') or None
                trap_condition_id = request.form.get('trap_condition_id')
                strikes = request.form.get('strikes') or 0
                note = request.form.get('note')

                # Required field validation
                if not all([date, species_id, sex, maturity, trap_status_id, trap_condition_id]):
                    flash("Please fill in all required fields (Date, Species, Sex, Maturity, Status, Condition).", "danger")
                    return redirect(url_for('operator.edit_catch', catches_id=catches_id))
                
                try:
                    # Parse new bait_amount from form
                    raw_amt = request.form.get('bait_amount')
                    try:
                        new_bait_amount = float(raw_amt) if raw_amt else None
                    except ValueError:
                        new_bait_amount = None

                    cursor.execute("""
                        UPDATE trap_catches 
                        SET date = %s, species_id = %s, sex = %s, maturity = %s, 
                            trap_status_id = %s, rebaited = %s, bait_type_id = %s,
                            bait_amount = %s,
                            trap_condition_id = %s, strikes = %s, note = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE catches_id = %s
                    """, (date, species_id, sex, maturity, trap_status_id, rebaited, 
                          bait_type_id, new_bait_amount, trap_condition_id, strikes, note, catches_id))

                    new_bait_type_id = str(bait_type_id) if bait_type_id is not None else None

                    if old_bait_type_id != new_bait_type_id:
                        # Restore old bait amount to inventory
                        if old_bait_type_id:
                            old_bait_amount = record.get('bait_amount') if record else None
                            restore_delta = float(old_bait_amount) if old_bait_amount else 1.0
                            restored = adjust_bait_inventory(
                                cursor,
                                current_group_id,
                                old_bait_type_id,
                                restore_delta,
                            )
                            if restored is False:
                                flash(
                                    "Previous bait item could not be returned to inventory automatically.",
                                    "warning",
                                )

                        # Deduct new bait amount from inventory
                        if bait_type_id:
                            raw_amt = request.form.get('bait_amount')
                            try:
                                new_bait_amount = float(raw_amt) if raw_amt else 1.0
                            except ValueError:
                                new_bait_amount = 1.0

                            if new_bait_amount <= 0:
                                flash("Please enter a valid positive quantity for the bait used.", "warning")
                            else:
                                consumed = adjust_bait_inventory(
                                    cursor,
                                    current_group_id,
                                    bait_type_id,
                                    -new_bait_amount,
                                )
                                if consumed is False:
                                    flash(
                                        "New bait item could not be deducted from inventory automatically. Please verify inventory quantities.",
                                        "warning",
                                    )

                    conn.commit()
                    flash("Catch record updated successfully!", "success")
                    if role_id <= ROLE_COORDINATOR:
                         return redirect(url_for('admin.view_catches'))
                    return redirect(url_for('operator.view_catches'))
                except Exception as e:
                    conn.rollback()
                    current_app.logger.exception(f"SQL Error in edit_catch: {e}")
                    flash(f"Database error: {str(e)}", "danger")
                    return redirect(url_for('operator.edit_catch', catches_id=catches_id))
                
            cursor.execute("""
                SELECT tc.*, t.line_id, l.line_name, tc.updated_at
                FROM trap_catches tc
                JOIN traps t ON tc.trap_code = t.trap_code
                JOIN `lines` l ON t.line_id = l.line_id
                WHERE tc.catches_id = %s
            """, (catches_id,))
            catch = cursor.fetchone()
            
            cursor.execute("SELECT * FROM species ORDER BY species_name")
            all_species = cursor.fetchall()
            cursor.execute("SELECT * FROM trap_status ORDER BY status_name")
            all_statuses = cursor.fetchall()
            cursor.execute("SELECT * FROM bait_type ORDER BY bait_type_name")
            all_baits = cursor.fetchall()
            cursor.execute("SELECT * FROM trap_condition ORDER BY trap_condition_name")
            all_conditions = cursor.fetchall()
            
        return render_template('operator/edit_catch.html', 
                               catch=catch, 
                               all_species=all_species, 
                               all_statuses=all_statuses, 
                               all_baits=all_baits, 
                               all_conditions=all_conditions,
                               is_retired=is_retired)
                               
    except Exception as e:
        current_app.logger.exception(f"Error editing catch (operator): {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        flash("An error occurred while accessing the record.", "danger")
        return redirect(url_for('operator.operator_dashboard'))

