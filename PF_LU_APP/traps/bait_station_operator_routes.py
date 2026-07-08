from flask import render_template, session, redirect, url_for, request, flash, current_app
from PF_LU_APP.db import get_db, get_cursor_context
from PF_LU_APP.roles.operator import operator_bp
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.shared.inventory import adjust_bait_inventory

@operator_bp.route('/add_bait_record', methods=['GET', 'POST'])
@operator_bp.route('/add_bait_record/<string:bait_station_code>', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)
def add_bait_record(bait_station_code=None):
    line_id = request.args.get('line_id')
    
    if not bait_station_code and request.method == 'POST':
        bait_station_code = request.form.get('bait_station_code')
        
    if bait_station_code:
        try:
            with get_cursor_context() as cursor:
                cursor.execute("""
                    SELECT b.status, es.equipment_status_name
                    FROM bait_stations b
                    LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
                    WHERE b.bait_station_code = %s
                """, (bait_station_code,))
                bs_chk = cursor.fetchone()
                
                if not bs_chk:
                    flash("Bait station not found.", "danger")
                    return redirect(url_for('operator.operator_dashboard'))
                if bs_chk['status'] == 'inactive' or bs_chk['equipment_status_name'] == 'Retired':
                    flash("The item is no longer in service.", "danger")
                    return redirect(url_for('operator.operator_dashboard'))
        except Exception as e:
            current_app.logger.exception(f"Error checking bait station status in add_bait_record: {e}")

    if request.method == 'POST' and bait_station_code:
        date = request.form.get('date')
        target_species_id = request.form.get('target_species_id')
        bait_type_id = request.form.get('bait_type_id') or None
        active_ingredient = request.form.get('active_ingredient')
        formulation = request.form.get('formulation')
        concentration = request.form.get('concentration') or 0
        bait_remaining = request.form.get('bait_remaining') or 0
        bait_removed = request.form.get('bait_removed') or 0
        bait_added = request.form.get('bait_added') or 0
        notes = request.form.get('notes')

        try:
            f_concentration = float(concentration)
            f_bait_remaining = float(bait_remaining)
            f_bait_removed = float(bait_removed)
            f_bait_added = float(bait_added)
        except ValueError:
            flash("Invalid numeric value provided for bait quantities.", "danger")
            return redirect(url_for('operator.add_bait_record', bait_station_code=bait_station_code))

        if not all([date, target_species_id]):
            flash("Date and Target Species are required.", "danger")
        elif f_concentration < 0 or f_bait_remaining < 0 or f_bait_removed < 0 or f_bait_added < 0:
            flash("Concentration and bait quantities must be non-negative.", "danger")
        else:
            try:
                conn = get_db()
                with get_cursor_context() as cursor:
                    # Get group_id for this bait station
                    cursor.execute("""
                        SELECT l.group_id 
                        FROM bait_stations bs
                        JOIN `lines` l ON bs.line_id = l.line_id
                        WHERE bs.bait_station_code = %s
                    """, (bait_station_code,))
                    bs_row = cursor.fetchone()
                    group_id = bs_row['group_id'] if bs_row else None

                    if bait_type_id and f_bait_added > 0:
                        inventory_result = adjust_bait_inventory(
                            cursor,
                            group_id,
                            bait_type_id,
                            -f_bait_added
                        )
                        if inventory_result is not True:
                            conn.rollback()
                            flash(
                                "Bait selected but inventory could not be reduced because stock is unavailable. Please verify inventory quantities.",
                                "danger",
                            )
                            return redirect(url_for('operator.add_bait_record', bait_station_code=bait_station_code))

                    cursor.execute("""
                        INSERT INTO bait_station_records (
                            bait_station_code, recorded_by, target_species_id, bait_type_id, date, 
                            active_ingredient, formulation, concentration, 
                            bait_remaining, bait_removed, bait_added, notes
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (bait_station_code, session['user_id'], target_species_id, bait_type_id, date, 
                          active_ingredient, formulation, f_concentration, 
                          f_bait_remaining, f_bait_removed, f_bait_added, notes))

                    conn.commit()
                    flash("Bait station record saved successfully!", "success")

                with get_cursor_context() as curr:
                    curr.execute("SELECT line_id FROM bait_stations WHERE bait_station_code = %s", (bait_station_code,))
                    bs_info = curr.fetchone()

                if bs_info:
                    line_id = bs_info['line_id']
                    return redirect(url_for('operator.view_lines', line_id=line_id))
                return redirect(url_for('operator.operator_dashboard'))
            except Exception as e:
                current_app.logger.exception(f"Error adding bait record: {e}")
                flash("An error occurred while saving the record.", "danger")

    bait_stations = []
    line = None
    station = None
    species = []
    ingredients = []
    formulations = []
    baits = []

    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            if bait_station_code:
                cursor.execute("SELECT * FROM bait_stations WHERE bait_station_code = %s", (bait_station_code,))
                station = cursor.fetchone()
                if not station:
                    flash("Bait station not found.", "danger")
                    return redirect(url_for('operator.operator_dashboard'))
                if not line_id and station:
                    line_id = station['line_id']
            elif line_id:
                cursor.execute("SELECT line_name FROM `lines` WHERE line_id = %s", (line_id,))
                line = cursor.fetchone()
                cursor.execute("SELECT * FROM bait_stations WHERE line_id = %s AND status = 'active' ORDER BY bait_station_code", (line_id,))
                bait_stations = cursor.fetchall()

            cursor.execute("SELECT * FROM species ORDER BY species_name")
            species = cursor.fetchall()
            cursor.execute("SELECT * FROM bait_type ORDER BY bait_type_name")
            baits = cursor.fetchall()
            
            try:
                cursor.execute("SELECT * FROM bait_ingredients ORDER BY ingredient_name")
                ingredients = cursor.fetchall()
            except Exception:
                conn.rollback()
                ingredients = []
            
            try:
                cursor.execute("SELECT * FROM bait_formulations ORDER BY formulation_name")
                formulations = cursor.fetchall()
            except Exception:
                conn.rollback()
                formulations = []
                
    except Exception as e:
        current_app.logger.exception(f"Error loading bait record form data: {e}")
        try:
            conn.rollback()
        except Exception:
            pass

    return render_template('operator/add_bait_record.html', 
                           bait_station_code=bait_station_code, 
                           station=station, 
                           line_id=line_id, 
                           line=line,
                           bait_stations=bait_stations, 
                           species=species,
                           baits=baits,
                           ingredients=ingredients,
                           formulations=formulations)

@operator_bp.route('/view_bait_records', methods=['GET'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER)
def view_bait_records():
    current_group_id = session.get('current_group_id')
    conn = get_db()
    try:
        with get_cursor_context() as cursor:
            if session.get('is_super_admin'):
                cursor.execute("SELECT line_id, line_name FROM `lines` WHERE status = 'active' AND line_type = 'bait_station' ORDER BY line_name ASC")
            elif session.get('role_id') in (ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER):
                cursor.execute("SELECT line_id, line_name FROM `lines` WHERE status = 'active' AND line_type = 'bait_station' AND group_id = %s ORDER BY line_name ASC", (current_group_id,))
            else:
                cursor.execute("""SELECT l.line_id, l.line_name
                    FROM `lines` l 
                    JOIN operator_lines ol ON l.line_id = ol.line_id
                    WHERE l.status = 'active' AND l.line_type = 'bait_station' AND ol.user_id = %s
                    ORDER BY l.line_name ASC""", (session['user_id'],))
            all_lines = cursor.fetchall()
            
            cursor.execute("SELECT species_id, species_name FROM species WHERE species_id IN (SELECT DISTINCT target_species_id FROM bait_station_records) ORDER BY species_name ASC")
            all_target_species = cursor.fetchall()
            
            line_filter = request.args.get('line_filter')
            target_species_filter = request.args.get('target_species_filter')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            line = None
            if line_filter:
                cursor.execute("SELECT line_name FROM `lines` WHERE line_id = %s", (line_filter,))
                line = cursor.fetchone()

            query = """
                SELECT bsr.record_id, bsr.bait_station_code, bsr.`date`, s.species_name as target_species,
                       bsr.active_ingredient, bsr.formulation, bsr.concentration,
                       bsr.bait_remaining, bsr.bait_removed, bsr.bait_added, bsr.notes,
                       CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, '')) as recorded_by_name,
                       bsr.recorded_by, l.line_name, bsr.updated_at,
                       bs.latitude, bs.longitude,
                       bs.status AS station_overall_status, es_bs.equipment_status_name AS station_equipment_status,
                       bt.bait_type_name
                FROM bait_station_records bsr
                JOIN bait_stations bs ON bsr.bait_station_code = bs.bait_station_code
                LEFT JOIN equipment_status es_bs ON bs.equipment_status_id = es_bs.equipment_status_id
                JOIN `lines` l ON bs.line_id = l.line_id
                JOIN species s ON bsr.target_species_id = s.species_id
                JOIN users u ON bsr.recorded_by = u.user_id
                LEFT JOIN bait_type bt ON bsr.bait_type_id = bt.bait_type_id
                WHERE 1=1
            """
            params = []
            if session.get('is_super_admin'):
                pass
            elif session.get('role_id') in (ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER):
                query += " AND l.group_id = %s"
                params.append(current_group_id)
            else:
                query += " AND l.line_id IN (SELECT line_id FROM operator_lines WHERE user_id = %s)"
                params.append(session.get('user_id'))
                
            if line_filter:
                query += " AND l.line_id = %s"
                params.append(line_filter)
            if target_species_filter:
                query += " AND bsr.target_species_id = %s"
                params.append(target_species_filter)
            if start_date:
                query += " AND DATE(bsr.`date`) >= %s"
                params.append(start_date)
            if end_date:
                query += " AND DATE(bsr.`date`) <= %s"
                params.append(f"{end_date} 23:59:59")
                
            query += " ORDER BY bsr.`date` DESC"
            
            cursor.execute(query, tuple(params))
            records = cursor.fetchall()

            # Build map data from records (grouped by station)
            map_data = []
            seen_stations = set()
            for r in records:
                if r.get('latitude') and r.get('longitude') and r['bait_station_code'] not in seen_stations:
                    map_data.append({
                        'bait_station_code': r['bait_station_code'],
                        'target_species': r['target_species'],
                        'bait_type_name': r['bait_type_name'] or '',
                        'formulation': r['formulation'] or '',
                        'date': r['date'].strftime('%Y-%m-%d %H:%M') if r['date'] else 'N/A',
                        'lat': float(r['latitude']),
                        'lng': float(r['longitude']),
                        'line_name': r['line_name'],
                    })
                    seen_stations.add(r['bait_station_code'])

            # ── KPI & STATISTICS ──────────────────────────────────────
            stats = {
                'total_records': len(records),
                'active_stations': 0,
                'maintenance_required': 0
            }

            # Active Stations
            cursor.execute("SELECT COUNT(*) as count FROM bait_stations bs JOIN `lines` l ON bs.line_id = l.line_id WHERE (bs.status = 'active' OR bs.status IS NULL) AND l.group_id = %s", (current_group_id,))
            stats['active_stations'] = cursor.fetchone()['count']

            # Maintenance Required
            maint_query = """
                SELECT COUNT(DISTINCT bs.bait_station_code) as count 
                FROM bait_stations bs
                JOIN `lines` l ON bs.line_id = l.line_id
                LEFT JOIN equipment_status es ON bs.equipment_status_id = es.equipment_status_id
                WHERE l.group_id = %s AND (es.equipment_status_name != 'Functional' AND es.equipment_status_name IS NOT NULL)
            """
            cursor.execute(maint_query, (current_group_id,))
            stats['maintenance_required'] = cursor.fetchone()['count']

            # Species Distribution (from records)
            dist_query = """
                SELECT s.species_name, COUNT(*) as count
                FROM bait_station_records bsr
                JOIN species s ON bsr.target_species_id = s.species_id
                JOIN bait_stations bs ON bsr.bait_station_code = bs.bait_station_code
                JOIN `lines` l ON bs.line_id = l.line_id
                WHERE l.group_id = %s
                GROUP BY s.species_name ORDER BY count DESC
            """
            cursor.execute(dist_query, (current_group_id,))
            species_distribution = cursor.fetchall()

        import json
        return render_template('operator/bait_list.html', 
                               records=records, 
                               all_lines=all_lines,
                               all_target_species=all_target_species,
                               line=line,
                               line_filter=line_filter,
                               target_species_filter=target_species_filter,
                               start_date=start_date,
                               end_date=end_date,
                               stats=stats,
                               map_data=json.dumps(map_data),
                               species_distribution=json.dumps([dict(row) for row in species_distribution]))
    except Exception as e:
        current_app.logger.exception(f"Error viewing bait records: {e}")
        flash(f"Could not load bait records: {str(e)}", "danger")
        return redirect(url_for('operator.operator_dashboard'))

@operator_bp.route('/edit_bait_record/<int:record_id>', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)
def edit_bait_record(record_id):
    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            cursor.execute("SELECT recorded_by, bait_type_id, bait_added FROM bait_station_records WHERE record_id = %s", (record_id,))
            record = cursor.fetchone()
            
            if not record:
                flash("Bait record not found.", "danger")
                return redirect(url_for('operator.operator_dashboard'))
                
            # Check if the associated bait station is retired
            cursor.execute("""
                SELECT bs.status, es.equipment_status_name
                FROM bait_stations bs
                LEFT JOIN equipment_status es ON bs.equipment_status_id = es.equipment_status_id
                WHERE bs.bait_station_code = (SELECT bait_station_code FROM bait_station_records WHERE record_id = %s)
            """, (record_id,))
            bs_status_row = cursor.fetchone()
            is_retired = False
            if bs_status_row:
                is_retired = (bs_status_row['status'] == 'inactive' or bs_status_row['equipment_status_name'] == 'Retired')
                
            # Permission Check
            role_id = session.get('role_id')
            current_group_id = session.get('current_group_id')

            # Scope Check: Find which group this record belongs to
            cursor.execute("""
                SELECT l.group_id 
                FROM bait_station_records bsr
                JOIN bait_stations bs ON bsr.bait_station_code = bs.bait_station_code
                JOIN `lines` l ON bs.line_id = l.line_id
                WHERE bsr.record_id = %s
            """, (record_id,))
            record_group = cursor.fetchone()

            if session.get('is_super_admin'):
                pass # Authorized
            elif role_id == ROLE_COORDINATOR: # Coordinator
                if not record_group or str(record_group['group_id']) != str(current_group_id):
                    flash("Access denied. You can only edit records within your own group.", "danger")
                    return redirect(url_for('operator.view_bait_records'))
            else: # Operator
                if record['recorded_by'] != session.get('user_id'):
                    flash("You can only edit records that you created yourself.", "danger")
                    return redirect(url_for('operator.view_bait_records'))
                
            if request.method == 'POST':
                if is_retired:
                    flash("Cannot modify records associated with a retired item.", "warning")
                    return redirect(url_for('operator.edit_bait_record', record_id=record_id))

                date = request.form.get('date')
                target_species_id = request.form.get('target_species_id')
                bait_type_id = request.form.get('bait_type_id') or None
                active_ingredient = request.form.get('active_ingredient')
                formulation = request.form.get('formulation')
                concentration = request.form.get('concentration') or 0
                bait_remaining = request.form.get('bait_remaining') or 0
                bait_removed = request.form.get('bait_removed') or 0
                bait_added = request.form.get('bait_added') or 0
                notes = request.form.get('notes')
                
                try:
                    f_concentration = float(concentration)
                    f_bait_remaining = float(bait_remaining)
                    f_bait_removed = float(bait_removed)
                    f_bait_added = float(bait_added)
                except ValueError:
                    flash("Invalid numeric value provided for bait quantities.", "danger")
                    return redirect(url_for('operator.edit_bait_record', record_id=record_id))

                if not all([date, target_species_id, active_ingredient, formulation]):
                    flash("Please fill in all required fields.", "danger")
                elif f_concentration < 0 or f_bait_remaining < 0 or f_bait_removed < 0 or f_bait_added < 0:
                    flash("Concentration and bait quantities must be non-negative.", "danger")
                else:
                    try:
                        group_id = record_group['group_id'] if record_group else None
                        
                        old_bait_type_id = record['bait_type_id'] if record else None
                        old_bait_added = float(record['bait_added']) if (record and record['bait_added'] is not None) else 0.0
                        
                        new_bait_type_id = int(bait_type_id) if bait_type_id is not None else None
                        new_bait_added = f_bait_added
                        
                        # Revert old inventory addition
                        if old_bait_type_id and old_bait_added > 0:
                            adjust_bait_inventory(
                                cursor,
                                group_id,
                                old_bait_type_id,
                                old_bait_added
                            )
                            
                        # Deduct new inventory addition
                        if new_bait_type_id and new_bait_added > 0:
                            consumed = adjust_bait_inventory(
                                cursor,
                                group_id,
                                new_bait_type_id,
                                -new_bait_added
                            )
                            if consumed is False:
                                flash(
                                    "New bait item could not be deducted from inventory automatically. Please verify inventory quantities.",
                                    "warning",
                                )

                        cursor.execute("""
                            UPDATE bait_station_records
                            SET date = %s, target_species_id = %s, bait_type_id = %s,
                                active_ingredient = %s, 
                                formulation = %s, concentration = %s, bait_remaining = %s, 
                                bait_removed = %s, bait_added = %s, notes = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE record_id = %s
                        """, (date, target_species_id, bait_type_id, active_ingredient, formulation, 
                              f_concentration, f_bait_remaining, f_bait_removed, f_bait_added, notes, record_id))
                        conn.commit()
                        flash("Bait record updated successfully!", "success")
                        return redirect(url_for('operator.view_bait_records'))
                    except Exception as e:
                        conn.rollback()
                        current_app.logger.exception(f"SQL Error in edit_bait_record: {e}")
                        flash(f"Database error: {str(e)}", "danger")
                        return redirect(url_for('operator.edit_bait_record', record_id=record_id))
                    
            cursor.execute("""
                SELECT bsr.*, bs.line_id, l.line_name
                FROM bait_station_records bsr
                JOIN bait_stations bs ON bsr.bait_station_code = bs.bait_station_code
                JOIN `lines` l ON bs.line_id = l.line_id
                WHERE bsr.record_id = %s
            """, (record_id,))
            bait_record = cursor.fetchone()
            
            cursor.execute("SELECT * FROM species ORDER BY species_name")
            all_species = cursor.fetchall()
            cursor.execute("SELECT * FROM bait_type ORDER BY bait_type_name")
            all_baits = cursor.fetchall()
            
            try:
                cursor.execute("SELECT * FROM bait_ingredients ORDER BY ingredient_name")
                all_ingredients = cursor.fetchall()
            except Exception:
                conn.rollback()
                all_ingredients = []
                
            try:
                cursor.execute("SELECT * FROM bait_formulations ORDER BY formulation_name")
                all_formulations = cursor.fetchall()
            except Exception:
                conn.rollback()
                all_formulations = []
            
        return render_template('operator/edit_bait_record.html', 
                               record=bait_record, 
                               species=all_species, 
                               baits=all_baits,
                               ingredients=all_ingredients, 
                               formulations=all_formulations,
                               is_retired=is_retired)
                               
    except Exception as e:
        current_app.logger.exception(f"Error editing bait record: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        flash("An error occurred while accessing the record.", "danger")
        return redirect(url_for('operator.operator_dashboard'))