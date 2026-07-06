import logging
from flask import render_template, request, redirect, url_for, flash, session
from PF_LU_APP.db import get_db, get_cursor
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER
from . import inventory_bp
from .utils import (
    can_access_inventory,
    can_manage_storage,
    can_create_items,
    can_retire_items,
    can_view_audit,
    inventory_denied_redirect,
    group_scope_sql,
    location_label_from_row,
    format_location,
)
from .inventory_repository import (
    fetch_item_by_id, fetch_stock_list, fetch_consumable_stock,
    fetch_low_stock_alerts, create_item as repo_create_item, update_item,
    update_item_location, retire_item as repo_retire_item, adjust_item_quantity,
    create_split_item, fetch_item_audit_log, fetch_audit_log,
    fetch_storage_areas, create_storage_area, validate_storage_area,
    fetch_stored_equipment, fetch_destinations,
    merge_or_create_item, find_alternative_stock, find_existing_item,
)
from .utils import log_inventory_action


def _fetch_item(cursor, item_id):
    """Fetch item with group scope (uses group_scope_sql for permission filtering)."""
    scope, params = group_scope_sql('i')
    cursor.execute(f"""
        SELECT i.*, sa.storage_area_name, l.line_name, g.group_name
        FROM inventory_items i
        JOIN groups g ON i.group_id = g.group_id
        LEFT JOIN storage_area sa ON i.storage_area_id = sa.storage_area_id
        LEFT JOIN lines l ON i.line_id = l.line_id
        WHERE i.item_id = %s {scope}
    """, [item_id] + params)
    return cursor.fetchone()


@inventory_bp.route('/')
def stock_list():
    if not can_access_inventory():
        return inventory_denied_redirect()

    group_id = session.get('current_group_id')
    if not group_id and not session.get('is_super_admin'):
        flash('Please select a group context first.', 'info')
        return redirect(url_for('auth.select_group'))

    items = []
    storage_areas = []
    show_retired = False
    try:
        show_retired = request.args.get('show_retired') == '1' and can_manage_storage()
        items = fetch_stock_list(group_id, show_retired=show_retired)

        if group_id:
            storage_areas, _ = fetch_destinations(group_id)
    except Exception as e:
        logging.exception(f'Error loading stock inventory: {e}')
        flash('Error loading stock inventory.', 'danger')

    return render_template(
        'inventory/stock_list.html',
        items=items,
        storage_areas=storage_areas,
        show_retired=show_retired if can_manage_storage() else False,
    )


@inventory_bp.route('/item/<int:item_id>')
def item_detail(item_id):
    if not can_access_inventory():
        return inventory_denied_redirect()

    item = None
    history = []
    try:
        item = _fetch_item(get_cursor(), item_id)
        if not item:
            flash('Item not found.', 'warning')
            return redirect(url_for('inventory.stock_list'))
        history = fetch_item_audit_log(item_id)
    except Exception as e:
        logging.exception(f'Error loading item detail: {e}')
        flash('Error loading item.', 'danger')
        return redirect(url_for('inventory.stock_list'))

    return render_template('inventory/item_detail.html', item=item, history=history)


@inventory_bp.route('/item/<int:item_id>/move', methods=['GET', 'POST'])
def move_item(item_id):
    if not can_access_inventory():
        return inventory_denied_redirect()

    if session.get('role_id') not in (ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR):
        flash('You do not have permission to move items.', 'danger')
        return redirect(url_for('inventory.stock_list'))

    try:
        cursor = get_cursor()
        item = _fetch_item(cursor, item_id)
        if not item:
            flash('Item not found.', 'warning')
            return redirect(url_for('inventory.stock_list'))
        if item.get('is_retired'):
            flash('Cannot move a retired item.', 'warning')
            return redirect(url_for('inventory.item_detail', item_id=item_id))

        storage_areas, lines = fetch_destinations(item['group_id'])
        current_loc = location_label_from_row(item)

        if request.method == 'POST':
            action = request.form.get('action') or 'move'
            confirmed = request.form.get('confirmed') == '1'

            if action == 'move':
                # support multiple destinations with quantities: dest_type[], dest_id[], move_qty[]
                raw_types = request.form.getlist('dest_type') or []
                raw_ids = request.form.getlist('dest_id') or []
                raw_qtys = request.form.getlist('move_qty') or []
                # backward-compat: single-field names
                if not raw_types and request.form.get('dest_type'):
                    raw_types = [request.form.get('dest_type')]
                if not raw_ids and request.form.get('dest_id'):
                    raw_ids = [request.form.get('dest_id')]
                if not raw_qtys and request.form.get('move_qty'):
                    raw_qtys = [request.form.get('move_qty')]

                comment = (request.form.get('comment') or '').strip() or None

                destinations = []
                for i, t in enumerate(raw_types):
                    try:
                        dest_id = raw_ids[i]
                    except IndexError:
                        dest_id = None
                    try:
                        qty_raw = raw_qtys[i]
                    except IndexError:
                        qty_raw = ''
                    try:
                        qty = float(qty_raw) if qty_raw not in (None, '', 'None') else None
                    except ValueError:
                        qty = None
                    if not t or not dest_id:
                        continue
                    destinations.append({'type': t, 'id': dest_id, 'qty': qty})

                # if no explicit destinations parsed, attempt to use single select fields
                if not destinations:
                    flash('Please select at least one destination.', 'danger')
                else:
                    # build labels and validate
                    validated = []
                    total_move = 0.0
                    for d in destinations:
                        dtype = d['type']
                        did = d['id']
                        q = d['qty']
                        if q is None:
                            # treat as full-move flag for single destination
                            q = None
                        label = None
                        if dtype == 'storage':
                            sa = next((s for s in storage_areas if str(s['storage_area_id']) == str(did)), None)
                            if not sa:
                                flash('Invalid storage area.', 'danger')
                                validated = None
                                break
                            label = format_location(storage_name=sa['storage_area_name'])
                        elif dtype == 'line':
                            ln = next((l for l in lines if str(l['line_id']) == str(did)), None)
                            if not ln:
                                flash('Invalid line.', 'danger')
                                validated = None
                                break
                            label = format_location(line_name=ln['line_name'])
                        else:
                            flash('Invalid destination type.', 'danger')
                            validated = None
                            break
                        validated.append({'type': dtype, 'id': did, 'label': label, 'qty': q})

                    if validated is None:
                        pass
                    else:
                        old_qty = float(item['quantity'] or 0)
                        # compute total of explicit qtys (ignore None entries)
                        explicit_total = sum(d['qty'] for d in validated if d['qty'] is not None)
                        # if any destination has qty None and there is exactly one destination, treat as full move
                        has_none = any(d['qty'] is None for d in validated)

                        if has_none and len(validated) == 1:
                            # single full move
                            d = validated[0]
                            if not confirmed:
                                return render_template(
                                    'inventory/move_confirm.html',
                                    item=item,
                                    current_loc=current_loc,
                                    destinations=[{'type': d['type'], 'id': d['id'], 'label': d['label'], 'qty': old_qty}],
                                    comment=comment,
                                )
                            # perform full move — check for merge at destination
                            new_storage_id = d['type'] == 'storage' and d['id'] or None
                            new_line_id = d['type'] == 'line' and d['id'] or None
                            conn = get_db()
                            cur = get_cursor()
                            # Check if same item already exists at destination
                            dest_item = find_existing_item(
                                item['group_id'], item['item_category'], item['item_name'],
                                new_storage_id,
                            )
                            if dest_item and dest_item['item_id'] != item_id:
                                # Merge: add qty to existing item, delete original
                                new_qty = (dest_item['quantity'] or 0) + old_qty
                                adjust_item_quantity(dest_item['item_id'], new_qty)
                                cur.execute("DELETE FROM inventory_items WHERE item_id = %s", (item_id,))
                                details = f'Merged {old_qty} into existing item at {d["label"]}'
                                if comment:
                                    details += f'; comment: {comment}'
                                log_inventory_action(
                                    cur, item['group_id'], session['user_id'], 'merge', dest_item['item_id'],
                                    previous_location=current_loc, new_location=d['label'], details=details,
                                )
                                conn.commit()
                                cur.close()
                                flash(f'Item merged with existing stock at {d["label"]}.', 'success')
                                return redirect(url_for('inventory.stock_list'))
                            else:
                                # No merge — just update location
                                cur.execute("""
                                    UPDATE inventory_items
                                    SET storage_area_id = %s, line_id = %s
                                    WHERE item_id = %s
                                """, (new_storage_id, new_line_id, item_id))
                                details = None
                                if comment:
                                    details = f'comment: {comment}'
                                log_inventory_action(
                                    cur, item['group_id'], session['user_id'], 'move', item_id,
                                    previous_location=current_loc, new_location=d['label'], details=details,
                                )
                                conn.commit()
                                cur.close()
                                flash(f'Item moved to {d["label"]}.', 'success')
                                return redirect(url_for('inventory.item_detail', item_id=item_id))

                        # partially-specified moves: require explicit qtys for each destination
                        if any(d['qty'] is None for d in validated):
                            flash('When moving to multiple destinations, specify a quantity for each destination.', 'danger')
                        else:
                            total_move = explicit_total
                            if total_move <= 0:
                                flash('Please enter positive quantities to move.', 'danger')
                            elif total_move > old_qty + 1e-9:
                                flash('Total moved quantity cannot exceed current quantity.', 'danger')
                            else:
                                if not confirmed:
                                    # show confirm page with destinations and qtys
                                    return render_template(
                                        'inventory/move_confirm.html',
                                        item=item,
                                        current_loc=current_loc,
                                        destinations=[{'type': d['type'], 'id': d['id'], 'label': d['label'], 'qty': d['qty']} for d in validated],
                                        comment=comment,
                                    )

                                # perform partial moves — check for merge at each destination
                                conn = get_db()
                                cur = get_cursor()
                                for d in validated:
                                    new_storage_id = d['type'] == 'storage' and d['id'] or None
                                    new_line_id = d['type'] == 'line' and d['id'] or None
                                    # Check if same item already exists at destination
                                    dest_item = find_existing_item(
                                        item['group_id'], item['item_category'], item['item_name'],
                                        new_storage_id,
                                    )
                                    if dest_item and dest_item['item_id'] != item_id:
                                        # Merge: add qty to existing item
                                        new_qty = (dest_item['quantity'] or 0) + d['qty']
                                        adjust_item_quantity(dest_item['item_id'], new_qty)
                                        details = f'Merged {d["qty"]} into existing item at {d["label"]}'
                                        if comment:
                                            details += f'; comment: {comment}'
                                        log_inventory_action(
                                            cur, item['group_id'], session['user_id'], 'merge', dest_item['item_id'],
                                            previous_location=current_loc, new_location=d['label'], details=details,
                                        )
                                    else:
                                        # No merge — create new row
                                        cur.execute(
                                            """
                                            INSERT INTO inventory_items (group_id, item_category, item_name, quantity, unit_of_measure, threshold, storage_area_id, line_id)
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                            RETURNING item_id
                                            """,
                                            (item['group_id'], item['item_category'], item['item_name'], d['qty'], item.get('unit_of_measure'), item.get('threshold') or 0, new_storage_id, new_line_id),
                                        )
                                        new_id = cur.fetchone()['item_id']
                                        details = f'moved: {d["qty"]}'
                                        if comment:
                                            details += f'; comment: {comment}'
                                        log_inventory_action(
                                            cur, item['group_id'], session['user_id'], 'move', new_id,
                                            previous_location=current_loc, new_location=d['label'], details=details,
                                        )

                                # subtract from original and delete if zero
                                remaining = max(0.0, old_qty - total_move)
                                if remaining <= 0:
                                    cur.execute("DELETE FROM inventory_items WHERE item_id = %s", (item_id,))
                                    details = f'Item fully moved ({total_move})'
                                else:
                                    cur.execute("UPDATE inventory_items SET quantity = %s WHERE item_id = %s", (remaining, item_id))
                                    details = f'quantity reduced by {total_move} -> qty: {old_qty} → {remaining}'
                                if comment:
                                    details += f'; comment: {comment}'
                                log_inventory_action(
                                    cur, item['group_id'], session['user_id'], 'update', item_id,
                                    previous_location=current_loc, new_location=current_loc, details=details,
                                )
                                conn.commit()
                                cur.close()
                                flash('Item quantities updated and moved.', 'success')
                                return redirect(url_for('inventory.item_detail', item_id=item_id))

            elif action in ('consume', 'receive'):
                # Adjust quantity
                adj = request.form.get('adjust_qty')
                try:
                    adj_val = float(adj) if adj is not None and adj != '' else None
                except ValueError:
                    adj_val = None

                if adj_val is None or adj_val <= 0:
                    flash('Please enter a valid positive quantity to adjust.', 'danger')
                else:
                    old_qty = float(item['quantity'] or 0)
                    if action == 'consume':
                        new_qty = max(0.0, old_qty - adj_val)
                    else:
                        new_qty = old_qty + adj_val

                    comment = (request.form.get('comment') or '').strip() or None
                    if not confirmed:
                        return render_template(
                            'inventory/adjust_confirm.html',
                            item=item,
                            action=action,
                            adjust_qty=adj_val,
                            new_qty=new_qty,
                            comment=comment,
                        )

                    # perform update
                    conn = get_db()
                    cur = get_cursor()
                    cur.execute(
                        """
                        UPDATE inventory_items SET quantity = %s WHERE item_id = %s
                        """,
                        (new_qty, item_id),
                    )
                    action_type = 'consumption' if action == 'consume' else 'receipt'
                    details = f'{action_type}: {adj_val} -> qty: {old_qty} → {new_qty}'
                    if comment:
                        details += f'; comment: {comment}'
                    log_inventory_action(
                        cur, item['group_id'], session['user_id'], action_type, item_id,
                        previous_location=current_loc, new_location=current_loc, details=details,
                    )
                    conn.commit()
                    cur.close()
                    flash('Inventory updated.', 'success')
                    # Low stock warning with cross-storage alternatives
                    threshold = item.get('threshold') or 0
                    if new_qty < threshold:
                        alternatives = find_alternative_stock(
                            item['group_id'], item['item_name'], item['item_category'],
                            item_id, item.get('storage_area_id'),
                        )
                        if alternatives:
                            alt_list = ', '.join(
                                f"{a['storage_area_name'] or 'Unassigned'} ({a['quantity']})"
                                for a in alternatives
                            )
                            flash(f'Warning: {item["item_name"]} is now low stock. Also available in: {alt_list}', 'warning')
                        else:
                            flash(f'Warning: {item["item_name"]} is now low stock and not available in other locations.', 'warning')
                    return redirect(url_for('inventory.item_detail', item_id=item_id))

        cursor.close()
    except Exception as e:
        logging.exception(f'Error moving item: {e}')
        flash('Error processing move.', 'danger')
        return redirect(url_for('inventory.stock_list'))

    return render_template(
        'inventory/move_item.html',
        item=item,
        current_loc=current_loc,
        storage_areas=storage_areas,
        lines=lines,
    )


@inventory_bp.route('/item/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_item(item_id):
    if not can_access_inventory():
        return inventory_denied_redirect()

    try:
        cursor = get_cursor()
        item = _fetch_item(cursor, item_id)
        if not item:
            flash('Item not found.', 'warning')
            return redirect(url_for('inventory.stock_list'))

        if request.method == 'POST':
            quantity = request.form.get('quantity')
            unit_of_measure = (request.form.get('unit_of_measure') or '').strip() or None
            threshold = request.form.get('threshold')
            if quantity is None or threshold is None:
                flash('Quantity and threshold are required.', 'danger')
            else:
                try:
                    qty = float(quantity)
                    thr = float(threshold)
                    if qty < 0 or thr < 0:
                        raise ValueError('negative')
                except ValueError:
                    flash('Quantity and threshold must be non-negative numbers.', 'danger')
                else:
                    old_qty = item['quantity']
                    old_thr = item['threshold']
                    old_uom = item.get('unit_of_measure')
                    can_edit_threshold = can_manage_storage()
                    new_thr = thr if can_edit_threshold else old_thr

                    conn = get_db()
                    cur = get_cursor()
                    cur.execute("""
                        UPDATE inventory_items SET quantity = %s, unit_of_measure = %s, threshold = %s WHERE item_id = %s
                    """, (qty, unit_of_measure, new_thr, item_id))
                    details = f'quantity: {old_qty} → {qty}'
                    if unit_of_measure != old_uom:
                        details += f'; unit: {old_uom or "—"} → {unit_of_measure or "—"}'
                    if can_edit_threshold and old_thr != new_thr:
                        details += f'; threshold: {old_thr} → {new_thr}'
                    log_inventory_action(
                        cur, item['group_id'], session['user_id'], 'update', item_id,
                        details=details,
                    )
                    conn.commit()
                    cur.close()
                    flash('Item updated.', 'success')
                    return redirect(url_for('inventory.item_detail', item_id=item_id))

        cursor.close()
    except Exception as e:
        logging.exception(f'Error editing item: {e}')
        flash('Error updating item.', 'danger')
        return redirect(url_for('inventory.stock_list'))

    return render_template('inventory/edit_item.html', item=item)


@inventory_bp.route('/item/new', methods=['GET', 'POST'])
def create_item():
    if not can_create_items():
        flash('You do not have permission to create inventory items.', 'danger')
        return inventory_denied_redirect() if 'user_id' not in session else redirect(url_for('inventory.stock_list'))

    group_id = session.get('current_group_id')
    if not group_id:
        flash('Please select a group context first.', 'info')
        return redirect(url_for('auth.select_group'))

    storage_areas = []
    if request.method == 'POST':
        name = (request.form.get('item_name') or '').strip()
        category = (request.form.get('item_category') or '').strip()
        quantity = request.form.get('quantity') or '0'
        unit_of_measure = (request.form.get('unit_of_measure') or '').strip() or None
        threshold = request.form.get('threshold') or '0'
        storage_id = request.form.get('storage_area_id') or None

        if not storage_id:
            storage_areas, _ = fetch_destinations(group_id)
            if storage_areas:
                storage_id = str(storage_areas[0]['storage_area_id'])

        if not name or not category:
            flash('Name and category are required.', 'danger')
        else:
            try:
                qty = float(quantity)
                thr = float(threshold)
                new_id, merged = merge_or_create_item(group_id, category, name, qty, unit_of_measure, thr, storage_id)
                loc = 'Unassigned'
                if storage_id:
                    areas = fetch_storage_areas(group_id)
                    sa = next((a for a in areas if str(a['storage_area_id']) == str(storage_id)), None)
                    if sa:
                        loc = format_location(storage_name=sa['storage_area_name'])
                cur = get_cursor()
                if merged:
                    log_inventory_action(
                        cur, group_id, session['user_id'], 'merge', new_id,
                        new_location=loc, details=f'Merged {qty} into existing: {category}: {name}',
                    )
                    flash('Item merged with existing stock.', 'success')
                else:
                    log_inventory_action(
                        cur, group_id, session['user_id'], 'create', new_id,
                        new_location=loc, details=f'{category}: {name}, qty={qty}',
                    )
                    flash('Item created.', 'success')
                get_db().commit()
                cur.close()
                return redirect(url_for('inventory.item_detail', item_id=new_id))
            except Exception as e:
                logging.exception(f'Error creating item: {e}')
                flash('Error creating item.', 'danger')

    try:
        storage_areas, _ = fetch_destinations(group_id)
    except Exception as e:
        logging.exception(f'Error loading form: {e}')

    return render_template('inventory/create_item.html', storage_areas=storage_areas)


@inventory_bp.route('/item/<int:item_id>/retire', methods=['POST'])
def retire_item(item_id):
    if not can_retire_items():
        flash('You do not have permission to retire items.', 'danger')
        return redirect(url_for('inventory.stock_list'))

    try:
        conn = get_db()
        cursor = get_cursor()
        item = _fetch_item(cursor, item_id)
        if not item:
            flash('Item not found.', 'warning')
        elif item.get('is_retired'):
            flash('Item is already retired.', 'info')
        else:
            repo_retire_item(item_id)
            log_inventory_action(
                cursor, item['group_id'], session['user_id'], 'retire', item_id,
                details=f"Retired: {item['item_name']}",
            )
            conn.commit()
            flash('Item retired.', 'success')
        cursor.close()
    except Exception as e:
        logging.exception(f'Error retiring item: {e}')
        flash('Error retiring item.', 'danger')

    return redirect(url_for('inventory.stock_list'))


@inventory_bp.route('/storage', methods=['GET', 'POST'])
def manage_storage():
    if not can_manage_storage():
        flash('You do not have permission to manage storage areas.', 'danger')
        return inventory_denied_redirect() if not can_access_inventory() else redirect(url_for('inventory.stock_list'))

    group_id = session.get('current_group_id')
    if not group_id:
        flash('Please select a group context first.', 'info')
        return redirect(url_for('auth.select_group'))

    if request.method == 'POST':
        name = (request.form.get('storage_area_name') or '').strip()
        if not name:
            flash('Storage area name is required.', 'danger')
        else:
            try:
                sa_id = create_storage_area(group_id, name)
                conn = get_db()
                cur = get_cursor()
                log_inventory_action(
                    cur, group_id, session['user_id'], 'create', sa_id,
                    target_item_type='storage_area',
                    details=f'Storage area: {name}',
                )
                conn.commit()
                cur.close()
                flash('Storage area created.', 'success')
            except Exception as e:
                logging.exception(f'Error creating storage area: {e}')
                flash('Error creating storage area.', 'danger')

    areas = []
    try:
        areas = fetch_storage_areas(group_id)
    except Exception as e:
        logging.exception(f'Error loading storage areas: {e}')
        flash('Error loading storage areas.', 'danger')

    return render_template('inventory/storage_areas.html', storage_areas=areas)


@inventory_bp.route('/audit')
def audit_log():
    if not can_view_audit():
        flash('You do not have permission to view audit logs.', 'danger')
        if session.get('role_id') == ROLE_OPERATOR:
            return redirect(url_for('operator.operator_dashboard'))
        if session.get('role_id') == ROLE_OBSERVER:
            return redirect(url_for('observer.observer_dashboard'))
        return redirect(url_for('main.home'))

    action_filter = request.args.get('action_type', '').strip()
    logs = []
    try:
        cursor = get_cursor()
        scope, params = group_scope_sql('il')
        query = """
            SELECT il.*, u.username, u.first_name, u.last_name,
                   ii.item_name, ii.item_category, g.group_name
            FROM inventory_log il
            LEFT JOIN users u ON il.user_id = u.user_id
            LEFT JOIN inventory_items ii ON il.target_item_type = 'item' AND il.target_item_id = ii.item_id
            LEFT JOIN groups g ON il.group_id = g.group_id
            WHERE 1=1
        """ + scope.replace('i.', 'il.')
        qparams = list(params)
        if action_filter:
            query += ' AND il.action_type = %s'
            qparams.append(action_filter)
        query += ' ORDER BY il.created_at DESC LIMIT 200'
        cursor.execute(query, tuple(qparams))
        logs = cursor.fetchall()
        cursor.close()
    except Exception as e:
        logging.exception(f'Error loading audit log: {e}')
        flash('Error loading audit log.', 'danger')

    return render_template(
        'inventory/audit_log.html',
        logs=logs,
        action_filter=action_filter,
        action_types=['create', 'update', 'move', 'retire'],
    )
