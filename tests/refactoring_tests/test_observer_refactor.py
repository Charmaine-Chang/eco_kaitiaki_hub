import unittest
from flask import Flask, session
from PF_LU_APP import create_app
from PF_LU_APP.constants import ROLE_SUPER_ADMIN, ROLE_COORDINATOR, ROLE_OPERATOR, ROLE_OBSERVER

class TestObserverRefactor(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_observer_dashboard_unauthenticated(self):
        """Test that unauthenticated users are redirected from observer dashboard."""
        response = self.client.get('/observer/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login', response.headers.get('Location', ''))

    def test_observer_dashboard_wrong_role(self):
        """Test that users with wrong roles are redirected from observer dashboard."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role_id'] = ROLE_OPERATOR # Not an observer
            
        response = self.client.get('/observer/')
        self.assertEqual(response.status_code, 302)
        # Should redirect to operator dashboard based on smart redirect in decorator
        self.assertIn('/operator/', response.headers.get('Location', ''))

    def test_observer_dashboard_correct_role_db_error_handled(self):
        """
        Test that users with the correct role can access the dashboard.
        Since we have no DB connection mocked here, it should hit the psycopg2/DB error
        and render the template with empty stats instead of crashing.
        """
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role_id'] = ROLE_OBSERVER
            sess['current_group_id'] = 1
            
        response = self.client.get('/observer/')
        self.assertEqual(response.status_code, 200)
        # Check if the page renders (meaning DB error was caught and handled)
        self.assertIn(b'Observer Dashboard', response.data)

if __name__ == '__main__':
    unittest.main()
