from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class EmailMessage(BaseModel):
    """Model representing an email message."""
    id: str
    user_id: str
    thread_id: Optional[str] = None
    labels: List[str] = []
    snippet: Optional[str] = None
    subject: str
    from_email: str  # Email sender address
    to: str          # Email recipient address
    cc: Optional[str] = None
    bcc: Optional[str] = None
    date: datetime
    body_html: Optional[str] = None  # HTML version of the email body
    body_text: str                   # Plain text version of the email body
    has_attachments: bool = False
    raw_data: Optional[Dict[str, Any]] = None