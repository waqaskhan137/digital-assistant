from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class EmailHeader(BaseModel):
    """Email header with name and value."""
    name: str
    value: str


class EmailAttachment(BaseModel):
    """Email attachment with filename and content details."""
    attachment_id: str
    filename: str
    mime_type: str
    size: int = 0


class EmailData(BaseModel):
    """Structured data from a Gmail email."""
    message_id: str = Field(..., alias="id")
    thread_id: str
    user_id: str
    labels: List[str] = Field([], alias="labelIds")
    snippet: str = ""
    headers: Dict[str, str] = {}
    subject: Optional[str] = None
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    cc_email: Optional[List[str]] = None
    date: Optional[datetime] = None
    body_plain: Optional[str] = None
    body_html: Optional[str] = None
    attachments: List[EmailAttachment] = []
    raw_data: Dict[str, Any] = {}
    
    class Config:
        allow_population_by_field_name = True

    @classmethod
    def from_gmail_message(cls, user_id: str, message: Dict[str, Any]) -> 'EmailData':
        """
        Create an EmailData instance from a Gmail API message.
        
        Args:
            user_id: Gmail user ID
            message: Gmail API message object
            
        Returns:
            EmailData instance with parsed message data
        """
        # Extract basic fields
        email_data = {
            "id": message.get("id"),
            "thread_id": message.get("threadId"),
            "user_id": user_id,
            "labelIds": message.get("labelIds", []),
            "snippet": message.get("snippet", ""),
            "raw_data": message,
        }
        
        # Extract headers
        headers = {}
        header_map = {
            "Subject": "subject",
            "From": "from_email",
            "To": "to_email",
            "Cc": "cc_email",
            "Date": "date",
        }
        
        if "payload" in message and "headers" in message["payload"]:
            for header in message["payload"]["headers"]:
                name = header.get("name")
                value = header.get("value")
                if name:
                    headers[name] = value
                    
                    # Map specific headers to fields
                    if name in header_map:
                        field_name = header_map[name]
                        
                        # Special handling for date
                        if field_name == "date" and value:
                            try:
                                # Try to parse various date formats
                                # This is simplified - in production you'd need more robust parsing
                                email_data[field_name] = datetime.strptime(
                                    value, "%a, %d %b %Y %H:%M:%S %z"
                                )
                            except ValueError:
                                # Fall back to string if parsing fails
                                email_data[field_name] = value
                        else:
                            email_data[field_name] = value
        
        email_data["headers"] = headers
        
        # Extract body content and attachments
        if "payload" in message:
            # Get plain text and HTML body
            email_data.update(
                _extract_body_content(message["payload"])
            )
            
            # Get attachments
            email_data["attachments"] = _extract_attachments(message["payload"])
        
        return cls(**email_data)


def _extract_body_content(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract the body content from a message payload.
    
    Args:
        payload: Gmail API message payload
        
    Returns:
        Dictionary with body_plain and body_html fields
    """
    result = {
        "body_plain": None,
        "body_html": None
    }
    
    # Handle the body if it's directly in the payload
    if "body" in payload and "data" in payload["body"]:
        mime_type = payload.get("mimeType", "")
        if "text/plain" in mime_type:
            result["body_plain"] = _decode_body(payload["body"]["data"])
        elif "text/html" in mime_type:
            result["body_html"] = _decode_body(payload["body"]["data"])
    
    # Handle multipart messages
    if "parts" in payload:
        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            
            if "text/plain" in mime_type and "body" in part and "data" in part["body"]:
                result["body_plain"] = _decode_body(part["body"]["data"])
            elif "text/html" in mime_type and "body" in part and "data" in part["body"]:
                result["body_html"] = _decode_body(part["body"]["data"])
            
            # Recursively check for nested parts
            if "parts" in part:
                nested_result = _extract_body_content(part)
                if not result["body_plain"] and nested_result["body_plain"]:
                    result["body_plain"] = nested_result["body_plain"]
                if not result["body_html"] and nested_result["body_html"]:
                    result["body_html"] = nested_result["body_html"]
    
    return result


def _extract_attachments(payload: Dict[str, Any]) -> List[EmailAttachment]:
    """
    Extract attachments from a message payload.
    
    Args:
        payload: Gmail API message payload
        
    Returns:
        List of EmailAttachment objects
    """
    attachments = []
    
    # Handle attachments in the main payload
    if "body" in payload and "attachmentId" in payload["body"]:
        attachments.append(
            EmailAttachment(
                attachment_id=payload["body"]["attachmentId"],
                filename=payload.get("filename", ""),
                mime_type=payload.get("mimeType", ""),
                size=payload["body"].get("size", 0)
            )
        )
    
    # Handle attachments in parts
    if "parts" in payload:
        for part in payload["parts"]:
            # Check if this part is an attachment
            if "body" in part and "attachmentId" in part["body"]:
                attachments.append(
                    EmailAttachment(
                        attachment_id=part["body"]["attachmentId"],
                        filename=part.get("filename", ""),
                        mime_type=part.get("mimeType", ""),
                        size=part["body"].get("size", 0)
                    )
                )
            
            # Recursively check nested parts
            if "parts" in part:
                nested_attachments = _extract_attachments(part)
                attachments.extend(nested_attachments)
    
    return attachments


def _decode_body(data: str) -> str:
    """
    Decode base64url encoded body content.
    
    Args:
        data: Base64url encoded string
        
    Returns:
        Decoded string
    """
    import base64
    
    # Replace URL-safe characters and add padding if needed
    data = data.replace("-", "+").replace("_", "/")
    padding = len(data) % 4
    if padding:
        data += "=" * (4 - padding)
    
    # Decode from base64
    try:
        return base64.b64decode(data).decode("utf-8")
    except Exception:
        # Fall back to empty string if decoding fails
        return ""