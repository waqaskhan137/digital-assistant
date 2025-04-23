import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.token_storage import RedisTokenStorage
from shared.models.token import Token


class TestRedisTokenStorage:
    """Test cases for the Redis token storage."""

    def setup_method(self):
        """Set up test fixtures."""
        self.redis_mock = MagicMock()
        with patch('src.token_storage.redis.Redis', return_value=self.redis_mock):
            self.token_storage = RedisTokenStorage(host="localhost", port=6379, db=0)
        
        # Create a sample token for testing
        self.user_id = "test_user_123"
        self.token = Token(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            token_type="Bearer",
            expires_at=datetime.now() + timedelta(hours=1),
            scope="https://www.googleapis.com/auth/gmail.readonly"
        )

    def test_save_token(self):
        """Test saving a token to Redis."""
        # Setup
        self.redis_mock.set.return_value = True
        
        # Execute
        result = self.token_storage.save_token(self.user_id, self.token)
        
        # Verify
        assert result is True
        self.redis_mock.set.assert_called_once()
        # Check that the token was serialized to JSON
        call_args = self.redis_mock.set.call_args[0]
        assert call_args[0] == f"token:{self.user_id}"
        assert "test_access_token" in call_args[1]
        assert "test_refresh_token" in call_args[1]

    def test_get_token(self):
        """Test retrieving a token from Redis."""
        # Setup
        token_json = self.token.model_dump_json()
        self.redis_mock.get.return_value = token_json
        
        # Execute
        retrieved_token = self.token_storage.get_token(self.user_id)
        
        # Verify
        assert retrieved_token is not None
        assert retrieved_token.access_token == self.token.access_token
        assert retrieved_token.refresh_token == self.token.refresh_token
        assert retrieved_token.token_type == self.token.token_type
        self.redis_mock.get.assert_called_once_with(f"token:{self.user_id}")

    def test_get_token_not_found(self):
        """Test retrieving a non-existent token."""
        # Setup
        self.redis_mock.get.return_value = None
        
        # Execute
        retrieved_token = self.token_storage.get_token("nonexistent_user")
        
        # Verify
        assert retrieved_token is None
        self.redis_mock.get.assert_called_once_with("token:nonexistent_user")

    def test_delete_token(self):
        """Test deleting a token from Redis."""
        # Setup
        self.redis_mock.delete.return_value = 1
        
        # Execute
        result = self.token_storage.delete_token(self.user_id)
        
        # Verify
        assert result is True
        self.redis_mock.delete.assert_called_once_with(f"token:{self.user_id}")

    def test_delete_token_not_found(self):
        """Test deleting a non-existent token."""
        # Setup
        self.redis_mock.delete.return_value = 0
        
        # Execute
        result = self.token_storage.delete_token("nonexistent_user")
        
        # Verify
        assert result is False
        self.redis_mock.delete.assert_called_once_with("token:nonexistent_user")