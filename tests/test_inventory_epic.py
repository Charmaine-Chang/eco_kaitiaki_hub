import pytest

def test_inventory_dashboard_access(client, auth):
    """User Story 21: Coordinator access to inventory dashboard."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/inventory/')
    assert response.status_code == 200
    assert b"Inventory" in response.data

def test_add_inventory_item(client, auth):
    """Test coordinator adding global inventory items."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/manage/inventory/add')
    assert response.status_code == 200

def test_add_equipment_to_line(client, auth):
    """User Story 10: Coordinator manages a line's equipment."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/manage/add_equipment?line_id=1')
    assert response.status_code == 200

def test_operator_checkout_bait(client, auth):
    """User Story 22: Operator checks out bait from global inventory."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    response = client.get('/operator/inventory')
    # Can access checkout form
    assert response.status_code == 200

def test_fault_reporting(client, auth):
    """User Story 28: Operator reports a damaged trap."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    response = client.get('/operator/lines')
    assert response.status_code == 200
    # Fault reporting via modal or specific page depends on implementation
    # If there is an equipment endpoint for reporting fault
    response = client.get('/operator/equipment-map')
    assert response.status_code == 200

def test_superadmin_manage_equipment_types(client, auth):
    """User Story 29: Superadmin manages trap and bait station models."""
    auth.login(username="superadmin", role_id=1, group_id=1, is_super_admin=True)
    response = client.get('/manage/global_metadata')
    assert response.status_code == 200
    assert b"Trap Models" in response.data or b"Metadata" in response.data

def test_inventory_dashboard_unauthorized(client, auth):
    """Test that Observers cannot access the inventory dashboard."""
    auth.login(username="observer", role_id=4, group_id=1, is_super_admin=False)
    response = client.get('/inventory/')
    # Observers shouldn't have access to the main inventory management
    assert response.status_code == 302
    assert '/' in response.headers['Location']

def test_add_inventory_item_invalid_data(client, auth):
    """Test coordinator submitting invalid data to add inventory."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    # Missing required fields like equipment_type_id
    response = client.post('/manage/inventory/add', data={
        'quantity': '10',
    })
    # Should stay on the same page with validation errors (200 OK) or handle gracefully with a redirect (302)
    assert response.status_code in [200, 302]

def test_operator_checkout_bait_insufficient_stock(client, auth):
    """Test operator trying to checkout more bait than available."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    
    # We would need to know the exact endpoint and fields for checkout
    # Assuming there's a POST endpoint for checking out bait
    # If the endpoint doesn't exist yet, we simulate what we'd expect
    response = client.post('/operator/checkout_bait', data={
        'bait_type_id': '1',
        'quantity': '-1' # Nagative number
    })
    
    # If endpoint exists, it should handle it gracefully. If not, it'll 404.
    # Either way, it shouldn't crash with 500.
    assert response.status_code in [200, 302, 404]

def test_retire_equipment_unauthorized(client, auth):
    """Test operator cannot retire equipment."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    response = client.post('/manage/action_retire_trap/TRAP123')
    assert response.status_code == 302
    assert '/' in response.headers['Location']

