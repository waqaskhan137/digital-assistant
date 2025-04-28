"""
Time-Based Polling Strategy

This module implements a strategy for calculating polling intervals based on time of day.
It follows the Strategy pattern to allow different algorithms to be swapped without
modifying the consuming code.
"""
from typing import List, Dict, Any
from datetime import datetime
from services.email_service.src.interfaces.polling_strategy import PollingStrategy

class TimeBasedPollingStrategy(PollingStrategy):
    """
    A strategy that calculates polling intervals based on time of day.
    
    This implementation uses the following rules for determining polling frequency:
    - Business hours (9 AM - 5 PM): Poll every 3 minutes
    - Evening hours (5 PM - 11 PM): Poll every 10 minutes
    - Night hours (11 PM - 9 AM): Poll every 20 minutes
    
    This approach optimizes resource usage by polling more frequently during business
    hours when email traffic is typically higher, and less frequently during off-hours.
    """
    
    # Constants defining time periods (hours in 24-hour format)
    BUSINESS_HOURS_START = 9   # 9 AM
    BUSINESS_HOURS_END = 17    # 5 PM
    EVENING_HOURS_END = 23     # 11 PM
    
    # Polling intervals in minutes
    BUSINESS_HOURS_INTERVAL = 3   # 3 minutes
    EVENING_HOURS_INTERVAL = 10   # 10 minutes
    NIGHT_HOURS_INTERVAL = 20     # 20 minutes
    
    DEFAULT_INTERVAL = 5          # Default interval
    
    def __init__(
        self, 
        business_hours_start: int = None,
        business_hours_end: int = None,
        evening_hours_end: int = None,
        business_hours_interval: int = None,
        evening_hours_interval: int = None,
        night_hours_interval: int = None
    ):
        """
        Initialize the strategy with optional custom hours and intervals.
        
        Args:
            business_hours_start: Hour when business hours start (24h format)
            business_hours_end: Hour when business hours end (24h format)
            evening_hours_end: Hour when evening hours end (24h format)
            business_hours_interval: Polling interval in minutes during business hours
            evening_hours_interval: Polling interval in minutes during evening hours
            night_hours_interval: Polling interval in minutes during night hours
        """
        self.business_hours_start = business_hours_start or self.BUSINESS_HOURS_START
        self.business_hours_end = business_hours_end or self.BUSINESS_HOURS_END
        self.evening_hours_end = evening_hours_end or self.EVENING_HOURS_END
        self.business_hours_interval = business_hours_interval or self.BUSINESS_HOURS_INTERVAL
        self.evening_hours_interval = evening_hours_interval or self.EVENING_HOURS_INTERVAL
        self.night_hours_interval = night_hours_interval or self.NIGHT_HOURS_INTERVAL
    
    async def calculate_polling_interval_minutes(
        self, 
        metrics: List[Dict[str, Any]]
    ) -> int:
        """
        Calculate the optimal polling interval based on current time of day.
        
        Args:
            metrics: List of metrics (unused in this strategy, but required by interface)
            
        Returns:
            Optimal polling interval in minutes
        """
        # Get current hour (0-23)
        current_hour = datetime.now().hour
        
        # Determine interval based on time of day
        if self.business_hours_start <= current_hour < self.business_hours_end:
            # Business hours (e.g., 9 AM - 5 PM)
            return self.business_hours_interval
        elif self.business_hours_end <= current_hour <= self.evening_hours_end:
            # Evening hours (e.g., 5 PM - 11 PM)
            return self.evening_hours_interval
        else:
            # Night hours (e.g., 11 PM - 9 AM)
            return self.night_hours_interval