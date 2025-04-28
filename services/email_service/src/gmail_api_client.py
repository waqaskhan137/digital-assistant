import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .rate_limiter import TokenBucketRateLimiter
from .auth_utils import convert_token_to_credentials
from shared.utils.retry import async_retry_on_rate_limit
import base64

logger = logging.getLogger(__name__)

class GmailApiClient:
    """
    Client for direct interactions with the Gmail API.
    
    This class handles all low-level API calls to the Gmail API, including
    authentication, rate limiting, and API error handling.
    """
    
    def __init__(
        self,
        auth_client,
        rate_limiter: TokenBucketRateLimiter,
        batch_size: int = 100,
        max_retries: int = 5,
        retry_delay: int = 1
    ):
        """
        Initialize the Gmail API client.
        
        Args:
            auth_client: Client for retrieving OAuth tokens
            rate_limiter: Rate limiter for managing API quotas
            batch_size: Number of emails to fetch per request (default: 100)
            max_retries: Maximum number of retries for rate limited requests (default: 5)
            retry_delay: Base delay in seconds between retries (default: 1)
        """
        self.auth_client = auth_client
        self.rate_limiter = rate_limiter
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def get_credentials(self, user_id: str):
        """
        Get Google API credentials for a user.
        
        This method retrieves the OAuth token from the Auth Service and converts
        it to a Google credentials object that can be used with the Gmail API.
        
        Args:
            user_id: The user ID to get credentials for
            
        Returns:
            Google OAuth2 Credentials object
        """
        # Get the token from the Auth Service
        token_dict = await self.auth_client.get_user_token(user_id)
        
        # Convert the token to a credentials object
        credentials = convert_token_to_credentials(token_dict)
        
        return credentials
    
    async def get_gmail_service(self, user_id: str):
        """
        Get an authenticated Gmail API service instance.
        
        Args:
            user_id: The user ID to get the service for
            
        Returns:
            Authenticated Gmail API service
        """
        credentials = await self.get_credentials(user_id)
        return build('gmail', 'v1', credentials=credentials)
    
    async def execute_request_with_rate_limiting(self, request):
        """
        Execute a Gmail API request with rate limiting.
        
        This is a helper method to abstract the common pattern of
        acquiring rate limit tokens before executing a request.
        
        Args:
            request: The Gmail API request object to execute
            
        Returns:
            The API response
        """
        # Acquire rate limit tokens
        await self.rate_limiter.acquire_tokens(1)
        
        # Execute the request (the retry logic is handled by the decorator)
        return request.execute()
    
    # Apply retry decorator to handle rate limiting
    @async_retry_on_rate_limit(max_retries=5, base_delay=1)
    async def get_email_list(
        self, user_id: str, query: str = "", page_token: str = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Get a list of emails for a user.
        
        Args:
            user_id: The user ID to fetch emails for
            query: Gmail search query string (default: "")
            page_token: Page token for pagination (default: None)
            
        Returns:
            Tuple containing:
                - List of email metadata
                - Next page token (None if no more pages)
        """
        # Acquire rate limit tokens
        await self.rate_limiter.acquire_tokens(1)
        
        # Get Gmail API service
        service = await self.get_gmail_service(user_id)
        
        # Build request
        request = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=self.batch_size,
            pageToken=page_token if page_token else None
        )
        
        # Execute request (retry logic handled by decorator)
        response = request.execute()
        messages = response.get('messages', [])
        next_page_token = response.get('nextPageToken')
        
        return messages, next_page_token
    
    @async_retry_on_rate_limit(max_retries=5, base_delay=1)
    async def get_email_details(
        self, user_id: str, message_id: str
    ) -> Dict[str, Any]:
        """
        Get full details for a specific email.
        
        Args:
            user_id: The user ID to fetch the email for
            message_id: The Gmail message ID
            
        Returns:
            Dict containing the full email details
        """
        # Acquire rate limit tokens
        await self.rate_limiter.acquire_tokens(1)
        
        # Get Gmail API service
        service = await self.get_gmail_service(user_id)
        
        # Build request
        request = service.users().messages().get(
            userId='me', 
            id=message_id,
            format='full'  # Get the full message
        )
        
        # Execute request (retry logic handled by decorator)
        return request.execute()
    
    @async_retry_on_rate_limit(max_retries=5, base_delay=1)
    async def get_attachment(
        self, 
        user_id: str, 
        message_id: str, 
        attachment_id: str
    ) -> Dict[str, Any]:
        """
        Get a specific attachment from an email.
        
        Args:
            user_id: The user ID to fetch the attachment for
            message_id: The Gmail message ID
            attachment_id: The attachment ID
            
        Returns:
            Dict containing the attachment data and metadata
        """
        # Acquire rate limit tokens
        await self.rate_limiter.acquire_tokens(1)
        
        # Get Gmail API service
        service = await self.get_gmail_service(user_id)
        
        # Build request
        request = service.users().messages().attachments().get(
            userId='me',
            messageId=message_id,
            id=attachment_id
        )
        
        # Execute request (retry logic handled by decorator)
        response = request.execute()
        
        # Decode data
        data = base64.urlsafe_b64decode(response['data'])
        
        return {
            'data': data,
            'size': response.get('size', 0),
            'attachment_id': attachment_id
        }