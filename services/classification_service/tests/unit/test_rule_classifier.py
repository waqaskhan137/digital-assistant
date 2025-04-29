"""Tests for the rule-based classifier."""
import pytest

from src.core import Rule, RuleBasedClassifier
from src.models import EmailCategory, ClassificationResult
from shared.models.email import EmailMessage, EmailAddress
from datetime import datetime


@pytest.mark.asyncio
async def test_rule_classifier_initializes_with_default_rules():
    """Test that the rule classifier initializes with default rules when none are provided."""
    classifier = RuleBasedClassifier()
    
    # Verify classifier initialized properly
    assert classifier is not None
    assert classifier.name == "RuleBasedClassifier"
    assert len(classifier.rules) > 0
    assert all(isinstance(rule, Rule) for rule in classifier.rules)


@pytest.mark.asyncio
async def test_rule_classifier_matches_support_email(sample_support_email, rule_classifier):
    """Test that the classifier correctly identifies a support email."""
    # Classify the email
    result = await rule_classifier.classify(sample_support_email)
    
    # Verify the classification result
    assert result is not None
    assert isinstance(result, ClassificationResult)
    assert result.category == EmailCategory.SUPPORT
    assert result.needs_reply is True
    assert result.confidence == 0.9
    assert result.priority == 2
    assert result.email_id == sample_support_email.message_id
    assert "Test support rule matched" in result.explanation


@pytest.mark.asyncio
async def test_rule_classifier_handles_no_match(sample_email, rule_classifier):
    """Test that the classifier returns a default classification when no rules match."""
    # The sample email doesn't match any rules in the fixture
    result = await rule_classifier.classify(sample_email)
    
    # Verify default classification is returned
    assert result is not None
    assert isinstance(result, ClassificationResult)
    assert result.category == EmailCategory.UNCATEGORIZED
    assert result.needs_reply is False
    assert result.confidence == 0.5
    assert result.email_id == sample_email.message_id
    assert "No specific rule matched" in result.explanation


@pytest.mark.asyncio
async def test_rule_matches_function():
    """Test the Rule.matches function correctly evaluates conditions."""
    # Create a test rule
    rule = Rule(
        name="Test Rule",
        category=EmailCategory.IMPORTANT,
        needs_reply=True,
        conditions={
            "sender": ["@important.com"],
            "subject": ["urgent"]
        }
    )
    
    # Create a matching email
    matching_email = EmailMessage(
        id="match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@important.com", name="Sender"),
        to_addresses=[EmailAddress(email="me@example.com", name="Recipient")],
        subject="This is urgent",
        text_content="Test content",
        date=datetime.fromisoformat("2023-01-01T00:00:00")
    )
    
    # Create a non-matching email
    non_matching_email = EmailMessage(
        id="non-match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@regular.com", name="Sender"),  # Doesn't match @important.com
        to_addresses=[EmailAddress(email="me@example.com", name="Recipient")],
        subject="This is urgent",  # Matches urgent
        text_content="Test content",
        date=datetime.fromisoformat("2023-01-01T00:00:00")
    )
    
    # Test matching
    assert rule.matches(matching_email) is True
    assert rule.matches(non_matching_email) is False