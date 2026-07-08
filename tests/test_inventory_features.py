"""Smoke tests for inventory user stories. Run: python test_inventory_features.py"""
import sys

from PF_LU_APP import create_app
from PF_LU_APP.db import get_db, get_cursor


def session_as(client, user_id, role_id, group_id=2, is_super_admin=False):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['role_id'] = role_id
        sess['current_group_id'] = group_id
        sess['current_group_name'] = 'Test Group'
        sess['is_super_admin'] = is_super_admin


def uid(cursor, username):
    cursor.execute('SELECT user_id FROM users WHERE username = %s', (username,))
    return cursor.fetchone()['user_id']


def main():
    app = create_app()
    failures = []
    client = app.test_client()

    with app.app_context():
        c = get_cursor()
        obs_id = uid(c, 'obs_Judy')
        op_id = uid(c, 'op_Eve')
        coord_id = uid(c, 'coord_Alice')
        c.execute('UPDATE inventory_items SET quantity = 0.5 WHERE item_id = 1')
        c.execute('SELECT line_id FROM lines WHERE group_id=2 LIMIT 1')
        line = c.fetchone()['line_id']
        get_db().commit()
        c.close()

    session_as(client, obs_id, 4, group_id=2)
    r = client.get('/inventory/')
    if r.status_code != 302 or 'observer' not in (r.location or ''):
        failures.append(f'Observer denied failed: {r.status_code}')

    session_as(client, op_id, 3, group_id=2)
    if client.get('/inventory/').status_code != 200:
        failures.append('Operator stock list failed')

    if client.get('/inventory/audit').status_code != 302:
        failures.append('Operator audit should be denied')

    session_as(client, coord_id, 2, group_id=2)
    if client.get('/inventory/audit').status_code != 200:
        failures.append('Coordinator audit failed')

    session_as(client, op_id, 3, group_id=2)
    r = client.post('/inventory/item/1/move', data={
        'dest_type': 'line', 'dest_id': str(line), 'confirmed': '0',
    })
    if b'Confirm move' not in r.data:
        failures.append('Move confirm page failed')

    client.post('/inventory/item/1/move', data={
        'dest_type': 'line', 'dest_id': str(line), 'confirmed': '1',
    })

    with app.app_context():
        c = get_cursor()
        c.execute("""
            SELECT previous_location, new_location FROM inventory_log
            WHERE target_item_id=1 AND action_type='move'
            ORDER BY created_at DESC LIMIT 1
        """)
        log = c.fetchone()
        c.close()
        if not log or not log['previous_location']:
            failures.append('Move audit log incomplete')

    with app.app_context():
        c = get_cursor()
        c.execute("SELECT bait_type_id, bait_type_name FROM bait_type LIMIT 1")
        bait = c.fetchone()
        if not bait:
            c.execute("INSERT INTO bait_type (bait_type_name) VALUES (%s)", ('Test Bait',))
            bait_type_id = c.lastrowid
            bait = {'bait_type_id': bait_type_id, 'bait_type_name': 'Test Bait'}
        bait_type_id = bait['bait_type_id']
        bait_type_name = bait['bait_type_name']

        c.execute(
            "SELECT item_id, quantity FROM inventory_items WHERE group_id = %s AND LOWER(item_category) = 'bait' AND LOWER(item_name) = LOWER(%s) LIMIT 1",
            (2, bait_type_name),
        )
        bait_item = c.fetchone()
        if not bait_item:
            c.execute(
                "INSERT INTO inventory_items (group_id, item_category, item_name, quantity, threshold) VALUES (%s, 'Bait', %s, %s, %s)",
                (2, bait_type_name, 5, 1),
            )
            item_id = c.lastrowid
            bait_item = {'item_id': item_id, 'quantity': 5}

        initial_qty = bait_item['quantity'] if bait_item['quantity'] is not None else 0
        c.execute(
            "SELECT t.trap_code FROM traps t JOIN lines l ON t.line_id = l.line_id WHERE l.group_id = %s AND t.status = 'active' LIMIT 1",
            (2,),
        )
        trap = c.fetchone()
        c.execute("SELECT species_id FROM species ORDER BY species_id LIMIT 1")
        species_id = c.fetchone()['species_id']
        c.execute("SELECT trap_status_id FROM trap_status ORDER BY trap_status_id LIMIT 1")
        trap_status_id = c.fetchone()['trap_status_id']
        c.execute("SELECT trap_condition_id FROM trap_condition ORDER BY trap_condition_id LIMIT 1")
        trap_condition_id = c.fetchone()['trap_condition_id']
        get_db().commit()
        c.close()
        if not trap:
            failures.append('No active trap available for bait usage test')
        else:
            trap_code = trap['trap_code']
            session_as(client, op_id, 3, group_id=2)
            r = client.post(f'/operator/add_catch/{trap_code}', data={
                'date': '2026-01-01 10:00',
                'species_id': str(species_id),
                'sex': 'male',
                'maturity': 'adult',
                'trap_status_id': str(trap_status_id),
                'trap_condition_id': str(trap_condition_id),
                'bait_type_id': str(bait_type_id),
            })
            if r.status_code != 302:
                failures.append('Operator bait usage record failed')
            with app.app_context():
                c = get_cursor()
                c.execute("SELECT quantity FROM inventory_items WHERE item_id = %s", (bait_item['item_id'],))
                updated_qty = c.fetchone()['quantity']
                c.close()
                if updated_qty != initial_qty - 1:
                    failures.append('Bait inventory did not decrement when usage recorded')

        # Test Bait Station Record inventory decrement
        c = get_cursor()
        c.execute(
            "SELECT bs.bait_station_code FROM bait_stations bs JOIN lines l ON bs.line_id = l.line_id WHERE l.group_id = %s AND (bs.status = 'active' OR bs.status IS NULL) LIMIT 1",
            (2,),
        )
        station_row = c.fetchone()
        c.close()
        
        if not station_row:
            failures.append('No active bait station available for bait usage test')
        else:
            bait_station_code = station_row['bait_station_code']
            
            # Reset bait item quantity to 10.0
            c = get_cursor()
            c.execute("UPDATE inventory_items SET quantity = 10.0 WHERE item_id = %s", (bait_item['item_id'],))
            get_db().commit()
            c.close()
            
            # POST add_bait_record
            session_as(client, op_id, 3, group_id=2)
            r = client.post(f'/operator/add_bait_record/{bait_station_code}', data={
                'date': '2026-01-01 10:00',
                'target_species_id': str(species_id),
                'bait_type_id': str(bait_type_id),
                'active_ingredient': 'Brodifacoum',
                'formulation': 'Pellet',
                'concentration': '0.005',
                'bait_remaining': '0.2',
                'bait_removed': '0.1',
                'bait_added': '1.5',
                'notes': 'Test add bait station record',
            })
            if r.status_code != 302:
                failures.append('Operator add bait station record failed')
                
            with app.app_context():
                c = get_cursor()
                c.execute("SELECT quantity FROM inventory_items WHERE item_id = %s", (bait_item['item_id'],))
                qty_after_add = c.fetchone()['quantity']
                c.close()
                if qty_after_add != 8.5:
                    failures.append(f'Bait station inventory did not decrement by bait_added (expected 8.5, got {qty_after_add})')
                    
            # Find the record we just inserted
            c = get_cursor()
            c.execute("SELECT record_id FROM bait_station_records WHERE bait_station_code = %s ORDER BY record_id DESC LIMIT 1", (bait_station_code,))
            rec_id = c.fetchone()['record_id']
            c.close()
            
            # POST edit_bait_record to change bait_added to 0.5 (returning 1.0 to inventory)
            session_as(client, op_id, 3, group_id=2)
            r = client.post(f'/operator/edit_bait_record/{rec_id}', data={
                'date': '2026-01-01 10:00',
                'target_species_id': str(species_id),
                'bait_type_id': str(bait_type_id),
                'active_ingredient': 'Brodifacoum',
                'formulation': 'Pellet',
                'concentration': '0.005',
                'bait_remaining': '0.2',
                'bait_removed': '0.1',
                'bait_added': '0.5',
                'notes': 'Test edit bait station record',
            })
            if r.status_code != 302:
                failures.append('Operator edit bait station record failed')
                
            with app.app_context():
                c = get_cursor()
                c.execute("SELECT quantity FROM inventory_items WHERE item_id = %s", (bait_item['item_id'],))
                qty_after_edit = c.fetchone()['quantity']
                c.close()
                if qty_after_edit != 9.5:
                    failures.append(f'Bait station inventory did not adjust correctly on edit (expected 9.5, got {qty_after_edit})')

    session_as(client, coord_id, 2, group_id=2)
    if b'Low bait' not in client.get('/manage/').data:
        failures.append('Dashboard low stock alert missing')

    if failures:
        for f in failures:
            print('FAILED:', f)
        return 1
    print('All inventory smoke tests passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
