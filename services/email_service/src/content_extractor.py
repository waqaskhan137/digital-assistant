import base64
import logging
from typing import Dict, Any, Tuple, List, Optional
from shared.utils.text_utils import html_to_text
from .interfaces.email_processor import IContentExtractor # Import interface

logger = logging.getLogger(__name__)

class EmailContentExtractor(IContentExtractor): # Implement interface
    """
    Extracts and processes email content from Gmail API message payloads.
    
    This class is responsible for extracting HTML and text content from Gmail
    API message payloads, as well as identifying attachments.
    """
    
    def extract_body(self, payload: Dict[str, Any]) -> Tuple[str, str]: # Matches interface
        """
        Extract HTML and plain text body from message payload.
        
        Args:
            payload: Gmail API message payload
            
        Returns:
            Tuple of (HTML body, plain text body)
        """
        body_html = ""
        body_text = ""
        
        # Check for body in the main payload
        if 'body' in payload and 'data' in payload['body']:
            data = payload['body']['data']
            try:
                decoded_data = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace') # Added error handling
            except (UnicodeDecodeError, ValueError) as e:
                logger.warning(f"Error decoding main body part data: {e}")
                decoded_data = "" # Fallback to empty string
            
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
                        decoded_data = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace') # Added error handling
                    except (UnicodeDecodeError, ValueError) as e:
                        logger.warning(f"Error decoding part data (mime: {part_mime_type}): {e}")
                        decoded_data = "" # Fallback
                    
                    if part_mime_type == 'text/html' and not body_html: # Prioritize first HTML part found
                        body_html = decoded_data
                    elif part_mime_type == 'text/plain' and not body_text: # Prioritize first text part found
                        body_text = decoded_data
                
                # Recursively check for nested parts (e.g., multipart/alternative)
                if 'parts' in part:
                    nested_html, nested_text = self.extract_body(part)
                    if nested_html and not body_html:
                        body_html = nested_html
                    if nested_text and not body_text:
                        body_text = nested_text
        
        # If we only have HTML, try to extract text from it
        if body_html and not body_text:
            try:
                body_text = html_to_text(body_html)
            except Exception as e:
                logger.error(f"Error converting HTML to text: {e}")
                # Keep body_text empty if conversion fails
        
        return body_html, body_text
    
    def get_attachments(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]: # Matches interface
        """
        Extract attachment metadata from message payload.
        
        Args:
            payload: Gmail API message payload
            
        Returns:
            List of attachment metadata
        """
        attachments = []
        
        # Check for attachments in the main payload (less common but possible)
        if ('body' in payload and 'attachmentId' in payload['body'] and
                payload.get('filename', '')):
            attachments.append({
                'id': payload['body']['attachmentId'],
                'filename': payload['filename'],
                'mime_type': payload.get('mimeType', 'application/octet-stream'),
                'size': payload['body'].get('size', 0)
            })
        
        # Check for attachments in parts (standard way)
        if 'parts' in payload:
            for part in payload['parts']:
                # If this part has an attachmentId and filename, it's an attachment
                if ('body' in part and 'attachmentId' in part['body'] and
                        part.get('filename', '')):
                    attachments.append({
                        'id': part['body']['attachmentId'],
                        'filename': part['filename'],
                        'mime_type': part.get('mimeType', 'application/octet-stream'),
                        'size': part['body'].get('size', 0)
                    })
                
                # Recursively check for nested parts (e.g., multipart/mixed)
                if 'parts' in part:
                    nested_attachments = self.get_attachments(part)
                    attachments.extend(nested_attachments)
        
        return attachments