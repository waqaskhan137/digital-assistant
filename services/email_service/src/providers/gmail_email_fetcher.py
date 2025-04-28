"""
Gmail Email Fetcher

This module implements the EmailFetcher interface for Gmail.
It encapsulates all Gmail-specific logic for fetching emails to provide
a clean separation of concerns.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from services.email_service.src.interfaces.email_fetcher import EmailFetcher
from services.email_service.src.gmail_api_client import GmailApiClient

logger = logging.getLogger(__name__)

class GmailEmailFetcher(EmailFetcher):
    """
    Gmail-specific implementation of the EmailFetcher interface.
    
    This class follows the Interface Segregation Principle by implementing only
    methods related to email fetching, not processing or normalizing them.
    """
    
    def __init__(self, api_client: GmailApiClient):
        """
        Initialize with a Gmail API client.
        
        Args:
            api_client: Gmail API client for making API requests
        """
        self.api_client = api_client
    
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
            List of email metadata in Gmail-specific format
        """
        logger.info(f"Fetching emails since {since_date} for user {user_id}")
        
        # Format date for Gmail query
        date_str = since_date.strftime("%Y/%m/%d")
        query = f"after:{date_str}"
        
        try:
            # Fetch messages matching the query
            messages = await self._fetch_emails_with_query(user_id, query, max_emails)
            logger.info(f"Fetched {len(messages)} emails since {date_str} for user {user_id}")
            return messages
        except Exception as e:
            logger.error(f"Error fetching emails since {date_str} for user {user_id}: {str(e)}")
            return []
    
    async def get_all_emails(
        self,
        user_id: str,
        max_emails: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all emails without date filtering.
        
        Args:
            user_id: The user ID to fetch emails for
            max_emails: Maximum number of emails to fetch
            
        Returns:
            List of email metadata in Gmail-specific format
        """
        logger.info(f"Fetching all emails for user {user_id} (max: {max_emails})")
        
        try:
            # Fetch messages without a specific query
            messages = await self._fetch_emails_with_query(user_id, "", max_emails)
            logger.info(f"Fetched {len(messages)} emails for user {user_id}")
            return messages
        except Exception as e:
            logger.error(f"Error fetching emails for user {user_id}: {str(e)}")
            return []
    
    async def get_email_details(
        self,
        user_id: str,
        message_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed information for a specific email.
        
        Args:
            user_id: The user ID to fetch the email for
            message_id: The ID of the email to fetch
            
        Returns:
            Detailed email information in Gmail-specific format
        """
        logger.info(f"Fetching email details for message {message_id}")
        
        try:
            # Get the full message details
            message = await self.api_client.get_email_details(user_id, message_id)
            return message
        except Exception as e:
            logger.error(f"Error fetching email details for message {message_id}: {str(e)}")
            return {}
    
    async def _fetch_emails_with_query(
        self,
        user_id: str,
        query: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Helper method to fetch emails with a specific query.
        
        Args:
            user_id: The user ID to fetch emails for
            query: Gmail query string
            max_results: Maximum number of results to fetch
            
        Returns:
            List of messages matching the query
        """
        try:
            # Get email list using the Gmail API client
            email_list = await self.api_client.get_email_list(
                user_id, 
                query=query, 
                max_results=max_results
            )
            
            # Extract and return the messages list
            return email_list.get("messages", [])
        except Exception as e:
            logger.error(f"Error fetching emails with query '{query}': {str(e)}")
            return []