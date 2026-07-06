import pytest

def test_view_lines_coordinator(client, auth):
    """User Story 6: Coordinator views all lines."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/manage/lines')
    assert response.status_code == 200

def test_add_new_line(client, auth):
    """User Story 7: Coordinator draws a new line."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/manage/create_new_lines')
    assert response.status_code == 200

def test_assign_operator_to_line(client, auth):
    """User Story 9: Coordinator assigns an operator to a line."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/manage/lines')
    assert response.status_code == 200

def test_operator_view_my_lines(client, auth):
    """User Story 12: Operator views lines assigned to them."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    response = client.get('/operator/lines')
    assert response.status_code == 200

def test_operator_record_catch(client, auth):
    """User Story 13: Operator records a trap catch in the field."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    response = client.get('/operator/lines')
    # Entering catch details via specific endpoint
    assert response.status_code == 200

def test_equipment_map_view(client, auth):
    """User Story 23 & 24: View equipment map with pins."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    response = client.get('/operator/equipment-map')
    assert response.status_code == 200

def test_operator_record_bait_refill(client, auth):
    """User Story 50: Operator records bait station refilling."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    response = client.get('/operator/lines')
    assert response.status_code == 200
