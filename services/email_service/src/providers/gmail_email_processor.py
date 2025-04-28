"""
Gmail Email Processor

This module implements the EmailProcessor interface for Gmail.
It encapsulates all Gmail-specific logic for processing and normalizing emails
to provide a clean separation of concerns.
"""
from typing import List, Dict, Any, Optional
import logging
import base64
from datetime import datetime

from services.email_service.src.interfaces.email_processor import EmailProcessor
from services.email_service.src.content_extractor import EmailContentExtractor
from shared.models.email import EmailMessage
from shared.utils.text_utils import html_to_text

logger = logging.getLogger(__name__)

class GmailEmailProcessor(EmailProcessor):
    """
    Gmail-specific implementation of the EmailProcessor interface.
    
    This class follows the Interface Segregation Principle by implementing only
    methods related to email processing and normalization, not fetching them.
    """
    
    def __init__(self, content_extractor: EmailContentExtractor = None):
        """
        Initialize with optional content extractor.
        
        Args:
            content_extractor: Helper for extracting email content
        """
        self.content_extractor = content_extractor or EmailContentExtractor()
    
    async def normalize_messages(
        self, 
        user_id: str, 
        messages: List[Dict[str, Any]]
    ) -> List[EmailMessage]:
        """
        Convert Gmail-specific email format to our internal EmailMessage model.
        
        Args:
            user_id: The user ID the messages belong to
            messages: List of Gmail-specific message objects
            
        Returns:
            List of normalized EmailMessage objects
        """
        logger.info(f"Normalizing {len(messages)} messages for user {user_id}")
        
        result = []
        for message in messages:
            try:
                if not message:
                    continue
                    
                # Extract basic message attributes
                message_id = message.get("id", "")
                thread_id = message.get("threadId", "")
                
                # Extract payload data
                payload = message.get("payload", {})
                headers = payload.get("headers", [])
                
                # Extract headers
                subject = self._get_header_value(headers, "Subject", "")
                from_email = self._get_header_value(headers, "From", "")
                to_email = self._get_header_value(headers, "To", "")
                cc = self._get_header_value(headers, "Cc", "")
                date_str = self._get_header_value(headers, "Date", "")
                
                # Parse received date
                received_date = self._parse_date(date_str)
                
                # Extract content
                content = await self.extract_content(message)
                
                # Create normalized email message
                normalized_message = EmailMessage(
                    id=message_id,
                    thread_id=thread_id,
                    user_id=user_id,
                    subject=subject,
                    from_email=from_email,
                    to=to_email,
                    cc=cc,
                    body_text=content.get("text", ""),
                    body_html=content.get("html", ""),
                    received_date=received_date,
                    has_attachments=bool(content.get("attachments")),
                    attachment_count=len(content.get("attachments", [])),
                    attachment_details=content.get("attachments", []),
                    labels=message.get("labelIds", []),
                    raw_data=message
                )
                
                result.append(normalized_message)
                
            except Exception as e:
                logger.error(f"Error normalizing message: {str(e)}")
                continue
                
        logger.info(f"Successfully normalized {len(result)} messages")
        return result
    
    async def extract_content(
        self,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract content from a Gmail message including body text, HTML, and attachments.
        
        Args:
            message: Gmail-specific message object
            
        Returns:
            Dictionary with extracted content
        """
        logger.info(f"Extracting content for message {message.get('id', 'unknown')}")
        
        try:
            # Use the content extractor to extract email content
            content = self.content_extractor.extract_content(message)
            return content
        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")
            return {
                "text": "",
                "html": "",
                "attachments": []
            }
    
    def _get_header_value(self, headers: List[Dict[str, str]], name: str, default: str = "") -> str:
        """
        Helper method to get a header value by name.
        
        Args:
            headers: List of header dictionaries
            name: Header name to search for
            default: Default value if header not found
            
        Returns:
            Header value or default if not found
        """
        for header in headers:
            if header.get("name", "").lower() == name.lower():
                return header.get("value", default)
        return default
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse a date string to datetime object.
        
        Args:
            date_str: Date string from email header
            
        Returns:
            Parsed datetime or None if parsing fails
        """
        if not date_str:
            return None
            
        try:
            # Try several date formats
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822 format
                "%d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S",
                "%d %b %Y %H:%M:%S"
            ]:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
                    
            logger.warning(f"Unable to parse date string: {date_str}")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing date: {str(e)}")
            return None