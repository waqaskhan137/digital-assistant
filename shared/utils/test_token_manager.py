import pytest
import time
from unittest.mock import patch
from shared.utils.token_manager import TokenManager

class TestTokenManager:
    """Test cases for the TokenManager class."""
    
    @pytest.fixture
    def token_manager(self):
        """Create a TokenManager instance for testing."""
        return TokenManager(buffer_seconds=300)  # 5-minute buffer
    
    def test_init(self, token_manager):
        """Test TokenManager initialization."""
        assert token_manager.buffer_seconds == 300
        assert token_manager.token_cache == {}
    
    def test_get_cached_token_empty_cache(self, token_manager):
        """Test getting a token from an empty cache."""
        # Empty cache should return None
        result = token_manager.get_cached_token("user123")
        assert result is None
    
    def test_get_cached_token_valid(self, token_manager):
        """Test getting a valid token from the cache."""
        # Add a token to the cache that's valid (expires in 1 hour)
        token_data = {
            "access_token": "valid_token",
            "expiry_time": time.time() + 3600  # 1 hour from now
        }
        token_manager.token_cache["user123"] = token_data
        
        # Should get the cached token
        result = token_manager.get_cached_token("user123")
        assert result == token_data
        assert result["access_token"] == "valid_token"
    
    def test_get_cached_token_expired(self, token_manager):
        """Test getting an expired token from the cache."""
        # Add a token to the cache that's expired or close to expiry
        token_data = {
            "access_token": "expired_token",
            "expiry_time": time.time() + 60  # 1 minute from now (less than buffer)
        }
        token_manager.token_cache["user123"] = token_data
        
        # Should return None for expired token
        result = token_manager.get_cached_token("user123")
        assert result is None
    
    def test_cache_token_with_expires_in(self, token_manager):
        """Test caching a token with expires_in field."""
        # Token data with expires_in
        token_data = {
            "access_token": "new_token",
            "token_type": "Bearer",
            "expires_in": 3600  # 1 hour
        }
        
        with patch('time.time', return_value=1000.0):  # Mock time.time() to return 1000
            result = token_manager.cache_token("user123", token_data)
            
            # Should calculate expiry_time and add to token_data
            assert "expiry_time" in result
            assert result["expiry_time"] == 4600.0  # 1000 + 3600
            
            # Should store in cache
            assert "user123" in token_manager.token_cache
            assert token_manager.token_cache["user123"] == result
    
    def test_cache_token_without_expires_in(self, token_manager):
        """Test caching a token without expires_in field."""
        # Token data without expires_in
        token_data = {
            "access_token": "new_token",
            "token_type": "Bearer"
        }
        
        with patch('time.time', return_value=1000.0):  # Mock time.time() to return 1000
            result = token_manager.cache_token("user123", token_data)
            
            # Should add default expiry_time (30 minutes = 1800 seconds)
            assert "expiry_time" in result
            assert result["expiry_time"] == 2800.0  # 1000 + 1800
    
    def test_is_token_valid(self, token_manager):
        """Test token validity checking."""
        # Valid token (expires in 1 hour)
        valid_token = {
            "access_token": "valid_token",
            "expiry_time": time.time() + 3600
        }
        assert token_manager.is_token_valid(valid_token) is True
        
        # Expired token (expired 1 hour ago)
        expired_token = {
            "access_token": "expired_token",
            "expiry_time": time.time() - 3600
        }
        assert token_manager.is_token_valid(expired_token) is False
        
        # Token without expiry_time
        incomplete_token = {
            "access_token": "incomplete_token"
        }
        assert token_manager.is_token_valid(incomplete_token) is False
    
    def test_clear_token(self, token_manager):
        """Test clearing a specific token from the cache."""
        # Add some tokens to the cache
        token_manager.token_cache = {
            "user1": {"access_token": "token1"},
            "user2": {"access_token": "token2"}
        }
        
        # Clear one token
        token_manager.clear_token("user1")
        
        # Verify the token was cleared
        assert "user1" not in token_manager.token_cache
        assert "user2" in token_manager.token_cache
    
    def test_clear_all_tokens(self, token_manager):
        """Test clearing all tokens from the cache."""
        # Add some tokens to the cache
        token_manager.token_cache = {
            "user1": {"access_token": "token1"},
            "user2": {"access_token": "token2"}
        }
        
        # Clear all tokens
        token_manager.clear_all_tokens()
        
        # Verify all tokens were cleared
        assert len(token_manager.token_cache) == 0