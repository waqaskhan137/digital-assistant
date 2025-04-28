"""
Polling Strategy Interface

This module defines the interface for polling strategies used in email synchronization.
Following the Open/Closed Principle, this interface allows for different polling interval
calculation algorithms to be plugged in without modifying existing code.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class PollingStrategy(ABC):
    """
    Interface for determining optimal polling intervals.
    
    This interface follows the Open/Closed Principle by allowing different
    polling strategies to be implemented and swapped without modifying the
    consuming code. Concrete implementations might include:
    - VolumeBasedPollingStrategy (adjusts based on email volume)
    - TimeOfDayPollingStrategy (adjusts based on time of day)
    - UserActivityPollingStrategy (adjusts based on user's activity patterns)
    """
    
    @abstractmethod
    async def calculate_polling_interval_minutes(
        self, 
        metrics: List[Dict[str, Any]]
    ) -> int:
        """
        Calculate the optimal polling interval based on provided metrics.
        
        Args:
            metrics: List of metrics from previous sync operations
            
        Returns:
            Optimal polling interval in minutes
        """
        pass