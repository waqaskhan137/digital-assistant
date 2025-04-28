"""
Email Fetcher Interface

This module defines the interface for components that fetch emails from email providers.
Following the Interface Segregation Principle, this interface focuses only on email
fetching operations without mixing in processing or normalization concerns.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

class EmailFetcher(ABC):
    """
    Interface for components that fetch emails from email providers.
    
    This interface follows the Interface Segregation Principle by focusing only
    on operations related to fetching emails, not processing or normalizing them.
    Concrete implementations might include GmailEmailFetcher, OutlookEmailFetcher, etc.
    """
    
    @abstractmethod
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
            List of email metadata in provider-specific format
        """
        pass
    
    @abstractmethod
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
            List of email metadata in provider-specific format
        """
        pass
    
    @abstractmethod
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
            Detailed email information in provider-specific format
        """
        pass