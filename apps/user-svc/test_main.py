"""
=============================================================================
Unit Tests – User Microservice (Phase 3)
=============================================================================
Tests the Flask user-service CRUD endpoints using mocked database connections.
Validates the extracted service matches the monolith's expected behavior.
=============================================================================
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Import the Flask app
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_db():
    """Mock database connection and cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_dict_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor, mock_dict_cursor


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthCheck:
    @patch('main.get_db_connection')
    def test_health_check_healthy(self, mock_get_conn, client):
        """Health endpoint returns 200 when DB is reachable."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get('/health')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data['status'] == 'healthy'
        assert data['service'] == 'user-svc'

    @patch('main.get_db_connection')
    def test_health_check_unhealthy(self, mock_get_conn, client):
        """Health endpoint returns 503 when DB is unreachable."""
        mock_get_conn.side_effect = Exception("Connection refused")

        response = client.get('/health')
        data = json.loads(response.data)

        assert response.status_code == 503
        assert data['status'] == 'unhealthy'
        assert 'error' in data


# =============================================================================
# List Users Tests
# =============================================================================

class TestListUsers:
    @patch('main.get_db_connection')
    def test_list_users_success(self, mock_get_conn, client):
        """GET /api/users returns paginated users."""
        now = datetime.now(timezone.utc)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'email': 'alice@test.com', 'name': 'Alice', 'created_at': now, 'updated_at': now},
            {'id': 2, 'email': 'bob@test.com', 'name': 'Bob', 'created_at': now, 'updated_at': now},
        ]
        mock_cursor.fetchone.return_value = {'total': 2}
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get('/api/users')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert len(data['users']) == 2
        assert data['pagination']['total'] == 2
        assert data['pagination']['page'] == 1
        assert data['users'][0]['email'] == 'alice@test.com'

    @patch('main.get_db_connection')
    def test_list_users_pagination(self, mock_get_conn, client):
        """GET /api/users?page=2&per_page=1 paginates correctly."""
        now = datetime.now(timezone.utc)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 2, 'email': 'bob@test.com', 'name': 'Bob', 'created_at': now, 'updated_at': now}
        ]
        mock_cursor.fetchone.return_value = {'total': 5}
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get('/api/users?page=2&per_page=1')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data['pagination']['page'] == 2
        assert data['pagination']['per_page'] == 1
        assert data['pagination']['total'] == 5
        assert data['pagination']['pages'] == 5

    @patch('main.get_db_connection')
    def test_list_users_per_page_capped_at_100(self, mock_get_conn, client):
        """per_page parameter is capped at 100."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {'total': 0}
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get('/api/users?per_page=500')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data['pagination']['per_page'] == 100

    @patch('main.get_db_connection')
    def test_list_users_empty(self, mock_get_conn, client):
        """GET /api/users returns empty list when no users exist."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {'total': 0}
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get('/api/users')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data['users'] == []
        assert data['pagination']['total'] == 0

    @patch('main.get_db_connection')
    def test_list_users_trailing_slash(self, mock_get_conn, client):
        """GET /api/users/ (with trailing slash) also works."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {'total': 0}
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get('/api/users/')
        data = json.loads(response.data)

        assert response.status_code == 200


# =============================================================================
# Get Single User Tests
# =============================================================================

class TestGetUser:
    @patch('main.get_db_connection')
    def test_get_user_found(self, mock_get_conn, client):
        """GET /api/users/:id returns user when found."""
        now = datetime.now(timezone.utc)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1, 'email': 'alice@test.com', 'name': 'Alice',
            'created_at': now, 'updated_at': now
        }
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get('/api/users/1')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data['id'] == 1
        assert data['email'] == 'alice@test.com'

    @patch('main.get_db_connection')
    def test_get_user_not_found(self, mock_get_conn, client):
        """GET /api/users/:id returns 404 when user doesn't exist."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.get('/api/users/999')
        data = json.loads(response.data)

        assert response.status_code == 404
        assert 'error' in data


# =============================================================================
# Create User Tests
# =============================================================================

class TestCreateUser:
    @patch('main.get_db_connection')
    def test_create_user_success(self, mock_get_conn, client):
        """POST /api/users creates a new user."""
        now = datetime.now(timezone.utc)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1, 'email': 'new@test.com', 'name': 'New User',
            'created_at': now, 'updated_at': now
        }
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.post('/api/users',
            data=json.dumps({'email': 'new@test.com', 'name': 'New User'}),
            content_type='application/json')
        data = json.loads(response.data)

        assert response.status_code == 201
        assert data['email'] == 'new@test.com'
        assert data['name'] == 'New User'
        mock_conn.commit.assert_called_once()

    def test_create_user_missing_body(self, client):
        """POST /api/users returns 400 when body is empty."""
        response = client.post('/api/users', content_type='application/json')
        assert response.status_code == 400

    def test_create_user_missing_email(self, client):
        """POST /api/users returns 400 when email is missing."""
        response = client.post('/api/users',
            data=json.dumps({'name': 'Only Name'}),
            content_type='application/json')
        data = json.loads(response.data)

        assert response.status_code == 400
        assert 'required' in data['error']

    def test_create_user_missing_name(self, client):
        """POST /api/users returns 400 when name is missing."""
        response = client.post('/api/users',
            data=json.dumps({'email': 'only@email.com'}),
            content_type='application/json')

        assert response.status_code == 400

    @patch('main.get_db_connection')
    def test_create_user_duplicate_email(self, mock_get_conn, client):
        """POST /api/users returns 409 for duplicate email."""
        import psycopg2.errors
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = psycopg2.errors.UniqueViolation("duplicate")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.post('/api/users',
            data=json.dumps({'email': 'dup@test.com', 'name': 'Duplicate'}),
            content_type='application/json')

        assert response.status_code == 409
        mock_conn.rollback.assert_called_once()


# =============================================================================
# Update User Tests
# =============================================================================

class TestUpdateUser:
    @patch('main.get_db_connection')
    def test_update_user_success(self, mock_get_conn, client):
        """PUT /api/users/:id updates user fields."""
        now = datetime.now(timezone.utc)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1, 'email': 'updated@test.com', 'name': 'Updated',
            'created_at': now, 'updated_at': now
        }
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.put('/api/users/1',
            data=json.dumps({'name': 'Updated'}),
            content_type='application/json')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data['name'] == 'Updated'
        mock_conn.commit.assert_called_once()

    @patch('main.get_db_connection')
    def test_update_user_not_found(self, mock_get_conn, client):
        """PUT /api/users/:id returns 404 for non-existent user."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.put('/api/users/999',
            data=json.dumps({'name': 'Nobody'}),
            content_type='application/json')

        assert response.status_code == 404

    def test_update_user_empty_body(self, client):
        """PUT /api/users/:id returns 400 with empty body."""
        response = client.put('/api/users/1', content_type='application/json')
        assert response.status_code == 400

    @patch('main.get_db_connection')
    def test_update_user_no_valid_fields(self, mock_get_conn, client):
        """PUT /api/users/:id returns 400 when no valid fields provided."""
        response = client.put('/api/users/1',
            data=json.dumps({'invalid_field': 'value'}),
            content_type='application/json')
        assert response.status_code == 400


# =============================================================================
# Delete User Tests
# =============================================================================

class TestDeleteUser:
    @patch('main.get_db_connection')
    def test_delete_user_success(self, mock_get_conn, client):
        """DELETE /api/users/:id deletes a user."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.delete('/api/users/1')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert 'deleted' in data['message']
        mock_conn.commit.assert_called_once()

    @patch('main.get_db_connection')
    def test_delete_user_not_found(self, mock_get_conn, client):
        """DELETE /api/users/:id returns 404 for non-existent user."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        response = client.delete('/api/users/999')
        assert response.status_code == 404
