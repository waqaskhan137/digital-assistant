import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from shared.models.email import EmailMessage
from .rate_limiter import TokenBucketRateLimiter
from .gmail_api_client import GmailApiClient
from .email_normalizer import EmailNormalizer
from .content_extractor import EmailContentExtractor

logger = logging.getLogger(__name__)

class GmailClient:
    """
    High-level client for working with Gmail API.
    
    This class acts as a facade that coordinates between the GmailApiClient for
    raw API interactions, the EmailNormalizer for message format conversion, and
    the EmailContentExtractor for content processing.
    
    Attributes:
        api_client: Client for raw Gmail API interactions
        normalizer: Converter for Gmail format to internal format
        batch_size: Number of emails to fetch per request
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
        Initialize the Gmail client.
        
        Args:
            auth_client: Client for retrieving OAuth tokens
            rate_limiter: Rate limiter for managing API quotas
            batch_size: Number of emails to fetch per request (default: 100)
            max_retries: Maximum number of retries for rate limited requests (default: 5)
            retry_delay: Base delay in seconds between retries (default: 1)
        """
        # Create component instances
        self.content_extractor = EmailContentExtractor()
        self.api_client = GmailApiClient(
            auth_client=auth_client,
            rate_limiter=rate_limiter,
            batch_size=batch_size,
            max_retries=max_retries,
            retry_delay=retry_delay
        )
        self.normalizer = EmailNormalizer(content_extractor=self.content_extractor)
        self.batch_size = batch_size
    
    async def _fetch_emails_with_query(
        self,
        user_id: str,
        query: str,
        max_emails: int
    ) -> List[Dict[str, Any]]:
        """
        Helper method to fetch emails using a specific query with pagination.
        
        This reduces duplication between different email fetching methods.
        
        Args:
            user_id: The user ID to fetch emails for
            query: Gmail search query string
            max_emails: Maximum number of emails to fetch
            
        Returns:
            List of email metadata
        """
        all_emails = []
        page_token = None
        
        while True:
            # Check if we've reached the maximum
            if len(all_emails) >= max_emails:
                logger.info(f"Reached maximum of {max_emails} emails")
                break
                
            # Get next page of emails
            emails, page_token = await self.api_client.get_email_list(
                user_id=user_id,
                query=query,
                page_token=page_token
            )
            
            # Log the response for debugging
            logger.info(f"Gmail API response: found {len(emails)} emails")
            
            # Add to result list
            all_emails.extend(emails)
            
            # Break if no more pages
            if not page_token:
                break
                
            # Break if we'd exceed the maximum on the next page
            if len(all_emails) + self.batch_size > max_emails:
                logger.info(f"Would exceed maximum emails on next page, stopping.")
                break
                
        return all_emails
    
    async def get_emails_since(
        self, 
        user_id: str, 
        since_date: datetime,
        include_labels: Optional[List[str]] = None,
        max_emails: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get all emails since a given date.
        
        Args:
            user_id: The user ID to fetch emails for
            since_date: Fetch emails since this date
            include_labels: This parameter is now ignored (kept for backwards compatibility)
            max_emails: Maximum number of emails to fetch
            
        Returns:
            List of email metadata
        """
        # Build Gmail search query
        days_ago = (datetime.now() - since_date).days
        
        # Construct primary query for date filtering
        query = f"newer_than:{max(1, days_ago)}d"
        logger.info(f"Gmail search query: {query}")
        
        # Fetch emails using the query
        all_emails = await self._fetch_emails_with_query(user_id, query, max_emails)
        
        # If no emails found, use a fallback query
        if not all_emails:
            logger.warning("No emails found with the date-based query, trying fallback query")
            fallback_query = "in:anywhere"
            logger.info(f"Fallback Gmail search query: {fallback_query}")
            
            all_emails = await self._fetch_emails_with_query(user_id, fallback_query, max_emails)
        
        logger.info(f"Retrieved {len(all_emails)} emails since approximately {since_date}")
        return all_emails
    
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
        logger.info(f"Fetching up to {max_emails} most recent emails without date filtering")
        
        # Empty query returns all emails, sorted by most recent first
        return await self._fetch_emails_with_query(user_id, "", max_emails)
    
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
                detailed_message = await self.api_client.get_email_details(user_id, message['id'])
                detailed_messages.append(detailed_message)
            else:
                detailed_messages.append(message)
        
        # Use the normalizer to convert messages to EmailMessage objects
        normalized_messages = self.normalizer.normalize_messages(user_id, detailed_messages)
        
        return normalized_messages
    
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
        return await self.api_client.get_attachment(user_id, message_id, attachment_id)