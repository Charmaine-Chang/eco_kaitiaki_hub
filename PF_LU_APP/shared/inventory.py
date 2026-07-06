"""Shared inventory helpers used across admin, operator, and other modules."""


def adjust_bait_inventory(cursor, group_id, bait_type_id, delta):
    """Adjust bait inventory quantity for a given bait type and group.

    Args:
        cursor: Database cursor.
        group_id: The group whose inventory to adjust.
        bait_type_id: The bait_type to adjust.
        delta: Positive to add stock, negative to consume stock.

    Returns:
        True on success, False if insufficient stock, None if bait not found.
    """
    if not bait_type_id or not group_id:
        return None

    cursor.execute("SELECT bait_type_name FROM bait_type WHERE bait_type_id = %s", (bait_type_id,))
    bait = cursor.fetchone()
    if not bait:
        return None

    bait_name = bait['bait_type_name']
    cursor.execute(
        """
            SELECT item_id, quantity
            FROM inventory_items
            WHERE group_id = %s
              AND item_category = 'Bait'
              AND LOWER(item_name) = LOWER(%s)
            ORDER BY quantity DESC
        """,
        (group_id, bait_name),
    )
    inventory_rows = cursor.fetchall()
    if not inventory_rows:
        return None

    if delta < 0:
        for item in inventory_rows:
            available = item['quantity'] if item['quantity'] is not None else 0
            if available + delta >= 0:
                cursor.execute(
                    "UPDATE inventory_items SET quantity = %s WHERE item_id = %s",
                    (available + delta, item['item_id']),
                )
                return True
        return False

    first_item = inventory_rows[0]
    current_quantity = first_item['quantity'] if first_item['quantity'] is not None else 0
    cursor.execute(
        "UPDATE inventory_items SET quantity = %s WHERE item_id = %s",
        (current_quantity + delta, first_item['item_id']),
    )
    return True
