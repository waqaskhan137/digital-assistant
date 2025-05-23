"""
Client for interacting with the Authentication Service.
This module provides a client for making API calls to the Auth Service.
"""
import os
import logging
import httpx
from typing import Dict, Any, Optional, Callable
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
    
    async def _fetch_and_cache_token(
        self, 
        user_id: str, 
        endpoint: str, 
        http_method: str = "get",
        log_message: str = "Fetching token"
    ) -> Dict[str, Any]:
        """
        Helper method to fetch and cache a token from the Auth Service.
        
        This centralizes the logic for getting tokens and caching them,
        reducing duplication between get_user_token and refresh_token.
        
        Args:
            user_id: User identifier
            endpoint: API endpoint to call
            http_method: HTTP method to use (default: "get")
            log_message: Message to log before making the request
            
        Returns:
            Dictionary containing the token data
            
        Raises:
            Exception: If the token cannot be retrieved
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"{log_message} for user {user_id}")
                
                # Dynamically choose the HTTP method
                if (http_method.lower() == "post"):
                    response = await client.post(url)
                else:
                    response = await client.get(url)
                
                response.raise_for_status()
                token_data = response.json()
                
                # Cache the token and return it
                return self.token_manager.cache_token(user_id, token_data)
        except Exception as e:
            logger.error(f"Error fetching token for user {user_id}: {str(e)}")
            raise
    
    def get_user_token(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Pure retrieval of the OAuth token for a user from the cache.
        No side effects.
        
        Args:
            user_id: User identifier (usually email address)
            
        Returns:
            Cached token dictionary or None if not present/expired
        """
        return self.token_manager.get_cached_token(user_id)

    async def get_and_cache_user_token(self, user_id: str) -> Dict[str, Any]:
        """
        Get the OAuth token for a user, fetching and caching if not present or expired.
        Side effect: may update the cache.
        
        Args:
            user_id: User identifier (usually email address)
            
        Returns:
            Dictionary containing the access token and related information
            
        Raises:
            Exception: If the token cannot be retrieved
        """
        cached_token = self.token_manager.get_cached_token(user_id)
        if cached_token:
            return cached_token
        
        # No valid cached token, fetch from auth service
        return await self._fetch_and_cache_token(
            user_id,
            f"/auth/token/{user_id}",
            "get",
            "Fetching fresh token from Auth Service"
        )
    
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
        return await self._fetch_and_cache_token(
            user_id,
            f"/auth/refresh/{user_id}",
            "post",
            "Refreshing token"
        )
            
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