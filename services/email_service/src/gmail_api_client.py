import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .rate_limiter import TokenBucketRateLimiter
from .auth_utils import convert_token_to_credentials
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
        credentials = await self.get_credentials(user_id)
        service = build('gmail', 'v1', credentials=credentials)
        
        # Build request
        request = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=self.batch_size,
            pageToken=page_token if page_token else None
        )
        
        # Execute request with retries
        for attempt in range(self.max_retries):
            try:
                response = request.execute()
                messages = response.get('messages', [])
                next_page_token = response.get('nextPageToken')
                
                return messages, next_page_token
                
            except HttpError as error:
                # Check if rate limited (429)
                if error.resp.status == 429 and attempt < self.max_retries - 1:
                    retry_delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Retrying in {retry_delay} seconds.")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"Error fetching emails: {error}")
                    raise
        
        # If we reach here, all retries failed
        raise Exception(f"Failed to fetch emails after {self.max_retries} attempts")
    
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
        credentials = await self.get_credentials(user_id)
        service = build('gmail', 'v1', credentials=credentials)
        
        # Build request
        request = service.users().messages().get(
            userId='me', 
            id=message_id,
            format='full'  # Get the full message
        )
        
        # Execute request with retries
        for attempt in range(self.max_retries):
            try:
                response = request.execute()
                return response
                
            except HttpError as error:
                # Check if rate limited (429)
                if error.resp.status == 429 and attempt < self.max_retries - 1:
                    retry_delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Retrying in {retry_delay} seconds.")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"Error fetching email details: {error}")
                    raise
        
        # If we reach here, all retries failed
        raise Exception(f"Failed to fetch email details after {self.max_retries} attempts")
    
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
        credentials = await self.get_credentials(user_id)
        service = build('gmail', 'v1', credentials=credentials)
        
        # Build request
        request = service.users().messages().attachments().get(
            userId='me',
            messageId=message_id,
            id=attachment_id
        )
        
        # Execute request with retries
        for attempt in range(self.max_retries):
            try:
                response = request.execute()
                
                # Decode data
                data = base64.urlsafe_b64decode(response['data'])
                
                return {
                    'data': data,
                    'size': response.get('size', 0),
                    'attachment_id': attachment_id
                }
                
            except HttpError as error:
                # Check if rate limited (429)
                if error.resp.status == 429 and attempt < self.max_retries - 1:
                    retry_delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Retrying in {retry_delay} seconds.")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"Error fetching attachment: {error}")
                    raise
        
        # If we reach here, all retries failed
        raise Exception(f"Failed to fetch attachment after {self.max_retries} attempts")