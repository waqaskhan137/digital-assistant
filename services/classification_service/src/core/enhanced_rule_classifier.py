"""Enhanced rule-based classifier implementation."""
import json
import logging
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Set, Union, Callable

from shared.models.email import EmailMessage
from ..models import ClassificationResult, EmailCategory
from .classifier_abc import BaseClassifier

logger = logging.getLogger(__name__)


class ConditionOperator(str, Enum):
    """Operators for combining conditions."""
    AND = "and"
    OR = "or"
    NOT = "not"


class RuleCondition:
    """A single condition or group of conditions to check."""
    
    def __init__(
        self,
        field: Optional[str] = None,
        pattern: Optional[Union[str, List[str], Pattern, bool]] = None,
        operator: Optional[ConditionOperator] = None,
        conditions: Optional[List['RuleCondition']] = None
    ):
        """Initialize a rule condition.
        
        Args:
            field: Email field to check (sender, subject, etc.)
            pattern: Pattern to match against the field
            operator: Logical operator for combining nested conditions
            conditions: Nested conditions when using operators
        """
        # Simple condition
        self.field = field
        self.pattern = pattern
        
        # Compound condition
        self.operator = operator
        self.conditions = conditions or []
        
        # Validate
        if operator and not conditions:
            raise ValueError(f"Operator {operator} requires conditions list")
        if not operator and not field:
            raise ValueError("Either operator or field must be specified")
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'RuleCondition':
        """Create a condition from a dictionary.
        
        Args:
            data: Dictionary representation of a condition
            
        Returns:
            RuleCondition instance
        """
        # Check if this is a compound condition
        if "operator" in data:
            operator = ConditionOperator(data["operator"])
            subconditions = [
                RuleCondition.from_dict(c) for c in data.get("conditions", [])
            ]
            return RuleCondition(operator=operator, conditions=subconditions)
        
        # Simple condition
        field = data.get("field")
        pattern = data.get("pattern")
        
        # Handle regex patterns
        if isinstance(pattern, str) and pattern.startswith("regex:"):
            pattern = re.compile(pattern[6:])
        
        return RuleCondition(field=field, pattern=pattern)
    
    def matches(self, email: EmailMessage) -> bool:
        """Check if an email matches this condition.
        
        Args:
            email: The email to check against
            
        Returns:
            True if the condition matches, False otherwise
        """
        # Compound condition
        if self.operator:
            if self.operator == ConditionOperator.AND:
                return all(condition.matches(email) for condition in self.conditions)
            elif self.operator == ConditionOperator.OR:
                return any(condition.matches(email) for condition in self.conditions)
            elif self.operator == ConditionOperator.NOT:
                return not all(condition.matches(email) for condition in self.conditions)
        
        # Simple condition
        if not self.field or self.pattern is None:
            return False
        
        # Get the value from the email
        value = self._get_field_value(email, self.field)
        
        # Skip None values
        if value is None:
            return False
        
        # Check the pattern against the value
        if isinstance(self.pattern, Pattern):
            return bool(self.pattern.search(str(value)))
        elif isinstance(self.pattern, list):
            return any(p in str(value) for p in self.pattern)
        elif isinstance(self.pattern, bool):
            return self.pattern == value
        else:
            return self.pattern in str(value)
    
    @staticmethod
    def _get_field_value(email: EmailMessage, field: str) -> Any:
        """Extract a field value from an email.
        
        Args:
            email: The email to extract from
            field: Field name to extract
            
        Returns:
            The field value or None if not found
        """
        if field == "sender":
            return email.sender
        elif field == "recipient":
            return email.recipient
        elif field == "subject":
            return email.subject
        elif field == "body":
            return email.body_text or ""
        elif field == "body_html":
            return email.body_html or ""
        elif field == "has_attachments":
            return len(email.attachments) > 0
        elif field == "labels":
            return email.labels
        elif field == "date":
            return email.date
        elif field == "thread_id":
            return email.thread_id
        else:
            logger.warning(f"Unknown field in rule condition: {field}")
            return None


class EnhancedRule:
    """An enhanced classification rule with compound conditions and outcomes."""
    
    def __init__(
        self,
        name: str,
        category: EmailCategory,
        needs_reply: bool,
        condition: RuleCondition,
        confidence: float = 1.0,
        priority: Optional[int] = None,
        explanation: Optional[str] = None
    ):
        """Initialize a rule.
        
        Args:
            name: Descriptive name for the rule
            category: Category to assign if rule matches
            needs_reply: Whether emails matching this rule need a reply
            condition: Root condition for this rule
            confidence: Confidence level for this classification
            priority: Priority level for emails matching this rule
            explanation: Human-readable explanation of this rule
        """
        self.name = name
        self.category = category
        self.needs_reply = needs_reply
        self.condition = condition
        self.confidence = confidence
        self.priority = priority
        self.explanation = explanation or f"Matched rule: {name}"
        
        # Statistics
        self.match_count = 0
        self.evaluation_count = 0
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'EnhancedRule':
        """Create a rule from a dictionary.
        
        Args:
            data: Dictionary representation of a rule
            
        Returns:
            EnhancedRule instance
        """
        # Required fields
        name = data["name"]
        category = EmailCategory(data["category"])
        needs_reply = data["needs_reply"]
        
        # Parse the condition
        condition_data = data["condition"]
        condition = RuleCondition.from_dict(condition_data)
        
        # Optional fields
        confidence = data.get("confidence", 1.0)
        priority = data.get("priority")
        explanation = data.get("explanation")
        
        return EnhancedRule(
            name=name,
            category=category,
            needs_reply=needs_reply,
            condition=condition,
            confidence=confidence,
            priority=priority,
            explanation=explanation
        )
    
    def matches(self, email: EmailMessage) -> bool:
        """Check if an email matches this rule's condition.
        
        Args:
            email: The email to check against
            
        Returns:
            True if the email matches the condition, False otherwise
        """
        self.evaluation_count += 1
        result = self.condition.matches(email)
        if result:
            self.match_count += 1
        return result


class EnhancedRuleBasedClassifier(BaseClassifier):
    """Enhanced classifier using complex, configurable rules for classification."""
    
    def __init__(self, rules: Optional[List[EnhancedRule]] = None, config_path: Optional[str] = None):
        """Initialize the enhanced rule-based classifier.
        
        Args:
            rules: Optional list of rules to use for classification
            config_path: Path to rules configuration file (JSON)
        """
        self.rules = rules or []
        
        # Load from configuration file if provided
        if config_path and os.path.exists(config_path):
            self._load_rules_from_config(config_path)
        
        # If no rules are provided or loaded, use defaults
        if not self.rules:
            self.rules = self._default_rules()
    
    @property
    def name(self) -> str:
        """Get the name of this classifier."""
        return "EnhancedRuleBasedClassifier"
    
    async def classify(self, email: EmailMessage) -> ClassificationResult:
        """Classify an email based on the rules.
        
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
                    email_id=email.message_id,
                    explanation=rule.explanation
                )
        
        # If no rule matched, return default classification
        logger.info("No rule matched the email, using default classification")
        return ClassificationResult(
            category=EmailCategory.UNCATEGORIZED,
            needs_reply=False,
            confidence=0.5,
            email_id=email.message_id,
            explanation="No specific rule matched"
        )
    
    def _load_rules_from_config(self, config_path: str) -> None:
        """Load rules from a configuration file.
        
        Args:
            config_path: Path to the configuration file (JSON)
        """
        try:
            with open(config_path, 'r') as file:
                config_data = json.load(file)
                
                # Get rules array from config
                rules_data = config_data.get("rules", [])
                
                # Parse each rule
                for rule_data in rules_data:
                    try:
                        rule = EnhancedRule.from_dict(rule_data)
                        self.rules.append(rule)
                    except Exception as e:
                        logger.error(f"Error parsing rule {rule_data.get('name', 'unknown')}: {str(e)}")
                
                logger.info(f"Loaded {len(self.rules)} rules from {config_path}")
        except Exception as e:
            logger.error(f"Error loading rules from {config_path}: {str(e)}")
    
    def get_rule_statistics(self) -> List[Dict[str, Any]]:
        """Get statistics for all rules.
        
        Returns:
            List of dictionaries with rule statistics
        """
        return [
            {
                "name": rule.name,
                "category": rule.category.value,
                "match_count": rule.match_count,
                "evaluation_count": rule.evaluation_count,
                "match_rate": rule.match_count / rule.evaluation_count if rule.evaluation_count > 0 else 0,
                "priority": rule.priority
            }
            for rule in self.rules
        ]
    
    @staticmethod
    def _default_rules() -> List[EnhancedRule]:
        """Create a default set of classification rules.
        
        Returns:
            List of default rules
        """
        return [
            # Support requests
            EnhancedRule(
                name="Support Request",
                category=EmailCategory.SUPPORT,
                needs_reply=True,
                condition=RuleCondition(
                    operator=ConditionOperator.OR,
                    conditions=[
                        RuleCondition(field="subject", pattern=["help", "support", "issue", "problem", "trouble", "error"]),
                        RuleCondition(
                            operator=ConditionOperator.AND,
                            conditions=[
                                RuleCondition(field="body", pattern=["help", "problem", "not working"]),
                                RuleCondition(field="body", pattern=["please", "thanks", "thank you"])
                            ]
                        )
                    ]
                ),
                confidence=0.8,
                priority=2,
                explanation="Email contains support-related keywords"
            ),
            
            # Important sender domains
            EnhancedRule(
                name="Important Domain",
                category=EmailCategory.IMPORTANT,
                needs_reply=True,
                condition=RuleCondition(field="sender", pattern=["@important-client.com", "@boss-domain.com", "@ceo-email.com"]),
                confidence=0.9,
                priority=3,
                explanation="Sender is from an important domain"
            ),
            
            # Spam indicators
            EnhancedRule(
                name="Spam Keywords",
                category=EmailCategory.SPAM,
                needs_reply=False,
                condition=RuleCondition(
                    operator=ConditionOperator.OR,
                    conditions=[
                        RuleCondition(field="subject", pattern=["viagra", "lottery", "winner", "millions", "prince", "inheritance"]),
                        RuleCondition(
                            operator=ConditionOperator.AND,
                            conditions=[
                                RuleCondition(field="sender", pattern=re.compile(r".*@.*\.(info|xyz|click|top|loan)")),
                                RuleCondition(field="subject", pattern=re.compile(r".*urgent.*|.*limited time.*|.*act now.*", re.IGNORECASE))
                            ]
                        )
                    ]
                ),
                confidence=0.7,
                explanation="Email contains spam indicators"
            ),
            
            # Promotional emails
            EnhancedRule(
                name="Promotional Content",
                category=EmailCategory.PROMOTIONAL,
                needs_reply=False,
                condition=RuleCondition(
                    operator=ConditionOperator.OR,
                    conditions=[
                        RuleCondition(field="subject", pattern=["discount", "sale", "offer", "off", "limited time", "promotion"]),
                        RuleCondition(field="sender", pattern=["@marketing.", "@newsletter.", "@promotions."])
                    ]
                ),
                confidence=0.8,
                explanation="Email contains promotional content"
            ),
            
            # Personal emails
            EnhancedRule(
                name="Personal Content",
                category=EmailCategory.PERSONAL,
                needs_reply=True,
                condition=RuleCondition(
                    operator=ConditionOperator.AND,
                    conditions=[
                        RuleCondition(
                            operator=ConditionOperator.OR,
                            conditions=[
                                RuleCondition(field="subject", pattern=["lunch", "coffee", "meet", "hello", "hi", "catch up", "family", "personal"]),
                                RuleCondition(field="body", pattern=["would you like to", "let's meet", "get together", "how are you"])
                            ]
                        ),
                        RuleCondition(
                            operator=ConditionOperator.NOT,
                            conditions=[
                                RuleCondition(field="sender", pattern=["@newsletter.", "@noreply.", "@marketing."])
                            ]
                        )
                    ]
                ),
                confidence=0.6,
                priority=1,
                explanation="Email appears to be personal communication"
            ),
            
            # Social media notifications
            EnhancedRule(
                name="Social Media",
                category=EmailCategory.SOCIAL,
                needs_reply=False,
                condition=RuleCondition(field="sender", pattern=["@facebook.com", "@twitter.com", "@instagram.com", "@linkedin.com"]),
                confidence=0.9,
                explanation="Email is from a social media platform"
            ),
        ]