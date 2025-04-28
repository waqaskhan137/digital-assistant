"""
Tests for the retry decorator.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from googleapiclient.errors import HttpError
from shared.utils.retry import async_retry_on_rate_limit

# Mock HttpError for testing
class MockHttpError(HttpError):
    def __init__(self, status=429):
        self.resp = MagicMock()
        self.resp.status = status
        super().__init__(self.resp, b'')

# Create a mock for asyncio.sleep that returns a completed future
async def mock_sleep(*args, **kwargs):
    return None

# Test cases
@pytest.mark.asyncio
async def test_retry_on_rate_limit_success_first_try():
    """Test that the function is called and returns correctly on first try."""
    # Create a mock function that succeeds
    mock_func = MagicMock()
    mock_func.__name__ = "mock_success_func"  # Add __name__ attribute
    mock_func.return_value = asyncio.Future()
    mock_func.return_value.set_result("success")
    
    # Decorate the function
    decorated = async_retry_on_rate_limit()(mock_func)
    
    # Call the decorated function
    result = await decorated("arg1", kwarg1="kwarg1")
    
    # Check that the function was called once with the correct arguments
    mock_func.assert_called_once_with("arg1", kwarg1="kwarg1")
    assert result == "success"

@pytest.mark.asyncio
async def test_retry_on_rate_limit_after_rate_limiting():
    """Test that the function retries after rate limiting."""
    # Create a mock function that fails with 429 once, then succeeds
    mock_func = MagicMock()
    mock_func.__name__ = "mock_retry_func"  # Add __name__ attribute
    
    # First call raises HttpError with 429 status
    first_call = asyncio.Future()
    first_call.set_exception(MockHttpError(status=429))
    
    # Second call succeeds
    second_call = asyncio.Future()
    second_call.set_result("success after retry")
    
    mock_func.side_effect = [first_call, second_call]
    
    # Patch asyncio.sleep to avoid actual waiting
    with patch('asyncio.sleep', mock_sleep):
        # Decorate the function
        decorated = async_retry_on_rate_limit(max_retries=2, base_delay=0.1)(mock_func)
        
        # Call the decorated function
        result = await decorated("arg1", kwarg1="kwarg1")
        
        # Check that the function was called twice
        assert mock_func.call_count == 2
        assert result == "success after retry"

@pytest.mark.asyncio
async def test_retry_on_rate_limit_non_rate_limit_error():
    """Test that non-rate limit errors are not retried."""
    # Create a mock function that fails with 500 error
    mock_func = MagicMock()
    mock_func.__name__ = "mock_error_func"  # Add __name__ attribute
    future = asyncio.Future()
    future.set_exception(MockHttpError(status=500))
    mock_func.return_value = future
    
    # Decorate the function
    decorated = async_retry_on_rate_limit()(mock_func)
    
    # Call the decorated function and expect it to raise
    with pytest.raises(HttpError):
        await decorated("arg1", kwarg1="kwarg1")
    
    # Check that the function was called only once (no retries)
    mock_func.assert_called_once()

@pytest.mark.asyncio
async def test_retry_on_rate_limit_max_retries_exceeded():
    """Test that the function gives up after max retries."""
    # Create a mock function that always fails with 429
    mock_func = MagicMock()
    mock_func.__name__ = "mock_max_retries_func"  # Add __name__ attribute
    
    # All calls raise HttpError with 429 status
    def create_rate_limit_error():
        future = asyncio.Future()
        future.set_exception(MockHttpError(status=429))
        return future
    
    mock_func.side_effect = [create_rate_limit_error() for _ in range(3)]
    
    # Patch asyncio.sleep to avoid actual waiting
    with patch('asyncio.sleep', mock_sleep):
        # Decorate the function with max_retries=3
        decorated = async_retry_on_rate_limit(max_retries=3, base_delay=0.1)(mock_func)
        
        # Call the decorated function and expect it to raise after 3 attempts
        with pytest.raises(HttpError):
            await decorated("arg1", kwarg1="kwarg1")
        
        # Check that the function was called 3 times
        assert mock_func.call_count == 3