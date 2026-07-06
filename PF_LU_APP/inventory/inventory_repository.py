"""Repository layer for inventory management queries.

Consolidates SQL from inventory/routes.py, admin/inventory.py, and inventory/utils.py.
"""

from PF_LU_APP.db import get_cursor


# ── Item Queries ──────────────────────────────────────────────────

def fetch_item_by_id(item_id, group_scope=None):
    """Fetch a single inventory item with location joins."""
    cursor = get_cursor()
    scope = ""
    params = [item_id]
    if group_scope:
        scope = " AND i.group_id = %s"
        params.append(group_scope)
    cursor.execute(f"""
        SELECT i.*, sa.storage_area_name, l.line_name, g.group_name
        FROM inventory_items i
        JOIN groups g ON i.group_id = g.group_id
        LEFT JOIN storage_area sa ON i.storage_area_id = sa.storage_area_id
        LEFT JOIN lines l ON i.line_id = l.line_id
        WHERE i.item_id = %s{scope}
    """, tuple(params))
    row = cursor.fetchone()
    cursor.close()
    return row


def fetch_stock_list(group_id=None, show_retired=False):
    """Fetch all inventory items for stock list view."""
    cursor = get_cursor()
    query = """
        SELECT i.*, sa.storage_area_name, l.line_name, g.group_name
        FROM inventory_items i
        JOIN groups g ON i.group_id = g.group_id
        LEFT JOIN storage_area sa ON i.storage_area_id = sa.storage_area_id
        LEFT JOIN lines l ON i.line_id = l.line_id
        WHERE 1=1
    """
    params = []
    if group_id:
        query += " AND i.group_id = %s"
        params.append(group_id)
    if not show_retired:
        query += " AND (i.is_retired IS NOT TRUE)"
    query += " ORDER BY i.is_retired ASC, i.item_category, i.item_name"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_consumable_stock(group_id=None, all_groups=False):
    """Fetch bait/toxin inventory items for dashboard alerts."""
    cursor = get_cursor()
    query = """
        SELECT i.item_id, i.item_category, i.item_name, i.quantity, i.threshold,
               i.group_id, g.group_name, sa.storage_area_name
        FROM inventory_items i
        JOIN groups g ON i.group_id = g.group_id
        LEFT JOIN storage_area sa ON i.storage_area_id = sa.storage_area_id
        WHERE i.is_retired IS NOT TRUE
          AND LOWER(i.item_category) LIKE 'bait%%'
    """
    params = []
    if not all_groups and group_id:
        query += " AND i.group_id = %s"
        params.append(group_id)
    query += " ORDER BY i.item_name ASC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_low_stock_alerts(group_id=None, all_groups=False):
    """Fetch items below their threshold for dashboard alerts."""
    cursor = get_cursor()
    query = """
        SELECT i.item_id, i.item_name, i.quantity, i.threshold, i.group_id, g.group_name
        FROM inventory_items i
        JOIN groups g ON i.group_id = g.group_id
        WHERE i.is_retired IS NOT TRUE
          AND (LOWER(i.item_category) LIKE 'bait%%' OR LOWER(i.item_category) LIKE 'toxin%%')
          AND i.quantity < i.threshold
    """
    params = []
    if not all_groups and group_id:
        query += " AND i.group_id = %s"
        params.append(group_id)
    query += " ORDER BY i.item_name ASC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    return rows


# ── Item Mutations ───────────────────────────────────────────────

def create_item(group_id, category, name, quantity, unit_of_measure=None,
                threshold=None, storage_area_id=None, line_id=None):
    """Create a new inventory item."""
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO inventory_items
            (group_id, item_category, item_name, quantity, unit_of_measure,
             threshold, storage_area_id, line_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING item_id
    """, (group_id, category, name, quantity, unit_of_measure,
          threshold, storage_area_id, line_id))
    result = cursor.fetchone()
    cursor.close()
    return result['item_id'] if result else None


def find_existing_item(group_id, category, name, storage_area_id=None):
    """Find an existing active item matching name, category, and storage area (case-insensitive)."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT item_id, quantity FROM inventory_items
        WHERE group_id = %s
          AND LOWER(item_category) = LOWER(%s)
          AND LOWER(item_name) = LOWER(%s)
          AND ((storage_area_id IS NULL AND %s IS NULL) OR storage_area_id = %s)
          AND (is_retired IS NOT TRUE)
        LIMIT 1
    """, (group_id, category, name, storage_area_id, storage_area_id))
    row = cursor.fetchone()
    cursor.close()
    return row


def merge_or_create_item(group_id, category, name, quantity, unit_of_measure=None,
                         threshold=None, storage_area_id=None, line_id=None):
    """If a matching item exists, add quantity to it. Otherwise create a new item.

    Returns:
        (item_id, merged: bool) — merged is True if quantity was added to existing item.
    """
    existing = find_existing_item(group_id, category, name, storage_area_id)
    if existing:
        new_qty = (existing['quantity'] or 0) + (quantity or 0)
        adjust_item_quantity(existing['item_id'], new_qty)
        return existing['item_id'], True
    else:
        new_id = create_item(group_id, category, name, quantity, unit_of_measure,
                             threshold, storage_area_id, line_id)
        return new_id, False


def update_item(item_id, quantity, unit_of_measure=None, threshold=None):
    """Update an inventory item's quantity, unit, and threshold."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE inventory_items SET quantity = %s, unit_of_measure = %s, threshold = %s WHERE item_id = %s",
        (quantity, unit_of_measure, threshold, item_id),
    )
    cursor.close()


def update_item_location(item_id, storage_area_id, line_id):
    """Move an item to a new storage area or line."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE inventory_items SET storage_area_id = %s, line_id = %s WHERE item_id = %s",
        (storage_area_id, line_id, item_id),
    )
    cursor.close()


def retire_item(item_id):
    """Mark an inventory item as retired."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE inventory_items SET is_retired = TRUE, retired_at = CURRENT_TIMESTAMP WHERE item_id = %s",
        (item_id,),
    )
    cursor.close()


def adjust_item_quantity(item_id, new_quantity):
    """Set an inventory item's quantity to a specific value."""
    cursor = get_cursor()
    cursor.execute(
        "UPDATE inventory_items SET quantity = %s WHERE item_id = %s",
        (new_quantity, item_id),
    )
    cursor.close()


def create_split_item(group_id, category, name, quantity, unit_of_measure,
                      threshold, storage_area_id, line_id):
    """Create a new item during a partial move (split)."""
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO inventory_items
            (group_id, item_category, item_name, quantity, unit_of_measure,
             threshold, storage_area_id, line_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING item_id
    """, (group_id, category, name, quantity, unit_of_measure,
          threshold, storage_area_id, line_id))
    result = cursor.fetchone()
    cursor.close()
    return result['item_id'] if result else None


# ── Audit Log ─────────────────────────────────────────────────────

def fetch_item_audit_log(item_id):
    """Fetch audit log for a specific inventory item."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT il.*, u.username, u.first_name, u.last_name
        FROM inventory_log il
        LEFT JOIN users u ON il.user_id = u.user_id
        WHERE il.target_item_type = 'item' AND il.target_item_id = %s
        ORDER BY il.created_at DESC
    """, (item_id,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_audit_log(group_id=None):
    """Fetch the full audit log (admin view)."""
    cursor = get_cursor()
    query = """
        SELECT il.*, u.username, u.first_name, u.last_name,
               ii.item_name, ii.item_category, g.group_name
        FROM inventory_log il
        LEFT JOIN users u ON il.user_id = u.user_id
        LEFT JOIN inventory_items ii ON il.target_item_type = 'item' AND il.target_item_id = ii.item_id
        LEFT JOIN groups g ON il.group_id = g.group_id
        WHERE 1=1
    """
    params = []
    if group_id:
        query += " AND il.group_id = %s"
        params.append(group_id)
    query += " ORDER BY il.created_at DESC LIMIT 200"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def log_inventory_action(group_id, user_id, action_type, target_item_id,
                         previous_location=None, new_location=None, details=None):
    """Insert an inventory audit log entry."""
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO inventory_log
            (group_id, user_id, action_type, target_item_type, target_item_id,
             previous_location, new_location, details)
        VALUES (%s, %s, %s, 'item', %s, %s, %s, %s)
    """, (group_id, user_id, action_type, target_item_id,
          previous_location, new_location, details))
    cursor.close()


# ── Storage Areas ─────────────────────────────────────────────────

def fetch_storage_areas(group_id):
    """Fetch storage areas for a group."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT storage_area_id, storage_area_name FROM storage_area WHERE group_id = %s ORDER BY storage_area_name",
        (group_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


def create_storage_area(group_id, name):
    """Create a new storage area."""
    cursor = get_cursor()
    cursor.execute(
        "INSERT INTO storage_area (group_id, storage_area_name) VALUES (%s, %s) RETURNING storage_area_id",
        (group_id, name),
    )
    result = cursor.fetchone()
    cursor.close()
    return result['storage_area_id'] if result else None


def validate_storage_area(storage_area_id, group_id):
    """Check that a storage area belongs to the group."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT storage_area_id FROM storage_area WHERE storage_area_id = %s AND group_id = %s",
        (storage_area_id, group_id),
    )
    row = cursor.fetchone()
    cursor.close()
    return row is not None


def fetch_stored_equipment(group_id):
    """Fetch traps and bait stations that are 'In Storage'."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT NULL::integer AS item_id, 'Trap' AS item_category,
               CONCAT('Trap #', t.trap_code) AS item_name,
               NULL::numeric AS quantity, NULL::numeric AS threshold,
               sa.storage_area_id, sa.storage_area_name
        FROM traps t
        LEFT JOIN lines l ON t.line_id = l.line_id
        LEFT JOIN storage_area sa ON t.storage_area_id = sa.storage_area_id
        LEFT JOIN equipment_status es ON t.equipment_status_id = es.equipment_status_id
        WHERE es.equipment_status_name = 'In Storage'
          AND (sa.group_id = %s OR l.group_id = %s)
        UNION ALL
        SELECT NULL::integer AS item_id, 'Bait Station' AS item_category,
               CONCAT('Station #', b.bait_station_code) AS item_name,
               NULL::numeric AS quantity, NULL::numeric AS threshold,
               sa.storage_area_id, sa.storage_area_name
        FROM bait_stations b
        LEFT JOIN lines l ON b.line_id = l.line_id
        LEFT JOIN storage_area sa ON b.storage_area_id = sa.storage_area_id
        LEFT JOIN equipment_status es ON b.equipment_status_id = es.equipment_status_id
        WHERE es.equipment_status_name = 'In Storage'
          AND (sa.group_id = %s OR l.group_id = %s)
        ORDER BY item_category ASC, item_name ASC
    """, (group_id, group_id, group_id, group_id))
    rows = cursor.fetchall()
    cursor.close()
    return rows


# ── Destinations (for move form) ─────────────────────────────────

def fetch_destinations(group_id):
    """Fetch storage areas and active lines for a group (move form dropdowns)."""
    cursor = get_cursor()
    cursor.execute(
        "SELECT storage_area_id, storage_area_name FROM storage_area WHERE group_id = %s ORDER BY storage_area_name",
        (group_id,),
    )
    storage_areas = cursor.fetchall()
    cursor.execute(
        "SELECT line_id, line_name FROM lines WHERE group_id = %s AND status = 'active' ORDER BY line_name",
        (group_id,),
    )
    lines = cursor.fetchall()
    cursor.close()
    return storage_areas, lines


# ── Cross-Storage Alerts ─────────────────────────────────────────

def find_alternative_stock(group_id, item_name, item_category, exclude_item_id,
                           exclude_storage_area_id=None):
    """Find the same item in other storage areas with stock available.

    Returns:
        list of dicts with item_id, quantity, storage_area_name.
    """
    cursor = get_cursor()
    cursor.execute("""
        SELECT i.item_id, i.quantity, i.storage_area_id,
               sa.storage_area_name
        FROM inventory_items i
        LEFT JOIN storage_area sa ON i.storage_area_id = sa.storage_area_id
        WHERE i.group_id = %s
          AND LOWER(i.item_name) = LOWER(%s)
          AND LOWER(i.item_category) = LOWER(%s)
          AND i.item_id != %s
          AND (i.is_retired IS NOT TRUE)
          AND i.quantity > 0
    """, (group_id, item_name, item_category, exclude_item_id))
    rows = cursor.fetchall()
    cursor.close()
    # Filter out same storage area in Python (NULL handling)
    result = []
    for r in rows:
        r_storage = r.get('storage_area_id')
        if r_storage != exclude_storage_area_id:
            result.append(r)
    return result


