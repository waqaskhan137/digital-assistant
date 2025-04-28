import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import redis.asyncio as redis
from src.sync_state import SyncStateManager

# Import pytest_asyncio for better fixture support
import pytest_asyncio


class TestSyncStateManager:
    """Test cases for the SyncStateManager class."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client that mimics async behavior."""
        mock = AsyncMock()
        
        # Set up the ping method
        mock.ping = AsyncMock(return_value=True)
        
        # Set up get/set methods
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        
        # Set up close method
        mock.close = AsyncMock(return_value=True)
        
        return mock
    
    @pytest_asyncio.fixture
    async def sync_manager(self, mock_redis):
        """Create a SyncStateManager instance with mocked Redis."""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            manager = SyncStateManager("redis://test:6379/0", key_prefix="test:")
            await manager.initialize()
            yield manager
            await manager.close()
    
    @pytest.mark.asyncio
    async def test_initialize(self, mock_redis):
        """Test initializing the SyncStateManager."""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            manager = SyncStateManager("redis://test:6379/0")
            await manager.initialize()
            
            # Verify Redis connection initialization
            assert manager._initialized is True
            mock_redis.ping.assert_called_once()
            
            # Clean up
            await manager.close()
    
    @pytest.mark.asyncio
    async def test_close(self, sync_manager, mock_redis):
        """Test closing the Redis connection."""
        await sync_manager.close()
        
        # Verify Redis connection closed
        assert sync_manager._initialized is False
        mock_redis.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_key(self, sync_manager):
        """Test generating a Redis key for a user."""
        # Test key generation
        user_id = "test_user"
        key_type = "state"
        
        key = sync_manager._get_user_key(user_id, key_type)
        expected_key = "test:test_user:state"
        
        assert key == expected_key
    
    @pytest.mark.asyncio
    async def test_save_sync_state(self, sync_manager, mock_redis):
        """Test saving synchronization state for a user."""
        user_id = "test_user"
        sync_state = {
            "status": "completed",
            "emails_processed": 100
        }
        
        # Call the method
        result = await sync_manager.save_sync_state(user_id, sync_state)
        
        # Verify result
        assert result is True
        
        # Verify Redis set was called with the correct key and data
        mock_redis.set.assert_called_once()
        args = mock_redis.set.call_args[0]
        assert args[0] == "test:test_user:state"
        
        # Verify the data includes our sync state plus a timestamp
        data = json.loads(args[1])
        assert data["status"] == "completed"
        assert data["emails_processed"] == 100
        assert "last_updated" in data  # Should have a timestamp
    
    @pytest.mark.asyncio
    async def test_get_sync_state(self, sync_manager, mock_redis):
        """Test retrieving synchronization state for a user."""
        user_id = "test_user"
        mock_state = {
            "status": "completed",
            "emails_processed": 100,
            "last_updated": "2025-04-24T10:00:00"
        }
        
        # Set up mock to return our test data
        mock_redis.get.return_value = json.dumps(mock_state)
        
        # Call the method
        result = await sync_manager.get_sync_state(user_id)
        
        # Verify Redis get was called with the correct key
        mock_redis.get.assert_called_once_with("test:test_user:state")
        
        # Verify the result matches our mock data
        assert result == mock_state
    
    @pytest.mark.asyncio
    async def test_save_last_message_id(self, sync_manager, mock_redis):
        """Test saving the last processed message ID."""
        user_id = "test_user"
        message_id = "msg123"
        
        # Call the method
        result = await sync_manager.save_last_message_id(user_id, message_id)
        
        # Verify result
        assert result is True
        
        # Verify Redis set was called with the correct key and data
        mock_redis.set.assert_called_once()
        args = mock_redis.set.call_args[0]
        assert args[0] == "test:test_user:last_message"
        
        # Verify the data includes our message ID plus a timestamp
        data = json.loads(args[1])
        assert data["message_id"] == message_id
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_get_last_message_id(self, sync_manager, mock_redis):
        """Test retrieving the last processed message ID."""
        user_id = "test_user"
        mock_data = {
            "message_id": "msg123",
            "timestamp": "2025-04-24T10:00:00"
        }
        
        # Set up mock to return our test data
        mock_redis.get.return_value = json.dumps(mock_data)
        
        # Call the method
        result = await sync_manager.get_last_message_id(user_id)
        
        # Verify Redis get was called with the correct key
        mock_redis.get.assert_called_once_with("test:test_user:last_message")
        
        # Verify the result matches our mock message ID
        assert result == "msg123"
    
    @pytest.mark.asyncio
    async def test_record_sync_metrics(self, sync_manager, mock_redis):
        """Test recording metrics from a sync operation."""
        user_id = "test_user"
        metrics = {
            "batch_size": 100,
            "total_processed": 500
        }
        
        # Set up mock to return existing metrics
        existing_metrics = [
            {"batch_size": 50, "total_processed": 400, "timestamp": "2025-04-23T10:00:00"}
        ]
        mock_redis.get.return_value = json.dumps(existing_metrics)
        
        # Call the method
        result = await sync_manager.record_sync_metrics(user_id, metrics)
        
        # Verify result
        assert result is True
        
        # Verify Redis operations
        mock_redis.get.assert_called_once_with("test:test_user:metrics")
        mock_redis.set.assert_called_once()
        
        # Verify the data was correctly appended to the existing metrics
        args = mock_redis.set.call_args[0]
        data = json.loads(args[1])
        assert len(data) == 2  # Should now have 2 entries
        assert data[0]["batch_size"] == 50  # First entry from mock
        assert data[1]["batch_size"] == 100  # Our new entry
        assert "timestamp" in data[1]  # Should have a timestamp
    
    @pytest.mark.asyncio
    async def test_get_sync_metrics(self, sync_manager, mock_redis):
        """Test retrieving sync metrics history."""
        user_id = "test_user"
        mock_metrics = [
            {"batch_size": 100, "total_processed": 500, "timestamp": "2025-04-24T10:00:00"},
            {"batch_size": 50, "total_processed": 400, "timestamp": "2025-04-23T10:00:00"}
        ]
        
        # Set up mock to return our test data
        mock_redis.get.return_value = json.dumps(mock_metrics)
        
        # Call the method
        result = await sync_manager.get_sync_metrics(user_id)
        
        # Verify Redis get was called with the correct key
        mock_redis.get.assert_called_once_with("test:test_user:metrics")
        
        # Verify the result matches our mock metrics
        assert result == mock_metrics
    
    @pytest.mark.asyncio
    async def test_calculate_optimal_polling_interval(self, sync_manager):
        """Test calculating optimal polling interval based on email volume."""
        user_id = "test_user"
        
        # Test with high volume
        with patch.object(sync_manager, 'get_sync_metrics', new_callable=AsyncMock) as mock_get_metrics:
            # Mock high volume metrics
            mock_get_metrics.return_value = [
                {"email_count": 60},
                {"email_count": 70},
                {"email_count": 80}
            ]
            
            # Call the method
            interval = await sync_manager.calculate_optimal_polling_interval(user_id)
            
            # Verify high volume polling interval
            assert interval == 2  # 2 minutes for high volume
        
        # Test with medium volume
        with patch.object(sync_manager, 'get_sync_metrics', new_callable=AsyncMock) as mock_get_metrics:
            # Mock medium volume metrics
            mock_get_metrics.return_value = [
                {"email_count": 20},
                {"email_count": 15},
                {"email_count": 25}
            ]
            
            # Call the method
            interval = await sync_manager.calculate_optimal_polling_interval(user_id)
            
            # Verify medium volume polling interval
            assert interval == 5  # 5 minutes for medium volume
        
        # Test with low volume
        with patch.object(sync_manager, 'get_sync_metrics', new_callable=AsyncMock) as mock_get_metrics:
            # Mock low volume metrics
            mock_get_metrics.return_value = [
                {"email_count": 5},
                {"email_count": 8},
                {"email_count": 3}
            ]
            
            # Call the method
            interval = await sync_manager.calculate_optimal_polling_interval(user_id)
            
            # Verify low volume polling interval
            assert interval == 15  # 15 minutes for low volume
    
    @pytest.mark.asyncio
    async def test_set_sync_status(self, sync_manager, mock_redis):
        """Test setting the current sync status for a user."""
        user_id = "test_user"
        status = "running"
        details = {"progress": 50}
        
        # Call the method
        result = await sync_manager.set_sync_status(user_id, status, details)
        
        # Verify result
        assert result is True
        
        # Verify Redis set was called with the correct key and data
        mock_redis.set.assert_called_once()
        args = mock_redis.set.call_args[0]
        assert args[0] == "test:test_user:status"
        
        # Verify the data includes our status plus details and a timestamp
        data = json.loads(args[1])
        assert data["status"] == "running"
        assert data["details"]["progress"] == 50
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_get_sync_status(self, sync_manager, mock_redis):
        """Test retrieving the current sync status for a user."""
        user_id = "test_user"
        mock_status = {
            "status": "running",
            "details": {"progress": 50},
            "timestamp": "2025-04-24T10:00:00"
        }
        
        # Set up mock to return our test data
        mock_redis.get.return_value = json.dumps(mock_status)
        
        # Call the method
        result = await sync_manager.get_sync_status(user_id)
        
        # Verify Redis get was called with the correct key
        mock_redis.get.assert_called_once_with("test:test_user:status")
        
        # Verify the result matches our mock status
        assert result == mock_status
    
    @pytest.mark.asyncio
    async def test_initialize_exception(self):
        """Test handling exception during initialization."""
        # Create mock that raises exception on ping
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection error")
        
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            manager = SyncStateManager("redis://test:6379/0")
            
            # Verify exception is raised
            with pytest.raises(Exception):
                await manager.initialize()
            
            # Verify Redis ping was called
            mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_sync_state_not_initialized(self, mock_redis):
        """Test saving sync state when not initialized calls initialize first."""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            manager = SyncStateManager("redis://test:6379/0")
            # Don't initialize, should auto-initialize when needed
            
            user_id = "test_user"
            sync_state = {"status": "completed"}
            
            # Call method without prior initialization
            await manager.save_sync_state(user_id, sync_state)
            
            # Verify Redis connection was initialized
            mock_redis.ping.assert_called_once()
            mock_redis.set.assert_called_once()