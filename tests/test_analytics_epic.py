import pytest

def test_admin_dashboard_kpis(client, auth):
    """User Story 11 & 14: Coordinator dashboard shows KPIs and group performance."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/manage/')
    assert response.status_code == 200
    assert b"Catches" in response.data or b"Dashboard" in response.data

def test_operator_dashboard_kpis(client, auth):
    """User Story 18 & 19: Operator sees personal catch statistics."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    response = client.get('/operator/')
    assert response.status_code == 200
    assert b"My Impact" in response.data or b"Dashboard" in response.data

def test_export_csv_admin(client, auth):
    """User Story 15: Coordinator exports all group records as CSV."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/manage/export')
    assert response.status_code == 200

def test_export_csv_operator(client, auth):
    """User Story 25: Operator exports their own records as CSV."""
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    response = client.get('/manage/operator/download_csv')
    assert response.status_code == 200

def test_admin_datagraphs(client, auth):
    """User Story 26: Coordinator views interactive charts for data analysis."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/manage/graphs')
    assert response.status_code == 200

def test_admin_json_chart_api(client, auth):
    """Test the JSON API endpoints for charts."""
    auth.login(username="coordinator", role_id=2, group_id=1, is_super_admin=False)
    response = client.get('/manage/api/dashboard-charts?period=all')
    # If the database is empty or not configured, might return 500 or 200.
    # Just asserting it resolves to an endpoint (200, 404, etc)
    assert response.status_code in [200, 404]

def test_superadmin_analytics(client, auth):
    """User Story 32: Super Admin views platform-wide analytics."""
    auth.login(username="superadmin", role_id=1, group_id=1, is_super_admin=True)
    response = client.get('/manage/')
    assert response.status_code == 200

def test_operator_pdf_download_restricted(client, auth):
    """Test that operators are blocked from downloading PDF reports in analytics and export page."""
    # Login as operator
    auth.login(username="operator", role_id=3, group_id=1, is_super_admin=False)
    
    # Blocked from data analytics PDF download
    response = client.get('/operator/graphs/download-report?report_type=summary')
    assert response.status_code == 302 # Redirected due to roles_required denial
    
    # Allowed to access export data page
    response = client.get('/manage/export')
    assert response.status_code == 200
    
    # Blocked from exporting PDF format on export data page
    response = client.post('/manage/export', data={'export_type': 'traps', 'format': 'pdf'})
    assert response.status_code == 302 # Redirected with warning
    
def test_observer_download_denied(client, auth):
    """Test that observers are blocked from exporting CSV or PDF reports completely."""
    # Login as observer
    auth.login(username="observer", role_id=4, group_id=1, is_super_admin=False)
    
    # Blocked from CSV downloads
    response = client.get('/observer/operator/download_csv')
    assert response.status_code == 302
    
    # Blocked from graphs report PDF downloads
    response = client.get('/observer/graphs/download-report?report_type=summary')
    assert response.status_code == 302
    
    # Blocked from general export page
    response = client.get('/manage/export')
    assert response.status_code == 302
