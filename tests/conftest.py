import pytest
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PF_LU_APP import create_app
from PF_LU_APP.db import get_db

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,  # Disable CSRF for testing
    })

    yield app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

@pytest.fixture
def auth(client):
    """Authentication helper fixture."""
    class AuthActions:
        def login(self, username="admin", role_id=1, group_id=1, is_super_admin=True):
            """Simulates a login by modifying the session directly."""
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['username'] = username
                sess['role_id'] = role_id
                sess['current_group_id'] = group_id
                sess['is_super_admin'] = is_super_admin

        def logout(self):
            """Simulates a logout."""
            with client.session_transaction() as sess:
                sess.clear()

    return AuthActions()
