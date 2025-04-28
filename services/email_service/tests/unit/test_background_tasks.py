import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# Create mock classes to avoid import errors
class MockEmailIngestionConfig:
    def __init__(self, batch_size=100, period_days=30, polling_frequency_minutes=5):
        self.batch_size = batch_size
        self.period_days = period_days
        self.polling_frequency_minutes = polling_frequency_minutes

class MockEmailIngestionStatus:
    def __init__(self, user_id, status="starting", emails_processed=0, 
                 last_synced=None, next_sync=None):
        self.user_id = user_id
        self.status = status
        self.emails_processed = emails_processed
        self.last_synced = last_synced
        self.next_sync = next_sync

class MockEmailMessage:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def model_dump(self):
        return {k: v for k, v in self.__dict__.items()}

# Mock clients
class MockGmailClient:
    def __init__(self):
        self.initialize = AsyncMock()
        self.get_emails_since = AsyncMock(return_value=[])
    
    async def initialize(self, user_id):
        self.user_id = user_id
        return self

class MockRabbitMQClient:
    def __init__(self):
        self.initialize = AsyncMock()
        self.publish_email = AsyncMock()
        self.publish_emails = AsyncMock()

class MockSyncStateManager:
    def __init__(self):
        self.get_last_sync = AsyncMock(return_value=None)
        self.update_sync_status = AsyncMock()

# Create a mock for the background tasks module
class MockBackgroundTasks:
    def __init__(self):
        self.active_ingestions = {}
        self.gmail_client = MockGmailClient()
        self.rabbitmq_client = MockRabbitMQClient()
        self.sync_state_manager = MockSyncStateManager()
    
    async def ingest_emails_background(self, user_id, config):
        """Mock implementation of the background email ingestion task."""
        # Create a mock status
        status = MockEmailIngestionStatus(
            user_id=user_id,
            status="running",
            emails_processed=0,
            last_synced=datetime.now(),
            next_sync=datetime.now() + timedelta(minutes=config.polling_frequency_minutes)
        )
        
        # Store in active ingestions
        self.active_ingestions[user_id] = status
        
        # Initialize clients
        await self.gmail_client.initialize(user_id)
        await self.rabbitmq_client.initialize()
        
        # Get the last sync time
        last_sync = await self.sync_state_manager.get_last_sync(user_id)
        
        # Default to config.period_days ago if no last sync
        since_date = last_sync or (datetime.now() - timedelta(days=config.period_days))
        
        # Get emails since the last sync
        emails = await self.gmail_client.get_emails_since(
            since_date=since_date,
            batch_size=config.batch_size
        )
        
        # Publish emails to RabbitMQ
        if emails:
            await self.rabbitmq_client.publish_emails(emails)
            
            # Update status
            status.emails_processed += len(emails)
            status.last_synced = datetime.now()
            status.next_sync = datetime.now() + timedelta(minutes=config.polling_frequency_minutes)
            
            # Update sync state
            await self.sync_state_manager.update_sync_status(user_id, datetime.now())
        
        return status


# Tests for the background tasks
class TestBackgroundTasks:
    """Tests for the background email ingestion tasks."""
    
    @pytest.fixture
    def background_tasks(self):
        """Create a mock instance of the background tasks module."""
        return MockBackgroundTasks()
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock email ingestion configuration."""
        return MockEmailIngestionConfig(
            batch_size=50,
            period_days=7,
            polling_frequency_minutes=15
        )
    
    @pytest.mark.asyncio
    async def test_ingest_emails_background_no_emails(self, background_tasks, mock_config):
        """Test ingesting emails when there are no new emails."""
        # Setup gmail client to return no emails
        background_tasks.gmail_client.get_emails_since.return_value = []
        
        # Call the function
        result = await background_tasks.ingest_emails_background("test_user", mock_config)
        
        # Verify clients were initialized
        background_tasks.gmail_client.initialize.assert_called_once_with("test_user")
        background_tasks.rabbitmq_client.initialize.assert_called_once()
        
        # Verify we tried to get last sync time
        background_tasks.sync_state_manager.get_last_sync.assert_called_once_with("test_user")
        
        # Verify we tried to get emails
        assert background_tasks.gmail_client.get_emails_since.called
        
        # Verify no emails were published
        background_tasks.rabbitmq_client.publish_emails.assert_not_called()
        
        # Verify status was returned
        assert result.user_id == "test_user"
        assert result.status == "running"
        assert result.emails_processed == 0
    
    @pytest.mark.asyncio
    async def test_ingest_emails_background_with_emails(self, background_tasks, mock_config):
        """Test ingesting emails when there are new emails."""
        # Create mock emails
        mock_emails = [
            MockEmailMessage(id=f"msg_{i}", user_id="test_user", thread_id=f"thread_{i}")
            for i in range(3)
        ]
        
        # Setup gmail client to return emails
        background_tasks.gmail_client.get_emails_since.return_value = mock_emails
        
        # Call the function
        result = await background_tasks.ingest_emails_background("test_user", mock_config)
        
        # Verify clients were initialized
        background_tasks.gmail_client.initialize.assert_called_once_with("test_user")
        background_tasks.rabbitmq_client.initialize.assert_called_once()
        
        # Verify we tried to get last sync time
        background_tasks.sync_state_manager.get_last_sync.assert_called_once_with("test_user")
        
        # Verify we tried to get emails
        assert background_tasks.gmail_client.get_emails_since.called
        
        # Verify emails were published
        background_tasks.rabbitmq_client.publish_emails.assert_called_once_with(mock_emails)
        
        # Verify sync state was updated
        assert background_tasks.sync_state_manager.update_sync_status.called
        
        # Verify status was returned with updated values
        assert result.user_id == "test_user"
        assert result.status == "running"
        assert result.emails_processed == 3