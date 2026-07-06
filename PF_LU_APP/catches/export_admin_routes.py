import csv
import io
from datetime import datetime
from flask import request, redirect, url_for, flash, session, make_response, render_template, current_app
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER
from PF_LU_APP.catches.catch_repository import fetch_catches_for_csv
from PF_LU_APP.utils.pdf_generator import generate_table_export_pdf, FPDF_AVAILABLE
from PF_LU_APP.repositories.export_repository import (
    get_all_active_groups, get_group_name_by_id, 
    get_traps_export_data, get_bait_stations_export_data
)

@admin_bp.route('/operator/download_csv', methods=['GET'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)
def download_catches_csv():
    try:
        catches = fetch_catches_for_csv(
            session,
            request.args.get('line_filter'),
            request.args.get('species_filter'),
            request.args.get('start_date'),
            request.args.get('end_date'),
        )
    except Exception as e:
        current_app.logger.exception(f"Error generating CSV: {e}")
        flash("Could not generate CSV file.", "danger")
        return redirect(url_for('admin.view_catches'))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Record ID', 'Trap Code', 'Date', 'Line', 'Species', 'Sex', 'Maturity',
        'Trap Status', 'Rebaited', 'Bait Type', 'Trap Condition', 'Strikes', 'Note',
        'Recorded By',
    ])
    for c in catches:
        writer.writerow([
            c['catches_id'],
            c['trap_code'],
            c['date'].strftime('%Y-%m-%d %H:%M') if c['date'] else '',
            c['line_name'],
            c['species_name'],
            c['sex'],
            c['maturity'],
            c['trap_status'],
            'Yes' if c['rebaited'] else 'No',
            c['bait_type_name'] or '',
            c['trap_condition'],
            c['strikes'],
            c['note'] or '',
            c['recorded_by_name'],
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=trap_catch_records.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    return response



@admin_bp.route('/export', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)
def export_data():
    group_id = session.get('current_group_id')
    is_super_admin = session.get('is_super_admin', False)
    
    if not group_id and not is_super_admin:
        flash('No group context found. Please select a group first.', 'danger')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        form_group_id = request.form.get('group_id')
        if is_super_admin and form_group_id:
            group_id = form_group_id

    if not group_id and request.method == 'POST':
        flash('Please select a group to export.', 'warning')
        return redirect(url_for('admin.export_data'))

    all_groups = []
    if is_super_admin:
        all_groups = get_all_active_groups()

    group_name = 'All Groups'
    if group_id:
        group_name = get_group_name_by_id(group_id)
    
    if request.method == 'GET':
        return render_template('admin/export.html', 
                               today=datetime.today().strftime('%Y-%m-%d'), 
                               group_name=group_name,
                               all_groups=all_groups,
                               current_group_id=group_id)

    export_type = request.form.get('export_type', 'traps')
    date_from   = request.form.get('date_from', '').strip()
    date_to     = request.form.get('date_to', '').strip()
    selected_cols = request.form.getlist('columns')
    export_format = request.form.get('format', 'csv')
    if session.get('role_id') == ROLE_OPERATOR and export_format == 'pdf':
        flash('PDF export is restricted to administrators and coordinators.', 'danger')
        return redirect(url_for('admin.export_data'))
    today_str  = datetime.today().strftime('%Y-%m-%d')
    
    # ── Define Field Mappings ──
    trap_field_map = {
        'code': ('code', 'Code'),
        'date': ('date', 'Date'),
        'line': ('line', 'Line'),
        'recorded_by': ('recorded_by', 'Recorded By'),
        'species_caught': ('species_caught', 'Species Caught'),
        'sex': ('sex', 'Sex'),
        'maturity': ('maturity', 'Maturity'),
        'status': ('status', 'Status'),
        'rebaited': ('rebaited', 'Rebaited'),
        'bait_type': ('bait_type', 'Bait Type'),
        'trap_condition': ('trap_condition', 'Condition'),
        'strikes': ('strikes', 'Strikes'),
        'notes': ('note', 'Notes')
    }
    bait_field_map = {
        'code': ('code', 'Code'),
        'date': ('date', 'Date'),
        'line': ('line', 'Line'),
        'recorded_by': ('recorded_by', 'Recorded By'),
        'bait_type': ('bait_type', 'Bait Type'),
        'target_species': ('target_species', 'Target Species'),
        'active_ingredient': ('active_ingredient', 'Active Ingredient'),
        'formulation': ('formulation', 'Formulation'),
        'concentration': ('concentration', 'Concentration'),
        'bait_remaining': ('bait_remaining', 'Bait Remaining'),
        'bait_removed': ('bait_removed', 'Bait Removed'),
        'bait_added': ('bait_added', 'Bait Added'),
        'notes': ('notes', 'Notes')
    }

    # Default to trap.nz standard if no columns selected
    if not selected_cols:
        if export_type == 'traps':
            selected_cols = ['code', 'date', 'species_caught', 'status', 'rebaited', 'bait_type', 'trap_condition', 'strikes']
        else:
            selected_cols = ['code', 'date']

    field_map = trap_field_map if export_type == 'traps' else bait_field_map
    
    # Filter only valid columns
    active_cols = [c for c in selected_cols if c in field_map]
    if not active_cols:
        flash('At least one column must be selected.', 'warning')
        return redirect(url_for('admin.export_data'))

    # Compile filter summary string
    filter_details = []
    if date_from:
        filter_details.append(f"From {date_from}")
    if date_to:
        filter_details.append(f"To {date_to}")
    filter_summary = " & ".join(filter_details) if filter_details else "All Dates"

    try:
        if export_type == 'traps':
            rows = get_traps_export_data(group_id, date_from, date_to)
            filename = f"mokomoko_traps_{date_from or 'all'}_to_{date_to or 'all'}.csv"
        else:
            rows = get_bait_stations_export_data(group_id, date_from, date_to)
            filename = f"mokomoko_baitstations_{date_from or 'all'}_to_{date_to or 'all'}.csv"
    except Exception as e:
        current_app.logger.exception(f'Export query error: {e}')
        flash('An error occurred querying the export database.', 'danger')
        return redirect(url_for('admin.export_data'))

    # ── Export CSV Format ──
    if export_format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)

        # Write metadata headers required by User Story
        writer.writerow(["Group Name", group_name])
        writer.writerow(["Generated Date", datetime.now().strftime('%Y-%m-%d %H:%M')])
        writer.writerow(["Filter Summary", filter_summary])
        writer.writerow([]) # Separator row

        # Write data table headers
        headers = [field_map[c][1] for c in active_cols]
        writer.writerow(headers)

        for row in rows:
            writer.writerow([row[field_map[c][0]] for c in active_cols])

        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        return response

    # ── Export PDF Format ──
    else:
        if not FPDF_AVAILABLE:
            flash("PDF export requires 'fpdf2' package. Install with: pip install fpdf2", "danger")
            return redirect(url_for('admin.export_data'))

        column_weights = {
            'code': 25, 'date': 28, 'line': 25, 'recorded_by': 22, 'species_caught': 25,
            'sex': 15, 'maturity': 15, 'status': 20, 'rebaited': 15, 'bait_type': 22,
            'trap_condition': 22, 'strikes': 15, 'notes': 40,
            'target_species': 25, 'active_ingredient': 25, 'formulation': 22, 'concentration': 20,
            'bait_remaining': 22, 'bait_removed': 22, 'bait_added': 22
        }

        pdf_data = generate_table_export_pdf(
            group_name=group_name,
            title="Trap Catch Records Export" if export_type == 'traps' else "Bait Station Records Export",
            filter_summary=filter_summary,
            active_cols=active_cols,
            field_map=field_map,
            rows=rows,
            column_weights=column_weights
        )

        pdf_filename = filename.replace('.csv', '.pdf')
        response = make_response(pdf_data)
        response.headers['Content-Disposition'] = f'attachment; filename={pdf_filename}'
        response.headers['Content-Type'] = 'application/pdf'
        return response
