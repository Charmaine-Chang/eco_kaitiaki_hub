def test_admin_dashboard_unauthenticated(client):
    """Test that unauthenticated users are redirected from admin dashboard."""
    response = client.get('/manage/')
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']

def test_admin_dashboard_authenticated(client, auth):
    """Test that super admins can access the admin dashboard."""
    auth.login(role_id=1, is_super_admin=True)
    response = client.get('/manage/')
    assert response.status_code == 200

def test_admin_dashboard_access_denied_operator(client, auth):
    """Test that Operators cannot access the admin dashboard."""
    auth.login(role_id=3, is_super_admin=False)
    response = client.get('/manage/')
    # Expect redirect to home or 403. Our app redirects with flash on unauthorized access.
    assert response.status_code == 302
    assert '/' in response.headers['Location']

def test_admin_dashboard_access_denied_observer(client, auth):
    """Test that Observers cannot access the admin dashboard."""
    auth.login(role_id=4, is_super_admin=False)
    response = client.get('/manage/')
    assert response.status_code == 302
    assert '/' in response.headers['Location']

def test_admin_users_access_denied_coordinator(client, auth):
    """Test that a Coordinator cannot access global users page (Super Admin only)."""
    auth.login(role_id=2, is_super_admin=False)
    response = client.get('/manage/global_users')
    assert response.status_code == 302
    assert '/' in response.headers['Location']

def test_delete_group_invalid(client, auth):
    """Test attempting to delete a non-existent group ID fails gracefully."""
    auth.login(role_id=1, is_super_admin=True)
    # POST to a non-existent group ID 99999
    response = client.post('/manage/delete_group/99999')
    # Should handle gracefully, likely 302 redirect back to manage_groups with error flash
    # or 404
    assert response.status_code in [302, 404]


def test_remove_member_from_group_coordinator_access_denied(client, auth):
    """Test that a Coordinator cannot remove a user from a group."""
    auth.login(role_id=2, is_super_admin=False)
    response = client.post('/manage/user/3/remove_from_group/1')
    assert response.status_code == 302
    assert '/' in response.headers['Location']


def test_remove_member_from_group_super_admin_invalid_membership(client, auth):
    """Test that Super Admin POST with invalid membership redirects back to user detail with error."""
    auth.login(role_id=1, is_super_admin=True)
    # Attempt to remove a non-existent membership (user 99999, group 99999)
    response = client.post('/manage/user/99999/remove_from_group/99999')
    assert response.status_code == 302
    assert '/manage/users/99999' in response.headers['Location']


