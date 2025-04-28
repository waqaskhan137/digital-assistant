import email.utils
import logging
from datetime import datetime
from typing import List, Dict, Any
from shared.models.email import EmailMessage
from .content_extractor import EmailContentExtractor

logger = logging.getLogger(__name__)

class EmailNormalizer:
    """
    Converts Gmail API message format to internal EmailMessage model.
    
    This class is responsible for extracting metadata from Gmail API messages
    and converting them to a standardized internal format (EmailMessage).
    """
    
    def __init__(self, content_extractor: EmailContentExtractor):
        """
        Initialize the EmailNormalizer.
        
        Args:
            content_extractor: EmailContentExtractor instance for handling message content
        """
        self.content_extractor = content_extractor
    
    def normalize_message(self, user_id: str, message: Dict[str, Any]) -> EmailMessage:
        """
        Convert a single Gmail API message to an EmailMessage.
        
        Args:
            user_id: The user ID the message belongs to
            message: Gmail API message object
            
        Returns:
            Normalized EmailMessage object
        """
        # Extract headers
        headers = {header['name'].lower(): header['value'] 
                for header in message['payload']['headers']}
        
        # Parse date
        date_str = headers.get('date', '')
        try:
            date_tuple = email.utils.parsedate_tz(date_str)
            if date_tuple:
                timestamp = email.utils.mktime_tz(date_tuple)
                date = datetime.fromtimestamp(timestamp)
            else:
                date = datetime.now()
        except Exception as e:
            logger.warning(f"Failed to parse date: {date_str}, {str(e)}")
            date = datetime.now()
        
        # Extract content
        body_html, body_text = self.content_extractor.extract_body(message['payload'])
        
        # Check for attachments
        attachments = self.content_extractor.get_attachments(message['payload'])
        
        # Create normalized message
        email_message = EmailMessage(
            id=message['id'],
            user_id=user_id,
            thread_id=message.get('threadId', ''),
            labels=message.get('labelIds', []),
            snippet=message.get('snippet', ''),
            subject=headers.get('subject', ''),
            from_email=headers.get('from', ''),
            to=headers.get('to', ''),
            cc=headers.get('cc', ''),
            bcc=headers.get('bcc', ''),
            date=date,
            body_html=body_html,
            body_text=body_text,
            has_attachments=bool(attachments),
            raw_data=message
        )
        
        return email_message
    
    def normalize_messages(self, user_id: str, messages: List[Dict[str, Any]]) -> List[EmailMessage]:
        """
        Convert multiple Gmail API messages to EmailMessage objects.
        
        Args:
            user_id: The user ID the messages belong to
            messages: List of Gmail API message objects
            
        Returns:
            List of normalized EmailMessage objects
        """
        normalized_messages = []
        
        for message in messages:
            normalized_message = self.normalize_message(user_id, message)
            normalized_messages.append(normalized_message)
        
        return normalized_messages