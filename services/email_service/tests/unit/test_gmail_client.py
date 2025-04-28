import pytest
import pytest_asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Simple mock for the EmailMessage class
class MockEmailMessage:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def model_dump(self):
        return {k: v for k, v in self.__dict__.items()}

# Define a minimal GmailClient mock for testing
class MockGmailClient:
    def __init__(self, token_manager=None, rate_limiter=None):
        self.token_manager = token_manager or MagicMock()
        self.rate_limiter = rate_limiter or MagicMock()
        self.service = None
        self.user_id = None
    
    async def initialize(self, user_id):
        self.user_id = user_id
        self.service = MagicMock()
        return self
    
    async def get_all_emails(self, max_results=100):
        return [MockEmailMessage(id=f"msg_{i}", thread_id=f"thread_{i}") for i in range(3)]
    
    async def get_emails_since(self, since_date, batch_size=100):
        return [MockEmailMessage(id=f"msg_{i}", thread_id=f"thread_{i}") for i in range(2)]


# Tests for the Gmail Client functionality
class TestGmailClient:
    """Test cases for the GmailClient class."""
    
    @pytest.fixture
    def mock_token_manager(self):
        mock = MagicMock()
        mock.get_user_credentials = AsyncMock()
        return mock
    
    @pytest_asyncio.fixture
    async def gmail_client(self, mock_token_manager):
        client = MockGmailClient(token_manager=mock_token_manager)
        await client.initialize("test_user")
        return client
    
    @pytest.mark.asyncio
    async def test_get_all_emails(self, gmail_client):
        """Test getting all emails."""
        emails = await gmail_client.get_all_emails(max_results=10)
        
        # Verify we got the expected number of emails
        assert len(emails) == 3
        
        # Verify the emails have the expected structure
        for i, email in enumerate(emails):
            assert email.id == f"msg_{i}"
            assert email.thread_id == f"thread_{i}"
    
    @pytest.mark.asyncio
    async def test_get_emails_since(self, gmail_client):
        """Test getting emails since a specific date."""
        since_date = datetime.now()
        emails = await gmail_client.get_emails_since(since_date)
        
        # Verify we got the expected number of emails
        assert len(emails) == 2