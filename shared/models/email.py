from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class EmailAddress(BaseModel):
    """Model representing an email address with optional display name."""
    email: str
    name: Optional[str] = ""


class EmailAttachment(BaseModel):
    """Model representing an email attachment."""
    id: str
    message_id: str
    filename: str
    mime_type: str
    size: int = 0
    content: Optional[bytes] = None


class EmailMessage(BaseModel):
    """Model representing an email message."""
    id: str
    user_id: str
    thread_id: Optional[str] = None
    labels: List[str] = []
    subject: str
    # Updated to use EmailAddress objects instead of strings
    from_address: EmailAddress
    to_addresses: List[EmailAddress] = []
    cc_addresses: List[EmailAddress] = []
    bcc_addresses: List[EmailAddress] = []
    date: datetime
    html_content: Optional[str] = None  # HTML version of the email body
    text_content: str                   # Plain text version of the email body
    attachments: List[EmailAttachment] = []
    raw_data: Optional[Dict[str, Any]] = None
    
    # For backward compatibility with existing code
    @property
    def from_email(self) -> str:
        """Get the sender's email address."""
        return self.from_address.email
    
    @property
    def to(self) -> str:
        """Get the primary recipient's email address, or comma-separated list if multiple."""
        if not self.to_addresses:
            return ""
        return ", ".join([addr.email for addr in self.to_addresses])
    
    @property
    def cc(self) -> Optional[str]:
        """Get CC addresses as comma-separated string."""
        if not self.cc_addresses:
            return None
        return ", ".join([addr.email for addr in self.cc_addresses])
    
    @property
    def bcc(self) -> Optional[str]:
        """Get BCC addresses as comma-separated string."""
        if not self.bcc_addresses:
            return None
        return ", ".join([addr.email for addr in self.bcc_addresses])
    
    @property
    def body_html(self) -> Optional[str]:
        """Get HTML content (for backward compatibility)."""
        return self.html_content
    
    @property
    def body_text(self) -> str:
        """Get text content (for backward compatibility)."""
        return self.text_content
    
    @property
    def has_attachments(self) -> bool:
        """Check if the email has attachments."""
        return len(self.attachments) > 0
    
    @property
    def message_id(self) -> str:
        """Get the message ID (for backward compatibility)."""
        return self.id
    
    @property
    def sender(self) -> str:
        """Get the sender's email address (for backward compatibility)."""
        return self.from_address.email if self.from_address else ""
    
    @property
    def recipient(self) -> str:
        """Get the primary recipient (for backward compatibility)."""
        if not self.to_addresses:
            return ""
        return self.to_addresses[0].email