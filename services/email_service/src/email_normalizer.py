import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import email.utils
from shared.models.email import EmailMessage, EmailAttachment, EmailAddress
from .interfaces.email_processor import IContentExtractor, IEmailNormalizer
from shared.exceptions import EmailProcessingError, ValidationError

logger = logging.getLogger(__name__)

class EmailNormalizer(IEmailNormalizer):
    """
    Normalizes Gmail API email data into a standard internal format.
    
    This class converts raw Gmail API email data into our internal
    EmailMessage model for consistent processing across the system.
    """
    
    def __init__(self, content_extractor: IContentExtractor):
        """
        Initialize the normalizer with a content extractor.
        
        Args:
            content_extractor: Component that extracts content from message payloads
        """
        self.content_extractor = content_extractor
    
    def normalize(self, raw_message: Dict[str, Any], user_id: str) -> EmailMessage:
        """
        Convert a raw Gmail API message to our internal EmailMessage format.
        
        Args:
            raw_message: The raw message data from Gmail API
            user_id: The user ID this message belongs to
            
        Returns:
            EmailMessage object
            
        Raises:
            ValidationError: If raw_message is None, not a dict, or missing required fields
            EmailProcessingError: If normalization fails due to unexpected issues
        """
        if raw_message is None:
            logger.error("Cannot normalize None message")
            raise ValidationError("Raw email message cannot be None")
            
        if not isinstance(raw_message, dict):
            logger.error(f"Invalid message type: {type(raw_message)}, expected dict")
            raise ValidationError(f"Raw email message must be a dictionary, got {type(raw_message)}")
            
        # Check for required fields
        if 'id' not in raw_message:
            logger.error("Raw message missing required field 'id'")
            raise ValidationError("Raw email message missing required field 'id'")
            
        try:
            # Extract basic message information
            message_id = raw_message['id']
            thread_id = raw_message.get('threadId', '')
            
            # Get headers (as dictionary for easier access)
            headers = self._get_headers_dict(raw_message)
            
            # Get from, to, cc, bcc information
            try:
                from_address = self._parse_email_address(headers.get('From', ''))
                to_addresses = self._parse_email_addresses(headers.get('To', ''))
                cc_addresses = self._parse_email_addresses(headers.get('Cc', ''))
                bcc_addresses = self._parse_email_addresses(headers.get('Bcc', ''))
            except Exception as e:
                logger.warning(f"Error parsing email addresses: {e}")
                # Create fallback addresses to avoid complete failure
                from_address = EmailAddress(email="unknown@example.com", name="Unknown Sender")
                to_addresses = []
                cc_addresses = []
                bcc_addresses = []
                
            # Parse date
            date = self._parse_date(headers.get('Date', ''))
            if not date:
                # Use Gmail's internal date as fallback (in milliseconds since epoch)
                internal_date = raw_message.get('internalDate')
                if internal_date:
                    try:
                        date = datetime.fromtimestamp(int(internal_date) / 1000)
                    except (ValueError, TypeError, OverflowError) as e:
                        logger.warning(f"Error parsing internal date {internal_date}: {e}")
                        date = datetime.utcnow()  # Use current time as fallback
                else:
                    date = datetime.utcnow()  # Use current time as fallback
            
            # Get subject
            subject = headers.get('Subject', '(No Subject)')
            
            # Get payload and extract HTML/text content
            payload = raw_message.get('payload', {})
            if not payload:
                logger.warning(f"Message {message_id} is missing payload")
                html_content = ""
                text_content = ""
            else:
                try:
                    html_content, text_content = self.content_extractor.extract_body(payload)
                except (ValidationError, EmailProcessingError) as e:
                    logger.error(f"Error extracting content for message {message_id}: {e}")
                    # Provide empty content rather than failing completely
                    html_content = ""
                    text_content = f"[Error extracting email content: {e}]"
            
            # Get labels
            labels = raw_message.get('labelIds', [])
            
            # Get attachment metadata
            try:
                attachments = self._get_attachments(payload, message_id)
            except (ValidationError, EmailProcessingError) as e:
                logger.warning(f"Error extracting attachments for message {message_id}: {e}")
                attachments = []
            
            # Create EmailMessage
            email_message = EmailMessage(
                id=message_id,
                thread_id=thread_id,
                user_id=user_id,
                date=date,
                subject=subject,
                from_address=from_address,
                to_addresses=to_addresses,
                cc_addresses=cc_addresses,
                bcc_addresses=bcc_addresses,
                html_content=html_content or None,  # Convert empty string to None
                text_content=text_content or "(No content)",  # Provide placeholder if empty
                labels=labels,
                attachments=attachments,
                raw_data={
                    'message_id': message_id,
                    'thread_id': thread_id,
                    'headers': headers,
                }
            )
            
            return email_message
            
        except ValidationError as e:
            # Let ValidationError pass through
            raise
        except EmailProcessingError as e:
            # Let EmailProcessingError pass through
            raise
        except Exception as e:
            logger.error(f"Unexpected error normalizing message {raw_message.get('id', 'unknown')}: {e}", exc_info=True)
            raise EmailProcessingError(f"Failed to normalize email: {e}") from e
    
    def normalize_batch(self, raw_messages: List[Dict[str, Any]], user_id: str) -> List[EmailMessage]:
        """
        Normalize a batch of raw Gmail API messages.
        
        Args:
            raw_messages: List of raw messages from Gmail API
            user_id: The user ID these messages belong to
            
        Returns:
            List of EmailMessage objects
            
        Raises:
            ValidationError: If raw_messages is None or not a list
        """
        if raw_messages is None:
            logger.error("Cannot normalize None message batch")
            raise ValidationError("Raw email messages batch cannot be None")
            
        if not isinstance(raw_messages, list):
            logger.error(f"Invalid message batch type: {type(raw_messages)}, expected list")
            raise ValidationError(f"Raw email messages must be a list, got {type(raw_messages)}")
        
        normalized_messages = []
        
        for index, raw_message in enumerate(raw_messages):
            try:
                normalized_message = self.normalize(raw_message, user_id)
                normalized_messages.append(normalized_message)
            except (ValidationError, EmailProcessingError) as e:
                # Log but continue processing other messages
                logger.warning(f"Error normalizing message at index {index}: {e}")
                continue
        
        return normalized_messages
    
    def _get_headers_dict(self, message: Dict[str, Any]) -> Dict[str, str]:
        """
        Convert Gmail API's headers list to a dictionary for easier access.
        
        Args:
            message: Raw message from Gmail API
            
        Returns:
            Dictionary of headers
        """
        headers = {}
        
        if 'payload' in message and 'headers' in message['payload']:
            for header in message['payload']['headers']:
                if 'name' in header and 'value' in header:
                    headers[header['name']] = header['value']
        
        return headers
    
    def _parse_email_address(self, address_string: str) -> EmailAddress:
        """
        Parse a single email address string into an EmailAddress object.
        
        Args:
            address_string: Email address string (e.g., "John Doe <john@example.com>")
            
        Returns:
            EmailAddress object
        """
        if not address_string:
            return EmailAddress(email="", name="")
        
        try:
            parsed_addresses = email.utils.getaddresses([address_string])
            if parsed_addresses:
                name, email_addr = parsed_addresses[0]
                return EmailAddress(email=email_addr, name=name)
            else:
                return EmailAddress(email=address_string, name="")
        except Exception as e:
            logger.warning(f"Error parsing email address '{address_string}': {e}")
            # If parsing fails, try to extract just the email part using a simple heuristic
            if '<' in address_string and '>' in address_string:
                email_part = address_string.split('<')[1].split('>')[0].strip()
                return EmailAddress(email=email_part, name="")
            else:
                return EmailAddress(email=address_string, name="")
    
    def _parse_email_addresses(self, addresses_string: str) -> List[EmailAddress]:
        """
        Parse a comma-separated list of email addresses.
        
        Args:
            addresses_string: Comma-separated email addresses
            
        Returns:
            List of EmailAddress objects
        """
        if not addresses_string:
            return []
        
        try:
            parsed_addresses = email.utils.getaddresses([addresses_string])
            return [
                EmailAddress(email=email_addr, name=name)
                for name, email_addr in parsed_addresses
                if email_addr  # Only include addresses that have an email part
            ]
        except Exception as e:
            logger.warning(f"Error parsing email addresses '{addresses_string}': {e}")
            # Fallback: split by comma and try to extract emails
            result = []
            for part in addresses_string.split(','):
                if '@' in part:  # Simple check for valid email
                    parsed = self._parse_email_address(part.strip())
                    if parsed.email:
                        result.append(parsed)
            return result
    
    def _parse_date(self, date_string: str) -> Optional[datetime]:
        """
        Parse an email date string into a datetime object.
        
        Args:
            date_string: Email date string
            
        Returns:
            Datetime object or None if parsing fails
        """
        if not date_string:
            return None
        
        try:
            # Parse RFC 2822 date format
            time_tuple = email.utils.parsedate_tz(date_string)
            if time_tuple:
                # Convert to datetime with timezone adjustment
                timestamp = email.utils.mktime_tz(time_tuple)
                return datetime.fromtimestamp(timestamp)
        except Exception as e:
            logger.warning(f"Error parsing date '{date_string}': {e}")
        
        return None
    
    def _get_attachments(self, payload: Dict[str, Any], message_id: str) -> List[EmailAttachment]:
        """
        Convert Gmail API attachment metadata to EmailAttachment objects.
        
        Args:
            payload: Message payload from Gmail API
            message_id: ID of the email message
            
        Returns:
            List of EmailAttachment objects
        """
        if not payload:
            return []
        
        try:
            attachment_metadata = self.content_extractor.get_attachments(payload)
            return [
                EmailAttachment(
                    id=meta['id'],
                    message_id=message_id,
                    filename=meta['filename'],
                    mime_type=meta['mime_type'],
                    size=meta['size']
                )
                for meta in attachment_metadata
            ]
        except Exception as e:
            logger.error(f"Error converting attachment metadata for message {message_id}: {e}")
            raise EmailProcessingError(f"Failed to process email attachments: {e}") from e