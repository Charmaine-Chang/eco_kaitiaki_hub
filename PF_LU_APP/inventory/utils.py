"""Role-based access helpers for consumable stock inventory."""

from flask import session, redirect, url_for, flash
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER


def _role_id():
    rid = session.get('role_id')
    return int(rid) if rid is not None else None


def inventory_denied_redirect():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('auth.login'))
    role_id = _role_id()
    flash('You do not have permission to access stock inventory.', 'danger')
    if role_id == ROLE_OBSERVER:
        return redirect(url_for('observer.observer_dashboard'))
    if role_id == ROLE_OPERATOR:
        return redirect(url_for('operator.operator_dashboard'))
    return redirect(url_for('main.home'))


def can_access_inventory():
    """Observer denied; Operator, Coordinator, Super Admin allowed."""
    if 'user_id' not in session:
        return False
    role_id = _role_id()
    return role_id is not None and role_id in (ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR)


def can_manage_storage():
    """Coordinator and Super Admin only."""
    role_id = _role_id()
    return role_id is not None and role_id <= ROLE_COORDINATOR


def can_create_items():
    return can_manage_storage()


def can_retire_items():
    return can_manage_storage()


def can_view_audit():
    return can_manage_storage()


def group_scope_sql(alias='i'):
    """Return (sql_fragment, params) for group filtering."""
    if session.get('is_super_admin'):
        gid = session.get('current_group_id')
        if gid:
            return f' AND {alias}.group_id = %s', [gid]
        return '', []
    gid = session.get('current_group_id')
    if not gid:
        return ' AND 1=0', []
    return f' AND {alias}.group_id = %s', [gid]


def format_location(storage_name=None, line_name=None):
    if line_name:
        return f'Line: {line_name}'
    if storage_name:
        return f'Storage: {storage_name}'
    return 'Unassigned'


def location_label_from_row(row):
    if row.get('line_name'):
        return format_location(line_name=row['line_name'])
    if row.get('storage_area_name'):
        return format_location(storage_name=row['storage_area_name'])
    return 'Unassigned'


def log_inventory_action(cursor, group_id, user_id, action_type, target_id,
                         target_item_type='item',
                         previous_location=None, new_location=None, details=None):
    cursor.execute("""
        INSERT INTO inventory_log
            (group_id, user_id, action_type, target_item_type, target_item_id,
             previous_location, new_location, details)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (group_id, user_id, action_type, target_item_type, target_id,
          previous_location, new_location, details))


def merge_duplicate_inventory_items(cursor, group_id=None):
    """Consolidate duplicate inventory items with the same item, location, and unit."""
    query = """
        SELECT i.group_id,
               i.item_category,
               i.item_name,
               i.storage_area_id,
               i.line_id,
               i.unit_of_measure,
               GROUP_CONCAT(i.item_id ORDER BY i.item_id) AS item_ids,
               SUM(i.quantity) AS total_quantity,
               MAX(i.threshold) AS merged_threshold
        FROM inventory_items i
        WHERE i.is_retired IS NOT TRUE
    """
    params = []
    if group_id:
        query += ' AND i.group_id = %s'
        params.append(group_id)
    query += """
        GROUP BY i.group_id, i.item_category, i.item_name,
                 i.storage_area_id, i.line_id, i.unit_of_measure
        HAVING COUNT(*) > 1
    """
    cursor.execute(query, tuple(params))
    changed = False
    for dup in cursor.fetchall():
        item_ids_str = dup['item_ids']
        if not item_ids_str:
            continue
        item_ids = [int(x) for x in item_ids_str.split(',')]
        if len(item_ids) < 2:
            continue
        keep_id = item_ids[0]
        remove_ids = item_ids[1:]
        cursor.execute(
            """
            UPDATE inventory_items
            SET quantity = %s, threshold = %s
            WHERE item_id = %s
            """,
            (dup['total_quantity'], dup['merged_threshold'], keep_id),
        )
        placeholders = ', '.join(['%s'] * len(remove_ids))
        cursor.execute(
            f"DELETE FROM inventory_items WHERE item_id IN ({placeholders})",
            tuple(remove_ids),
        )
        changed = True
    if changed and hasattr(cursor, 'connection'):
        try:
            cursor.connection.commit()
        except Exception:
            pass


def fetch_consumable_stock(cursor, group_id=None, all_groups=False):
    """Return consumable bait stock entries for the current group scope."""
    merge_duplicate_inventory_items(cursor, None if all_groups else group_id)
    query = """
        SELECT
            MIN(i.item_id) AS item_id,
            i.item_category,
            i.item_name,
            SUM(i.quantity) AS quantity,
            MAX(i.threshold) AS threshold,
            i.group_id,
            g.group_name,
            sa.storage_area_id,
            sa.storage_area_name,
            l.line_id,
            l.line_name,
            i.unit_of_measure
        FROM inventory_items i
        JOIN `groups` g ON i.group_id = g.group_id
        LEFT JOIN storage_area sa ON i.storage_area_id = sa.storage_area_id
        LEFT JOIN `lines` l ON i.line_id = l.line_id
        WHERE i.is_retired IS NOT TRUE
          AND LOWER(i.item_category) LIKE 'bait%%'
    """
    params = []
    if not all_groups and group_id:
        query += ' AND i.group_id = %s'
        params.append(group_id)
    query += """
        GROUP BY i.item_category, i.item_name, i.group_id, g.group_name,
                 sa.storage_area_id, sa.storage_area_name,
                 l.line_id, l.line_name, i.unit_of_measure
        ORDER BY i.item_name ASC, sa.storage_area_name IS NULL, sa.storage_area_name ASC, l.line_name IS NULL, l.line_name ASC
    """
    cursor.execute(query, tuple(params))
    return cursor.fetchall()


def fetch_low_stock_alerts(cursor, group_id=None, all_groups=False):
    """Bait/toxin/equipment items below re-ordering threshold (not retired), with storage area info."""
    query = """
        SELECT i.item_id, i.item_name, i.item_category, i.quantity, i.threshold, i.group_id,
               i.storage_area_id, g.group_name, sa.storage_area_name
        FROM inventory_items i
        JOIN `groups` g ON i.group_id = g.group_id
        LEFT JOIN storage_area sa ON i.storage_area_id = sa.storage_area_id
        WHERE i.is_retired IS NOT TRUE
          AND (LOWER(i.item_category) LIKE 'bait%%' OR LOWER(i.item_category) LIKE 'toxin%%' OR LOWER(i.item_category) LIKE 'equipment%%')
          AND i.quantity < i.threshold
    """
    params = []
    if not all_groups and group_id:
        query += ' AND i.group_id = %s'
        params.append(group_id)
    query += ' ORDER BY i.item_name ASC'
    cursor.execute(query, tuple(params))
    return cursor.fetchall()
