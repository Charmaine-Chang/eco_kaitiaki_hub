import csv
import io
import json
from flask import Blueprint, render_template, session, redirect, url_for, request, make_response, flash, current_app
from PF_LU_APP.db import get_cursor_context
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.shared.utils import resolve_date_preset
from PF_LU_APP.catches.catch_repository import (
    fetch_catches, fetch_catches_kpis,
    fetch_catches_for_csv,
)
from PF_LU_APP.catches.analytics_repository import (
    fetch_species_distribution, fetch_data_graphs, fetch_trend_analytics,
)

from PF_LU_APP.roles.observer import observer_bp

@observer_bp.route('/graphs', methods=['GET', 'POST'])
@roles_required(ROLE_OBSERVER)
def data_graphs():
    line_ids = [line_id for line_id in request.args.getlist('line_id') if line_id]
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    preset = request.args.get('preset')
    species_id = request.args.get('species_id')
    record_type = request.args.get('record_type', 'all')
    operator_id = request.args.get('operator_id')
    if record_type not in ('all', 'trap', 'bait'):
        record_type = 'all'

    if preset:
        start_date, end_date = resolve_date_preset(preset)

    try:
        data = fetch_data_graphs(session, line_ids, start_date, end_date, species_id, record_type, operator_id)
        return render_template('dashboards/graphs.html',
                               lines=data['lines'],
                               selected_line_id=line_ids[0] if len(line_ids) == 1 else '',
                               selected_line_ids=line_ids,
                               species=data['species'],
                               operators=data['operators'],
                               species_filter=species_id,
                               record_type_filter=record_type,
                               selected_operator_id=operator_id,
                               start_date=start_date,
                               end_date=end_date,
                               species_data=json.dumps(data['species_data']),
                               lines_data=json.dumps(data['lines_data']),
                               dates_data=json.dumps(data['dates_data']),
                               seasonal_data=json.dumps(data['seasonal_data']),
                               map_data=json.dumps(data['map_data']),
                               kpis=data['kpis'],
                               recent_catches=data['recent_catches'],
                               operator_stats=data['operator_stats'],
                               selected_operator_detail=data['selected_operator_detail'],
                               line_hotspots=data['line_hotspots'],
                               station_hotspots=data['station_hotspots'],
                               role='observer')
    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.exception(f"Error loading graphs: {e}")
        flash(f"Could not load graph data: {e}", "danger")
        return render_template('dashboards/graphs.html',
                               lines=[], selected_line_id='', selected_line_ids=line_ids,
                               species=[], operators=[], species_filter=species_id,
                               record_type_filter=record_type, selected_operator_id=operator_id,
                               start_date=start_date, end_date=end_date,
                               species_data='[]', lines_data='[]', dates_data='[]',
                               seasonal_data='[]', map_data='[]',
                               kpis={'total_catches': 0, 'active_lines': 0, 'active_stations': 0,
                                     'total_trap_records': 0, 'total_bait_records': 0,
                                     'total_bait_consumed': 0, 'maintenance_issues': 0,
                                     'success_rate': 0, 'hotspot': 'N/A'},
                               recent_catches=[], operator_stats=[],
                               selected_operator_detail=None, line_hotspots=[],
                               station_hotspots=[], role='observer')

@observer_bp.route('/operator/download_csv')
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
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
        return redirect(url_for('observer.view_catches'))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Record ID', 'Trap Code', 'Date', 'Line', 'Species', 'Sex', 'Maturity',
        'Trap Status', 'Rebaited', 'Bait Type', 'Trap Condition', 'Strikes', 'Note',
        'Recorded By'
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
            c['note'],
            c['recorded_by_name']
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=observer_catch_records.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    return response


@observer_bp.route('/graphs/download-report', methods=['GET'])
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR)
def download_graphs_report():
    from PF_LU_APP.utils.pdf_generator import generate_graphs_report_pdf
    from datetime import datetime

    report_type = request.args.get('report_type', 'summary')
    line_id = request.args.get('line_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    try:
        with get_cursor_context() as cursor:
            current_group_id = session.get('current_group_id')

            where_clause = ['l.group_id = %s']
            params = [current_group_id]

            if line_id:
                where_clause.append('t.line_id = %s')
                params.append(line_id)
            if start_date:
                where_clause.append('tc.date >= %s')
                params.append(start_date)
            if end_date:
                where_clause.append('tc.date <= %s')
                params.append(f"{end_date} 23:59:59")

            where_str = " AND ".join(where_clause)

            cursor.execute(f"""SELECT s.species_name, COUNT(*) as count
                FROM trap_catches tc JOIN species s ON tc.species_id = s.species_id
                JOIN traps t ON tc.trap_code = t.trap_code
                JOIN lines l ON t.line_id = l.line_id
                WHERE {where_str} GROUP BY s.species_name""", tuple(params))
            species_data = [dict(r) for r in cursor.fetchall()]

            cursor.execute(f"""SELECT l.line_name, COUNT(*) as count
                FROM trap_catches tc JOIN traps t ON tc.trap_code = t.trap_code
                JOIN lines l ON t.line_id = l.line_id
                WHERE {where_str} GROUP BY l.line_name""", tuple(params))
            lines_data = [dict(r) for r in cursor.fetchall()]

            cursor.execute(f"""SELECT TO_CHAR(DATE(tc.date), 'YYYY-MM-DD') as catch_date, COUNT(*) as count
                FROM trap_catches tc JOIN traps t ON tc.trap_code = t.trap_code
                JOIN lines l ON t.line_id = l.line_id
                WHERE {where_str} GROUP BY DATE(tc.date) ORDER BY DATE(tc.date)""", tuple(params))
            dates_data = [dict(r) for r in cursor.fetchall()]

            total_catches = sum(d['count'] for d in species_data)
            active_lines_count = len(lines_data)
            hotspot = max(lines_data, key=lambda x: x['count'])['line_name'] if lines_data else 'N/A'

            cursor.execute(f"SELECT COUNT(*) as count FROM trap_catches tc JOIN traps t ON tc.trap_code = t.trap_code JOIN lines l ON t.line_id = l.line_id WHERE {where_str}", tuple(params))
            total_records = cursor.fetchone()['count']
            success_rate = round((total_catches / total_records) * 100, 1) if total_records > 0 else 0

            cursor.execute(f"""SELECT tc.date, s.species_name, t.trap_code, l.line_name, g.group_name
                FROM trap_catches tc JOIN species s ON tc.species_id = s.species_id
                JOIN traps t ON tc.trap_code = t.trap_code
                JOIN lines l ON t.line_id = l.line_id
                JOIN groups g ON l.group_id = g.group_id
                WHERE {where_str} ORDER BY tc.date DESC LIMIT 10""", tuple(params))
            recent_catches = cursor.fetchall()

            cursor.execute("SELECT group_name FROM groups WHERE group_id = %s", (current_group_id,))
            g = cursor.fetchone()
            group_name = g['group_name'] if g else 'Unknown Group'

            filter_parts = []
            if line_id:
                filter_parts.append(f"Line {line_id}")
            if start_date:
                filter_parts.append(f"From {start_date}")
            if end_date:
                filter_parts.append(f"To {end_date}")
            filter_summary = " & ".join(filter_parts) if filter_parts else "All Data"

            kpis = {'total_catches': total_catches, 'active_lines': active_lines_count, 'success_rate': success_rate, 'hotspot': hotspot}

            pdf_data = generate_graphs_report_pdf(
                group_name, species_data, lines_data, dates_data,
                kpis, recent_catches, report_type, filter_summary
            )

            type_label = {'summary': 'executive_summary', 'species': 'species_analysis', 'full': 'full_report'}.get(report_type, 'report')
            filename = f"mokomoko_graphs_{type_label}_{datetime.today().strftime('%Y%m%d')}.pdf"

            response = make_response(pdf_data)
            response.headers['Content-Disposition'] = f'attachment; filename={filename}'
            response.headers['Content-Type'] = 'application/pdf'
            return response

    except Exception as e:
        current_app.logger.exception(f"Error generating graphs report: {e}")
        flash("Could not generate the report.", "danger")
        return redirect(url_for('observer.data_graphs', line_id=line_id, start_date=start_date, end_date=end_date))


@observer_bp.route('/trend-analytics', methods=['GET'])
@roles_required(ROLE_OBSERVER)
def trend_analytics():
    interval = request.args.get('interval', 'month')
    if interval not in ('day', 'week', 'month', 'year'):
        interval = 'month'

    line_id = request.args.get('line_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    lines = []
    try:
        with get_cursor_context() as cursor:
            current_group_id = session.get('current_group_id')
            if current_group_id:
                cursor.execute("""SELECT l.line_id, l.line_name
                    FROM lines l 
                    WHERE l.status = 'active' AND l.group_id = %s
                    ORDER BY l.line_name ASC""", (current_group_id,))
                lines = cursor.fetchall()
    except Exception as e:
        current_app.logger.exception(f"Error fetching lines: {e}")

    try:
        data = fetch_trend_analytics(session, interval, line_id, start_date, end_date)
        return render_template('dashboards/trend_analytics.html',
                               catches_trend=json.dumps(data['catches_trend']),
                               bait_trend=json.dumps(data['bait_trend']),
                               station_trend=json.dumps(data['station_trend']),
                               seasonal_data=json.dumps(data['seasonal_data']),
                               interval=interval,
                               kpis=data['kpis'],
                               role='observer',
                               lines=lines,
                               selected_line_id=line_id,
                               start_date=start_date,
                               end_date=end_date)
    except Exception as e:
        current_app.logger.exception(f"Error loading trend analytics: {e}")
        flash(f"Could not load trend data: {e}", "danger")
        return render_template('dashboards/trend_analytics.html',
                               catches_trend='[]',
                               bait_trend='[]',
                               station_trend='[]',
                               seasonal_data='[]',
                               interval=interval,
                               kpis={'total_catches': 0, 'total_bait_consumed': 0, 'total_station_checks': 0},
                               role='observer',
                               lines=lines,
                               selected_line_id=line_id,
                               start_date=start_date,
                               end_date=end_date)
