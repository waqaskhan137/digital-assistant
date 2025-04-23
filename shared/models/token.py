from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    """Model representing an OAuth token."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    expires_at: datetime
    scope: str

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        return datetime.now() > self.expires_at