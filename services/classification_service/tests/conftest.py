"""Test fixtures for classification service tests."""
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

import pytest
from pytest_mock import MockerFixture

from shared.models.email import EmailMessage, EmailAttachment, EmailAddress

from src.core import Rule, RuleBasedClassifier
from src.models import EmailCategory


# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


@pytest.fixture
def sample_email() -> EmailMessage:
    """Create a sample email for testing."""
    return EmailMessage(
        id="test-message-id-123",
        user_id="test-user-id",
        thread_id="test-thread-id-456",
        from_address=EmailAddress(email="test.sender@example.com", name="Test Sender"),
        to_addresses=[EmailAddress(email="test.recipient@example.com", name="Test Recipient")],
        subject="Test Subject Line",
        text_content="This is a test email body text.",
        html_content="<p>This is a test email body HTML.</p>",
        date=datetime.fromisoformat("2023-11-15T12:34:56"),
        labels=["INBOX"],
        attachments=[]
    )


@pytest.fixture
def sample_support_email() -> EmailMessage:
    """Create a sample support email for testing."""
    return EmailMessage(
        id="support-message-id-123",
        user_id="test-user-id",
        thread_id="support-thread-id-456",
        from_address=EmailAddress(email="customer@example.com", name="Customer"),
        to_addresses=[EmailAddress(email="support@ourcompany.com", name="Support")],
        subject="Help with my account issue",
        text_content="I need help with my account. It's not working properly.",
        html_content="<p>I need help with my account. It's not working properly.</p>",
        date=datetime.fromisoformat("2023-11-15T12:34:56"),
        labels=["INBOX"],
        attachments=[]
    )


@pytest.fixture
def sample_rules() -> List[Rule]:
    """Create a list of sample rules for testing."""
    return [
        Rule(
            name="Test Support Rule",
            category=EmailCategory.SUPPORT,
            needs_reply=True,
            conditions={"subject": ["help", "support", "issue"]},
            confidence=0.9,
            priority=2,
            explanation="Test support rule matched"
        ),
        Rule(
            name="Test Spam Rule",
            category=EmailCategory.SPAM,
            needs_reply=False,
            conditions={"subject": ["viagra", "lottery", "winner"]},
            confidence=0.8,
            explanation="Test spam rule matched"
        )
    ]


@pytest.fixture
def rule_classifier(sample_rules) -> RuleBasedClassifier:
    """Create a rule-based classifier with test rules."""
    return RuleBasedClassifier(rules=sample_rules)


@pytest.fixture
def mock_aio_pika(mocker: MockerFixture):
    """Mock the aio_pika module for testing."""
    # Create mock connection
    mock_connection = mocker.AsyncMock()
    
    # Create a custom mock for add_close_callback that properly handles async callbacks
    # This prevents the "coroutine was never awaited" warnings
    def mock_add_close_callback(callback):
        # Store the callback without calling it
        mock_connection._stored_callback = callback
        # Return nothing as the real method would
        return None
    
    # Replace the mock's add_close_callback with our custom function
    mock_connection.add_close_callback = mock_add_close_callback
    
    # Create mock channel
    mock_channel = mocker.AsyncMock()
    mock_connection.channel.return_value = mock_channel
    
    # Create mock queue
    mock_queue = mocker.AsyncMock()
    mock_channel.declare_queue.return_value = mock_queue
    
    # Create mock for aio_pika.connect_robust
    mock_connect = mocker.patch("aio_pika.connect_robust", autospec=True)
    mock_connect.return_value = mock_connection
    
    return {
        "connect": mock_connect,
        "connection": mock_connection,
        "channel": mock_channel,
        "queue": mock_queue
    }


@pytest.fixture
def mock_message(mocker: MockerFixture, sample_email: EmailMessage):
    """Create a mock RabbitMQ message."""
    message = mocker.AsyncMock()
    
    # Convert the sample email to JSON using the custom encoder
    message.body = json.dumps(sample_email.model_dump(), cls=DateTimeEncoder).encode()
    message.message_id = "test-message-id"
    
    # Create a proper async context manager
    process_context = mocker.AsyncMock()
    process_manager = mocker.AsyncMock()
    process_manager.__aenter__ = mocker.AsyncMock(return_value=process_context)
    process_manager.__aexit__ = mocker.AsyncMock(return_value=None)
    message.process.return_value = process_manager
    
    return message