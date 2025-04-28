"""
Volume-Based Polling Strategy

This module implements a strategy for calculating polling intervals based on email volume.
It follows the Strategy pattern to allow different algorithms to be swapped without
modifying the consuming code.
"""
from typing import List, Dict, Any
from services.email_service.src.interfaces.polling_strategy import PollingStrategy

class VolumeBasedPollingStrategy(PollingStrategy):
    """
    A strategy that calculates polling intervals based on email volume.
    
    This implementation uses the following rules for determining polling frequency:
    - High volume (50+ emails per sync): Poll every 2 minutes
    - Medium volume (10-49 emails per sync): Poll every 5 minutes
    - Low volume (<10 emails per sync): Poll every 15 minutes
    
    This approach optimizes resource usage by polling more frequently for users with
    high email traffic and less frequently for users with lower traffic.
    """
    
    # Constants defining thresholds and intervals
    HIGH_VOLUME_THRESHOLD = 50
    MEDIUM_VOLUME_THRESHOLD = 10
    
    HIGH_VOLUME_INTERVAL = 2    # 2 minutes
    MEDIUM_VOLUME_INTERVAL = 5   # 5 minutes
    LOW_VOLUME_INTERVAL = 15     # 15 minutes
    
    DEFAULT_INTERVAL = 5         # Default to medium interval
    
    def __init__(
        self, 
        high_volume_threshold: int = None,
        medium_volume_threshold: int = None,
        high_volume_interval: int = None,
        medium_volume_interval: int = None,
        low_volume_interval: int = None
    ):
        """
        Initialize the strategy with optional custom thresholds and intervals.
        
        Args:
            high_volume_threshold: Emails per sync to be considered high volume
            medium_volume_threshold: Emails per sync to be considered medium volume
            high_volume_interval: Polling interval in minutes for high volume
            medium_volume_interval: Polling interval in minutes for medium volume
            low_volume_interval: Polling interval in minutes for low volume
        """
        self.high_volume_threshold = high_volume_threshold or self.HIGH_VOLUME_THRESHOLD
        self.medium_volume_threshold = medium_volume_threshold or self.MEDIUM_VOLUME_THRESHOLD
        self.high_volume_interval = high_volume_interval or self.HIGH_VOLUME_INTERVAL
        self.medium_volume_interval = medium_volume_interval or self.MEDIUM_VOLUME_INTERVAL
        self.low_volume_interval = low_volume_interval or self.LOW_VOLUME_INTERVAL
    
    async def calculate_polling_interval_minutes(
        self, 
        metrics: List[Dict[str, Any]]
    ) -> int:
        """
        Calculate the optimal polling interval based on email volume metrics.
        
        Args:
            metrics: List of metrics from previous sync operations
            
        Returns:
            Optimal polling interval in minutes
        """
        if not metrics:
            return self.DEFAULT_INTERVAL
        
        # Calculate average email count from metrics
        email_counts = [
            m.get("email_count", 0) for m in metrics 
            if isinstance(m.get("email_count"), (int, float))
        ]
        
        if not email_counts:
            return self.DEFAULT_INTERVAL
        
        avg_email_count = sum(email_counts) / len(email_counts)
        
        # Determine interval based on volume thresholds
        if avg_email_count >= self.high_volume_threshold:
            return self.high_volume_interval
        elif avg_email_count >= self.medium_volume_threshold:
            return self.medium_volume_interval
        else:
            return self.low_volume_interval