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

@observer_bp.route('/catches', defaults={'line_id': None}, methods=['GET'])
@observer_bp.route('/catches/<int:line_id>', methods=['GET'])
@roles_required(ROLE_OBSERVER)
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
        return redirect(url_for('observer.observer_dashboard'))


