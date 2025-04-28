import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .rate_limiter import TokenBucketRateLimiter
from .auth_utils import convert_token_to_credentials
from shared.utils.retry import async_retry_on_rate_limit
from .interfaces.email_fetcher import IEmailFetcher
import base64

logger = logging.getLogger(__name__)

class GmailApiClient(IEmailFetcher):
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
    
    # Apply retry decorator to handle rate limiting
    @async_retry_on_rate_limit(max_retries=5, base_delay=1)
    async def get_email_list(
        self, user_id: str, query: str = "", max_results: int = 100
    ) -> List[dict]:
        """
        Fetches a list of email message IDs and thread IDs matching the query.
        
        Args:
            user_id: The user ID to fetch emails for
            query: Gmail search query string (default: "")
            max_results: Maximum number of results to return (default: 100)
            
        Returns:
            List of email message/thread IDs matching the query.
        """
        messages = []
        page_token = None
        service = await self.get_gmail_service(user_id)
        
        # Loop to handle pagination if needed, up to max_results
        while len(messages) < max_results:
            await self.rate_limiter.acquire_tokens(1)
            try:
                request = service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=min(self.batch_size, max_results - len(messages)),
                    pageToken=page_token
                )
                response = request.execute()
                found_messages = response.get('messages', [])
                messages.extend(found_messages)
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            except HttpError as error:
                logger.error(f"An error occurred fetching email list for user {user_id}: {error}")
                break
            except Exception as e:
                logger.error(f"Unexpected error fetching email list for user {user_id}: {e}")
                break

        return messages[:max_results]

    @async_retry_on_rate_limit(max_retries=5, base_delay=1)
    async def get_email_details(
        self, user_id: str, message_id: str
    ) -> Optional[dict]:
        """
        Fetches the detailed content of a specific email message.
        
        Args:
            user_id: The user ID to fetch the email for
            message_id: The Gmail message ID
            
        Returns:
            Dict containing the full email details or None on error.
        """
        await self.rate_limiter.acquire_tokens(1)
        try:
            service = await self.get_gmail_service(user_id)
            request = service.users().messages().get(
                userId='me', 
                id=message_id,
                format='full'
            )
            return request.execute()
        except HttpError as error:
            logger.error(f"An error occurred fetching details for message {message_id} for user {user_id}: {error}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching details for message {message_id} for user {user_id}: {e}")
            return None

    @async_retry_on_rate_limit(max_retries=5, base_delay=1)
    async def get_emails_batch(
        self, user_id: str, message_ids: List[str]
    ) -> AsyncGenerator[Optional[dict], None]:
        """Fetches details for a batch of email messages asynchronously."""
        tasks = [self.get_email_details(user_id, msg_id) for msg_id in message_ids]
        results = await asyncio.gather(*tasks)
        for result in results:
            yield result

    @async_retry_on_rate_limit(max_retries=5, base_delay=1)
    async def get_attachment(
        self, 
        user_id: str, 
        message_id: str, 
        attachment_id: str
    ) -> Optional[bytes]:
        """
        Fetches the content of a specific attachment.
        
        Args:
            user_id: The user ID to fetch the attachment for
            message_id: The Gmail message ID
            attachment_id: The attachment ID
            
        Returns:
            Bytes content of the attachment or None on error.
        """
        await self.rate_limiter.acquire_tokens(1)
        try:
            service = await self.get_gmail_service(user_id)
            request = service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            )
            response = request.execute()
            data = base64.urlsafe_b64decode(response['data'])
            return data
        except HttpError as error:
            logger.error(f"An error occurred fetching attachment {attachment_id} for message {message_id} for user {user_id}: {error}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching attachment {attachment_id} for message {message_id} for user {user_id}: {e}")
            return None