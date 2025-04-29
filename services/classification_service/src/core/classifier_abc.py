"""Abstract base class for email classifiers."""
import abc
from typing import List, Optional

from shared.models.email import EmailMessage
from ..models import ClassificationResult


class BaseClassifier(abc.ABC):
    """Base class for all email classifiers."""

    @abc.abstractmethod
    async def classify(self, email: EmailMessage) -> ClassificationResult:
        """Classify an email and determine if it needs a reply.
        
        Args:
            email: The email to classify
            
        Returns:
            ClassificationResult with category and reply determination
        """
        pass
    
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Get the name of this classifier."""
        pass