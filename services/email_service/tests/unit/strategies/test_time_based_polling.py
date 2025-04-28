"""
Tests for the TimeBasedPollingStrategy

This module contains tests for the time-based polling strategy implementation
to ensure it correctly calculates polling intervals based on time of day.
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from services.email_service.src.strategies.time_based_polling import TimeBasedPollingStrategy

class TestTimeBasedPollingStrategy:
    """Tests for the TimeBasedPollingStrategy class."""
    
    @pytest.fixture
    def strategy(self):
        """Create a TimeBasedPollingStrategy instance for testing."""
        return TimeBasedPollingStrategy()
    
    @pytest.mark.asyncio
    @patch('services.email_service.src.strategies.time_based_polling.datetime')
    async def test_business_hours_polling(self, mock_datetime, strategy):
        """Test that business hours result in frequent polling."""
        # Mock datetime to return a business hours time (e.g., 10 AM)
        mock_now = MagicMock()
        mock_now.hour = 10  # 10 AM
        mock_datetime.now.return_value = mock_now
        
        # Calculate polling interval (metrics don't matter for this strategy)
        interval = await strategy.calculate_polling_interval_minutes([])
        
        # Assert it's using the business hours interval (3 minutes)
        assert interval == strategy.BUSINESS_HOURS_INTERVAL
    
    @pytest.mark.asyncio
    @patch('services.email_service.src.strategies.time_based_polling.datetime')
    async def test_evening_hours_polling(self, mock_datetime, strategy):
        """Test that evening hours result in standard polling."""
        # Mock datetime to return an evening time (e.g., 7 PM = 19 hours)
        mock_now = MagicMock()
        mock_now.hour = 19  # 7 PM
        mock_datetime.now.return_value = mock_now
        
        # Calculate polling interval
        interval = await strategy.calculate_polling_interval_minutes([])
        
        # Assert it's using the evening hours interval (10 minutes)
        assert interval == strategy.EVENING_HOURS_INTERVAL
    
    @pytest.mark.asyncio
    @patch('services.email_service.src.strategies.time_based_polling.datetime')
    async def test_night_hours_polling(self, mock_datetime, strategy):
        """Test that night hours result in infrequent polling."""
        # Mock datetime to return a night time (e.g., 3 AM)
        mock_now = MagicMock()
        mock_now.hour = 3  # 3 AM
        mock_datetime.now.return_value = mock_now
        
        # Calculate polling interval
        interval = await strategy.calculate_polling_interval_minutes([])
        
        # Assert it's using the night hours interval (20 minutes)
        assert interval == strategy.NIGHT_HOURS_INTERVAL
    
    @pytest.mark.asyncio
    @patch('services.email_service.src.strategies.time_based_polling.datetime')
    async def test_custom_hours(self, mock_datetime):
        """Test that custom hours settings are respected."""
        # Create strategy with custom hours and intervals
        custom_strategy = TimeBasedPollingStrategy(
            business_hours_start=8,     # Start business hours at 8 AM
            business_hours_end=16,      # End business hours at 4 PM
            evening_hours_end=22,       # End evening hours at 10 PM
            business_hours_interval=2,  # More frequent polling in business hours
            evening_hours_interval=7,   # Custom evening interval
            night_hours_interval=15     # Less frequent polling at night
        )
        
        # Mock datetime to return a time that would be business hours in the custom strategy
        mock_now = MagicMock()
        mock_now.hour = 8  # 8 AM
        mock_datetime.now.return_value = mock_now
        
        # Calculate polling interval
        interval = await custom_strategy.calculate_polling_interval_minutes([])
        
        # Assert it's using the custom business hours interval (2 minutes)
        assert interval == 2