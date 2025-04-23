import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
from datetime import datetime, timedelta
from googleapiclient.errors import HttpError
from src.gmail_client import GmailClient

class TestGmailClient:
    """Test cases for the GmailClient class."""
    
    @pytest.fixture
    def mock_auth_client(self):
        mock = MagicMock()
        mock.get_user_token = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_rate_limiter(self):
        mock = MagicMock()
        mock.acquire_tokens = AsyncMock(return_value=True)
        return mock
    
    @pytest.fixture
    def gmail_client(self, mock_auth_client, mock_rate_limiter):
        client = GmailClient(
            auth_client=mock_auth_client, 
            rate_limiter=mock_rate_limiter,
            batch_size=100
        )
        # Patch the _execute_request method to return the value directly
        client._execute_request = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_gmail_api(self):
        with patch('src.gmail_client.build') as mock_build:
            mock_service = MagicMock()
            mock_users = MagicMock()
            mock_messages = MagicMock()
            
            # Set up the mock chain for Gmail API calls
            mock_build.return_value = mock_service
            mock_service.users.return_value = mock_users
            mock_users.messages.return_value = mock_messages
            
            yield {
                'build': mock_build,
                'service': mock_service,
                'users': mock_users,
                'messages': mock_messages
            }
    
    @pytest.mark.asyncio
    async def test_init(self, gmail_client, mock_auth_client, mock_rate_limiter):
        """Test initializing the Gmail client."""
        assert gmail_client.auth_client == mock_auth_client
        assert gmail_client.rate_limiter == mock_rate_limiter
        assert gmail_client.batch_size == 100
        
    @pytest.mark.asyncio
    async def test_get_email_list(self, gmail_client, mock_auth_client, mock_gmail_api, mock_rate_limiter):
        """Test fetching email list from Gmail API."""
        user_id = "user123"
        query = "is:unread"
        
        # Mock token response
        mock_auth_client.get_user_token.return_value = {
            "access_token": "test_token",
            "token_type": "Bearer"
        }
        
        # Mock Gmail API response
        mock_response = {
            "messages": [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"}
            ],
            "nextPageToken": None
        }
        
        # Set up _execute_request to return our mock response
        gmail_client._execute_request.return_value = mock_response
        
        # Call the method
        emails = await gmail_client.get_email_list(user_id, query)
        
        # Verify results
        assert len(emails) == 2
        assert emails[0]["id"] == "msg1"
        assert emails[1]["id"] == "msg2"
        
        # Verify API calls
        mock_auth_client.get_user_token.assert_called_once_with(user_id)
        mock_rate_limiter.acquire_tokens.assert_called_once()
        mock_gmail_api['build'].assert_called_once_with(
            'gmail', 'v1', credentials=mock_auth_client.get_user_token.return_value
        )
        mock_gmail_api['messages'].list.assert_called_once_with(
            userId=user_id, 
            q=query,
            maxResults=100,
            pageToken=None
        )
    
    @pytest.mark.asyncio
    async def test_get_email_list_pagination(self, gmail_client, mock_auth_client, mock_gmail_api, mock_rate_limiter):
        """Test pagination when fetching email list."""
        user_id = "user123"
        query = "is:unread"
        
        # Mock token response
        mock_auth_client.get_user_token.return_value = {
            "access_token": "test_token",
            "token_type": "Bearer"
        }
        
        # Mock Gmail API responses for first and second pages
        first_page_response = {
            "messages": [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"}
            ],
            "nextPageToken": "page_token_123"
        }
        
        second_page_response = {
            "messages": [
                {"id": "msg3", "threadId": "thread3"},
                {"id": "msg4", "threadId": "thread4"}
            ],
            "nextPageToken": None
        }
        
        # Set up _execute_request to return different responses
        gmail_client._execute_request.side_effect = [
            first_page_response,
            second_page_response
        ]
        
        # Call the method
        emails = await gmail_client.get_email_list(user_id, query)
        
        # Verify results
        assert len(emails) == 4
        assert emails[0]["id"] == "msg1"
        assert emails[3]["id"] == "msg4"
        
        # Verify API calls - should be called twice due to pagination
        assert mock_gmail_api['messages'].list.call_count == 2
        mock_rate_limiter.acquire_tokens.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_email_details(self, gmail_client, mock_auth_client, mock_gmail_api, mock_rate_limiter):
        """Test fetching detailed email content."""
        user_id = "user123"
        message_id = "msg1"
        
        # Mock token response
        mock_auth_client.get_user_token.return_value = {
            "access_token": "test_token",
            "token_type": "Bearer"
        }
        
        # Mock Gmail API response for message details
        mock_response = {
            "id": "msg1",
            "threadId": "thread1",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "Email snippet text...",
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Test Email"},
                    {"name": "Date", "value": "Mon, 23 Apr 2025 10:00:00 -0700"}
                ],
                "body": {"data": "base64_encoded_body"},
                "parts": []
            }
        }
        
        # Set up _execute_request to return our mock response
        gmail_client._execute_request.return_value = mock_response
        
        # Call the method
        email_details = await gmail_client.get_email_details(user_id, message_id)
        
        # Verify results
        assert email_details["id"] == "msg1"
        assert email_details["labelIds"] == ["INBOX", "UNREAD"]
        
        # Verify API calls
        mock_auth_client.get_user_token.assert_called_once_with(user_id)
        mock_rate_limiter.acquire_tokens.assert_called_once()
        mock_gmail_api['messages'].get.assert_called_once_with(
            userId=user_id,
            id=message_id, 
            format='full'
        )
    
    @pytest.mark.asyncio
    async def test_get_emails_since(self, gmail_client, mock_auth_client, mock_gmail_api, mock_rate_limiter):
        """Test fetching emails since a specific timestamp."""
        user_id = "user123"
        since_date = datetime.now() - timedelta(days=7)
        since_timestamp = int(since_date.timestamp())  # Convert to seconds
        
        # Create the expected query with date filter
        expected_query = f"after:{since_timestamp}"
        
        # Mock the get_email_list method
        with patch.object(gmail_client, 'get_email_list', AsyncMock()) as mock_get_email_list:
            mock_get_email_list.return_value = [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"}
            ]
            
            # Call the method
            emails = await gmail_client.get_emails_since(user_id, since_date)
            
            # Verify the get_email_list was called with the correct query
            mock_get_email_list.assert_called_once()
            call_args = mock_get_email_list.call_args[0]
            assert call_args[0] == user_id
            # Verify the query contains the timestamp
            assert f"after:" in call_args[1]
            
            # Verify results
            assert len(emails) == 2
            assert emails[0]["id"] == "msg1"
    
    @pytest.mark.asyncio
    async def test_handle_rate_limit_exception(self, gmail_client, mock_auth_client, mock_gmail_api, mock_rate_limiter):
        """Test handling of rate limit exceptions."""
        user_id = "user123"
        query = "is:unread"
        
        # Mock token response
        mock_auth_client.get_user_token.return_value = {
            "access_token": "test_token",
            "token_type": "Bearer"
        }
        
        # First simulate a rate limit error, then success
        mock_http_error = HttpError(resp=MagicMock(status=429), content=b'Rate limit exceeded')
        
        # Set up _execute_request to first raise an error, then return success
        gmail_client._execute_request.side_effect = [
            mock_http_error,  # First call raises HttpError
            {  # Second call succeeds
                "messages": [
                    {"id": "msg1", "threadId": "thread1"},
                    {"id": "msg2", "threadId": "thread2"}
                ],
                "nextPageToken": None
            }
        ]
        
        # Configure rate limiter behavior for tests
        mock_rate_limiter.acquire_tokens.side_effect = [True, False, True]  # First succeeds, second fails, third succeeds
        
        # We need to patch the sleep function to speed up the test
        with patch('asyncio.sleep', AsyncMock()) as mock_sleep:
            # Call the method
            emails = await gmail_client.get_email_list(user_id, query)
            
            # Verify sleep was called due to rate limiting
            mock_sleep.assert_called()
            
            # Verify results after retrying
            assert len(emails) == 2
            assert emails[0]["id"] == "msg1"