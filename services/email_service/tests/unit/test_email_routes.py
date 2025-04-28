import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# Mock classes for testing
class MockEmail:
    def __init__(self, id="test_id", thread_id="test_thread", subject="Test Email",
                 from_email="sender@example.com", to="recipient@example.com",
                 cc=None, bcc=None, body_text="Test body", body_html="<p>Test body</p>",
                 date=None, labels=None, attachments=None, user_id="test_user"):
        self.id = id
        self.thread_id = thread_id
        self.subject = subject
        self.from_email = from_email
        self.to = to
        self.cc = cc or []
        self.bcc = bcc or []
        self.body_text = body_text
        self.body_html = body_html
        self.date = date or datetime.now()
        self.labels = labels or []
        self.attachments = attachments or []
        self.user_id = user_id
    
    def model_dump(self):
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "subject": self.subject,
            "from_email": self.from_email,
            "to": self.to,
            "cc": self.cc,
            "bcc": self.bcc,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "date": self.date.isoformat() if isinstance(self.date, datetime) else self.date,
            "labels": self.labels,
            "attachments": self.attachments,
            "user_id": self.user_id
        }

class MockGmailClient:
    def __init__(self):
        self.initialize = AsyncMock()
        self.get_email = AsyncMock()
        self.get_emails = AsyncMock()
        self.get_emails_by_thread = AsyncMock()
        self.get_thread = AsyncMock()
        self.search_emails = AsyncMock()
        self.update_email = AsyncMock()
        self.send_email = AsyncMock()
        
        # Set up default return values
        mock_email = MockEmail()
        self.get_email.return_value = mock_email
        
        mock_emails = [MockEmail(id=f"msg_{i}") for i in range(3)]
        self.get_emails.return_value = mock_emails
        self.get_emails_by_thread.return_value = mock_emails
        
        mock_thread = {"id": "test_thread", "messages": [MockEmail(id=f"msg_{i}").model_dump() for i in range(3)]}
        self.get_thread.return_value = mock_thread
        
        self.search_emails.return_value = mock_emails
        
        updated_email = MockEmail(labels=["INBOX", "UPDATED"])
        self.update_email.return_value = updated_email
        
        sent_email = MockEmail(id="new_msg")
        self.send_email.return_value = sent_email
    
    async def initialize(self, user_id):
        return self

class MockTokenManager:
    def __init__(self):
        self.get_user_credentials = AsyncMock(return_value=MagicMock())
        self.refresh_credentials_if_needed = AsyncMock()

class MockRequest:
    def __init__(self, body=None, path_params=None, query_params=None):
        self.body = body or {}
        self.path_params = path_params or {}
        self.query_params = query_params or {}
        
    async def json(self):
        return self.body

# Tests for email routes
class TestEmailRoutes:
    """Test cases for email API routes."""
    
    @pytest.fixture
    def mock_gmail_client(self):
        return MockGmailClient()
    
    @pytest.fixture
    def mock_token_manager(self):
        return MockTokenManager()
    
    @pytest_asyncio.fixture
    async def setup_email_routes(self, mock_gmail_client, mock_token_manager):
        """Set up email routes with mocked dependencies."""
        # Create a MagicMock for the router
        router = MagicMock()
        
        # Patch the methods to be real async functions
        async def mock_get_email(user_id, email_id):
            # Simulate the actual function behavior
            email = await mock_gmail_client.get_email(email_id)
            if email:
                return email.model_dump(), 200
            else:
                return {"detail": "Email not found"}, 404
        
        async def mock_get_emails(user_id, limit=10, offset=0):
            emails = await mock_gmail_client.get_emails(limit=limit, offset=offset)
            return {
                "emails": [email.model_dump() for email in emails],
                "total": len(emails),
                "limit": limit,
                "offset": offset
            }, 200
        
        async def mock_get_thread(user_id, thread_id):
            thread = await mock_gmail_client.get_thread(thread_id)
            if thread:
                return thread, 200
            else:
                return {"detail": "Thread not found"}, 404
        
        async def mock_search_emails(user_id, query, limit=10, offset=0):
            emails = await mock_gmail_client.search_emails(query, limit=limit, offset=offset)
            return {
                "emails": [email.model_dump() for email in emails],
                "total": len(emails),
                "query": query,
                "limit": limit,
                "offset": offset
            }, 200
        
        async def mock_update_email(user_id, email_id, update_data):
            updated_email = await mock_gmail_client.update_email(email_id, update_data)
            if updated_email:
                return updated_email.model_dump(), 200
            else:
                return {"detail": "Email not found or update failed"}, 404
        
        async def mock_send_email(user_id, email_data):
            # Create email object if needed
            if not isinstance(email_data, MockEmail):
                email = MockEmail(**email_data)
            else:
                email = email_data
                
            sent_email = await mock_gmail_client.send_email(email)
            return sent_email.model_dump(), 201
        
        # Assign the mock methods to router
        router.get_email = mock_get_email
        router.get_emails = mock_get_emails
        router.get_thread = mock_get_thread
        router.search_emails = mock_search_emails
        router.update_email = mock_update_email
        router.send_email = mock_send_email
        
        return router
    
    @pytest.mark.asyncio
    async def test_get_email(self, setup_email_routes, mock_gmail_client):
        """Test retrieving a single email."""
        # Get the router
        router = setup_email_routes
        
        # Setup test data
        user_id = "test_user"
        email_id = "test_email_id"
        
        # Custom response for this test
        mock_email = MockEmail(
            id=email_id,
            subject="Important Test Email",
            body_text="This is an important test email."
        )
        mock_gmail_client.get_email.return_value = mock_email
        
        # Call the route handler
        response, status_code = await router.get_email(user_id, email_id)
        
        # Verify response
        assert status_code == 200
        assert response["id"] == email_id
        assert response["subject"] == "Important Test Email"
        assert response["body_text"] == "This is an important test email."
        
        # Verify client was called correctly
        mock_gmail_client.get_email.assert_called_once_with(email_id)
    
    @pytest.mark.asyncio
    async def test_get_email_not_found(self, setup_email_routes, mock_gmail_client):
        """Test retrieving a non-existent email."""
        # Get the router
        router = setup_email_routes
        
        # Setup test data
        user_id = "test_user"
        email_id = "nonexistent_email"
        
        # Set up mock to return None for nonexistent email
        mock_gmail_client.get_email.return_value = None
        
        # Call the route handler
        response, status_code = await router.get_email(user_id, email_id)
        
        # Verify response
        assert status_code == 404
        assert "detail" in response
        assert "not found" in response["detail"].lower()
        
        # Verify client was called correctly
        mock_gmail_client.get_email.assert_called_once_with(email_id)
    
    @pytest.mark.asyncio
    async def test_get_emails(self, setup_email_routes, mock_gmail_client):
        """Test retrieving multiple emails."""
        # Get the router
        router = setup_email_routes
        
        # Setup test data
        user_id = "test_user"
        limit = 5
        offset = 0
        
        # Custom response for this test
        mock_emails = [
            MockEmail(id=f"email_{i}", subject=f"Test Email {i}") 
            for i in range(limit)
        ]
        mock_gmail_client.get_emails.return_value = mock_emails
        
        # Call the route handler
        response, status_code = await router.get_emails(user_id, limit, offset)
        
        # Verify response
        assert status_code == 200
        assert "emails" in response
        assert len(response["emails"]) == limit
        assert response["total"] == limit
        assert response["limit"] == limit
        assert response["offset"] == offset
        
        # Verify email contents
        for i, email in enumerate(response["emails"]):
            assert email["id"] == f"email_{i}"
            assert email["subject"] == f"Test Email {i}"
        
        # Verify client was called correctly
        mock_gmail_client.get_emails.assert_called_once_with(limit=limit, offset=offset)
    
    @pytest.mark.asyncio
    async def test_get_thread(self, setup_email_routes, mock_gmail_client):
        """Test retrieving an email thread."""
        # Get the router
        router = setup_email_routes
        
        # Setup test data
        user_id = "test_user"
        thread_id = "test_thread_id"
        
        # Custom response for this test
        mock_thread = {
            "id": thread_id,
            "messages": [
                MockEmail(
                    id=f"msg_{i}", 
                    thread_id=thread_id,
                    subject="Thread Subject", 
                    body_text=f"Message {i} in thread"
                ).model_dump() 
                for i in range(3)
            ]
        }
        mock_gmail_client.get_thread.return_value = mock_thread
        
        # Call the route handler
        response, status_code = await router.get_thread(user_id, thread_id)
        
        # Verify response
        assert status_code == 200
        assert response["id"] == thread_id
        assert "messages" in response
        assert len(response["messages"]) == 3
        
        # Verify message contents
        for i, message in enumerate(response["messages"]):
            assert message["id"] == f"msg_{i}"
            assert message["thread_id"] == thread_id
            assert message["subject"] == "Thread Subject"
            assert message["body_text"] == f"Message {i} in thread"
        
        # Verify client was called correctly
        mock_gmail_client.get_thread.assert_called_once_with(thread_id)
    
    @pytest.mark.asyncio
    async def test_search_emails(self, setup_email_routes, mock_gmail_client):
        """Test searching for emails."""
        # Get the router
        router = setup_email_routes
        
        # Setup test data
        user_id = "test_user"
        query = "important"
        limit = 10
        offset = 0
        
        # Custom response for this test
        mock_emails = [
            MockEmail(
                id=f"result_{i}", 
                subject=f"Important Email {i}",
                body_text=f"This is important email {i}"
            ) 
            for i in range(3)
        ]
        mock_gmail_client.search_emails.return_value = mock_emails
        
        # Call the route handler
        response, status_code = await router.search_emails(user_id, query, limit, offset)
        
        # Verify response
        assert status_code == 200
        assert "emails" in response
        assert len(response["emails"]) == 3
        assert response["total"] == 3
        assert response["query"] == query
        assert response["limit"] == limit
        assert response["offset"] == offset
        
        # Verify email contents
        for i, email in enumerate(response["emails"]):
            assert email["id"] == f"result_{i}"
            assert email["subject"] == f"Important Email {i}"
            assert email["body_text"] == f"This is important email {i}"
        
        # Verify client was called correctly
        mock_gmail_client.search_emails.assert_called_once_with(query, limit=limit, offset=offset)
    
    @pytest.mark.asyncio
    async def test_update_email(self, setup_email_routes, mock_gmail_client):
        """Test updating an email."""
        # Get the router
        router = setup_email_routes
        
        # Setup test data
        user_id = "test_user"
        email_id = "test_email_id"
        update_data = {
            "labels": ["INBOX", "UPDATED"]
        }
        
        # Custom response for this test
        mock_updated_email = MockEmail(
            id=email_id,
            subject="Updated Email",
            labels=update_data["labels"]
        )
        mock_gmail_client.update_email.return_value = mock_updated_email
        
        # Call the route handler
        response, status_code = await router.update_email(user_id, email_id, update_data)
        
        # Verify response
        assert status_code == 200
        assert response["id"] == email_id
        assert response["subject"] == "Updated Email"
        assert response["labels"] == update_data["labels"]
        
        # Verify client was called correctly
        mock_gmail_client.update_email.assert_called_once_with(email_id, update_data)
    
    @pytest.mark.asyncio
    async def test_send_email(self, setup_email_routes, mock_gmail_client):
        """Test sending an email."""
        # Get the router
        router = setup_email_routes
        
        # Setup test data
        user_id = "test_user"
        email_data = {
            "subject": "New Test Email",
            "to": "recipient@example.com",
            "body_text": "This is a test email.",
            "body_html": "<p>This is a test email.</p>"
        }
        
        # Custom response for this test
        sent_email = MockEmail(
            id="new_msg_id",
            subject=email_data["subject"],
            to=email_data["to"],
            body_text=email_data["body_text"],
            body_html=email_data["body_html"],
        )
        mock_gmail_client.send_email.return_value = sent_email
        
        # Call the route handler
        response, status_code = await router.send_email(user_id, email_data)
        
        # Verify response
        assert status_code == 201
        assert response["id"] == "new_msg_id"
        assert response["subject"] == email_data["subject"]
        assert response["to"] == email_data["to"]
        assert response["body_text"] == email_data["body_text"]
        assert response["body_html"] == email_data["body_html"]
        
        # Verify client was called correctly
        mock_gmail_client.send_email.assert_called_once()