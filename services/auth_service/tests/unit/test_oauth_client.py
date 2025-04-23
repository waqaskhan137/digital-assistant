import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.oauth_client import OAuthClient
from shared.models.token import Token


class TestOAuthClient:
    """Test cases for the OAuth client."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client_id = "test_client_id"
        self.client_secret = "test_client_secret"
        self.redirect_uri = "http://localhost:8000/auth/callback"
        self.client = OAuthClient(self.client_id, self.client_secret, self.redirect_uri)

    def test_initialization(self):
        """Test OAuth client initialization with correct parameters."""
        assert self.client.client_id == self.client_id
        assert self.client.client_secret == self.client_secret
        assert self.client.redirect_uri == self.redirect_uri
        assert "gmail.readonly" in " ".join(self.client.scopes)
        assert "gmail.modify" in " ".join(self.client.scopes)
        assert "gmail.labels" in " ".join(self.client.scopes)

    def test_get_authorization_url(self):
        """Test generation of authorization URL."""
        auth_url = self.client.get_authorization_url()
        
        assert "accounts.google.com/o/oauth2/auth" in auth_url
        assert f"client_id={self.client_id}" in auth_url
        assert "redirect_uri=" in auth_url
        assert "scope=" in auth_url
        assert "response_type=code" in auth_url
        assert "access_type=offline" in auth_url

    @patch('src.oauth_client.requests.post')
    def test_exchange_code_for_token(self, mock_post):
        """Test exchanging authorization code for tokens."""
        # Setup mock response
        expires_in = 3600
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_type": "Bearer",
            "expires_in": expires_in,
            "scope": "https://www.googleapis.com/auth/gmail.readonly"
        }
        mock_post.return_value = mock_response
        
        # Call method
        token = self.client.exchange_code_for_token("test_auth_code")
        
        # Verify
        assert isinstance(token, Token)
        assert token.access_token == "test_access_token"
        assert token.refresh_token == "test_refresh_token"
        assert token.token_type == "Bearer"
        assert token.scope == "https://www.googleapis.com/auth/gmail.readonly"
        assert token.expires_at > datetime.now()
        assert token.expires_at < datetime.now() + timedelta(seconds=expires_in + 10)
        
        # Verify POST request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]['data']
        assert call_args['client_id'] == self.client_id
        assert call_args['client_secret'] == self.client_secret
        assert call_args['code'] == "test_auth_code"
        assert call_args['redirect_uri'] == self.redirect_uri
        assert call_args['grant_type'] == "authorization_code"

    @patch('src.oauth_client.requests.post')
    def test_refresh_token(self, mock_post):
        """Test refreshing an expired token."""
        # Setup mock response
        expires_in = 3600
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "token_type": "Bearer",
            "expires_in": expires_in,
            "scope": "https://www.googleapis.com/auth/gmail.readonly"
        }
        mock_post.return_value = mock_response
        
        # Create expired token
        expired_token = Token(
            access_token="old_access_token",
            refresh_token="test_refresh_token",
            token_type="Bearer",
            expires_at=datetime.now() - timedelta(hours=1),
            scope="https://www.googleapis.com/auth/gmail.readonly"
        )
        
        # Call method
        new_token = self.client.refresh_token(expired_token)
        
        # Verify
        assert isinstance(new_token, Token)
        assert new_token.access_token == "new_access_token"
        assert new_token.refresh_token == "test_refresh_token"  # Should preserve refresh token
        assert new_token.token_type == "Bearer"
        assert new_token.scope == "https://www.googleapis.com/auth/gmail.readonly"
        assert new_token.expires_at > datetime.now()
        
        # Verify POST request
        mock_post.assert_called_once()
        call_args = mock_post.call_args[1]['data']
        assert call_args['client_id'] == self.client_id
        assert call_args['client_secret'] == self.client_secret
        assert call_args['refresh_token'] == expired_token.refresh_token
        assert call_args['grant_type'] == "refresh_token"