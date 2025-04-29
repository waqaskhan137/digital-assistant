"""Tests for the rule-based classifier."""
import json
import os
import pytest
from datetime import datetime
from unittest.mock import patch, mock_open

from src.core import RuleBasedClassifier, Rule
from src.models import EmailCategory, ClassificationResult
from shared.models.email import EmailMessage, EmailAddress


@pytest.mark.asyncio
async def test_classifier_load_rules_from_file():
    """Test that the classifier loads rules from a file."""
    # Skip this test since RuleBasedClassifier no longer supports loading from file directly
    pytest.skip("RuleBasedClassifier no longer supports loading from file directly")
    
    # Note: The EnhancedRuleBasedClassifier supports loading from config files
    # This test should be rewritten to test that functionality instead


@pytest.mark.asyncio
async def test_rule_matching():
    """Test that rules correctly match emails."""
    # Create a test rule
    rule = Rule(
        name="Test Rule",
        category=EmailCategory.IMPORTANT,
        needs_reply=True,
        conditions={"subject": ["important"]},
        priority=2
    )
    
    # Create a matching email
    matching_email = EmailMessage(
        id="match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="sender@example.com", name="Sender"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is an important email",
        text_content="This is the body text",
        html_content="<p>This is the body text</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Create a non-matching email
    non_matching_email = EmailMessage(
        id="non-match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="sender@example.com", name="Sender"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is a regular email",
        text_content="This is the body text",
        html_content="<p>This is the body text</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Test matching
    assert rule.matches(matching_email) is True
    assert rule.matches(non_matching_email) is False


@pytest.mark.asyncio
async def test_classifier_classify():
    """Test that the classifier correctly classifies emails."""
    # Create a classifier with a test rule
    classifier = RuleBasedClassifier(rules=[
        Rule(
            name="Important Rule",
            category=EmailCategory.IMPORTANT,
            needs_reply=True,
            conditions={"subject": ["important"]},
            priority=2
        )
    ])
    
    # Create a matching email
    matching_email = EmailMessage(
        id="match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="sender@example.com", name="Sender"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is an important email",
        text_content="This is the body text",
        html_content="<p>This is the body text</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Create a non-matching email
    non_matching_email = EmailMessage(
        id="non-match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="sender@example.com", name="Sender"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is a regular email",
        text_content="This is the body text",
        html_content="<p>This is the body text</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Classify the matching email
    result = await classifier.classify(matching_email)
    
    # Verify classification result
    assert result is not None
    assert isinstance(result, ClassificationResult)
    assert result.category == EmailCategory.IMPORTANT
    assert result.needs_reply is True
    assert result.priority == 2
    assert result.email_id == matching_email.id
    assert "important rule" in result.explanation.lower()
    
    # Classify the non-matching email
    result = await classifier.classify(non_matching_email)
    
    # Verify classification result for non-matching email
    assert result is not None
    assert result.category == EmailCategory.UNCATEGORIZED
    assert "No specific rule matched" in result.explanation


@pytest.mark.asyncio
async def test_classifier_multiple_matching_rules():
    """Test that the classifier returns the first matching rule when multiple rules could match."""
    # Create a classifier with multiple rules
    classifier = RuleBasedClassifier(rules=[
        Rule(
            name="Important Rule",
            category=EmailCategory.IMPORTANT,
            needs_reply=True,
            conditions={"subject": ["email"]},
            priority=1
        ),
        Rule(
            name="Urgent Rule",
            category=EmailCategory.URGENT,
            needs_reply=True,
            conditions={"subject": ["important"]},
            priority=3
        )
    ])
    
    # Create an email that could match both rules
    email = EmailMessage(
        id="multi-match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="sender@example.com", name="Sender"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is an important email",
        text_content="This is the body text",
        html_content="<p>This is the body text</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Classify the email
    result = await classifier.classify(email)
    
    # Verify the first matching rule was chosen - in this case "Important Rule" since it's first in the list
    # The RuleBasedClassifier doesn't actually sort by priority, it returns the first match
    assert result is not None
    assert result.category == EmailCategory.IMPORTANT
    assert result.priority == 1
    assert "important rule" in result.explanation.lower()


@pytest.mark.asyncio
async def test_classifier_field_matching():
    """Test that rules correctly match different email fields."""
    # Create a classifier with rules for different fields
    classifier = RuleBasedClassifier(rules=[
        Rule(
            name="Subject Rule",
            category=EmailCategory.IMPORTANT,
            needs_reply=True,
            conditions={"subject": ["important"]},
            priority=1
        ),
        Rule(
            name="Body Rule",
            category=EmailCategory.URGENT,
            needs_reply=True,
            conditions={"body": ["urgent"]},
            priority=2
        ),
        Rule(
            name="Sender Rule",
            category=EmailCategory.IMPORTANT,
            needs_reply=True,
            conditions={"sender": ["boss@example.com"]},
            priority=3
        )
    ])
    
    # Create test emails for each rule
    subject_email = EmailMessage(
        id="subject-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="sender@example.com", name="Sender"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is an important email",
        text_content="This is the body text",
        html_content="<p>This is the body text</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    body_email = EmailMessage(
        id="body-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="sender@example.com", name="Sender"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="Regular subject",
        text_content="This matter is urgent and needs attention",
        html_content="<p>This matter is urgent and needs attention</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    sender_email = EmailMessage(
        id="sender-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="boss@example.com", name="Boss"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="Regular subject",
        text_content="Regular body text",
        html_content="<p>Regular body text</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Classify and verify each email
    result1 = await classifier.classify(subject_email)
    assert result1 is not None
    assert result1.category == EmailCategory.IMPORTANT
    assert "subject rule" in result1.explanation.lower()
    
    result2 = await classifier.classify(body_email)
    assert result2 is not None
    assert result2.category == EmailCategory.URGENT
    assert "body rule" in result2.explanation.lower()
    
    result3 = await classifier.classify(sender_email)
    assert result3 is not None
    assert result3.category == EmailCategory.IMPORTANT
    assert "sender rule" in result3.explanation.lower()