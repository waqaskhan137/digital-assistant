"""
Email Processor Interface

This module defines the interface for components that process and normalize emails.
Following the Interface Segregation Principle, this interface focuses only on email
processing operations without mixing in fetching or attachment handling concerns.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from shared.models.email import EmailMessage

class EmailProcessor(ABC):
    """
    Interface for components that process and normalize emails.
    
    This interface follows the Interface Segregation Principle by focusing only
    on operations related to processing and normalizing emails, not fetching them.
    Concrete implementations might include GmailEmailProcessor, OutlookEmailProcessor, etc.
    """
    
    @abstractmethod
    async def normalize_messages(
        self, 
        user_id: str, 
        messages: List[Dict[str, Any]]
    ) -> List[EmailMessage]:
        """
        Convert provider-specific email format to our internal EmailMessage model.
        
        Args:
            user_id: The user ID the messages belong to
            messages: List of provider-specific message objects
            
        Returns:
            List of normalized EmailMessage objects
        """
        pass
    
    @abstractmethod
    async def extract_content(
        self,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract content from a message including body text, HTML, and metadata.
        
        Args:
            message: Provider-specific message object
            
        Returns:
            Dictionary with extracted content
        """
        pass