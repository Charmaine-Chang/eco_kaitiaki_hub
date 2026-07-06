from flask import render_template, request, redirect, url_for, flash, current_app
from PF_LU_APP.db import get_db, get_cursor, get_cursor_context
from PF_LU_APP.roles.admin import admin_bp
from PF_LU_APP.shared.decorators import roles_required
from PF_LU_APP.constants import ROLE_SUPER_ADMIN


@admin_bp.route('/global_metadata', methods=['GET', 'POST'])
@roles_required(ROLE_SUPER_ADMIN)
def global_metadata():
    """Unified Global Metadata dashboard: manages Species, Trap Types, and Bait in a single UI."""
    conn = get_db()
    active_tab = request.args.get('tab', 'species')  # species | trap_types | bait | status

    if request.method == 'POST':
        action = request.form.get('action')
        entity = request.form.get('entity')  # species | trap_type | bait | status
        tab_map = {'species': 'species', 'trap_type': 'trap_types', 'bait': 'bait', 'status': 'status'}
        tab_param = tab_map.get(entity, 'species')

        try:
            with get_cursor_context() as cursor:
                if entity == 'species':
                    if action == 'add':
                        name = request.form.get('species_name', '').strip()
                        color = request.form.get('species_color', '').strip()
                        if name:
                            cursor.execute("SELECT species_id FROM species WHERE LOWER(species_name) = LOWER(%s)", (name,))
                            if cursor.fetchone():
                                flash(f"Species '{name}' already exists.", "danger")
                            else:
                                cursor.execute(
                                    "INSERT INTO species (species_name, species_color) VALUES (%s, %s)",
                                    (name, color if color else None),
                                )
                                conn.commit()
                                from PF_LU_APP.species_colors import refresh_cache
                                refresh_cache()
                                flash(f"Species '{name}' added successfully.", "success")
                    elif action == 'edit':
                        sid = request.form.get('record_id')
                        name = request.form.get('species_name', '').strip()
                        color = request.form.get('species_color', '').strip()
                        if sid and name:
                            cursor.execute(
                                "SELECT species_id FROM species WHERE LOWER(species_name) = LOWER(%s) AND species_id != %s",
                                (name, sid),
                            )
                            if cursor.fetchone():
                                flash(f"Species '{name}' already exists.", "danger")
                            else:
                                cursor.execute(
                                    "UPDATE species SET species_name = %s, species_color = %s WHERE species_id = %s",
                                    (name, color if color else None, sid),
                                )
                                conn.commit()
                                from PF_LU_APP.species_colors import refresh_cache
                                refresh_cache()
                                flash(f"Species updated to '{name}'.", "success")
                    elif action == 'delete':
                        sid = request.form.get('record_id')
                        if sid:
                            cursor.execute("SELECT COUNT(*) AS cnt FROM trap_catches WHERE species_id = %s", (sid,))
                            row = cursor.fetchone()
                            if row and row['cnt'] > 0:
                                flash(
                                    f"Cannot delete: this species is linked to {row['cnt']} catch record(s). "
                                    "Remove or reassign those records first.",
                                    "danger",
                                )
                            else:
                                try:
                                    cursor.execute("DELETE FROM species WHERE species_id = %s", (sid,))
                                    conn.commit()
                                    flash("Species deleted successfully.", "success")
                                except Exception as inner_e:
                                    conn.rollback()
                                    current_app.logger.error(f"Error deleting species: {inner_e}")
                                    flash("Cannot delete this species as it is currently in use.", "danger")

                elif entity == 'trap_type':
                    if action == 'add':
                        name = request.form.get('trap_type_name', '').strip()
                        if name:
                            cursor.execute("SELECT trap_type_id FROM trap_type WHERE LOWER(trap_type_name) = LOWER(%s)", (name,))
                            if cursor.fetchone():
                                flash(f"Trap type '{name}' already exists.", "danger")
                            else:
                                cursor.execute("INSERT INTO trap_type (trap_type_name) VALUES (%s)", (name,))
                                conn.commit()
                                flash(f"Trap type '{name}' added successfully.", "success")
                    elif action == 'edit':
                        tid = request.form.get('record_id')
                        name = request.form.get('trap_type_name', '').strip()
                        if tid and name:
                            cursor.execute(
                                "SELECT trap_type_id FROM trap_type WHERE LOWER(trap_type_name) = LOWER(%s) AND trap_type_id != %s",
                                (name, tid),
                            )
                            if cursor.fetchone():
                                flash(f"Trap type '{name}' already exists.", "danger")
                            else:
                                cursor.execute("UPDATE trap_type SET trap_type_name = %s WHERE trap_type_id = %s", (name, tid))
                                conn.commit()
                                flash(f"Trap type updated to '{name}'.", "success")
                    elif action == 'delete':
                        tid = request.form.get('record_id')
                        if tid:
                            cursor.execute("SELECT COUNT(*) AS cnt FROM traps WHERE trap_type_id = %s", (tid,))
                            row = cursor.fetchone()
                            if row and row['cnt'] > 0:
                                flash(
                                    f"Cannot delete: this trap type is assigned to {row['cnt']} trap(s). "
                                    "Reassign or remove those traps first.",
                                    "danger",
                                )
                            else:
                                try:
                                    cursor.execute("DELETE FROM trap_type WHERE trap_type_id = %s", (tid,))
                                    conn.commit()
                                    flash("Trap type deleted successfully.", "success")
                                except Exception as inner_e:
                                    conn.rollback()
                                    current_app.logger.error(f"Error deleting trap_type: {inner_e}")
                                    flash("Cannot delete this trap type as it is currently in use.", "danger")

                elif entity == 'bait':
                    if action == 'add':
                        name = request.form.get('bait_name', '').strip()
                        if name:
                            cursor.execute("SELECT bait_type_id FROM bait_type WHERE LOWER(bait_type_name) = LOWER(%s)", (name,))
                            if cursor.fetchone():
                                flash(f"Bait '{name}' already exists.", "danger")
                            else:
                                cursor.execute("INSERT INTO bait_type (bait_type_name) VALUES (%s)", (name,))
                                conn.commit()
                                flash(f"Bait '{name}' added successfully.", "success")
                    elif action == 'edit':
                        bid = request.form.get('record_id')
                        name = request.form.get('bait_name', '').strip()
                        if bid and name:
                            cursor.execute(
                                "SELECT bait_type_id FROM bait_type WHERE LOWER(bait_type_name) = LOWER(%s) AND bait_type_id != %s",
                                (name, bid),
                            )
                            if cursor.fetchone():
                                flash(f"Bait '{name}' already exists.", "danger")
                            else:
                                cursor.execute("UPDATE bait_type SET bait_type_name = %s WHERE bait_type_id = %s", (name, bid))
                                conn.commit()
                                flash(f"Bait updated to '{name}'.", "success")
                    elif action == 'delete':
                        bid = request.form.get('record_id')
                        if bid:
                            cursor.execute("SELECT COUNT(*) AS cnt FROM trap_catches WHERE bait_type_id = %s", (bid,))
                            row = cursor.fetchone()
                            if row and row['cnt'] > 0:
                                flash(
                                    f"Cannot delete: this bait type is linked to {row['cnt']} catch record(s). "
                                    "Remove or reassign those records first.",
                                    "danger",
                                )
                            else:
                                try:
                                    cursor.execute("DELETE FROM bait_type WHERE bait_type_id = %s", (bid,))
                                    conn.commit()
                                    flash("Bait type deleted successfully.", "success")
                                except Exception as inner_e:
                                    conn.rollback()
                                    current_app.logger.error(f"Error deleting bait: {inner_e}")
                                    flash("Cannot delete this bait type as it is currently in use.", "danger")

                elif entity == 'status':
                    if action == 'add':
                        name = request.form.get('status_name', '').strip()
                        if name:
                            cursor.execute(
                                "SELECT trap_status_id FROM trap_status WHERE LOWER(status_name) = LOWER(%s)",
                                (name,),
                            )
                            if cursor.fetchone():
                                flash(f"Status '{name}' already exists.", "danger")
                            else:
                                cursor.execute("INSERT INTO trap_status (status_name) VALUES (%s)", (name,))
                                conn.commit()
                                flash(f"Status '{name}' added successfully.", "success")
                    elif action == 'edit':
                        sid = request.form.get('record_id')
                        name = request.form.get('status_name', '').strip()
                        if sid and name:
                            cursor.execute(
                                "SELECT trap_status_id FROM trap_status WHERE LOWER(status_name) = LOWER(%s) AND trap_status_id != %s",
                                (name, sid),
                            )
                            if cursor.fetchone():
                                flash(f"Status '{name}' already exists.", "danger")
                            else:
                                cursor.execute(
                                    "UPDATE trap_status SET status_name = %s WHERE trap_status_id = %s",
                                    (name, sid),
                                )
                                conn.commit()
                                flash(f"Status updated to '{name}'.", "success")
                    elif action == 'delete':
                        sid = request.form.get('record_id')
                        if sid:
                            cursor.execute(
                                "SELECT COUNT(*) AS cnt FROM trap_catches WHERE trap_status_id = %s",
                                (sid,),
                            )
                            row = cursor.fetchone()
                            if row and row['cnt'] > 0:
                                flash(
                                    f"Cannot delete: this status is linked to {row['cnt']} catch record(s). "
                                    "Remove or reassign those records first.",
                                    "danger",
                                )
                            else:
                                try:
                                    cursor.execute("DELETE FROM trap_status WHERE trap_status_id = %s", (sid,))
                                    conn.commit()
                                    flash("Status deleted successfully.", "success")
                                except Exception as inner_e:
                                    conn.rollback()
                                    current_app.logger.error(f"Error deleting status: {inner_e}")
                                    flash("Cannot delete this status as it is currently in use.", "danger")
        except Exception as e:
            current_app.logger.exception(f"Database error in metadata POST: {e}")
            flash("An unexpected error occurred.", "danger")

        return redirect(url_for('admin.global_metadata', tab=tab_param))

    try:
        with get_cursor_context() as cursor:
            cursor.execute("SELECT species_id, species_name, species_color FROM species ORDER BY species_name ASC")
            species_list = cursor.fetchall()

            cursor.execute("SELECT trap_type_id, trap_type_name FROM trap_type ORDER BY trap_type_name ASC")
            trap_type_list = cursor.fetchall()

            cursor.execute("SELECT bait_type_id, bait_type_name FROM bait_type ORDER BY bait_type_name ASC")
            bait_list = cursor.fetchall()

            cursor.execute("SELECT species_id, COUNT(*) AS cnt FROM trap_catches GROUP BY species_id")
            species_usage = {r['species_id']: r['cnt'] for r in cursor.fetchall()}

            cursor.execute("SELECT trap_type_id, COUNT(*) AS cnt FROM traps GROUP BY trap_type_id")
            trap_type_usage = {r['trap_type_id']: r['cnt'] for r in cursor.fetchall()}

            cursor.execute(
                "SELECT bait_type_id, COUNT(*) AS cnt FROM trap_catches WHERE bait_type_id IS NOT NULL GROUP BY bait_type_id"
            )
            bait_usage = {r['bait_type_id']: r['cnt'] for r in cursor.fetchall()}

            cursor.execute("SELECT trap_status_id, status_name FROM trap_status ORDER BY status_name ASC")
            status_list = cursor.fetchall()

            cursor.execute("SELECT trap_status_id, COUNT(*) AS cnt FROM trap_catches GROUP BY trap_status_id")
            status_usage = {r['trap_status_id']: r['cnt'] for r in cursor.fetchall()}

        return render_template(
            'admin/metadata.html',
            species_list=species_list,
            trap_type_list=trap_type_list,
            bait_list=bait_list,
            status_list=status_list,
            species_usage=species_usage,
            trap_type_usage=trap_type_usage,
            bait_usage=bait_usage,
            status_usage=status_usage,
            active_tab=active_tab,
        )
    except Exception as e:
        current_app.logger.exception(f"Error fetching metadata: {e}")
        flash("Could not load metadata.", "danger")
        return redirect(url_for('admin.admin_dashboard'))
