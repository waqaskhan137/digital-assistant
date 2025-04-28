import base64
import logging
from typing import Dict, Any, Tuple, List, Optional
from shared.utils.text_utils import html_to_text
from .interfaces.email_processor import IContentExtractor
from shared.exceptions import EmailProcessingError, ValidationError

logger = logging.getLogger(__name__)

class EmailContentExtractor(IContentExtractor):
    """
    Extracts and processes email content from Gmail API message payloads.
    
    This class is responsible for extracting HTML and text content from Gmail
    API message payloads, as well as identifying attachments.
    """
    
    def extract_body(self, payload: Dict[str, Any]) -> Tuple[str, str]:
        """
        Extract HTML and plain text body from message payload.
        
        Args:
            payload: Gmail API message payload
            
        Returns:
            Tuple of (HTML body, plain text body)
            
        Raises:
            ValidationError: If payload is None or not properly formatted
            EmailProcessingError: If content extraction fails due to unexpected issues
        """
        if payload is None:
            logger.error("Cannot extract body from None payload")
            raise ValidationError("Email payload cannot be None")
            
        if not isinstance(payload, dict):
            logger.error(f"Invalid payload type: {type(payload)}, expected dict")
            raise ValidationError(f"Email payload must be a dictionary, got {type(payload)}")
            
        body_html = ""
        body_text = ""
        
        try:
            # Check for body in the main payload
            if 'body' in payload and 'data' in payload['body']:
                data = payload['body']['data']
                try:
                    decoded_data = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                except (UnicodeDecodeError, ValueError, base64.binascii.Error) as e:
                    logger.warning(f"Error decoding main body part data: {e}")
                    decoded_data = ""  # Fallback to empty string
                
                if payload.get('mimeType') == 'text/html':
                    body_html = decoded_data
                elif payload.get('mimeType') == 'text/plain':
                    body_text = decoded_data
            
            # Check for body in parts
            if 'parts' in payload:
                for part in payload['parts']:
                    part_mime_type = part.get('mimeType', '')
                    
                    # Skip parts that are attachments (identified by filename)
                    if part.get('filename'):
                        continue
                        
                    if 'body' in part and 'data' in part['body']:
                        data = part['body']['data']
                        try:
                            decoded_data = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                        except (UnicodeDecodeError, ValueError, base64.binascii.Error) as e:
                            logger.warning(f"Error decoding part data (mime: {part_mime_type}): {e}")
                            decoded_data = ""  # Fallback
                        
                        if part_mime_type == 'text/html' and not body_html:  # Prioritize first HTML part found
                            body_html = decoded_data
                        elif part_mime_type == 'text/plain' and not body_text:  # Prioritize first text part found
                            body_text = decoded_data
                    
                    # Recursively check for nested parts (e.g., multipart/alternative)
                    if 'parts' in part:
                        try:
                            nested_html, nested_text = self.extract_body(part)
                            if nested_html and not body_html:
                                body_html = nested_html
                            if nested_text and not body_text:
                                body_text = nested_text
                        except (ValidationError, EmailProcessingError) as e:
                            # Log but continue with other parts if one nested part fails
                            logger.warning(f"Error extracting nested part: {e}")
            
            # If we only have HTML, try to extract text from it
            if body_html and not body_text:
                try:
                    body_text = html_to_text(body_html)
                except Exception as e:
                    logger.error(f"Error converting HTML to text: {e}")
                    # Keep body_text empty if conversion fails, but add a placeholder message
                    body_text = "[Error extracting text content]"
            
            return body_html, body_text
            
        except Exception as e:
            logger.error(f"Unexpected error extracting email body: {e}", exc_info=True)
            raise EmailProcessingError(f"Failed to extract email content: {e}") from e
    
    def get_attachments(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract attachment metadata from message payload.
        
        Args:
            payload: Gmail API message payload
            
        Returns:
            List of attachment metadata
            
        Raises:
            ValidationError: If payload is None or not properly formatted
            EmailProcessingError: If attachment extraction fails due to unexpected issues
        """
        if payload is None:
            logger.error("Cannot extract attachments from None payload")
            raise ValidationError("Email payload cannot be None")
            
        if not isinstance(payload, dict):
            logger.error(f"Invalid payload type: {type(payload)}, expected dict")
            raise ValidationError(f"Email payload must be a dictionary, got {type(payload)}")
        
        try:
            attachments = []
            
            # Check for attachments in the main payload (less common but possible)
            if ('body' in payload and 'attachmentId' in payload['body'] and
                    payload.get('filename', '')):
                attachments.append({
                    'id': payload['body']['attachmentId'],
                    'filename': payload.get('filename', 'unknown_filename'),
                    'mime_type': payload.get('mimeType', 'application/octet-stream'),
                    'size': payload['body'].get('size', 0)
                })
            
            # Check for attachments in parts (standard way)
            if 'parts' in payload:
                for part in payload['parts']:
                    # If this part has an attachmentId and filename, it's an attachment
                    if ('body' in part and 'attachmentId' in part['body'] and
                            part.get('filename', '')):
                        try:
                            attachments.append({
                                'id': part['body']['attachmentId'],
                                'filename': part.get('filename', 'unknown_filename'),
                                'mime_type': part.get('mimeType', 'application/octet-stream'),
                                'size': part['body'].get('size', 0)
                            })
                        except Exception as e:
                            logger.warning(f"Error processing attachment metadata: {e}. Skipping attachment.")
                    
                    # Recursively check for nested parts (e.g., multipart/mixed)
                    if 'parts' in part:
                        try:
                            nested_attachments = self.get_attachments(part)
                            attachments.extend(nested_attachments)
                        except (ValidationError, EmailProcessingError) as e:
                            # Log but continue with other parts if one nested part fails
                            logger.warning(f"Error extracting nested attachments: {e}")
            
            return attachments
            
        except Exception as e:
            logger.error(f"Unexpected error extracting email attachments: {e}", exc_info=True)
            raise EmailProcessingError(f"Failed to extract email attachments: {e}") from e