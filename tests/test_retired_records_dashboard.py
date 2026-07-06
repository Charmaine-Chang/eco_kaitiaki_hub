"""Tests for retired items and dashboard pending tasks. Run: .venv/bin/python test_retired_records_dashboard.py"""
import sys
from PF_LU_APP import create_app
from PF_LU_APP.db import get_db, get_cursor

def session_as(client, user_id, role_id, group_id=None, is_super_admin=False):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['role_id'] = role_id
        sess['current_group_id'] = group_id
        sess['current_group_name'] = 'System Management' if not group_id else 'Test Group'
        sess['is_super_admin'] = is_super_admin

def uid(cursor, username):
    cursor.execute('SELECT user_id FROM users WHERE username = %s', (username,))
    return cursor.fetchone()['user_id']

def run_tests():
    app = create_app()
    client = app.test_client()
    failures = []

    with app.app_context():
        db = get_db()
        cursor = get_cursor()

        # Get relevant users
        admin_id = uid(cursor, 'superadmin')
        coord_id = uid(cursor, 'coord_Alice')
        op_id = uid(cursor, 'op_Eve')

        # 1. Verify Retired Trap Edit Guard
        # Let's insert or update a trap as retired
        cursor.execute("SELECT trap_code FROM traps LIMIT 1")
        trap = cursor.fetchone()
        if not trap:
            failures.append("No trap found to test")
            return failures
        
        trap_code = trap['trap_code']
        print(f"Testing with trap_code: {trap_code}")
        # Set trap to Retired status (equipment_status_id = 4 or inactive status overall)
        cursor.execute("""
            UPDATE traps 
            SET status = 'inactive', equipment_status_id = 4 
            WHERE trap_code = %s
        """, (trap_code,))
        db.commit()

    # Log in as admin and try editing the retired trap
    session_as(client, admin_id, 1, group_id=2, is_super_admin=True)
    
    # Try updating status of retired trap from inventory page
    response = client.post('/manage/inventory/update_status', data={
        'equipment_code': trap_code,
        'equipment_type': 'trap',
        'status_id': '1'  # Try to make it active (1)
    }, follow_redirects=True)
    print("Status Update Response Status:", response.status_code)
    print("Status Update Response Snippet:", response.data[:500])
    if b"The item is no longer in service." not in response.data:
        failures.append("Retired trap status update should be rejected with 'The item is no longer in service.'")

    # Try recording catch on retired trap
    response = client.post('/operator/add_catch', data={
        'trap_code': trap_code,
        'species_id': '1',
        'date': '2026-05-25 12:00:00',
        'notes': 'test'
    }, follow_redirects=True)
    print("Catches Response Status:", response.status_code)
    print("Catches Response Snippet:", response.data[:500])
    if b"The item is no longer in service." not in response.data:
        failures.append("Recording catch on retired trap should be rejected with 'The item is no longer in service.'")

    # Try editing retired trap details
    response = client.post(f'/manage/edit_trap/{trap_code}', data={
        'trap_code': trap_code,
        'trap_type_id': '1',
        'line_id': '1',
        'status_id': '1',
        'notes': 'should fail'
    }, follow_redirects=True)
    print("Edit Response Status:", response.status_code)
    print("Edit Response Snippet:", response.data[:500])
    if b"The item is no longer in service." not in response.data:
        failures.append("Editing retired trap should be rejected with 'The item is no longer in service.'")

    # 2. Test Pending Tasks Count on Global View (Super Admin)
    with app.app_context():
        db = get_db()
        cursor = get_cursor()

        # Count current pending groups, memberships, upgrades, and low stock items
        cursor.execute("SELECT COUNT(*) as count FROM groups WHERE status = 'pending'")
        initial_groups = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM group_membership WHERE membership_status = 'pending'")
        initial_members = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM role_upgrade_requests WHERE status = 'pending'")
        initial_upgrades = cursor.fetchone()['count']

        from PF_LU_APP.inventory.utils import fetch_low_stock_alerts
        initial_low_stock = len(fetch_low_stock_alerts(cursor, all_groups=True))

        expected_tasks = initial_groups + initial_members + initial_upgrades + initial_low_stock

    # Load global dashboard
    session_as(client, admin_id, 1, group_id=None, is_super_admin=True)
    response = client.get('/manage/')
    
    # Check if the pending tasks KPI shows the expected number
    expected_tasks_str = f"{expected_tasks}".encode('utf-8')
    if expected_tasks_str not in response.data:
        failures.append(f"Global admin dashboard pending tasks count mismatch: expected {expected_tasks}")

    # Now let's insert a pending member and verify count increments
    with app.app_context():
        db = get_db()
        cursor = get_cursor()
        
        # Find a user
        cursor.execute("SELECT user_id FROM users WHERE username = 'op_Eve'")
        user_id = cursor.fetchone()['user_id']
        
        # Delete existing pending if any
        cursor.execute("DELETE FROM group_membership WHERE user_id = %s AND group_id = 2", (user_id,))
        # Insert a pending membership
        cursor.execute("""
            INSERT INTO group_membership (user_id, group_id, role_id, membership_status)
            VALUES (%s, 2, 3, 'pending')
        """, (user_id,))
        db.commit()

    response = client.get('/manage/')
    new_expected_tasks = expected_tasks + 1
    new_expected_tasks_str = f"{new_expected_tasks}".encode('utf-8')
    if new_expected_tasks_str not in response.data:
        failures.append(f"Global admin dashboard pending tasks count did not increment after adding pending member. Expected {new_expected_tasks}")

    # Clean up
    with app.app_context():
        db = get_db()
        cursor = get_cursor()
        cursor.execute("DELETE FROM group_membership WHERE user_id = %s AND group_id = 2 AND membership_status = 'pending'", (user_id,))
        # Restore trap status
        cursor.execute("""
            UPDATE traps 
            SET status = 'active', equipment_status_id = 1 
            WHERE trap_code = %s
        """, (trap_code,))
        db.commit()

    return failures

if __name__ == '__main__':
    failures = run_tests()
    if failures:
        print("Test Suite Failed:")
        for failure in failures:
            print("-", failure)
        sys.exit(1)
    else:
        print("All retired items and pending tasks tests passed successfully!")
        sys.exit(0)
