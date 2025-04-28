"""
Retry decorator for handling API rate limiting and transient errors.

This module provides a decorator that can be applied to functions
to implement retry logic with exponential backoff.
"""
import asyncio
import functools
import logging
from typing import Any, Callable, Optional, Type, TypeVar, cast
from googleapiclient.errors import HttpError

# Set up logging
logger = logging.getLogger(__name__)

# Type variable for the decorated function
F = TypeVar('F', bound=Callable[..., Any])

def async_retry_on_rate_limit(
    max_retries: int = 5,
    base_delay: int = 1,
    rate_limit_codes: tuple = (429,),
    exception_types: tuple = (HttpError,)
) -> Callable[[F], F]:
    """
    Decorator for retrying async functions when rate limited.
    
    This decorator implements retry logic with exponential backoff
    for async functions that might encounter rate limiting.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Base delay in seconds between retries (default: 1)
        rate_limit_codes: HTTP status codes to retry on (default: 429)
        exception_types: Exception types to catch and potentially retry
                         (default: HttpError)
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_retries):
                try:
                    # Attempt to call the function
                    return await func(*args, **kwargs)
                except exception_types as error:
                    # For HttpError, check if it's a rate limit response
                    if isinstance(error, HttpError):
                        status = error.resp.status
                        is_rate_limit = status in rate_limit_codes
                    else:
                        # For other exceptions, we can't determine if it's rate-limiting
                        # so we'll just retry as per the decorator configuration
                        is_rate_limit = True
                    
                    # If it's the last attempt or not a rate limit error, re-raise
                    if attempt >= max_retries - 1 or not is_rate_limit:
                        logger.error(f"Error in {func.__name__}: {error}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    retry_delay = base_delay * (2 ** attempt)
                    
                    # Log and wait before retrying
                    logger.warning(
                        f"Request rate limited. Retrying {func.__name__} "
                        f"in {retry_delay} seconds (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_delay)
            
            # This should never be reached, but added for completeness
            raise Exception(f"Failed after {max_retries} attempts")
        
        return cast(F, wrapper)
    
    return decorator