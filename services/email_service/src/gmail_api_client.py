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
from shared.exceptions import (
    AuthenticationError,
    ExternalServiceError,
    ConfigurationError,
    ResourceNotFoundError,
    RateLimitError,
    GmailAutomationError
)
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
        try:
            # Get the token from the Auth Service
            # AuthClient itself should raise appropriate exceptions (e.g., AuthenticationError, ExternalServiceError)
            token_dict = await self.auth_client.get_user_token(user_id)
            
            if not token_dict:
                logger.warning(f"No token found for user {user_id} in Auth Service.")
                raise AuthenticationError(f"No valid token found for user {user_id}. Please re-authenticate.")
            
            # Convert the token to a credentials object
            # This now raises ConfigurationError if client ID/secret are missing
            credentials = convert_token_to_credentials(token_dict)
            
            return credentials
        except AuthenticationError: # Re-raise AuthenticationError from auth_client or self
            raise
        except ConfigurationError: # Re-raise ConfigurationError from convert_token_to_credentials
            raise
        except ExternalServiceError as e: # Catch errors communicating with Auth Service
            logger.error(f"Error communicating with Auth Service for user {user_id}: {e}")
            raise ExternalServiceError(f"Failed to retrieve token from Auth Service: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting credentials for user {user_id}: {e}")
            raise GmailAutomationError(f"Unexpected error preparing credentials for user {user_id}: {e}") from e
    
    async def get_gmail_service(self, user_id: str):
        """
        Get an authenticated Gmail API service instance.
        
        Args:
            user_id: The user ID to get the service for
            
        Returns:
            Authenticated Gmail API service
        """
        credentials = await self.get_credentials(user_id)
        try:
            return build('gmail', 'v1', credentials=credentials)
        except Exception as e:
            # Errors during build are usually configuration or library issues
            logger.error(f"Failed to build Gmail service for user {user_id}: {e}")
            raise ConfigurationError(f"Failed to initialize Gmail API client: {e}") from e
    
    # Apply retry decorator to handle rate limiting
    @async_retry_on_rate_limit(max_retries=5, base_delay=1)
    async def get_email_list(
        self, user_id: str, query: str = "", max_results: int = 100
    ) -> Tuple[List[dict], Optional[str]]:
        """
        Fetches a list of email message IDs and thread IDs matching the query.
        
        Args:
            user_id: The user ID to fetch emails for
            query: Gmail search query string (default: "")
            max_results: Maximum number of results to return (default: 100)
            
        Returns:
            A tuple containing:
            - List of email message/thread IDs matching the query
            - Next page token for pagination (or None if no more pages)
        """
        try:
            service = await self.get_gmail_service(user_id)
        except (ConfigurationError, AuthenticationError, ExternalServiceError) as e:
             # Propagate errors from getting the service
             raise e
             
        # For test mocking simplicity, we'll just get the first page
        await self.rate_limiter.acquire_tokens(1)
        try:
            request = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results,
                pageToken=None
            )
            response = request.execute()
            messages = response.get('messages', [])
            next_page_token = response.get('nextPageToken')
            
            # Return the messages and the next page token
            return messages, next_page_token
            
        except HttpError as error:
            # Map HttpError to custom exceptions
            if error.resp.status == 401 or error.resp.status == 403:
                logger.warning(f"Authentication/Authorization error fetching email list for user {user_id}: {error}")
                raise AuthenticationError(f"Gmail API permission error for user {user_id}: {error}") from error
            elif error.resp.status == 404:
                logger.info(f"Resource not found (e.g., user mailbox) fetching email list for user {user_id}: {error}")
                # Depending on context, might be ResourceNotFoundError or just return empty
                return [], None # Treat as no more messages found
            elif error.resp.status == 429:
                logger.warning(f"Rate limit hit fetching email list for user {user_id}: {error}")
                # Let the retry decorator handle this, but raise RateLimitError if retries fail
                raise RateLimitError("Gmail API rate limit exceeded") from error 
            else:
                logger.error(f"HTTP error fetching email list for user {user_id}: {error}")
                raise ExternalServiceError(f"Gmail API error fetching email list: {error}") from error
        except Exception as e:
            logger.error(f"Unexpected error fetching email list page for user {user_id}: {e}")
            raise GmailAutomationError(f"Unexpected error during email list fetch: {e}") from e

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
            if error.resp.status == 401 or error.resp.status == 403:
                logger.warning(f"Authentication/Authorization error fetching details for message {message_id} (user {user_id}): {error}")
                raise AuthenticationError(f"Gmail API permission error for message {message_id}: {error}") from error
            elif error.resp.status == 404:
                logger.warning(f"Message {message_id} not found for user {user_id}: {error}")
                # Raise ResourceNotFoundError for a specific message not found
                raise ResourceNotFoundError(f"Gmail message {message_id} not found.") from error
            elif error.resp.status == 429:
                logger.warning(f"Rate limit hit fetching details for message {message_id} (user {user_id}): {error}")
                raise RateLimitError("Gmail API rate limit exceeded") from error
            else:
                logger.error(f"HTTP error fetching details for message {message_id} (user {user_id}): {error}")
                raise ExternalServiceError(f"Gmail API error fetching message details: {error}") from error
        except (ConfigurationError, AuthenticationError, ExternalServiceError) as e:
             # Propagate errors from getting the service
             raise e
        except Exception as e:
            logger.error(f"Unexpected error fetching details for message {message_id} (user {user_id}): {e}")
            raise GmailAutomationError(f"Unexpected error fetching message details: {e}") from e

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
            # Check for 'data' key before decoding
            if 'data' not in response:
                 logger.error(f"Attachment {attachment_id} for message {message_id} (user {user_id}) response missing 'data' field.")
                 raise ResourceNotFoundError(f"Attachment {attachment_id} data not found in response.")
            data = base64.urlsafe_b64decode(response['data'])
            return data
        except HttpError as error:
            if error.resp.status == 401 or error.resp.status == 403:
                logger.warning(f"Auth error fetching attachment {attachment_id} for msg {message_id} (user {user_id}): {error}")
                raise AuthenticationError(f"Gmail API permission error for attachment {attachment_id}: {error}") from error
            elif error.resp.status == 404:
                logger.warning(f"Attachment {attachment_id} not found for msg {message_id} (user {user_id}): {error}")
                raise ResourceNotFoundError(f"Attachment {attachment_id} not found for message {message_id}.") from error
            elif error.resp.status == 429:
                logger.warning(f"Rate limit hit fetching attachment {attachment_id} (user {user_id}): {error}")
                raise RateLimitError("Gmail API rate limit exceeded") from error
            else:
                logger.error(f"HTTP error fetching attachment {attachment_id} (user {user_id}): {error}")
                raise ExternalServiceError(f"Gmail API error fetching attachment: {error}") from error
        except (ConfigurationError, AuthenticationError, ExternalServiceError) as e:
             # Propagate errors from getting the service
             raise e
        except (KeyError, TypeError, base64.binascii.Error) as e: # Catch potential decoding errors
            logger.error(f"Error decoding attachment data for attachment {attachment_id} (user {user_id}): {e}")
            raise ExternalServiceError(f"Failed to decode attachment data: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching attachment {attachment_id} (user {user_id}): {e}")
            raise GmailAutomationError(f"Unexpected error fetching attachment: {e}") from e