"""
Hybrid Polling Strategy

This module implements a strategy that combines volume-based and time-based approaches
for calculating polling intervals. It demonstrates the composability of strategies
and the flexibility of the Strategy pattern.
"""
from typing import List, Dict, Any
from datetime import datetime
from services.email_service.src.interfaces.polling_strategy import PollingStrategy
from services.email_service.src.strategies.volume_based_polling import VolumeBasedPollingStrategy
from services.email_service.src.strategies.time_based_polling import TimeBasedPollingStrategy

class HybridPollingStrategy(PollingStrategy):
    """
    A strategy that combines volume-based and time-based polling interval calculations.
    
    This implementation uses both email volume and time of day to determine the optimal
    polling interval. It applies the following logic:
    1. Calculate interval based on volume
    2. Calculate interval based on time of day
    3. Choose the shorter interval during business hours
    4. Choose the longer interval during off-hours
    
    This approach provides an optimal balance between responsiveness and resource efficiency.
    """
    
    def __init__(
        self,
        volume_strategy: VolumeBasedPollingStrategy = None,
        time_strategy: TimeBasedPollingStrategy = None,
        business_hours_preference: str = "shorter",
        off_hours_preference: str = "longer"
    ):
        """
        Initialize the hybrid strategy with optional custom strategies and preferences.
        
        Args:
            volume_strategy: Custom volume-based strategy (or None for default)
            time_strategy: Custom time-based strategy (or None for default)
            business_hours_preference: Which interval to prefer during business hours ("shorter" or "longer")
            off_hours_preference: Which interval to prefer during off-hours ("shorter" or "longer")
        """
        self.volume_strategy = volume_strategy or VolumeBasedPollingStrategy()
        self.time_strategy = time_strategy or TimeBasedPollingStrategy()
        
        # Validate preference values
        valid_preferences = ["shorter", "longer"]
        if business_hours_preference not in valid_preferences:
            raise ValueError(f"Business hours preference must be one of {valid_preferences}")
        if off_hours_preference not in valid_preferences:
            raise ValueError(f"Off hours preference must be one of {valid_preferences}")
            
        self.business_hours_preference = business_hours_preference
        self.off_hours_preference = off_hours_preference
    
    async def calculate_polling_interval_minutes(
        self, 
        metrics: List[Dict[str, Any]]
    ) -> int:
        """
        Calculate the optimal polling interval using both volume and time considerations.
        
        Args:
            metrics: List of metrics from previous sync operations
            
        Returns:
            Optimal polling interval in minutes
        """
        # Get interval based on volume
        volume_interval = await self.volume_strategy.calculate_polling_interval_minutes(metrics)
        
        # Get interval based on time of day
        time_interval = await self.time_strategy.calculate_polling_interval_minutes(metrics)
        
        # Determine the current time period exactly as the TimeBasedPollingStrategy does
        current_hour = datetime.now().hour
        
        # Check which time period we're in
        is_business_hours = (
            self.time_strategy.business_hours_start <= 
            current_hour < 
            self.time_strategy.business_hours_end
        )
        
        # Choose which interval to use based on time period and preferences
        if is_business_hours:
            preference = self.business_hours_preference
        else:
            preference = self.off_hours_preference
            
        if preference == "shorter":
            return min(volume_interval, time_interval)
        else:  # preference == "longer"
            return max(volume_interval, time_interval)