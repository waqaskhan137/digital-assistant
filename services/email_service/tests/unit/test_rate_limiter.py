import pytest
import time
from unittest.mock import patch, MagicMock, call
from src.rate_limiter import TokenBucketRateLimiter

class TestTokenBucketRateLimiter:
    """Test cases for the TokenBucketRateLimiter class."""
    
    @pytest.fixture
    def mock_redis(self):
        mock_redis_instance = MagicMock()
        yield mock_redis_instance
    
    @pytest.fixture
    def rate_limiter(self, mock_redis):
        return TokenBucketRateLimiter(
            redis_url='redis://localhost:6379/0',
            bucket_name='test-bucket',
            max_tokens=100,
            refill_rate=10,
            refill_time=1,
            redis_client=mock_redis
        )
    
    def test_init(self, rate_limiter, mock_redis):
        """Test initializing the rate limiter."""
        assert rate_limiter.bucket_name == 'test-bucket'
        assert rate_limiter.max_tokens == 100
        assert rate_limiter.refill_rate == 10
        assert rate_limiter.refill_time == 1
        assert rate_limiter.redis == mock_redis
        
    @pytest.mark.asyncio
    async def test_acquire_tokens_success(self, rate_limiter, mock_redis):
        """Test successfully acquiring tokens."""
        # Setup initial state with a function-based side_effect
        mock_redis.set.return_value = True
        mock_redis.set.reset_mock()
        
        # Use a function for side_effect to handle multiple calls properly
        def mock_get_side_effect(key):
            if key == f'{rate_limiter.bucket_name}:tokens':
                return '100'
            elif key == f'{rate_limiter.bucket_name}:last_refill':
                return str(int(time.time()))
            return None
            
        mock_redis.get.side_effect = mock_get_side_effect
        
        # Should be able to acquire tokens on first try
        result = await rate_limiter.acquire_tokens(50)
        assert result is True
        
        # Verify Redis calls for consuming tokens
        mock_redis.set.assert_called_with(f'{rate_limiter.bucket_name}:tokens', '50', ex=None)
    
    @pytest.mark.asyncio
    async def test_acquire_tokens_insufficient(self, rate_limiter, mock_redis):
        """Test when there are insufficient tokens."""
        # Setup initial state with a function-based side_effect
        mock_redis.set.reset_mock()
        
        # Use a function for side_effect to handle multiple calls properly
        def mock_get_side_effect(key):
            if key == f'{rate_limiter.bucket_name}:tokens':
                return '30'
            elif key == f'{rate_limiter.bucket_name}:last_refill':
                return str(int(time.time()))
            return None
            
        mock_redis.get.side_effect = mock_get_side_effect
        
        # Trying to acquire 50 tokens should fail
        result = await rate_limiter.acquire_tokens(50)
        assert result is False
        
        # Verify no tokens were consumed (no set call for tokens)
        assert mock_redis.set.call_count == 0
    
    @pytest.mark.asyncio
    async def test_refill_tokens(self, rate_limiter, mock_redis):
        """Test token refill mechanism."""
        # Setup initial state for refill test
        current_time = int(time.time())
        last_refill_time = current_time - 10  # 10 seconds ago
        
        # Reset side_effect and return_value to avoid StopIteration
        mock_redis.get.side_effect = None
        mock_redis.set.reset_mock()
        
        # Setup get calls with different returns for different keys
        def mock_get_side_effect(key):
            if key == f'{rate_limiter.bucket_name}:tokens':
                return '50'
            elif key == f'{rate_limiter.bucket_name}:last_refill':
                return str(last_refill_time)
            return None
            
        mock_redis.get.side_effect = mock_get_side_effect
        mock_redis.set.return_value = True
        
        # Call refill_tokens
        await rate_limiter._refill_tokens()
        
        # Should add 10 tokens/second * 10 seconds = 100 tokens
        # But max is 100, so should be 100
        mock_redis.set.assert_any_call(
            f'{rate_limiter.bucket_name}:tokens', 
            '100',  # Refilled to max
            ex=None
        )
    
    @pytest.mark.asyncio
    async def test_reset_bucket(self, rate_limiter, mock_redis):
        """Test resetting the token bucket."""
        # Setup for testing reset
        mock_redis.set.return_value = True
        mock_redis.set.reset_mock()  # Clear any previous calls
        
        # Freeze time for consistent test
        with patch('time.time', return_value=12345):
            await rate_limiter.reset_bucket()
            
            # Verify both Redis calls happened with correct parameters
            expected_calls = [
                call(f'{rate_limiter.bucket_name}:tokens', '100', ex=None),
                call(f'{rate_limiter.bucket_name}:last_refill', '12345', ex=None)
            ]
            mock_redis.set.assert_has_calls(expected_calls, any_order=True)