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

@observer_bp.route('/')
@roles_required(ROLE_OBSERVER)
def observer_dashboard():
    try:
        with get_cursor_context() as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
            user = cursor.fetchone()

            # Fetch stats for the current group (or global if none selected)
            group_id = session.get('current_group_id')
            stats = {'total_lines': 0, 'total_traps': 0, 'total_members': 0}
            
            if group_id:
                # Scoped to group
                cursor.execute("SELECT COUNT(*) as count FROM `lines` WHERE group_id = %s AND status = 'active'", (group_id,))
                stats['total_lines'] = cursor.fetchone()['count']
                
                cursor.execute("""
                    SELECT (
                        (SELECT COUNT(*) FROM traps t JOIN `lines` l ON t.line_id = l.line_id WHERE l.group_id = %s AND (t.status = 'active' OR t.status IS NULL)) +
                        (SELECT COUNT(*) FROM bait_stations b JOIN `lines` l ON b.line_id = l.line_id WHERE l.group_id = %s AND (b.status = 'active' OR b.status IS NULL))
                    ) as count
                """, (group_id, group_id))
                stats['total_traps'] = cursor.fetchone()['count']
                
                cursor.execute("SELECT COUNT(*) as count FROM group_membership WHERE group_id = %s AND membership_status = 'active'", (group_id,))
                stats['total_members'] = cursor.fetchone()['count']
            else:
                # Global stats (Role 4 is System Observer)
                cursor.execute("SELECT COUNT(*) as count FROM `lines` WHERE status = 'active'")
                stats['total_lines'] = cursor.fetchone()['count']
                
                cursor.execute("""
                    SELECT (
                        (SELECT COUNT(*) FROM traps WHERE (status = 'active' OR status IS NULL)) +
                        (SELECT COUNT(*) FROM bait_stations WHERE (status = 'active' OR status IS NULL))
                    ) as count
                """)
                stats['total_traps'] = cursor.fetchone()['count']
                
                cursor.execute("SELECT COUNT(*) as count FROM users") # Global member count
                stats['total_members'] = cursor.fetchone()['count']
                
            # Fetch group boundary for the map
            boundary_geojson = None
            group_latitude = None
            group_longitude = None
            if group_id:
                cursor.execute("SELECT boundary_geojson, latitude, longitude FROM `groups` WHERE group_id = %s", (group_id,))
                grp = cursor.fetchone()
                if grp:
                    boundary_geojson = grp.get('boundary_geojson')
                    group_latitude = grp.get('latitude')
                    group_longitude = grp.get('longitude')
    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.exception(f"Error fetching dashboard data: {e}")
        user = {}
        stats = {'total_lines': 0, 'total_traps': 0, 'total_members': 0}
        boundary_geojson = None
        group_latitude = None
        group_longitude = None

    return render_template('dashboards/observer_dashboard.html', user=user, stats=stats,
                           boundary_geojson=boundary_geojson,
                           group_latitude=group_latitude,
                           group_longitude=group_longitude)

