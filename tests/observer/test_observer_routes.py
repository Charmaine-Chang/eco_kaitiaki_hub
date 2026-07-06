def test_observer_dashboard_unauthenticated(client):
    """Test that unauthenticated users cannot access observer dashboard."""
    response = client.get('/observer/')
    assert response.status_code == 302

def test_observer_dashboard_authenticated(client, auth):
    """Test that observers can access their dashboard."""
    auth.login(role_id=4, is_super_admin=False)  # ROLE_OBSERVER
    response = client.get('/observer/')
    assert response.status_code == 200
    assert b'Observer' in response.data or b'Dashboard' in response.data
