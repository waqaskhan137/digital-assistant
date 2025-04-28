import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from src.main import app
from shared.models.token import Token


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_oauth_client():
    """Create a mock OAuth client."""
    with patch('src.routes.auth.get_oauth_client') as mock:
        oauth_client = MagicMock()
        mock.return_value = oauth_client
        yield oauth_client


@pytest.fixture
def mock_token_storage():
    """Create a mock token storage."""
    with patch('src.routes.auth.get_token_storage') as mock:
        token_storage = MagicMock()
        mock.return_value = token_storage
        yield token_storage


class TestAuthRoutes:
    """Test cases for the auth routes."""

    def test_login_url(self, client, mock_oauth_client):
        """Test getting the login URL."""
        # Setup
        auth_url = "https://accounts.google.com/o/oauth2/auth?param=value"
        mock_oauth_client.get_authorization_url.return_value = auth_url
        
        # Execute
        response = client.get("/auth/login")
        
        # Verify
        assert response.status_code == 200
        response_json = response.json()
        assert "auth_url" in response_json
        assert response_json["auth_url"] == auth_url
        # The endpoint also returns a 'state' parameter for tracking the user
        assert "state" in response_json
        assert response_json["state"].startswith("test_user_")
        mock_oauth_client.get_authorization_url.assert_called_once()

    def test_callback_success(self, client, mock_oauth_client, mock_token_storage):
        """Test successful OAuth callback."""
        # Setup
        auth_code = "test_auth_code"
        user_id = "test_user_123"
        
        token = Token(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            token_type="Bearer",
            expires_at=datetime.now() + timedelta(hours=1),
            scope="https://www.googleapis.com/auth/gmail.readonly"
        )
        
        mock_oauth_client.exchange_code_for_token.return_value = token
        mock_token_storage.save_token.return_value = True
        
        # Execute
        response = client.get(f"/auth/callback?code={auth_code}&state={user_id}")
        
        # Verify
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["user_id"] == user_id
        mock_oauth_client.exchange_code_for_token.assert_called_once_with(auth_code)
        mock_token_storage.save_token.assert_called_once_with(user_id, token)

    def test_callback_missing_code(self, client):
        """Test callback with missing code parameter."""
        # Execute
        response = client.get("/auth/callback?state=test_user")
        
        # Verify
        assert response.status_code == 400
        assert "detail" in response.json()  # Changed from "error" to "detail"

    def test_callback_token_error(self, client, mock_oauth_client):
        """Test callback with token exchange error."""
        # Setup
        auth_code = "invalid_code"
        mock_oauth_client.exchange_code_for_token.side_effect = Exception("Token error")
        
        # Execute
        response = client.get(f"/auth/callback?code={auth_code}&state=test_user")
        
        # Verify
        assert response.status_code == 500
        assert "detail" in response.json()  # Changed from "error" to "detail"

    def test_token_get_success(self, client, mock_token_storage):
        """Test getting a token successfully."""
        # Setup
        user_id = "test_user_123"
        token = Token(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            token_type="Bearer",
            expires_at=datetime.now() + timedelta(hours=1),
            scope="https://www.googleapis.com/auth/gmail.readonly"
        )
        mock_token_storage.get_token.return_value = token
        
        # Execute
        response = client.get(f"/auth/token/{user_id}")
        
        # Verify
        assert response.status_code == 200
        assert response.json()["access_token"] == token.access_token
        mock_token_storage.get_token.assert_called_once_with(user_id)

    def test_token_not_found(self, client, mock_token_storage):
        """Test getting a non-existent token."""
        # Setup
        user_id = "nonexistent_user"
        mock_token_storage.get_token.return_value = None
        
        # Execute
        response = client.get(f"/auth/token/{user_id}")
        
        # Verify
        assert response.status_code == 404
        assert "detail" in response.json()  # Changed from "error" to "detail"

    @patch('os.getenv')
    def test_token_refresh_success(self, mock_getenv, client, mock_oauth_client, mock_token_storage):
        """Test refreshing a token successfully."""
        # Setup mock environment variables
        mock_getenv.return_value = "dummy_value"  # Make sure all env vars return a value
        
        # Setup
        user_id = "test_user_123"
        old_token = Token(
            access_token="old_access_token",
            refresh_token="test_refresh_token",
            token_type="Bearer",
            expires_at=datetime.now() - timedelta(hours=1),
            scope="https://www.googleapis.com/auth/gmail.readonly"
        )
        new_token = Token(
            access_token="new_access_token",
            refresh_token="test_refresh_token",
            token_type="Bearer",
            expires_at=datetime.now() + timedelta(hours=1),
            scope="https://www.googleapis.com/auth/gmail.readonly"
        )
        
        mock_token_storage.get_token.return_value = old_token
        mock_oauth_client.refresh_token.return_value = new_token
        mock_token_storage.save_token.return_value = True
        
        # Execute
        response = client.post(f"/auth/token/{user_id}/refresh")
        
        # Verify
        assert response.status_code == 200
        assert response.json()["access_token"] == new_token.access_token
        mock_token_storage.get_token.assert_called_once_with(user_id)
        mock_oauth_client.refresh_token.assert_called_once_with(old_token)
        mock_token_storage.save_token.assert_called_once_with(user_id, new_token)

    @patch('os.getenv')
    def test_token_refresh_not_found(self, mock_getenv, client, mock_token_storage):
        """Test refreshing a non-existent token."""
        # Setup mock environment variables
        mock_getenv.return_value = "dummy_value"  # Make sure all env vars return a value
        
        # Setup
        user_id = "nonexistent_user"
        mock_token_storage.get_token.return_value = None
        
        # Execute
        response = client.post(f"/auth/token/{user_id}/refresh")
        
        # Verify
        assert response.status_code == 404
        assert "detail" in response.json()  # Changed from "error" to "detail"

    def test_token_revoke_success(self, client, mock_token_storage):
        """Test revoking a token successfully."""
        # Setup
        user_id = "test_user_123"
        mock_token_storage.delete_token.return_value = True
        
        # Execute
        response = client.delete(f"/auth/token/{user_id}")
        
        # Verify
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_token_storage.delete_token.assert_called_once_with(user_id)

    def test_token_revoke_not_found(self, client, mock_token_storage):
        """Test revoking a non-existent token."""
        # Setup
        user_id = "nonexistent_user"
        mock_token_storage.delete_token.return_value = False
        
        # Execute
        response = client.delete(f"/auth/token/{user_id}")
        
        # Verify
        assert response.status_code == 404
        assert "detail" in response.json()  # Changed from "error" to "detail"