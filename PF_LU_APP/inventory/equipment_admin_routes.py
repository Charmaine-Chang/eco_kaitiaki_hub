from flask import render_template, request, redirect, url_for, flash, session
from PF_LU_APP.db import get_db, get_cursor_context
from PF_LU_APP.validators import validate_location_within_boundary
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR

@admin_bp.route('/add_equipment', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def add_equipment():
    current_group_id = session.get('current_group_id')
    if not current_group_id and not session.get('is_super_admin'):
        flash("Please enter a group context first (Home → Enter Group).", "info")
        return redirect(url_for('admin.admin_dashboard'))

    try:
        conn = get_db()
        with get_cursor_context() as cursor:
            if request.method == 'POST':
                equipment_type = request.form.get('equipment_type') # 'trap' or 'bait_station'
                code = request.form.get('code')
                line_id = request.form.get('line_id')
                latitude = request.form.get('latitude')
                longitude = request.form.get('longitude')

                if not all([equipment_type, code, line_id, latitude, longitude]):
                    flash("Please fill out all required fields.", "danger")
                    return redirect(url_for('admin.add_equipment', line_id=line_id))

                try:
                    lat = float(latitude)
                    lng = float(longitude)
                    l_id = int(line_id)
                except ValueError:
                    flash("Invalid numeric data provided for coordinates or assignments.", "danger")
                    return redirect(url_for('admin.add_equipment', line_id=line_id))

                cursor.execute("SELECT group_id FROM lines WHERE line_id = %s", (l_id,))
                line_row = cursor.fetchone()
                line_group_id = line_row['group_id'] if line_row else current_group_id

                if not validate_location_within_boundary(cursor, line_group_id, lat, lng):
                    flash(f"Cannot add {equipment_type.replace('_', ' ')}: coordinates are outside the group boundary.", "danger")
                    return redirect(url_for('admin.add_equipment', line_id=line_id))

                cursor.execute("SELECT equipment_status_id FROM equipment_status WHERE equipment_status_name = 'Deployed'")
                status_row = cursor.fetchone()
                status_id = status_row['equipment_status_id'] if status_row else None

                if equipment_type == 'trap':
                    trap_type_id = request.form.get('trap_type_id')
                    if not trap_type_id:
                        flash("Please select a trap model.", "danger")
                        return redirect(url_for('admin.add_equipment', line_id=line_id))
                    
                    cursor.execute('SELECT trap_code FROM traps WHERE trap_code = %s', (code,))
                    if cursor.fetchone():
                        flash(f"A trap with the code '{code}' already exists.", "danger")
                        return redirect(url_for('admin.add_equipment', line_id=line_id))

                    cursor.execute(
                        'INSERT INTO traps (trap_code, trap_type_id, line_id, latitude, longitude, equipment_status_id, status) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                        (code, int(trap_type_id), l_id, lat, lng, status_id, 'active'),
                    )
                    conn.commit()
                    flash("New trap added successfully and linked to line!", "success")

                elif equipment_type == 'bait_station':
                    bait_station_type_id = request.form.get('bait_station_type_id')
                    custom_station_type = request.form.get('custom_station_type')

                    if not bait_station_type_id and not custom_station_type:
                        flash("Please select or enter a bait station type.", "danger")
                        return redirect(url_for('admin.add_equipment', line_id=line_id))

                    cursor.execute('SELECT bait_station_code FROM bait_stations WHERE bait_station_code = %s', (code,))
                    if cursor.fetchone():
                        flash(f"A bait station with the code '{code}' already exists.", "danger")
                        return redirect(url_for('admin.add_equipment', line_id=line_id))

                    if bait_station_type_id == 'other' and custom_station_type:
                        cursor.execute("INSERT INTO bait_station_type (bait_station_type_name) VALUES (%s) RETURNING bait_station_type_id", (custom_station_type,))
                        bait_station_type_id = cursor.fetchone()['bait_station_type_id']
                    elif bait_station_type_id and bait_station_type_id != 'other':
                        bait_station_type_id = int(bait_station_type_id)
                    else:
                        flash("Please select a valid station type.", "warning")
                        return redirect(url_for('admin.add_equipment', line_id=line_id))

                    cursor.execute(
                        'INSERT INTO bait_stations (bait_station_code, bait_station_type_id, line_id, latitude, longitude, equipment_status_id, status) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                        (code, bait_station_type_id, l_id, lat, lng, status_id, 'active'),
                    )
                    conn.commit()
                    flash("New bait station added successfully and linked to line!", "success")

                return redirect(url_for('admin.add_equipment', line_id=line_id))

            # GET method
            if not session.get('is_super_admin'):
                cursor.execute("SELECT * FROM lines WHERE group_id = %s AND status = 'active' ORDER BY line_name ASC", (current_group_id,))
            else:
                cursor.execute("SELECT * FROM lines WHERE status = 'active' ORDER BY line_name ASC")
            lines = cursor.fetchall()

            cursor.execute('SELECT * FROM trap_type ORDER BY trap_type_name ASC')
            trap_types = cursor.fetchall()

            cursor.execute("SELECT * FROM bait_station_type ORDER BY bait_station_type_name ASC")
            station_types = cursor.fetchall()

            selected_line_id = request.args.get('line_id')
            equipment = []
            selected_line_group_id = None
            if selected_line_id:
                cursor.execute(
                    '''
                    SELECT t.trap_code as code, tt.trap_type_name as type, l.line_name, t.latitude, t.longitude, t.created_at, 'trap' as item_type
                    FROM traps t
                    JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
                    JOIN lines l ON t.line_id = l.line_id
                    WHERE t.line_id = %s AND (t.status = 'active' OR t.status IS NULL)
                    ''', (selected_line_id,)
                )
                traps = cursor.fetchall()

                cursor.execute(
                    '''
                    SELECT b.bait_station_code as code, bt.bait_station_type_name as type, l.line_name, b.latitude, b.longitude, b.created_at, 'bait_station' as item_type
                    FROM bait_stations b
                    JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
                    JOIN lines l ON b.line_id = l.line_id
                    WHERE b.line_id = %s AND (b.status = 'active' OR b.status IS NULL)
                    ''', (selected_line_id,)
                )
                stations = cursor.fetchall()
                
                # Sort descending by created_at handling None
                equipment = sorted(list(traps) + list(stations), key=lambda x: str(x['created_at']) if x['created_at'] else '', reverse=True)

                cursor.execute("SELECT group_id FROM lines WHERE line_id = %s", (selected_line_id,))
                line_row = cursor.fetchone()
                if line_row:
                    selected_line_group_id = line_row['group_id']

            boundary_geojson = None
            group_latitude = None
            group_longitude = None
            target_boundary_group_id = selected_line_group_id if selected_line_group_id else current_group_id
            if target_boundary_group_id:
                cursor.execute("SELECT boundary_geojson, latitude, longitude, group_name FROM groups WHERE group_id = %s", (target_boundary_group_id,))
                grp = cursor.fetchone()
                if grp and grp['group_name'] != 'System Management':
                    boundary_geojson = grp.get('boundary_geojson')
                    group_latitude = grp.get('latitude')
                    group_longitude = grp.get('longitude')

            return render_template(
                'admin/add_equipment.html',
                lines=lines,
                trap_types=trap_types,
                station_types=station_types,
                equipment=equipment,
                selected_line_id=selected_line_id,
                boundary_geojson=boundary_geojson,
                group_latitude=group_latitude,
                group_longitude=group_longitude,
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash("An error occurred while accessing the database.", "danger")
        return redirect(url_for('admin.view_lines'))
