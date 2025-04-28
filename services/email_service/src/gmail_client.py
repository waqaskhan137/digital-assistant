import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from shared.models.email import EmailMessage
from .rate_limiter import TokenBucketRateLimiter
from .gmail_api_client import GmailApiClient
from .email_normalizer import EmailNormalizer
from .content_extractor import EmailContentExtractor

# Import interfaces
from services.email_service.src.interfaces.email_fetcher import EmailFetcher
from services.email_service.src.interfaces.email_processor import EmailProcessor
from services.email_service.src.interfaces.attachment_handler import AttachmentHandler

# Import implementations
from services.email_service.src.providers.gmail_email_fetcher import GmailEmailFetcher
from services.email_service.src.providers.gmail_email_processor import GmailEmailProcessor
from services.email_service.src.providers.gmail_attachment_handler import GmailAttachmentHandler

logger = logging.getLogger(__name__)

class GmailClient:
    """
    High-level client for working with Gmail API.
    
    This class acts as a facade that coordinates between the interface implementations:
    - EmailFetcher for retrieving emails
    - EmailProcessor for normalizing and processing emails
    - AttachmentHandler for dealing with attachments
    
    Following the Dependency Inversion Principle, this class depends on
    abstractions (interfaces) rather than concrete implementations, making it more
    flexible and easier to test.
    
    Attributes:
        email_fetcher: Component for fetching emails
        email_processor: Component for processing and normalizing emails
        attachment_handler: Component for handling attachments
        batch_size: Number of emails to fetch per request
    """
    
    def __init__(
        self,
        auth_client,
        rate_limiter: TokenBucketRateLimiter,
        batch_size: int = 100,
        max_retries: int = 5,
        retry_delay: int = 1,
        email_fetcher: Optional[EmailFetcher] = None,
        email_processor: Optional[EmailProcessor] = None,
        attachment_handler: Optional[AttachmentHandler] = None
    ):
        """
        Initialize the Gmail client.
        
        Args:
            auth_client: Client for retrieving OAuth tokens
            rate_limiter: Rate limiter for managing API quotas
            batch_size: Number of emails to fetch per request (default: 100)
            max_retries: Maximum number of retries for rate limited requests (default: 5)
            retry_delay: Base delay in seconds between retries (default: 1)
            email_fetcher: Component for fetching emails (optional)
            email_processor: Component for processing emails (optional)
            attachment_handler: Component for handling attachments (optional)
        """
        # Create API client (used by the component implementations)
        api_client = GmailApiClient(
            auth_client=auth_client,
            rate_limiter=rate_limiter,
            batch_size=batch_size,
            max_retries=max_retries,
            retry_delay=retry_delay
        )
        
        # Create content extractor (used by the email processor)
        content_extractor = EmailContentExtractor()
        
        # Initialize components with default implementations if not provided
        self.email_fetcher = email_fetcher or GmailEmailFetcher(api_client)
        self.email_processor = email_processor or GmailEmailProcessor(content_extractor)
        self.attachment_handler = attachment_handler or GmailAttachmentHandler(api_client)
        
        self.batch_size = batch_size
    
    async def get_emails_since(
        self, 
        user_id: str, 
        since_date: datetime,
        max_emails: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get all emails since a given date.
        
        Args:
            user_id: The user ID to fetch emails for
            since_date: Fetch emails since this date
            max_emails: Maximum number of emails to fetch
            
        Returns:
            List of email metadata
        """
        return await self.email_fetcher.get_emails_since(user_id, since_date, max_emails)
    
    async def get_all_emails(
        self,
        user_id: str,
        max_emails: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all emails without date filtering.
        
        This method is useful for testing and verifying that the Gmail API
        connection is working correctly. It returns the most recent emails
        without any date filtering.
        
        Args:
            user_id: The user ID to fetch emails for
            max_emails: Maximum number of emails to fetch
            
        Returns:
            List of email metadata
        """
        return await self.email_fetcher.get_all_emails(user_id, max_emails)
    
    async def normalize_messages(
        self, 
        user_id: str, 
        messages: List[Dict[str, Any]]
    ) -> List[EmailMessage]:
        """
        Convert Gmail API message format to our internal EmailMessage model.
        
        Args:
            user_id: The user ID the messages belong to
            messages: List of Gmail API message objects
            
        Returns:
            List of normalized EmailMessage objects
        """
        # Get full message details for any messages that don't have them
        detailed_messages = []
        
        for message in messages:
            # Get full message details if not already present
            if 'payload' not in message:
                detailed_message = await self.email_fetcher.get_email_details(user_id, message['id'])
                detailed_messages.append(detailed_message)
            else:
                detailed_messages.append(message)
        
        # Use the processor to normalize messages
        return await self.email_processor.normalize_messages(user_id, detailed_messages)
    
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
        return await self.attachment_handler.get_attachment(user_id, message_id, attachment_id)
        
    async def extract_attachment_metadata(
        self,
        message: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract metadata for all attachments in a message.
        
        Args:
            message: Message object
            
        Returns:
            List of dictionaries with attachment metadata
        """
        return await self.attachment_handler.extract_attachment_metadata(message)
    
    async def extract_content(
        self,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract content from a message including body text, HTML, and metadata.
        
        Args:
            message: Message object
            
        Returns:
            Dictionary with extracted content
        """
        return await self.email_processor.extract_content(message)