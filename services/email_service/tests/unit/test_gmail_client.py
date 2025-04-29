import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from services.email_service.src.gmail_client import GmailClient
from services.email_service.src.gmail_api_client import GmailApiClient
from services.email_service.src.email_normalizer import EmailNormalizer
from services.email_service.src.content_extractor import EmailContentExtractor
from services.email_service.src.rate_limiter import TokenBucketRateLimiter
from shared.models.email import EmailMessage, EmailAddress

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
        """Create a mock content extractor with all required methods."""
        mock = MagicMock(spec=EmailContentExtractor)
        # Ensure extract_content method exists
        mock.extract_content = MagicMock(return_value={
            "text": "Test content", 
            "html": "<p>Test content</p>",
            "attachments": []
        })
        return mock
    
    @pytest.fixture
    def mock_normalizer(self):
        normalizer = AsyncMock(spec=EmailNormalizer)
        
        # Configure mock response with updated field names
        normalizer.normalize_messages.return_value = [
            EmailMessage(
                id="msg1",
                user_id="user123",
                thread_id="thread1",
                subject="Test Email",
                from_address=EmailAddress(email="sender@example.com", name="Sender Name"),
                text_content="Test content",
                date=datetime.now()
            ),
            EmailMessage(
                id="msg2",
                user_id="user123",
                thread_id="thread2",
                subject="Another Email",
                from_address=EmailAddress(email="another@example.com", name="Another Sender"),
                text_content="Another test",
                date=datetime.now()
            )
        ]
        
        return normalizer
    
    @pytest.fixture
    def gmail_client(self, mock_api_client, mock_content_extractor, mock_normalizer):
        """Create a GmailClient instance with properly mocked dependencies."""
        client = GmailClient(
            auth_client=AsyncMock(),  # We don't need this for testing
            rate_limiter=AsyncMock(),  # We don't need this for testing
            batch_size=10
        )
        
        # Replace the automatically created components with our mocks
        client.email_fetcher.api_client = mock_api_client
        client.email_processor.content_extractor = mock_content_extractor
        client.email_processor.normalizer = mock_normalizer
        
        return client
    
    @pytest.mark.asyncio
    async def test_get_emails_since(self, gmail_client, mock_api_client):
        """Test getting emails since a given date."""
        # Configure mock
        mock_api_client.get_email_list.return_value = (
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
        
        # Verify API call - GmailEmailFetcher passes user_id as a positional argument
        mock_api_client.get_email_list.assert_called_once()
        # Extract positional and keyword arguments
        args, kwargs = mock_api_client.get_email_list.call_args
        # First positional argument should be user_id
        assert args[0] == "user123"
        # Query should contain the date format
        assert "after:2025/04/01" in kwargs["query"]
    
    @pytest.mark.asyncio
    async def test_get_all_emails(self, gmail_client, mock_api_client):
        """Test getting all emails without date filtering."""
        # Create a simpler test that doesn't rely on pagination
        mock_api_client.get_email_list.return_value = (
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
    async def test_normalize_messages(self, gmail_client, mock_api_client, mock_content_extractor):
        """Test normalizing Gmail API messages to internal format."""
        # Configure mocks
        detailed_message = {
            "id": "msg1",
            "threadId": "thread1",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Date", "value": "Mon, 25 Apr 2025 12:00:00 +0000"}
                ]
            }
        }
        mock_api_client.get_email_details.return_value = detailed_message
        
        # Configure content extractor mock to return content
        mock_content_extractor.extract_content.return_value = {
            "text": "Test content", 
            "html": "<p>Test content</p>",
            "attachments": []
        }
        
        # Mock the entire email_processor component
        gmail_client.email_processor = AsyncMock()
        gmail_client.email_fetcher = AsyncMock()
        gmail_client.email_fetcher.get_email_details.return_value = detailed_message
        
        # Create test data - message without payload needs to be fetched
        messages = [{"id": "msg1"}]
        
        # Configure email_processor.normalize_messages to return test message
        from shared.models.email import EmailMessage, EmailAddress
        test_message = EmailMessage(
            id="msg1",
            user_id="user123",
            subject="Test Subject",
            text_content="Test content",
            from_address=EmailAddress(email="sender@example.com", name="Sender"),
            to_addresses=[EmailAddress(email="recipient@example.com", name="Recipient")],
            date=datetime.now(),
            thread_id="thread1",
            labels=[],
            html_content="<p>Test content</p>",
            attachments=[],
            raw_data={}
        )
        gmail_client.email_processor.normalize_messages.return_value = [test_message]
        
        # Call method
        normalized = await gmail_client.normalize_messages("user123", messages)
        
        # Verify results
        assert len(normalized) == 1
        assert normalized[0].id == "msg1"
        assert normalized[0].subject == "Test Subject"
        
        # Verify the detailed messages were passed to the email_processor
        expected_detailed_messages = [detailed_message]
        gmail_client.email_processor.normalize_messages.assert_called_once_with("user123", expected_detailed_messages)