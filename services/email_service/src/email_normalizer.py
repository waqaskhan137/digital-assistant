import email.utils
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from shared.models.email import EmailMessage
from .content_extractor import EmailContentExtractor
from .interfaces.email_processor import IEmailNormalizer, IContentExtractor

logger = logging.getLogger(__name__)

class EmailNormalizer(IEmailNormalizer):
    """
    Converts Gmail API message format to internal EmailMessage model.
    
    This class is responsible for extracting metadata from Gmail API messages
    and converting them to a standardized internal format (EmailMessage).
    """
    
    def __init__(self, content_extractor: IContentExtractor):
        """
        Initialize the EmailNormalizer.
        
        Args:
            content_extractor: IContentExtractor instance for handling message content
        """
        self.content_extractor = content_extractor
    
    async def normalize_message(self, user_id: str, message_data: Dict[str, Any]) -> Optional[EmailMessage]:
        """
        Convert a single Gmail API message to an EmailMessage.
        
        Args:
            user_id: The user ID the message belongs to
            message_data: Gmail API message object
            
        Returns:
            Normalized EmailMessage object or None if invalid data
        """
        if not message_data or 'payload' not in message_data or 'headers' not in message_data['payload']:
            logger.warning(f"Invalid message data received for user {user_id}: {message_data}")
            return None
            
        # Extract headers
        headers = {header['name'].lower(): header['value'] 
                   for header in message_data['payload']['headers']}
        
        # Parse date
        date_str = headers.get('date', '')
        try:
            date_tuple = email.utils.parsedate_tz(date_str)
            if date_tuple:
                timestamp = email.utils.mktime_tz(date_tuple)
                date = datetime.fromtimestamp(timestamp)
            else:
                # Attempt to parse internalDate if Date header is missing/invalid
                internal_date_ms = message_data.get('internalDate')
                if internal_date_ms:
                    date = datetime.fromtimestamp(int(internal_date_ms) / 1000)
                else:
                    date = datetime.now() # Fallback
        except Exception as e:
            logger.warning(f"Failed to parse date: {date_str}, {str(e)}. Falling back to internalDate or now.")
            internal_date_ms = message_data.get('internalDate')
            if internal_date_ms:
                try:
                    date = datetime.fromtimestamp(int(internal_date_ms) / 1000)
                except Exception as ie:
                    logger.error(f"Failed to parse internalDate {internal_date_ms}: {ie}. Using current time.")
                    date = datetime.now()
            else:
                 date = datetime.now()
        
        # Extract content using the injected content_extractor
        body_html, body_text = self.content_extractor.extract_body(message_data['payload'])
        
        # Check for attachments using the injected content_extractor
        attachments = self.content_extractor.get_attachments(message_data['payload'])
        
        # Create normalized message
        email_message = EmailMessage(
            id=message_data['id'],
            user_id=user_id,
            thread_id=message_data.get('threadId', ''),
            labels=message_data.get('labelIds', []),
            snippet=message_data.get('snippet', ''),
            subject=headers.get('subject', ''),
            from_email=headers.get('from', ''),
            to=headers.get('to', ''),
            cc=headers.get('cc', ''),
            bcc=headers.get('bcc', ''),
            date=date,
            body_html=body_html,
            body_text=body_text,
            has_attachments=bool(attachments),
            raw_data=message_data
        )
        
        return email_message
    
    async def normalize_messages(self, user_id: str, messages: List[Dict[str, Any]]) -> List[EmailMessage]:
        """
        Convert multiple Gmail API messages to EmailMessage objects.
        
        Args:
            user_id: The user ID the messages belong to
            messages: List of Gmail API message objects
            
        Returns:
            List of normalized EmailMessage objects
        """
        normalized_messages = []
        
        for message_data in messages:
            # Use the async normalize_message method
            normalized_message = await self.normalize_message(user_id, message_data)
            if normalized_message:
                normalized_messages.append(normalized_message)
            else:
                logger.warning(f"Skipping normalization for invalid message data: {message_data.get('id', 'N/A')}")
        
        return normalized_messages