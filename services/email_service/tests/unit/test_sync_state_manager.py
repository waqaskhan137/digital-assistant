"""
Tests for the SyncStateManager with polling strategy implementations.

This module tests that the SyncStateManager correctly uses the Strategy pattern
to calculate polling intervals based on different strategies.
"""
import pytest
import pytest_asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from services.email_service.src.sync_state import SyncStateManager
from services.email_service.src.interfaces.polling_strategy import PollingStrategy
from services.email_service.src.strategies.volume_based_polling import VolumeBasedPollingStrategy
from services.email_service.src.strategies.time_based_polling import TimeBasedPollingStrategy
from services.email_service.src.strategies.hybrid_polling import HybridPollingStrategy

class MockStrategy(PollingStrategy):
    """Mock strategy for testing."""
    
    def __init__(self, interval):
        self.interval = interval
        self.called_with = None
    
    async def calculate_polling_interval_minutes(self, metrics):
        """Return a fixed interval for testing."""
        self.called_with = metrics
        return self.interval

class TestSyncStateManager:
    """Tests for the SyncStateManager class with strategy pattern."""
    
    @pytest_asyncio.fixture
    async def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get.return_value = None
        redis.set.return_value = True
        redis.ping.return_value = True
        return redis
    
    @pytest_asyncio.fixture
    async def sync_manager(self, mock_redis):
        """Create a SyncStateManager with a mock Redis client."""
        # Create manager with a mock strategy
        mock_strategy = MockStrategy(interval=7)
        manager = SyncStateManager(
            redis_url="redis://localhost:6379",
            polling_strategy=mock_strategy
        )
        
        # Replace Redis with our mock
        manager._redis = mock_redis
        manager._initialized = True
        
        return manager
    
    @pytest.mark.asyncio
    async def test_default_strategy(self):
        """Test that the manager uses VolumeBasedPollingStrategy by default."""
        manager = SyncStateManager(redis_url="redis://localhost:6379")
        
        # Verify the default strategy type
        assert isinstance(manager.polling_strategy, VolumeBasedPollingStrategy)
    
    @pytest.mark.asyncio
    async def test_custom_strategy(self):
        """Test that the manager accepts a custom strategy."""
        # Test with each strategy type
        time_strategy = TimeBasedPollingStrategy()
        manager = SyncStateManager(
            redis_url="redis://localhost:6379",
            polling_strategy=time_strategy
        )
        
        assert manager.polling_strategy is time_strategy
        
        # Test with hybrid strategy
        hybrid_strategy = HybridPollingStrategy()
        manager = SyncStateManager(
            redis_url="redis://localhost:6379",
            polling_strategy=hybrid_strategy
        )
        
        assert manager.polling_strategy is hybrid_strategy
    
    @pytest.mark.asyncio
    async def test_calculate_optimal_polling_interval(self, sync_manager, mock_redis):
        """Test that calculate_optimal_polling_interval uses the strategy."""
        # Setup mock to return metrics
        metrics = [
            {"email_count": 50, "timestamp": "2025-04-28T10:00:00"}
        ]
        mock_redis.get.return_value = json.dumps(metrics)
        
        # Call the method
        interval = await sync_manager.calculate_optimal_polling_interval_minutes("user123")
        
        # Verify the strategy was used with the correct metrics
        assert isinstance(sync_manager.polling_strategy, MockStrategy)
        assert sync_manager.polling_strategy.called_with == metrics
        assert interval == 7  # The mock strategy always returns 7
    
    @pytest.mark.asyncio
    async def test_calculate_interval_with_no_metrics(self, sync_manager, mock_redis):
        """Test interval calculation with no metrics."""
        # Setup mock to return empty metrics
        mock_redis.get.return_value = json.dumps([])
        
        # Call the method
        interval = await sync_manager.calculate_optimal_polling_interval_minutes("user123")
        
        # Verify default value is used
        assert interval == 5  # Default value from the code
    
    @pytest.mark.asyncio
    async def test_record_and_retrieve_metrics(self, sync_manager, mock_redis):
        """Test recording and retrieving metrics used for polling decisions."""
        user_id = "test_user"
        
        # Mock existing metrics
        existing_metrics = [
            {"email_count": 20, "timestamp": "2025-04-28T09:00:00"}
        ]
        mock_redis.get.return_value = json.dumps(existing_metrics)
        
        # Record new metrics
        new_metrics = {"email_count": 30, "duration_seconds": 5}
        await sync_manager.record_sync_metrics(user_id, new_metrics)
        
        # Verify Redis was called correctly
        call_args = mock_redis.set.call_args[0]
        assert call_args[0] == f"email_sync:{user_id}:metrics"
        
        # The metrics should now include both old and new
        saved_metrics = json.loads(call_args[1])
        assert len(saved_metrics) == 2
        assert saved_metrics[0]["email_count"] == 20
        assert saved_metrics[1]["email_count"] == 30
        
        # New metrics should have a timestamp
        assert "timestamp" in saved_metrics[1]