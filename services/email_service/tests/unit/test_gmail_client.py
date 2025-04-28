import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from services.email_service.src.gmail_client import GmailClient
from services.email_service.src.gmail_api_client import GmailApiClient
from services.email_service.src.email_normalizer import EmailNormalizer
from services.email_service.src.content_extractor import EmailContentExtractor
from services.email_service.src.rate_limiter import TokenBucketRateLimiter
from shared.models.email import EmailMessage

class TestGmailClient:
    """Test cases for the GmailClient class."""
    
    @pytest.fixture
    def mock_auth_client(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_rate_limiter(self):
        return AsyncMock(spec=TokenBucketRateLimiter)
    
    @pytest.fixture
    def mock_api_client(self):
        api_client = AsyncMock(spec=GmailApiClient)
        
        # Configure mock responses
        api_client.get_email_list.return_value = (
            [{"id": "msg1"}, {"id": "msg2"}],
            "next_page_token"
        )
        
        api_client.get_email_details.return_value = {
            "id": "msg_detail",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"}
                ]
            }
        }
        
        return api_client
    
    @pytest.fixture
    def mock_content_extractor(self):
        return MagicMock(spec=EmailContentExtractor)
    
    @pytest.fixture
    def mock_normalizer(self):
        normalizer = AsyncMock(spec=EmailNormalizer)
        
        # Configure mock response
        normalizer.normalize_messages.return_value = [
            EmailMessage(
                id="msg1",
                user_id="user123",
                thread_id="thread1",
                subject="Test Email",
                from_email="sender@example.com",
                body_text="Test content"
            ),
            EmailMessage(
                id="msg2",
                user_id="user123",
                thread_id="thread2",
                subject="Another Email",
                from_email="another@example.com",
                body_text="Another test"
            )
        ]
        
        return normalizer
    
    @pytest.fixture
    def gmail_client(self, mock_auth_client, mock_rate_limiter):
        """Create a GmailClient instance with mocked dependencies."""
        client = GmailClient(
            auth_client=mock_auth_client,
            rate_limiter=mock_rate_limiter,
            batch_size=10
        )
        
        # Replace the automatically created components with mocks
        client.api_client = AsyncMock(spec=GmailApiClient)
        client.normalizer = AsyncMock(spec=EmailNormalizer)
        
        return client
    
    @pytest.mark.asyncio
    async def test_get_emails_since(self, gmail_client):
        """Test getting emails since a given date."""
        # Configure mock
        gmail_client.api_client.get_email_list.return_value = (
            [{"id": "msg1"}, {"id": "msg2"}],
            None  # No more pages
        )
        
        # Call method
        since_date = datetime(2025, 4, 1)
        emails = await gmail_client.get_emails_since("user123", since_date)
        
        # Verify results
        assert len(emails) == 2
        assert emails[0]["id"] == "msg1"
        assert emails[1]["id"] == "msg2"
        
        # Verify API call
        gmail_client.api_client.get_email_list.assert_called_once()
        call_args = gmail_client.api_client.get_email_list.call_args[1]
        assert call_args["user_id"] == "user123"
        assert "newer_than" in call_args["query"]
    
    @pytest.mark.asyncio
    async def test_get_all_emails(self, gmail_client):
        """Test getting all emails without date filtering."""
        # Create a simpler test that doesn't rely on pagination
        gmail_client.api_client.get_email_list.return_value = (
            [{"id": "msg1"}, {"id": "msg2"}, {"id": "msg3"}],
            None  # No pagination for simplicity
        )
        
        # Call method
        emails = await gmail_client.get_all_emails("user123", max_emails=5)
        
        # Verify results
        assert len(emails) == 3
        assert emails[0]["id"] == "msg1"
        assert emails[1]["id"] == "msg2"
        assert emails[2]["id"] == "msg3"
    
    @pytest.mark.asyncio
    async def test_normalize_messages(self, gmail_client):
        """Test normalizing Gmail API messages to internal format."""
        # Configure mocks
        gmail_client.api_client.get_email_details.return_value = {
            "id": "msg1",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"}
                ]
            }
        }
        
        # Configure normalizer mock
        test_message = EmailMessage(
            id="msg1",
            user_id="user123",
            subject="Test Subject",
            body_text="Test content",
            from_email="sender@example.com",  # Added required field
            to="recipient@example.com",       # Added required field
            date=datetime.now(),              # Added required field
            thread_id="",
            labels=[],
            snippet="",
            cc="",
            bcc="",
            body_html="",
            has_attachments=False,
            raw_data={}
        )
        gmail_client.normalizer.normalize_messages.return_value = [test_message]
        
        # Test data - message without payload needs to be fetched
        messages = [{"id": "msg1"}]
        
        # Call method
        normalized = await gmail_client.normalize_messages("user123", messages)
        
        # Verify results
        assert len(normalized) == 1
        assert normalized[0].id == "msg1"
        assert normalized[0].subject == "Test Subject"
        
        # Verify API calls
        gmail_client.api_client.get_email_details.assert_called_once_with("user123", "msg1")
        gmail_client.normalizer.normalize_messages.assert_called_once()