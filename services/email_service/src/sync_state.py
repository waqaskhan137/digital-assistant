import logging
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class SyncStateManager:
    """
    Manages email synchronization state using Redis.
    Tracks sync progress, history, and rates to enable resumable operations
    and adaptive polling.
    """
    def __init__(self, redis_url: str, key_prefix: str = "email_sync:"):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.redis = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Redis connection."""
        if self._initialized:
            return
            
        try:
            self.redis = redis.from_url(self.redis_url)
            # Test connection
            await self.redis.ping()
            self._initialized = True
            logger.info("Sync state manager initialized with Redis")
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {str(e)}")
            raise
    
    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            self._initialized = False
            logger.info("Redis connection closed")
    
    def _get_user_key(self, user_id: str, key_type: str) -> str:
        """Generate a Redis key for a user with a specific type."""
        return f"{self.key_prefix}{user_id}:{key_type}"
    
    async def save_sync_state(self, user_id: str, sync_state: Dict[str, Any]) -> bool:
        """
        Save synchronization state for a user.
        
        Args:
            user_id: The user ID
            sync_state: Dictionary with sync state information
        
        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            key = self._get_user_key(user_id, "state")
            # Add timestamp for tracking
            sync_state["last_updated"] = datetime.now().isoformat()
            
            # Convert to JSON and save
            await self.redis.set(key, json.dumps(sync_state))
            logger.info(f"Saved sync state for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save sync state for user {user_id}: {str(e)}")
            return False
    
    async def get_sync_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current synchronization state for a user.
        
        Args:
            user_id: The user ID
        
        Returns:
            Dict with sync state or None if not found
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            key = self._get_user_key(user_id, "state")
            state_json = await self.redis.get(key)
            
            if state_json:
                return json.loads(state_json)
            return None
        except Exception as e:
            logger.error(f"Failed to get sync state for user {user_id}: {str(e)}")
            return None
    
    async def save_last_message_id(self, user_id: str, message_id: str) -> bool:
        """
        Save the last successfully processed message ID for resumable syncs.
        
        Args:
            user_id: The user ID
            message_id: The last successfully processed message ID
        
        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            key = self._get_user_key(user_id, "last_message")
            timestamp = datetime.now().isoformat()
            data = {
                "message_id": message_id,
                "timestamp": timestamp
            }
            
            await self.redis.set(key, json.dumps(data))
            logger.info(f"Saved last message ID {message_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save last message ID for user {user_id}: {str(e)}")
            return False
    
    async def get_last_message_id(self, user_id: str) -> Optional[str]:
        """
        Get the last successfully processed message ID for resumable syncs.
        
        Args:
            user_id: The user ID
            
        Returns:
            The last message ID or None if not found
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            key = self._get_user_key(user_id, "last_message")
            data_json = await self.redis.get(key)
            
            if data_json:
                data = json.loads(data_json)
                return data.get("message_id")
            return None
        except Exception as e:
            logger.error(f"Failed to get last message ID for user {user_id}: {str(e)}")
            return None
    
    async def record_sync_metrics(self, user_id: str, metrics: Dict[str, Any]) -> bool:
        """
        Record metrics from a sync operation for adaptive polling.
        
        Args:
            user_id: The user ID
            metrics: Dictionary with metrics (count, duration, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            # Add current timestamp
            metrics["timestamp"] = datetime.now().isoformat()
            
            # Store in a list with the most recent 10 sync operations
            key = self._get_user_key(user_id, "metrics")
            
            # Get existing metrics list or create new one
            metrics_json = await self.redis.get(key)
            if metrics_json:
                metrics_list = json.loads(metrics_json)
            else:
                metrics_list = []
            
            # Add new metrics and limit to last 10
            metrics_list.append(metrics)
            if len(metrics_list) > 10:
                metrics_list = metrics_list[-10:]
            
            # Save updated list
            await self.redis.set(key, json.dumps(metrics_list))
            logger.info(f"Recorded sync metrics for user {user_id}: {metrics}")
            return True
        except Exception as e:
            logger.error(f"Failed to record sync metrics for user {user_id}: {str(e)}")
            return False
    
    async def get_sync_metrics(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get sync metrics history for adaptive polling decisions.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of metrics dictionaries, newest first
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            key = self._get_user_key(user_id, "metrics")
            metrics_json = await self.redis.get(key)
            
            if metrics_json:
                return json.loads(metrics_json)
            return []
        except Exception as e:
            logger.error(f"Failed to get sync metrics for user {user_id}: {str(e)}")
            return []
    
    async def calculate_optimal_polling_interval(self, user_id: str) -> int:
        """
        Calculate optimal polling interval based on email volume patterns.
        
        Args:
            user_id: The user ID
            
        Returns:
            Recommended polling interval in minutes
        """
        # Default interval (5 minutes)
        default_interval = 5
        
        try:
            # Get metrics history
            metrics = await self.get_sync_metrics(user_id)
            
            if not metrics or len(metrics) < 3:
                return default_interval
            
            # Calculate average email count per sync
            total_emails = sum(m.get("email_count", 0) for m in metrics)
            avg_count = total_emails / len(metrics)
            
            # Determine volume category and set interval
            if avg_count > 50:  # High volume
                return 2  # 2 minutes
            elif avg_count > 10:  # Medium volume
                return 5  # 5 minutes
            else:  # Low volume
                return 15  # 15 minutes
        except Exception as e:
            logger.error(f"Error calculating polling interval for user {user_id}: {str(e)}")
            return default_interval
    
    async def set_sync_status(self, user_id: str, status: str, details: Dict[str, Any] = None) -> bool:
        """
        Set the current sync status for a user.
        
        Args:
            user_id: The user ID
            status: Status string (e.g., "running", "completed", "failed")
            details: Optional details about the status
            
        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            key = self._get_user_key(user_id, "status")
            status_data = {
                "status": status,
                "timestamp": datetime.now().isoformat()
            }
            
            if details:
                status_data["details"] = details
                
            await self.redis.set(key, json.dumps(status_data))
            logger.info(f"Set sync status to '{status}' for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to set sync status for user {user_id}: {str(e)}")
            return False
    
    async def get_sync_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current sync status for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Status dictionary or None if not found
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            key = self._get_user_key(user_id, "status")
            status_json = await self.redis.get(key)
            
            if status_json:
                return json.loads(status_json)
            return None
        except Exception as e:
            logger.error(f"Failed to get sync status for user {user_id}: {str(e)}")
            return None