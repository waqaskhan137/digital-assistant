"""Tests for the enhanced rule-based classifier."""
import json
import pytest
import re
from datetime import datetime
from unittest.mock import patch, mock_open

from src.core import EnhancedRuleBasedClassifier, EnhancedRule, RuleCondition, ConditionOperator
from src.models import EmailCategory, ClassificationResult
from shared.models.email import EmailMessage, EmailAddress


@pytest.mark.asyncio
async def test_enhanced_rule_classifier_initializes_with_default_rules():
    """Test that the enhanced rule classifier initializes with default rules when none are provided."""
    classifier = EnhancedRuleBasedClassifier()
    
    # Verify classifier initialized properly
    assert classifier is not None
    assert classifier.name == "EnhancedRuleBasedClassifier"
    assert len(classifier.rules) > 0
    assert all(isinstance(rule, EnhancedRule) for rule in classifier.rules)


@pytest.mark.asyncio
async def test_enhanced_rule_classifier_loads_rules_from_config():
    """Test that the classifier can load rules from a configuration file."""
    # Mock configuration file content
    mock_config = {
        "rules": [
            {
                "name": "Test Rule",
                "category": "important",
                "needs_reply": True,
                "condition": {
                    "field": "subject",
                    "pattern": "important"
                },
                "confidence": 0.9,
                "priority": 2
            }
        ]
    }
    
    # Mock the open function
    with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
        with patch("os.path.exists", return_value=True):
            classifier = EnhancedRuleBasedClassifier(config_path="fake_path.json")
            
            # Verify rules were loaded correctly
            assert len(classifier.rules) == 1
            assert classifier.rules[0].name == "Test Rule"
            assert classifier.rules[0].category == EmailCategory.IMPORTANT
            assert classifier.rules[0].needs_reply is True


@pytest.mark.asyncio
async def test_simple_condition_matching():
    """Test that a simple condition correctly matches emails."""
    # Create a simple condition
    condition = RuleCondition(field="subject", pattern="test")
    
    # Create a matching email
    matching_email = EmailMessage(
        id="test-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="sender@example.com", name="Sender"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is a test subject",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
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
        subject="This has no match",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Test matching
    assert condition.matches(matching_email) is True
    assert condition.matches(non_matching_email) is False


@pytest.mark.asyncio
async def test_compound_and_condition():
    """Test that an AND compound condition works correctly."""
    # Create an AND condition
    condition = RuleCondition(
        operator=ConditionOperator.AND,
        conditions=[
            RuleCondition(field="sender", pattern="@example.com"),
            RuleCondition(field="subject", pattern="test")
        ]
    )
    
    # Create a matching email (matches both conditions)
    matching_email = EmailMessage(
        id="match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@example.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is a test subject",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Create a partially matching email (matches only one condition)
    partial_match = EmailMessage(
        id="partial-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@example.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This has no match",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Test matching
    assert condition.matches(matching_email) is True
    assert condition.matches(partial_match) is False


@pytest.mark.asyncio
async def test_compound_or_condition():
    """Test that an OR compound condition works correctly."""
    # Create an OR condition
    condition = RuleCondition(
        operator=ConditionOperator.OR,
        conditions=[
            RuleCondition(field="sender", pattern="@example.com"),
            RuleCondition(field="subject", pattern="urgent")
        ]
    )
    
    # Create emails with different match patterns
    email1 = EmailMessage(
        id="email1-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@example.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="Regular subject",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    email2 = EmailMessage(
        id="email2-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@other.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is urgent",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    email3 = EmailMessage(
        id="email3-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@other.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="Regular subject",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Test matching
    assert condition.matches(email1) is True
    assert condition.matches(email2) is True
    assert condition.matches(email3) is False


@pytest.mark.asyncio
async def test_compound_not_condition():
    """Test that a NOT compound condition works correctly."""
    # Create a NOT condition
    condition = RuleCondition(
        operator=ConditionOperator.NOT,
        conditions=[
            RuleCondition(field="sender", pattern="@spam.com")
        ]
    )
    
    # Create a matching email (doesn't match the negated condition)
    matching_email = EmailMessage(
        id="match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@example.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="Regular subject",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Create a non-matching email (matches the negated condition)
    non_matching_email = EmailMessage(
        id="non-match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@spam.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="Regular subject",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Test matching
    assert condition.matches(matching_email) is True
    assert condition.matches(non_matching_email) is False


@pytest.mark.asyncio
async def test_regex_pattern_matching():
    """Test that regex pattern matching works correctly."""
    # Create a condition with regex pattern
    condition = RuleCondition(
        field="subject",
        pattern=re.compile(r".*\b(urgent|important)\b.*", re.IGNORECASE)
    )
    
    # Create test emails
    email1 = EmailMessage(
        id="email1-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@example.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is URGENT please respond",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    email2 = EmailMessage(
        id="email2-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@example.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is important information",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    email3 = EmailMessage(
        id="email3-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@example.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="Regular subject line",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Test matching
    assert condition.matches(email1) is True
    assert condition.matches(email2) is True
    assert condition.matches(email3) is False


@pytest.mark.asyncio
async def test_enhanced_rule_matching():
    """Test that an enhanced rule correctly matches emails."""
    # Create a test rule
    rule = EnhancedRule(
        name="Test Rule",
        category=EmailCategory.IMPORTANT,
        needs_reply=True,
        condition=RuleCondition(
            operator=ConditionOperator.AND,
            conditions=[
                RuleCondition(field="sender", pattern="@example.com"),
                RuleCondition(field="subject", pattern="important")
            ]
        ),
        confidence=0.9,
        priority=2
    )
    
    # Create a matching email
    matching_email = EmailMessage(
        id="match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@example.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is important information",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Create a non-matching email
    non_matching_email = EmailMessage(
        id="non-match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@example.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="Regular information",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Test matching
    assert rule.matches(matching_email) is True
    assert rule.matches(non_matching_email) is False
    
    # Verify statistics were updated
    assert rule.evaluation_count == 2
    assert rule.match_count == 1


@pytest.mark.asyncio
async def test_enhanced_rule_classifier_classify():
    """Test that the enhanced classifier correctly classifies emails."""
    # Create a classifier with a test rule
    classifier = EnhancedRuleBasedClassifier(rules=[
        EnhancedRule(
            name="Test Rule",
            category=EmailCategory.IMPORTANT,
            needs_reply=True,
            condition=RuleCondition(field="subject", pattern="important"),
            confidence=0.9,
            priority=2,
            explanation="Found 'important' in subject"
        )
    ])
    
    # Create a matching email
    matching_email = EmailMessage(
        id="match-id",
        user_id="test-user-id",
        thread_id="thread-id",
        from_address=EmailAddress(email="person@example.com", name="Person"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        subject="This is important information",
        text_content="This is the email body",
        html_content="<p>This is the email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Classify the email
    result = await classifier.classify(matching_email)
    
    # Verify classification result
    assert result is not None
    assert isinstance(result, ClassificationResult)
    assert result.category == EmailCategory.IMPORTANT
    assert result.needs_reply is True
    assert result.confidence == 0.9
    assert result.priority == 2
    assert result.email_id == matching_email.id
    assert "Found 'important' in subject" in result.explanation


@pytest.mark.asyncio
async def test_rule_statistics():
    """Test that rule statistics are tracked and reported correctly."""
    # Create a rule
    rule = EnhancedRule(
        name="Test Rule",
        category=EmailCategory.IMPORTANT,
        needs_reply=True,
        condition=RuleCondition(field="subject", pattern="important"),
        confidence=0.9,
        priority=2
    )
    
    # Create emails
    match1 = EmailMessage(
        id="match1-id",
        user_id="test-user-id",
        subject="This is important",
        from_address=EmailAddress(email="test@example.com", name="Test"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        text_content="Email body",
        html_content="<p>Email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    match2 = EmailMessage(
        id="match2-id",
        user_id="test-user-id",
        subject="Another important email",
        from_address=EmailAddress(email="test@example.com", name="Test"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        text_content="Email body",
        html_content="<p>Email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    non_match = EmailMessage(
        id="non-match-id",
        user_id="test-user-id",
        subject="Regular email",
        from_address=EmailAddress(email="test@example.com", name="Test"),
        to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
        text_content="Email body",
        html_content="<p>Email body</p>",
        date=datetime.fromisoformat("2023-01-01T00:00:00"),
        labels=["INBOX"],
        attachments=[]
    )
    
    # Test matching multiple times
    rule.matches(match1)
    rule.matches(match2)
    rule.matches(non_match)
    
    # Verify statistics
    assert rule.evaluation_count == 3
    assert rule.match_count == 2
    
    # Create a classifier with this rule
    classifier = EnhancedRuleBasedClassifier(rules=[rule])
    
    # Get statistics
    stats = classifier.get_rule_statistics()
    
    # Verify statistics in the report
    assert len(stats) == 1
    assert stats[0]["name"] == "Test Rule"
    assert stats[0]["match_count"] == 2
    assert stats[0]["evaluation_count"] == 3
    assert stats[0]["match_rate"] == 2/3