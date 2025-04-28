"""
Gmail Attachment Handler

This module implements the AttachmentHandler interface for Gmail.
It encapsulates all Gmail-specific logic for handling email attachments
to provide a clean separation of concerns.
"""
from typing import Dict, Any, List, Optional
import logging
import base64

from services.email_service.src.interfaces.attachment_handler import AttachmentHandler
from services.email_service.src.gmail_api_client import GmailApiClient

logger = logging.getLogger(__name__)

class GmailAttachmentHandler(AttachmentHandler):
    """
    Gmail-specific implementation of the AttachmentHandler interface.
    
    This class follows the Interface Segregation Principle by implementing only
    methods related to attachment handling, not fetching or processing emails.
    """
    
    def __init__(self, api_client: GmailApiClient):
        """
        Initialize with a Gmail API client.
        
        Args:
            api_client: Gmail API client for making API requests
        """
        self.api_client = api_client
    
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
        logger.info(f"Fetching attachment {attachment_id} from message {message_id}")
        
        try:
            # Fetch the attachment from the Gmail API
            attachment_data = await self.api_client.get_attachment(
                user_id, 
                message_id, 
                attachment_id
            )
            
            if not attachment_data:
                logger.warning(f"No attachment data found for ID {attachment_id}")
                return {}
                
            # Decode attachment data
            if "data" in attachment_data:
                try:
                    # Base64 decode the attachment data
                    decoded_data = base64.urlsafe_b64decode(attachment_data["data"])
                    attachment_data["decoded_data"] = decoded_data
                except Exception as e:
                    logger.error(f"Error decoding attachment data: {str(e)}")
            
            return attachment_data
            
        except Exception as e:
            logger.error(f"Error fetching attachment: {str(e)}")
            return {}
    
    async def extract_attachment_metadata(
        self,
        message: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract metadata for all attachments in a message.
        
        Args:
            message: Gmail-specific message object
            
        Returns:
            List of dictionaries with attachment metadata
        """
        logger.info(f"Extracting attachment metadata from message {message.get('id', 'unknown')}")
        
        attachments = []
        
        try:
            # Get message payload
            payload = message.get("payload", {})
            
            # Process parts recursively to find attachments
            if "parts" in payload:
                self._process_parts(payload["parts"], attachments)
            elif "body" in payload and payload.get("filename"):
                # Handle single-part message with attachment
                self._add_attachment_metadata(payload, attachments)
                
            return attachments
            
        except Exception as e:
            logger.error(f"Error extracting attachment metadata: {str(e)}")
            return []
    
    def _process_parts(self, parts: List[Dict[str, Any]], attachments: List[Dict[str, Any]]):
        """
        Recursively process message parts to extract attachment metadata.
        
        Args:
            parts: List of message parts
            attachments: List to append attachment metadata to
        """
        for part in parts:
            # If part has a filename, it's an attachment
            if part.get("filename"):
                self._add_attachment_metadata(part, attachments)
                
            # Recursively process nested parts
            if "parts" in part:
                self._process_parts(part["parts"], attachments)
    
    def _add_attachment_metadata(self, part: Dict[str, Any], attachments: List[Dict[str, Any]]):
        """
        Extract and add attachment metadata from a message part.
        
        Args:
            part: Message part containing attachment
            attachments: List to append attachment metadata to
        """
        # Extract attachment metadata
        attachment_id = part.get("body", {}).get("attachmentId", "")
        filename = part.get("filename", "")
        mime_type = part.get("mimeType", "")
        size = part.get("body", {}).get("size", 0)
        
        # Skip if no attachment ID (inline content)
        if not attachment_id:
            return
            
        # Add metadata to results
        attachments.append({
            "id": attachment_id,
            "filename": filename,
            "mime_type": mime_type,
            "size": size
        })