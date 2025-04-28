"""
Manages OAuth token caching and expiry logic.
This module provides a reusable token management implementation that can be used
across different services that need to work with OAuth tokens.
"""
import time
import logging
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenManager:
    """
    Manages OAuth token caching and expiry checking.
    
    This class handles token storage, expiry calculations, and cache management,
    providing a clean separation of token management from API communication.
    
    Attributes:
        token_cache: In-memory cache of user tokens
        buffer_seconds: Number of seconds before actual expiry to consider a token expired
    """
    
    def __init__(self, buffer_seconds: int = 300):
        """
        Initialize the token manager.
        
        Args:
            buffer_seconds: Buffer time in seconds before actual expiry to consider a token expired
                          (default: 300 seconds = 5 minutes)
        """
        self.token_cache = {}  # Dictionary to cache tokens by user_id
        self.buffer_seconds = buffer_seconds
        logger.info(f"Token manager initialized with {buffer_seconds}s expiry buffer")
    
    def get_cached_token(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a token from the cache if it exists and is not expired.
        
        Args:
            user_id: User identifier
            
        Returns:
            Cached token dictionary or None if no valid token is cached
        """
        if user_id in self.token_cache:
            cached_token = self.token_cache[user_id]
            current_time = time.time()
            
            # Check if token is still valid (with buffer)
            if cached_token.get('expiry_time', 0) > current_time + self.buffer_seconds:
                logger.info(f"Using cached token for user {user_id}")
                return cached_token
            else:
                logger.info(f"Cached token for user {user_id} is expired or close to expiry")
                return None
        return None
    
    def cache_token(self, user_id: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cache a token with proper expiry time calculation.
        
        Args:
            user_id: User identifier
            token_data: Token data from the auth service
            
        Returns:
            Token data with expiry_time added
        """
        # Calculate absolute expiry time from relative expires_in
        if 'expires_in' in token_data:
            expiry_time = time.time() + token_data['expires_in']
            token_data['expiry_time'] = expiry_time
        else:
            # If no expires_in field, set a default expiry (30 minutes)
            expiry_time = time.time() + 1800
            token_data['expiry_time'] = expiry_time
            logger.warning(f"Token for user {user_id} missing expires_in field, setting default 30-minute expiry")
        
        # Store in cache
        self.token_cache[user_id] = token_data
        logger.info(f"Token cached for user {user_id}, expires in {(expiry_time - time.time())/60:.1f} minutes")
        
        return token_data
    
    def is_token_valid(self, token_data: Dict[str, Any]) -> bool:
        """
        Check if a token is valid and not close to expiry.
        
        Args:
            token_data: Token data with expiry_time
            
        Returns:
            True if the token is valid, False otherwise
        """
        if 'expiry_time' not in token_data:
            return False
            
        current_time = time.time()
        return token_data['expiry_time'] > current_time + self.buffer_seconds
    
    def clear_token(self, user_id: str) -> None:
        """
        Clear a specific user's token from the cache.
        
        Args:
            user_id: User identifier
        """
        if user_id in self.token_cache:
            del self.token_cache[user_id]
            logger.info(f"Cleared token cache for user {user_id}")
    
    def clear_all_tokens(self) -> None:
        """Clear all tokens from the cache."""
        self.token_cache.clear()
        logger.info("Cleared token cache for all users")