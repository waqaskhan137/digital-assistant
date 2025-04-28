import pytest
from unittest.mock import MagicMock
from datetime import datetime
from services.email_service.src.email_normalizer import EmailNormalizer
from services.email_service.src.content_extractor import EmailContentExtractor
from shared.models.email import EmailMessage

class TestEmailNormalizer:
    """Test cases for the EmailNormalizer class."""
    
    @pytest.fixture
    def mock_content_extractor(self):
        extractor = MagicMock(spec=EmailContentExtractor)
        # Configure the mock to return expected values
        extractor.extract_body.return_value = ("<html>Test</html>", "Test")
        extractor.get_attachments.return_value = []
        return extractor
    
    @pytest.fixture
    def normalizer(self, mock_content_extractor):
        return EmailNormalizer(content_extractor=mock_content_extractor)
    
    def test_normalize_message(self, normalizer, mock_content_extractor):
        """Test normalizing a single message."""
        # Create a test message
        message = {
            "id": "msg123",
            "threadId": "thread123",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "This is a test email",
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Subject", "value": "Test Email"},
                    {"name": "Date", "value": "Mon, 25 Apr 2025 12:00:00 +0000"}
                ]
            }
        }
        
        # Normalize the message
        normalized = normalizer.normalize_message("user123", message)
        
        # Verify the message was properly normalized
        assert isinstance(normalized, EmailMessage)
        assert normalized.id == "msg123"
        assert normalized.user_id == "user123"
        assert normalized.thread_id == "thread123"
        assert normalized.labels == ["INBOX", "UNREAD"]
        assert normalized.snippet == "This is a test email"
        assert normalized.subject == "Test Email"
        assert normalized.from_email == "sender@example.com"
        assert normalized.to == "recipient@example.com"
        assert normalized.body_html == "<html>Test</html>"
        assert normalized.body_text == "Test"
        assert normalized.has_attachments is False
        
        # Verify content extractor was called correctly
        mock_content_extractor.extract_body.assert_called_once_with(message["payload"])
        mock_content_extractor.get_attachments.assert_called_once_with(message["payload"])
    
    def test_normalize_messages(self, normalizer):
        """Test normalizing multiple messages."""
        # Create test messages
        messages = [
            {
                "id": "msg1",
                "threadId": "thread1",
                "labelIds": ["INBOX"],
                "snippet": "Email 1",
                "payload": {"headers": [{"name": "Subject", "value": "Subject 1"}]}
            },
            {
                "id": "msg2",
                "threadId": "thread2",
                "labelIds": ["SENT"],
                "snippet": "Email 2",
                "payload": {"headers": [{"name": "Subject", "value": "Subject 2"}]}
            }
        ]
        
        # Normalize the messages
        normalized = normalizer.normalize_messages("user123", messages)
        
        # Verify results
        assert len(normalized) == 2
        assert normalized[0].id == "msg1"
        assert normalized[0].subject == "Subject 1"
        assert normalized[1].id == "msg2"
        assert normalized[1].subject == "Subject 2"