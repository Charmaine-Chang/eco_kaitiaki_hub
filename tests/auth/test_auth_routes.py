def test_login_page_renders(client):
    """Test that the login page renders successfully."""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Login' in response.data

def test_logout_redirects(client, auth):
    """Test that logout redirects to home."""
    auth.login()
    response = client.get('/auth/logout')
    assert response.status_code == 302
    assert '/' in response.headers['Location']

def test_my_groups_buttons_coordinator(client, auth):
    """Test that a coordinator sees the Apply for New Group button and not Create New Group on the My Groups page."""
    auth.login(username="coord_Alice", role_id=2, group_id=2, is_super_admin=False)
    response = client.get('/auth/my-groups')
    assert response.status_code == 200
    assert b'Apply for New Group' in response.data
    assert b'Create New Group' not in response.data

def test_my_groups_buttons_superadmin(client, auth):
    """Test that a superadmin sees the Create New Group button on the My Groups page."""
    auth.login(username="superadmin", role_id=1, group_id=1, is_super_admin=True)
    response = client.get('/auth/my-groups')
    assert response.status_code == 200
    assert b'Create New Group' in response.data
    assert b'Apply for New Group' not in response.data

