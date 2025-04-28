"""
Tests for the HybridPollingStrategy

This module contains tests for the hybrid polling strategy implementation
to ensure it correctly combines volume-based and time-based approaches.
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from services.email_service.src.strategies.hybrid_polling import HybridPollingStrategy
from services.email_service.src.strategies.volume_based_polling import VolumeBasedPollingStrategy
from services.email_service.src.strategies.time_based_polling import TimeBasedPollingStrategy

class TestHybridPollingStrategy:
    """Tests for the HybridPollingStrategy class."""
    
    @pytest.fixture
    def volume_strategy(self):
        """Create a VolumeBasedPollingStrategy instance for testing."""
        return VolumeBasedPollingStrategy(
            high_volume_interval=1,    # 1 minute
            medium_volume_interval=5,  # 5 minutes 
            low_volume_interval=10     # 10 minutes
        )
    
    @pytest.fixture
    def time_strategy(self):
        """Create a TimeBasedPollingStrategy instance for testing."""
        return TimeBasedPollingStrategy(
            business_hours_interval=2,   # 2 minutes
            evening_hours_interval=6,    # 6 minutes
            night_hours_interval=12      # 12 minutes
        )
    
    @pytest.fixture
    def hybrid_strategy(self, volume_strategy, time_strategy):
        """Create a HybridPollingStrategy instance for testing."""
        return HybridPollingStrategy(
            volume_strategy=volume_strategy,
            time_strategy=time_strategy,
            business_hours_preference="shorter",
            off_hours_preference="longer"
        )
    
    @pytest.mark.asyncio
    @patch('services.email_service.src.strategies.time_based_polling.datetime')
    @patch('services.email_service.src.strategies.hybrid_polling.datetime')
    async def test_business_hours_shorter_interval(self, hybrid_mock_datetime, time_mock_datetime, hybrid_strategy):
        """Test that during business hours it uses the shorter interval."""
        # Mock datetime to return a business hours time (e.g., 10 AM)
        mock_now = MagicMock()
        mock_now.hour = 10  # 10 AM
        hybrid_mock_datetime.now.return_value = mock_now
        time_mock_datetime.now.return_value = mock_now
        
        # Create metrics for high volume (volume interval would be 1 min)
        # During business hours (time interval would be 2 min)
        # With "shorter" preference, should pick 1 min (from volume)
        metrics = [
            {"email_count": 60, "timestamp": "2025-04-26T10:00:00"}
        ]
        
        # Calculate polling interval
        interval = await hybrid_strategy.calculate_polling_interval_minutes(metrics)
        
        # Assert it's using the shorter interval (1 minute from volume strategy)
        assert interval == 1
    
    @pytest.mark.asyncio
    @patch('services.email_service.src.strategies.time_based_polling.datetime')
    @patch('services.email_service.src.strategies.hybrid_polling.datetime')
    async def test_off_hours_longer_interval(self, hybrid_mock_datetime, time_mock_datetime, hybrid_strategy):
        """Test that during off hours it uses the longer interval."""
        # Mock datetime to return a night hours time (e.g., 3 AM)
        mock_now = MagicMock()
        mock_now.hour = 3  # 3 AM
        hybrid_mock_datetime.now.return_value = mock_now
        time_mock_datetime.now.return_value = mock_now
        
        # Create metrics for medium volume (volume interval would be 5 min)
        # During night hours (time interval would be 12 min)
        # With "longer" preference, should pick 12 min (from time)
        metrics = [
            {"email_count": 20, "timestamp": "2025-04-26T03:00:00"}
        ]
        
        # Calculate polling interval
        interval = await hybrid_strategy.calculate_polling_interval_minutes(metrics)
        
        # Assert it's using the longer interval (12 minutes from time strategy)
        assert interval == 12
    
    @pytest.mark.asyncio
    @patch('services.email_service.src.strategies.time_based_polling.datetime')
    @patch('services.email_service.src.strategies.hybrid_polling.datetime')
    async def test_custom_preferences(self, hybrid_mock_datetime, time_mock_datetime, volume_strategy, time_strategy):
        """Test that custom preferences are respected."""
        # Create strategy with opposite preferences
        opposite_strategy = HybridPollingStrategy(
            volume_strategy=volume_strategy,
            time_strategy=time_strategy,
            business_hours_preference="longer",  # Normally "shorter"
            off_hours_preference="shorter"       # Normally "longer"
        )
        
        # Mock datetime to return a business hours time
        mock_now = MagicMock()
        mock_now.hour = 10  # 10 AM
        hybrid_mock_datetime.now.return_value = mock_now
        time_mock_datetime.now.return_value = mock_now
        
        # Create metrics for high volume (volume interval would be 1 min)
        # During business hours (time interval would be 2 min)
        # With "longer" preference, should pick 2 min (from time)
        metrics = [
            {"email_count": 60, "timestamp": "2025-04-26T10:00:00"}
        ]
        
        # Calculate polling interval
        interval = await opposite_strategy.calculate_polling_interval_minutes(metrics)
        
        # Assert it's using the longer interval (2 minutes from time strategy)
        assert interval == 2
    
    @pytest.mark.asyncio
    async def test_invalid_preference_value(self):
        """Test that invalid preference values raise ValueError."""
        with pytest.raises(ValueError):
            # Should raise ValueError for invalid business_hours_preference
            HybridPollingStrategy(
                business_hours_preference="invalid",
                off_hours_preference="longer"
            )