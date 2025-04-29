"""Rule-based classifier implementation."""
import logging
import re
from typing import Dict, List, Optional, Pattern, Union

from shared.models.email import EmailMessage
from ..models import ClassificationResult, EmailCategory
from .classifier_abc import BaseClassifier

logger = logging.getLogger(__name__)


class Rule:
    """A classification rule with conditions and outcome."""
    
    def __init__(
        self,
        name: str,
        category: EmailCategory,
        needs_reply: bool,
        conditions: Dict[str, Union[str, List[str], Pattern]],
        confidence: float = 1.0,
        priority: Optional[int] = None,
        explanation: Optional[str] = None
    ):
        """Initialize a rule.
        
        Args:
            name: Descriptive name for the rule
            category: Category to assign if rule matches
            needs_reply: Whether emails matching this rule need a reply
            conditions: Dict of condition fields and values to match
            confidence: Confidence level for this classification
            priority: Priority level for emails matching this rule
            explanation: Human-readable explanation of this rule
        """
        self.name = name
        self.category = category
        self.needs_reply = needs_reply
        self.conditions = conditions
        self.confidence = confidence
        self.priority = priority
        self.explanation = explanation or f"Matched rule: {name}"
    
    def matches(self, email: EmailMessage) -> bool:
        """Check if an email matches this rule's conditions.
        
        Args:
            email: The email to check against
            
        Returns:
            True if the email matches all conditions, False otherwise
        """
        for field, pattern in self.conditions.items():
            # Get the value from the email
            if field == "sender":
                value = email.from_address.email if email.from_address else None
            elif field == "recipient":
                value = email.to_addresses[0].email if email.to_addresses else None
            elif field == "subject":
                value = email.subject
            elif field == "body":
                value = email.text_content or ""
            elif field == "has_attachments":
                value = len(email.attachments) > 0
            else:
                logger.warning(f"Unknown field in rule condition: {field}")
                return False
            
            # Skip None values
            if value is None:
                return False
            
            # Check the pattern against the value
            if isinstance(pattern, Pattern):
                if not pattern.search(str(value)):
                    return False
            elif isinstance(pattern, list):
                if not any(p in str(value) for p in pattern):
                    return False
            elif isinstance(pattern, bool):
                if pattern != value:
                    return False
            else:
                if pattern not in str(value):
                    return False
        
        # If we get here, all conditions matched
        return True


class RuleBasedClassifier(BaseClassifier):
    """Classifier that uses predefined rules for classification."""
    
    def __init__(self, rules: Optional[List[Rule]] = None):
        """Initialize the rule-based classifier.
        
        Args:
            rules: Optional list of rules to use for classification
                  If None, default rules will be used
        """
        self.rules = rules or self._default_rules()
    
    @property
    def name(self) -> str:
        """Get the name of this classifier."""
        return "RuleBasedClassifier"
    
    async def classify(self, email: EmailMessage) -> ClassificationResult:
        """Classify an email based on predefined rules.
        
        Args:
            email: The email to classify
            
        Returns:
            ClassificationResult with category and reply determination
        """
        # Check each rule in order
        for rule in self.rules:
            if rule.matches(email):
                logger.info(f"Email matched rule: {rule.name}")
                return ClassificationResult(
                    category=rule.category,
                    needs_reply=rule.needs_reply,
                    confidence=rule.confidence,
                    priority=rule.priority,
                    email_id=email.id,
                    explanation=rule.explanation
                )
        
        # If no rule matched, return default classification
        logger.info("No rule matched the email, using default classification")
        return ClassificationResult(
            category=EmailCategory.UNCATEGORIZED,
            needs_reply=False,
            confidence=0.5,
            email_id=email.id,
            explanation="No specific rule matched"
        )
    
    @staticmethod
    def _default_rules() -> List[Rule]:
        """Create a default set of classification rules.
        
        Returns:
            List of default rules
        """
        return [
            # Support requests
            Rule(
                name="Support Request",
                category=EmailCategory.SUPPORT,
                needs_reply=True,
                conditions={
                    "subject": ["help", "support", "issue", "problem", "trouble", "error"],
                },
                confidence=0.8,
                priority=2,
                explanation="Email contains support-related keywords in subject"
            ),
            
            # Important sender domains (example)
            Rule(
                name="Important Domain",
                category=EmailCategory.IMPORTANT,
                needs_reply=True,
                conditions={
                    "sender": ["@important-client.com", "@boss-domain.com", "@ceo-email.com"]
                },
                confidence=0.9,
                priority=3,
                explanation="Sender is from an important domain"
            ),
            
            # Spam indicators
            Rule(
                name="Spam Keywords",
                category=EmailCategory.SPAM,
                needs_reply=False,
                conditions={
                    "subject": ["viagra", "lottery", "winner", "millions", "prince", "inheritance"]
                },
                confidence=0.7,
                explanation="Email contains common spam keywords"
            ),
            
            # Promotional emails
            Rule(
                name="Promotional Content",
                category=EmailCategory.PROMOTIONAL,
                needs_reply=False,
                conditions={
                    "subject": ["discount", "sale", "offer", "off", "limited time", "promotion"]
                },
                confidence=0.8,
                explanation="Email contains promotional keywords"
            ),
            
            # Personal emails (simplified example)
            Rule(
                name="Personal Content",
                category=EmailCategory.PERSONAL,
                needs_reply=True,
                conditions={
                    "subject": ["lunch", "coffee", "meet", "hello", "hi there", "catch up", "family", "personal"]
                },
                confidence=0.6,
                priority=1,
                explanation="Email appears to be personal communication"
            ),
            
            # Social media notifications
            Rule(
                name="Social Media",
                category=EmailCategory.SOCIAL,
                needs_reply=False,
                conditions={
                    "sender": ["@facebook.com", "@twitter.com", "@instagram.com", "@linkedin.com"]
                },
                confidence=0.9,
                explanation="Email is from a social media platform"
            ),
        ]