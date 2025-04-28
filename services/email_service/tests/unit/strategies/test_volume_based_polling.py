"""
Tests for the VolumeBasedPollingStrategy

This module contains tests for the volume-based polling strategy implementation
to ensure it correctly calculates polling intervals based on email volume metrics.
"""
import pytest
from services.email_service.src.strategies.volume_based_polling import VolumeBasedPollingStrategy

class TestVolumeBasedPollingStrategy:
    """Tests for the VolumeBasedPollingStrategy class."""
    
    @pytest.fixture
    def strategy(self):
        """Create a VolumeBasedPollingStrategy instance for testing."""
        return VolumeBasedPollingStrategy()
    
    @pytest.mark.asyncio
    async def test_high_volume_polling(self, strategy):
        """Test that high volume metrics result in frequent polling."""
        # Create metrics with high email counts (over 50 per sync)
        metrics = [
            {"email_count": 60, "timestamp": "2025-04-26T10:00:00"},
            {"email_count": 55, "timestamp": "2025-04-26T10:30:00"},
            {"email_count": 70, "timestamp": "2025-04-26T11:00:00"}
        ]
        
        # Calculate polling interval
        interval = await strategy.calculate_polling_interval_minutes(metrics)
        
        # Assert it's using the high volume interval (2 minutes)
        assert interval == strategy.HIGH_VOLUME_INTERVAL
    
    @pytest.mark.asyncio
    async def test_medium_volume_polling(self, strategy):
        """Test that medium volume metrics result in standard polling."""
        # Create metrics with medium email counts (10-49 per sync)
        metrics = [
            {"email_count": 15, "timestamp": "2025-04-26T10:00:00"},
            {"email_count": 25, "timestamp": "2025-04-26T10:30:00"},
            {"email_count": 20, "timestamp": "2025-04-26T11:00:00"}
        ]
        
        # Calculate polling interval
        interval = await strategy.calculate_polling_interval_minutes(metrics)
        
        # Assert it's using the medium volume interval (5 minutes)
        assert interval == strategy.MEDIUM_VOLUME_INTERVAL
    
    @pytest.mark.asyncio
    async def test_low_volume_polling(self, strategy):
        """Test that low volume metrics result in infrequent polling."""
        # Create metrics with low email counts (under 10 per sync)
        metrics = [
            {"email_count": 3, "timestamp": "2025-04-26T10:00:00"},
            {"email_count": 5, "timestamp": "2025-04-26T10:30:00"},
            {"email_count": 2, "timestamp": "2025-04-26T11:00:00"}
        ]
        
        # Calculate polling interval
        interval = await strategy.calculate_polling_interval_minutes(metrics)
        
        # Assert it's using the low volume interval (15 minutes)
        assert interval == strategy.LOW_VOLUME_INTERVAL
    
    @pytest.mark.asyncio
    async def test_empty_metrics(self, strategy):
        """Test handling of empty metrics."""
        # Calculate polling interval with empty metrics
        interval = await strategy.calculate_polling_interval_minutes([])
        
        # Assert it returns the default interval
        assert interval == strategy.DEFAULT_INTERVAL
    
    @pytest.mark.asyncio
    async def test_custom_thresholds(self):
        """Test that custom thresholds are respected."""
        # Create strategy with custom thresholds
        custom_strategy = VolumeBasedPollingStrategy(
            high_volume_threshold=30,  # Lower threshold for high volume
            medium_volume_threshold=5,  # Lower threshold for medium volume
            high_volume_interval=1,     # More frequent polling for high volume
            medium_volume_interval=3,   # More frequent polling for medium volume
            low_volume_interval=10      # More frequent polling for low volume
        )
        
        # Create metrics with counts that would be medium in the default strategy
        # but high in our custom strategy
        metrics = [
            {"email_count": 35, "timestamp": "2025-04-26T10:00:00"},
            {"email_count": 32, "timestamp": "2025-04-26T10:30:00"},
            {"email_count": 40, "timestamp": "2025-04-26T11:00:00"}
        ]
        
        # Calculate polling interval
        interval = await custom_strategy.calculate_polling_interval_minutes(metrics)
        
        # Assert it's using the custom high volume interval (1 minute)
        assert interval == 1