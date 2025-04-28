"""
Attachment Handler Interface

This module defines the interface for components that handle email attachments.
Following the Interface Segregation Principle, this interface focuses only on
attachment operations without mixing in email fetching or processing concerns.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class AttachmentHandler(ABC):
    """
    Interface for components that handle email attachments.
    
    This interface follows the Interface Segregation Principle by focusing only
    on operations related to attachment handling. Concrete implementations might 
    include GmailAttachmentHandler, OutlookAttachmentHandler, etc.
    """
    
    @abstractmethod
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
            message_id: The message ID containing the attachment
            attachment_id: The specific attachment ID
            
        Returns:
            Dict containing the attachment data and metadata
        """
        pass
    
    @abstractmethod
    async def extract_attachment_metadata(
        self,
        message: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract metadata for all attachments in a message.
        
        Args:
            message: Provider-specific message object
            
        Returns:
            List of dictionaries with attachment metadata
        """
        pass