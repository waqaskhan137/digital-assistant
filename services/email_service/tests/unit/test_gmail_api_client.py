import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from services.email_service.src.gmail_api_client import GmailApiClient
from services.email_service.src.rate_limiter import TokenBucketRateLimiter

class TestGmailApiClient:
    """Test cases for the GmailApiClient class."""
    
    @pytest.fixture
    def mock_auth_client(self):
        auth_client = AsyncMock()
        auth_client.get_user_token.return_value = {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        return auth_client
    
    @pytest.fixture
    def mock_rate_limiter(self):
        rate_limiter = AsyncMock(spec=TokenBucketRateLimiter)
        rate_limiter.acquire_tokens.return_value = True
        return rate_limiter
    
    @pytest.fixture
    def api_client(self, mock_auth_client, mock_rate_limiter):
        return GmailApiClient(
            auth_client=mock_auth_client,
            rate_limiter=mock_rate_limiter,
            batch_size=10,
            max_retries=2,
            retry_delay=0.1
        )
    
    @pytest.mark.asyncio
    @patch('services.email_service.src.gmail_api_client.build')
    @patch('services.email_service.src.gmail_api_client.convert_token_to_credentials')
    async def test_get_email_list(self, mock_convert_creds, mock_build, api_client, mock_auth_client):
        """Test getting a list of emails."""
        # Set up mocks
        mock_credentials = MagicMock()
        mock_convert_creds.return_value = mock_credentials
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_users = MagicMock()
        mock_service.users.return_value = mock_users
        
        mock_messages = MagicMock()
        mock_users.messages.return_value = mock_messages
        
        mock_list = MagicMock()
        mock_messages.list.return_value = mock_list
        
        # Set up mock response
        mock_list.execute.return_value = {
            "messages": [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"}
            ],
            "nextPageToken": "token123"
        }
        
        # Call the method
        messages, next_page_token = await api_client.get_email_list(
            user_id="user123",
            query="is:unread",
            page_token="pageToken"
        )
        
        # Verify results
        assert len(messages) == 2
        assert messages[0]["id"] == "msg1"
        assert messages[1]["id"] == "msg2"
        assert next_page_token == "token123"
        
        # Verify API calls
        mock_auth_client.get_user_token.assert_called_once_with("user123")
        mock_convert_creds.assert_called_once()
        mock_build.assert_called_once_with('gmail', 'v1', credentials=mock_credentials)
        
        mock_messages.list.assert_called_once_with(
            userId='me',
            q="is:unread",
            maxResults=10,
            pageToken="pageToken"
        )
    
    @pytest.mark.asyncio
    @patch('services.email_service.src.gmail_api_client.build')
    @patch('services.email_service.src.gmail_api_client.convert_token_to_credentials')
    async def test_get_email_details(self, mock_convert_creds, mock_build, api_client):
        """Test getting details for a specific email."""
        # Set up mocks
        mock_credentials = MagicMock()
        mock_convert_creds.return_value = mock_credentials
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        mock_users = MagicMock()
        mock_service.users.return_value = mock_users
        
        mock_messages = MagicMock()
        mock_users.messages.return_value = mock_messages
        
        mock_get = MagicMock()
        mock_messages.get.return_value = mock_get
        
        # Set up mock response
        mock_email_details = {
            "id": "msg123",
            "threadId": "thread123",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Email"}
                ]
            }
        }
        mock_get.execute.return_value = mock_email_details
        
        # Call the method
        result = await api_client.get_email_details("user123", "msg123")
        
        # Verify results
        assert result == mock_email_details
        
        # Verify API calls
        mock_messages.get.assert_called_once_with(
            userId='me',
            id='msg123',
            format='full'
        )