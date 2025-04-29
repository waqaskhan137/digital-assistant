"""Data models for the Classification Service."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EmailCategory(str, Enum):
    """Enumeration of supported email categories."""
    IMPORTANT = "important"
    URGENT = "urgent"
    SPAM = "spam"
    SUPPORT = "support"
    PERSONAL = "personal"
    PROMOTIONAL = "promotional"
    UPDATES = "updates"
    SOCIAL = "social"
    UNCATEGORIZED = "uncategorized"


class ClassificationResult(BaseModel):
    """Result of email classification."""
    
    # Primary classification output
    category: EmailCategory = Field(
        default=EmailCategory.UNCATEGORIZED,
        description="Category assigned to the email"
    )
    
    # Whether the email needs a reply
    needs_reply: bool = Field(
        default=False,
        description="Whether the email requires a response"
    )
    
    # Confidence score for the classification
    confidence: float = Field(
        default=1.0, 
        ge=0.0, 
        le=1.0,
        description="Confidence level for the classification (0.0-1.0)"
    )
    
    # Optional priority level (higher number = higher priority)
    priority: Optional[int] = Field(
        default=None,
        description="Priority level of the email (higher = more important)"
    )
    
    # Optional message ID for correlation
    email_id: Optional[str] = Field(
        default=None,
        description="ID of the classified email for correlation"
    )
    
    # Optional user-readable explanation of classification decision
    explanation: Optional[str] = Field(
        default=None,
        description="Human-readable explanation for the classification"
    )