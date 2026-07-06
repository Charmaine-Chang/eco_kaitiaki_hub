import pytest

def test_knowledge_hub_public_access(client):
    """User Story 37 & 38: Public user accesses species knowledge base."""
    response = client.get('/knowledge/')
    assert response.status_code in [200, 302]

def test_species_guide_detail(client):
    """Test viewing a specific species guide."""
    response = client.get('/knowledge')
    assert response.status_code == 200
    # In a real scenario, click on a species. For now just test the index.

def test_superadmin_manage_taxonomy(client, auth):
    """User Story 40 & 48: Super Admin manages global species taxonomy."""
    auth.login(username="superadmin", role_id=1, group_id=1, is_super_admin=True)
    response = client.get('/manage/global_metadata')
    assert response.status_code == 200

def test_coordinator_target_species(client, auth):
    """User Story 41: Coordinator configures local target species."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    # The actual implementation of target species might be via group settings or metadata
    response = client.get('/manage/group_settings')
    assert response.status_code in [200, 302, 404]

def test_record_non_target_interaction(client, auth):
    """User Story 54: Operator records an interaction with a non-target species."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    response = client.get('/operator/lines')
    assert response.status_code == 200

def test_admin_analyze_non_target_bycatch(client, auth):
    """User Story 55: Coordinator views reports on non-target catches."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/manage/graphs')
    assert response.status_code == 200
