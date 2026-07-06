import json
from flask import render_template, session, redirect, url_for, request, flash, jsonify, current_app
from PF_LU_APP.db import get_cursor_context
from PF_LU_APP.roles.operator import operator_bp
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER
from PF_LU_APP.shared.decorators import roles_required

@operator_bp.route('/equipment-map')
@roles_required(ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER)
def equipment_map():
    group_id = session.get('current_group_id')
    if not group_id:
        flash('Please select a group before accessing the map.', 'info')
        return redirect(url_for('operator.operator_dashboard'))

    line_id = request.args.get('line_id', type=int)  # optional filter

    try:
        with get_cursor_context() as cursor:
            # ---------- Gather traps ----------
            trap_sql = """
                SELECT t.trap_code AS code,
                       tt.trap_type_name AS type,
                       t.latitude,
                       t.longitude,
                       es.equipment_status_name AS status,
                       (SELECT MAX(tc.date) FROM trap_catches tc WHERE tc.trap_code = t.trap_code) AS last_check
                FROM traps t
                JOIN trap_type tt ON t.trap_type_id = tt.trap_type_id
                JOIN lines l ON t.line_id = l.line_id
                LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
                WHERE (t.status = 'active' OR t.status IS NULL)
                  AND l.group_id = %s
            """
            params = [group_id]
            if line_id:
                trap_sql += " AND t.line_id = %s"
                params.append(line_id)
            cursor.execute(trap_sql, tuple(params))
            traps = cursor.fetchall()

            # ---------- Gather bait stations ----------
            bait_sql = """
                SELECT b.bait_station_code AS code,
                       bt.bait_station_type_name AS type,
                       b.latitude,
                       b.longitude,
                       es.equipment_status_name AS status,
                       (SELECT MAX(bsr.date) FROM bait_station_records bsr WHERE bsr.bait_station_code = b.bait_station_code) AS last_check
                FROM bait_stations b
                JOIN bait_station_type bt ON b.bait_station_type_id = bt.bait_station_type_id
                JOIN lines l ON b.line_id = l.line_id
                LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
                WHERE (b.status = 'active' OR b.status IS NULL)
                  AND l.group_id = %s
            """
            params = [group_id]
            if line_id:
                bait_sql += " AND b.line_id = %s"
                params.append(line_id)
            cursor.execute(bait_sql, tuple(params))
            bait_stations = cursor.fetchall()

            # ---------- Build map data ----------
            map_data = []
            for t in traps:
                map_data.append({
                    "code": t["code"],
                    "type": "trap",
                    "equipment_type": t["type"],
                    "lat": t["latitude"],
                    "lng": t["longitude"],
                    "last_check": t["last_check"].strftime('%Y-%m-%d') if t["last_check"] else None,
                    "status": t["status"]
                })
            for b in bait_stations:
                map_data.append({
                    "code": b["code"],
                    "type": "bait_station",
                    "equipment_type": b["type"],
                    "lat": b["latitude"],
                    "lng": b["longitude"],
                    "last_check": b["last_check"].strftime('%Y-%m-%d') if b["last_check"] else None,
                    "status": b["status"]
                })

            # ---------- Compute geographic centroid (fallback center) ----------
            centroid_lat = None
            centroid_lng = None
            if map_data:
                lat_sum = sum(item["lat"] for item in map_data if item["lat"] is not None)
                lng_sum = sum(item["lng"] for item in map_data if item["lng"] is not None)
                count = len([item for item in map_data if item["lat"] is not None and item["lng"] is not None])
                if count:
                    centroid_lat = lat_sum / count
                    centroid_lng = lng_sum / count

            # ---------- Lines for filter dropdown ----------
            cursor.execute(
                """
                SELECT line_id, line_name FROM lines
                WHERE group_id = %s AND status = 'active'
                ORDER BY line_name ASC
                """,
                (group_id,)
            )
            all_lines = cursor.fetchall()

            # ---------- Fetch group boundary (safe) ----------
            boundary_geojson = None
            try:
                cursor.execute("SELECT boundary_geojson FROM groups WHERE group_id = %s", (group_id,))
                g_row = cursor.fetchone()
                boundary_geojson = g_row['boundary_geojson'] if (g_row and g_row.get('boundary_geojson')) else None
            except Exception as e:
                # Older DB may not have the column — continue without boundary
                current_app.logger.warning(f"Warning: could not read group boundary_geojson: {e}")

        return render_template(
            "operator/equipment_map.html",
            map_data=json.dumps(map_data),
            all_lines=all_lines,
            selected_line_id=line_id,
            center_lat=centroid_lat,
            center_lng=centroid_lng,
            current_group_boundary_geojson=boundary_geojson
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.exception(f"Error viewing equipment map: {e}")
        flash(f"An error occurred while loading map: {str(e)}", "danger")
        return redirect(url_for('operator.operator_dashboard'))
