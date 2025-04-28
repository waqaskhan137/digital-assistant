"""
Client for interacting with the Authentication Service.
This module provides a client for making API calls to the Auth Service.
"""
import os
import logging
import httpx
from typing import Dict, Any, Optional
from shared.utils.token_manager import TokenManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuthClient:
    """
    Client for interacting with the Authentication Service.
    
    This class handles communication with the Auth Service for operations like
    retrieving user tokens.
    
    Attributes:
        base_url: Base URL for the Auth Service
        token_manager: Manager for token caching and expiry
    """
    
    def __init__(self, base_url: Optional[str] = None, buffer_seconds: int = 300):
        """
        Initialize the Auth client.
        
        Args:
            base_url: Base URL for the Auth Service (default: from environment variable)
            buffer_seconds: Buffer time in seconds before expiry to consider a token expired
        """
        self.base_url = base_url or os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
        self.token_manager = TokenManager(buffer_seconds=buffer_seconds)
        logger.info(f"Auth client initialized with base URL: {self.base_url}")
    
    async def get_user_token(self, user_id: str) -> Dict[str, Any]:
        """
        Get the OAuth token for a user.
        
        Checks the token cache first and only makes an HTTP request
        if the token is not cached or has expired.
        
        Args:
            user_id: User identifier (usually email address)
            
        Returns:
            Dictionary containing the access token and related information
            
        Raises:
            Exception: If the token cannot be retrieved
        """
        # Check if we have a valid cached token
        cached_token = self.token_manager.get_cached_token(user_id)
        if cached_token:
            return cached_token
        
        # No valid cached token, fetch from auth service
        url = f"{self.base_url}/auth/token/{user_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Fetching fresh token from Auth Service for user {user_id}")
                response = await client.get(url)
                response.raise_for_status()
                token_data = response.json()
                
                # Cache the token with the token manager
                return self.token_manager.cache_token(user_id, token_data)
        except Exception as e:
            logger.error(f"Error getting token for user {user_id}: {str(e)}")
            raise
    
    async def refresh_token(self, user_id: str) -> Dict[str, Any]:
        """
        Refresh the OAuth token for a user.
        
        Args:
            user_id: User identifier (usually email address)
            
        Returns:
            Dictionary containing the refreshed access token and related information
            
        Raises:
            Exception: If the token cannot be refreshed
        """
        url = f"{self.base_url}/auth/refresh/{user_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Refreshing token for user {user_id}")
                response = await client.post(url)
                response.raise_for_status()
                token_data = response.json()
                
                # Cache the refreshed token with the token manager
                return self.token_manager.cache_token(user_id, token_data)
        except Exception as e:
            logger.error(f"Error refreshing token for user {user_id}: {str(e)}")
            raise
            
    def clear_cache(self, user_id: Optional[str] = None):
        """
        Clear the token cache for a specific user or all users.
        
        Args:
            user_id: User identifier to clear cache for, or None to clear all
        """
        if user_id:
            self.token_manager.clear_token(user_id)
        else:
            self.token_manager.clear_all_tokens()