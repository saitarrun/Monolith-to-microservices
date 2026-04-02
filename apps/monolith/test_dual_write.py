"""
=============================================================================
Unit Tests – Dual-Write Module (Phase 6)
=============================================================================
Tests the dual-write pattern for data consistency between monolith and
user-service during the Strangler Fig migration.
=============================================================================
"""

import pytest
import os
from unittest.mock import patch, MagicMock, PropertyMock
import requests


# Set env before importing
os.environ['DUAL_WRITE_ENABLED'] = 'true'
os.environ['USER_SVC_URL'] = 'http://mock-user-svc'
os.environ['USER_SVC_DB_URL'] = 'postgresql://mock:mock@localhost:5432/mock'

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from core.dual_write import (
    dual_write_user_http,
    dual_write_user_db,
    dual_write_update_user,
    dual_write_delete_user,
    DualWriteError,
)


SAMPLE_USER = {'email': 'test@example.com', 'name': 'Test User'}


# =============================================================================
# dual_write_user_http Tests
# =============================================================================

class TestDualWriteHTTP:
    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.requests.post')
    def test_http_success_201(self, mock_post):
        """HTTP dual-write returns response on 201."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'id': 1, 'email': 'test@example.com'}
        mock_post.return_value = mock_response

        result = dual_write_user_http(SAMPLE_USER)

        assert result is not None
        assert result['id'] == 1
        mock_post.assert_called_once()

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.requests.post')
    def test_http_success_200(self, mock_post):
        """HTTP dual-write returns response on 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 1}
        mock_post.return_value = mock_response

        result = dual_write_user_http(SAMPLE_USER)
        assert result is not None

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.requests.post')
    def test_http_idempotent_409(self, mock_post):
        """HTTP dual-write handles 409 (already exists) gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_post.return_value = mock_response

        result = dual_write_user_http(SAMPLE_USER)
        assert result is None  # Idempotent – no error raised

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.dual_write_user_db')
    @patch('core.dual_write.requests.post')
    def test_http_fallback_on_server_error(self, mock_post, mock_db_write):
        """HTTP dual-write falls back to DB on 500."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_post.return_value = mock_response
        mock_db_write.return_value = {'id': 99}

        result = dual_write_user_http(SAMPLE_USER)

        mock_db_write.assert_called_once_with(SAMPLE_USER)

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.dual_write_user_db')
    @patch('core.dual_write.requests.post')
    def test_http_fallback_on_connection_error(self, mock_post, mock_db_write):
        """HTTP dual-write falls back to DB when service is unreachable."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        mock_db_write.return_value = {'id': 100}

        result = dual_write_user_http(SAMPLE_USER)

        mock_db_write.assert_called_once_with(SAMPLE_USER)

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.dual_write_user_db')
    @patch('core.dual_write.requests.post')
    def test_http_fallback_on_timeout(self, mock_post, mock_db_write):
        """HTTP dual-write falls back to DB on timeout."""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        mock_db_write.return_value = None

        result = dual_write_user_http(SAMPLE_USER)

        mock_db_write.assert_called_once_with(SAMPLE_USER)

    @patch('core.dual_write.DUAL_WRITE_ENABLED', False)
    def test_http_disabled(self):
        """HTTP dual-write returns None when disabled."""
        result = dual_write_user_http(SAMPLE_USER)
        assert result is None


# =============================================================================
# dual_write_user_db Tests
# =============================================================================

class TestDualWriteDB:
    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.psycopg2.connect')
    def test_db_write_success(self, mock_connect):
        """DB dual-write inserts user and returns ID."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (42,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = dual_write_user_db(SAMPLE_USER)

        assert result is not None
        assert result['id'] == 42
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.psycopg2.connect')
    def test_db_write_idempotent_conflict(self, mock_connect):
        """DB dual-write handles ON CONFLICT DO NOTHING (returns None)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # ON CONFLICT DO NOTHING
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = dual_write_user_db(SAMPLE_USER)

        assert result is None  # Idempotent – no error
        mock_conn.commit.assert_called_once()

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.psycopg2.connect')
    def test_db_write_connection_error(self, mock_connect):
        """DB dual-write handles connection failures gracefully."""
        mock_connect.side_effect = Exception("Cannot connect")

        result = dual_write_user_db(SAMPLE_USER)
        assert result is None  # Non-fatal

    @patch('core.dual_write.DUAL_WRITE_ENABLED', False)
    def test_db_write_disabled(self):
        """DB dual-write returns None when disabled."""
        result = dual_write_user_db(SAMPLE_USER)
        assert result is None


# =============================================================================
# dual_write_update_user Tests
# =============================================================================

class TestDualWriteUpdate:
    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.requests.put')
    def test_update_success(self, mock_put):
        """Update dual-write returns response on 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 1, 'name': 'Updated'}
        mock_put.return_value = mock_response

        result = dual_write_update_user(1, {'name': 'Updated'})

        assert result is not None
        assert result['name'] == 'Updated'

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.requests.put')
    def test_update_failure(self, mock_put):
        """Update dual-write returns None on non-200."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Server Error'
        mock_put.return_value = mock_response

        result = dual_write_update_user(1, {'name': 'Updated'})
        assert result is None

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.requests.put')
    def test_update_connection_error(self, mock_put):
        """Update dual-write handles connection error."""
        mock_put.side_effect = requests.exceptions.ConnectionError()
        result = dual_write_update_user(1, {'name': 'Updated'})
        assert result is None

    @patch('core.dual_write.DUAL_WRITE_ENABLED', False)
    def test_update_disabled(self):
        """Update dual-write returns None when disabled."""
        result = dual_write_update_user(1, {'name': 'Updated'})
        assert result is None


# =============================================================================
# dual_write_delete_user Tests
# =============================================================================

class TestDualWriteDelete:
    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.requests.delete')
    def test_delete_success(self, mock_delete):
        """Delete dual-write returns True on 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response

        result = dual_write_delete_user(1)
        assert result is True

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.requests.delete')
    def test_delete_not_found_is_ok(self, mock_delete):
        """Delete dual-write treats 404 as success (idempotent)."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_delete.return_value = mock_response

        result = dual_write_delete_user(999)
        assert result is True  # 404 is acceptable

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.requests.delete')
    def test_delete_server_error(self, mock_delete):
        """Delete dual-write returns False on server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_delete.return_value = mock_response

        result = dual_write_delete_user(1)
        assert result is False

    @patch('core.dual_write.DUAL_WRITE_ENABLED', True)
    @patch('core.dual_write.requests.delete')
    def test_delete_connection_error(self, mock_delete):
        """Delete dual-write returns False on connection error."""
        mock_delete.side_effect = requests.exceptions.ConnectionError()
        result = dual_write_delete_user(1)
        assert result is False

    @patch('core.dual_write.DUAL_WRITE_ENABLED', False)
    def test_delete_disabled(self):
        """Delete dual-write returns False when disabled."""
        result = dual_write_delete_user(1)
        assert result is False
