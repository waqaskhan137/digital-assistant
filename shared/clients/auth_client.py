"""
Client for interacting with the Authentication Service.
This module provides a client for making API calls to the Auth Service.
"""
import os
import time
import httpx
import logging
from typing import Dict, Any, Optional

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
        token_cache: In-memory cache of user tokens
    """
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the Auth client.
        
        Args:
            base_url: Base URL for the Auth Service (default: from environment variable)
        """
        self.base_url = base_url or os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
        self.token_cache = {}  # Dictionary to cache tokens by user_id
        logger.info(f"Auth client initialized with base URL: {self.base_url}")
    
    async def get_user_token(self, user_id: str) -> Dict[str, Any]:
        """
        Get the OAuth token for a user.
        
        Checks the in-memory cache first and only makes an HTTP request
        if the token is not cached or has expired.
        
        Args:
            user_id: User identifier (usually email address)
            
        Returns:
            Dictionary containing the access token and related information
            
        Raises:
            Exception: If the token cannot be retrieved
        """
        # Check if we have a valid cached token
        if user_id in self.token_cache:
            cached_token = self.token_cache[user_id]
            current_time = time.time()
            
            # Check if token is still valid (with 5-minute buffer)
            if cached_token.get('expiry_time', 0) > current_time + 300:
                logger.info(f"Using cached token for user {user_id}")
                return cached_token
            else:
                logger.info(f"Cached token for user {user_id} is expired or close to expiry")
        
        # No valid cached token, fetch from auth service
        url = f"{self.base_url}/auth/token/{user_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Fetching fresh token from Auth Service for user {user_id}")
                response = await client.get(url)
                response.raise_for_status()
                token_data = response.json()
                
                # Cache the token with expiry time
                if 'expires_in' in token_data:
                    # Calculate absolute expiry time from relative expires_in
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
                
                # Update cache with new token
                if 'expires_in' in token_data:
                    # Calculate absolute expiry time
                    expiry_time = time.time() + token_data['expires_in']
                    token_data['expiry_time'] = expiry_time
                else:
                    # If no expires_in field, set a default expiry (30 minutes)
                    expiry_time = time.time() + 1800
                    token_data['expiry_time'] = expiry_time
                    logger.warning(f"Refreshed token for user {user_id} missing expires_in field, setting default 30-minute expiry")
                
                # Store in cache
                self.token_cache[user_id] = token_data
                logger.info(f"Refreshed token cached for user {user_id}, expires in {(expiry_time - time.time())/60:.1f} minutes")
                
                return token_data
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
            if user_id in self.token_cache:
                del self.token_cache[user_id]
                logger.info(f"Cleared token cache for user {user_id}")
        else:
            self.token_cache.clear()
            logger.info("Cleared token cache for all users")