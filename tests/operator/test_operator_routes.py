def test_operator_dashboard_unauthenticated(client):
    """Test that unauthenticated users cannot access operator dashboard."""
    response = client.get('/operator/')
    assert response.status_code == 302

def test_operator_dashboard_authenticated(client, auth):
    """Test that operators can access their dashboard."""
    auth.login(role_id=3, is_super_admin=False)  # ROLE_OPERATOR
    response = client.get('/operator/')
    assert response.status_code == 200
    assert b'Operator Dashboard' in response.data or b'Operator' in response.data

def test_operator_edit_bait_station_get(client, auth):
    """Test that operators can access the edit bait station page."""
    # Log in as op_Dave (user_id 5, group_id 2, role_id 3)
    auth.login(username='op_Dave', role_id=3, group_id=2, is_super_admin=False)
    # Perform GET request for a valid bait station in group 2
    response = client.get('/operator/edit_bait_station/D-BS1')
    assert response.status_code == 200
    assert b'Edit Bait Station' in response.data

def test_operator_edit_bait_station_post(client, auth):
    """Test that operators can successfully update a bait station."""
    auth.login(username='op_Dave', role_id=3, group_id=2, is_super_admin=False)
    # Perform POST request to update D-BS1
    response = client.post('/operator/edit_bait_station/D-BS1', data={
        'bait_station_type_id': '1',
        'line_id': '2',
        'latitude': '-43.0805',
        'longitude': '172.1745',
        'equipment_status': 'Active'
    })
    # Should redirect to view_lines (which matches operator.view_lines)
    assert response.status_code == 302
    assert 'operator/lines' in response.location

def test_operator_edit_trap_get(client, auth):
    """Test that operators can access the edit trap page."""
    auth.login(username='op_Dave', role_id=3, group_id=2, is_super_admin=False)
    response = client.get('/operator/edit_trap/D-T5')
    assert response.status_code == 200
    assert b'Edit Trap' in response.data

def test_operator_edit_trap_post(client, auth):
    """Test that operators can successfully update a trap."""
    auth.login(username='op_Dave', role_id=3, group_id=2, is_super_admin=False)
    response = client.post('/operator/edit_trap/D-T5', data={
        'trap_type_id': '1',
        'line_id': '6',
        'latitude': '-43.0805',
        'longitude': '172.1745',
        'equipment_status': 'Active'
    })
    assert response.status_code == 302
    assert 'operator/lines' in response.location

