def test_home_page(client):
    """Test that the home page loads successfully."""
    response = client.get('/')
    assert response.status_code == 200

def test_search_redirects_if_empty(client):
    """Test that empty search redirects."""
    response = client.get('/search?q=')
    assert response.status_code == 302
