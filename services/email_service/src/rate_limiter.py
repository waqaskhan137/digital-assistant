import time
import logging
from redis import Redis
from typing import Optional, Union

logger = logging.getLogger(__name__)

class TokenBucketRateLimiter:
    """
    A token bucket algorithm implementation for rate limiting backed by Redis.
    
    This class manages rate limiting for Gmail API requests, ensuring we stay within 
    quota limits. Each request consumes tokens from a bucket that refills over time.
    
    Attributes:
        redis: Redis client for storing token bucket state
        bucket_name: Unique identifier for this rate limiter bucket
        max_tokens: Maximum number of tokens the bucket can hold
        refill_rate: Number of tokens added per refill_time
        refill_time: Time period in seconds for token refill
    """

    def __init__(
        self, 
        redis_url: str, 
        bucket_name: str, 
        max_tokens: int = 200, 
        refill_rate: int = 200, 
        refill_time: int = 1,
        redis_client: Optional[Redis] = None
    ):
        """
        Initialize the token bucket rate limiter.
        
        Args:
            redis_url: Redis connection URL
            bucket_name: Unique name for this rate limiter bucket
            max_tokens: Maximum tokens the bucket can hold (default: 200)
            refill_rate: Number of tokens added per refill_time (default: 200)
            refill_time: Time period in seconds for token refill (default: 1)
            redis_client: Optional Redis client for testing
        """
        # Allow injection of Redis client for testing
        self.redis = redis_client if redis_client is not None else Redis.from_url(redis_url)
        self.bucket_name = bucket_name
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.refill_time = refill_time
        
    async def acquire_tokens(self, tokens_to_consume: int) -> bool:
        """
        Attempt to acquire tokens from the bucket.
        
        Args:
            tokens_to_consume: Number of tokens to consume
            
        Returns:
            bool: True if tokens were successfully acquired, False otherwise
        """
        # Refill tokens based on time elapsed
        await self._refill_tokens()
        
        # Get current token count
        current_tokens = await self._get_current_tokens()
        
        # Check if enough tokens are available
        if current_tokens < tokens_to_consume:
            logger.warning(
                f"Rate limit hit. Requested {tokens_to_consume} tokens, but only {current_tokens} available"
            )
            return False
        
        # Consume tokens
        new_tokens = current_tokens - tokens_to_consume
        self.redis.set(f"{self.bucket_name}:tokens", str(new_tokens), ex=None)
        
        logger.debug(
            f"Acquired {tokens_to_consume} tokens. {new_tokens} tokens remaining."
        )
        return True
    
    async def _get_current_tokens(self) -> int:
        """
        Get current token count from Redis.
        
        Returns:
            int: Current token count, or max_tokens if not set
        """
        tokens = self.redis.get(f"{self.bucket_name}:tokens")
        if tokens is None:
            # Initialize bucket if not exists
            await self.reset_bucket()
            return self.max_tokens
        return int(tokens)
    
    async def _refill_tokens(self) -> None:
        """Refill tokens based on time elapsed since last refill."""
        # Get last refill time
        last_refill_str = self.redis.get(f"{self.bucket_name}:last_refill")
        if last_refill_str is None:
            # Initialize if not exists
            await self.reset_bucket()
            return
        
        last_refill = int(last_refill_str)
        current_time = int(time.time())
        time_passed = current_time - last_refill
        
        # Only refill if enough time has passed
        if time_passed < self.refill_time:
            return
        
        # Calculate tokens to add
        periods_passed = time_passed // self.refill_time
        tokens_to_add = periods_passed * self.refill_rate
        
        if tokens_to_add <= 0:
            return
        
        # Add tokens up to max_tokens
        current_tokens = await self._get_current_tokens()
        new_tokens = min(current_tokens + tokens_to_add, self.max_tokens)
        
        # Update token count and last refill time
        self.redis.set(f"{self.bucket_name}:tokens", str(new_tokens), ex=None)
        self.redis.set(f"{self.bucket_name}:last_refill", str(current_time), ex=None)
        
        logger.debug(
            f"Refilled {tokens_to_add} tokens. New total: {new_tokens}/{self.max_tokens}"
        )
    
    async def reset_bucket(self) -> None:
        """Reset the token bucket to its initial state."""
        current_time = int(time.time())
        self.redis.set(f"{self.bucket_name}:tokens", str(self.max_tokens), ex=None)
        self.redis.set(f"{self.bucket_name}:last_refill", str(current_time), ex=None)
        logger.debug(f"Reset token bucket '{self.bucket_name}' to {self.max_tokens} tokens")