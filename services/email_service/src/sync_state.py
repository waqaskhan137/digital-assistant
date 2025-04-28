import logging
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable, TypeVar, cast
from datetime import datetime
import redis.asyncio as redis
import functools

from services.email_service.src.interfaces.polling_strategy import PollingStrategy
from services.email_service.src.strategies.volume_based_polling import VolumeBasedPollingStrategy

logger = logging.getLogger(__name__)

# Type variable for the return type of the Redis operation
T = TypeVar('T')

class SyncStateManager:
    """
    Manages email synchronization state using Redis.
    Tracks sync progress, history, and rates to enable resumable operations
    and adaptive polling.
    """
    def __init__(
        self, 
        redis_url: str, 
        key_prefix: str = "email_sync:",
        polling_strategy: Optional[PollingStrategy] = None
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self._redis = None
        self._initialized = False
        
        # Set polling strategy, defaulting to volume-based if not provided
        self.polling_strategy = polling_strategy or VolumeBasedPollingStrategy()
    
    async def initialize(self):
        """Initialize Redis connection."""
        if self._initialized:
            return
            
        try:
            self._redis = redis.from_url(self.redis_url)
            # Test connection
            await self._redis.ping()
            self._initialized = True
            logger.info("Sync state manager initialized with Redis")
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {str(e)}")
            raise
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._initialized = False
            logger.info("Redis connection closed")
    
    @property
    async def redis(self):
        """
        Get the Redis client, initializing if necessary.
        This property ensures Redis is always initialized before use.
        """
        if not self._initialized:
            await self.initialize()
        return self._redis
    
    def _get_user_key(self, user_id: str, key_type: str) -> str:
        """Generate a Redis key for a user with a specific type."""
        return f"{self.key_prefix}{user_id}:{key_type}"
    
    async def _redis_operation(self, operation: Callable, default_value: T, error_message: str) -> T:
        """
        Helper method to execute Redis operations with proper error handling.
        
        Args:
            operation: Async callable that performs the Redis operation
            default_value: Value to return if operation fails
            error_message: Message to log if operation fails
            
        Returns:
            Result of the operation or default_value if it fails
        """
        try:
            return await operation()
        except Exception as e:
            logger.error(f"{error_message}: {str(e)}")
            return default_value
    
    async def save_sync_state(self, user_id: str, sync_state: Dict[str, Any]) -> bool:
        """
        Save synchronization state for a user.
        
        Args:
            user_id: The user ID
            sync_state: Dictionary with sync state information
        
        Returns:
            True if successful, False otherwise
        """
        # Add timestamp for tracking
        sync_state["last_updated"] = datetime.now().isoformat()
        key = self._get_user_key(user_id, "state")
        
        async def operation():
            redis_client = await self.redis
            await redis_client.set(key, json.dumps(sync_state))
            logger.info(f"Saved sync state for user {user_id}")
            return True
            
        return await self._redis_operation(
            operation, 
            False, 
            f"Failed to save sync state for user {user_id}"
        )
    
    async def get_sync_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current synchronization state for a user.
        
        Args:
            user_id: The user ID
        
        Returns:
            Dict with sync state or None if not found
        """
        key = self._get_user_key(user_id, "state")
        
        async def operation():
            redis_client = await self.redis
            state_json = await redis_client.get(key)
            if state_json:
                return json.loads(state_json)
            return None
            
        return await self._redis_operation(
            operation,
            None,
            f"Failed to get sync state for user {user_id}"
        )
    
    async def save_last_message_id(self, user_id: str, message_id: str) -> bool:
        """
        Save the last successfully processed message ID for resumable syncs.
        
        Args:
            user_id: The user ID
            message_id: The last successfully processed message ID
        
        Returns:
            True if successful, False otherwise
        """
        key = self._get_user_key(user_id, "last_message")
        timestamp = datetime.now().isoformat()
        data = {
            "message_id": message_id,
            "timestamp": timestamp
        }
        
        async def operation():
            redis_client = await self.redis
            await redis_client.set(key, json.dumps(data))
            logger.info(f"Saved last message ID {message_id} for user {user_id}")
            return True
            
        return await self._redis_operation(
            operation,
            False,
            f"Failed to save last message ID for user {user_id}"
        )
    
    async def get_last_message_id(self, user_id: str) -> Optional[str]:
        """
        Get the last successfully processed message ID for resumable syncs.
        
        Args:
            user_id: The user ID
            
        Returns:
            The last message ID or None if not found
        """
        key = self._get_user_key(user_id, "last_message")
        
        async def operation():
            redis_client = await self.redis
            data_json = await redis_client.get(key)
            if data_json:
                data = json.loads(data_json)
                return data.get("message_id")
            return None
            
        return await self._redis_operation(
            operation,
            None,
            f"Failed to get last message ID for user {user_id}"
        )
    
    async def record_sync_metrics(self, user_id: str, metrics: Dict[str, Any]) -> bool:
        """
        Record metrics from a sync operation for adaptive polling.
        
        Args:
            user_id: The user ID
            metrics: Dictionary with metrics (count, duration, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        # Add current timestamp
        metrics["timestamp"] = datetime.now().isoformat()
        key = self._get_user_key(user_id, "metrics")
        
        async def operation():
            redis_client = await self.redis
            
            # Get existing metrics list or create new one
            metrics_json = await redis_client.get(key)
            metrics_list = json.loads(metrics_json) if metrics_json else []
            
            # Add new metrics and limit to last 10
            metrics_list.append(metrics)
            if len(metrics_list) > 10:
                metrics_list = metrics_list[-10:]
            
            # Save updated list
            await redis_client.set(key, json.dumps(metrics_list))
            logger.info(f"Recorded sync metrics for user {user_id}: {metrics}")
            return True
            
        return await self._redis_operation(
            operation,
            False,
            f"Failed to record sync metrics for user {user_id}"
        )
    
    async def get_sync_metrics(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get sync metrics history for adaptive polling decisions.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of metrics dictionaries, newest first
        """
        key = self._get_user_key(user_id, "metrics")
        
        async def operation():
            redis_client = await self.redis
            metrics_json = await redis_client.get(key)
            if metrics_json:
                return json.loads(metrics_json)
            return []
            
        return await self._redis_operation(
            operation,
            [],
            f"Failed to get sync metrics for user {user_id}"
        )
    
    async def calculate_optimal_polling_interval_minutes(self, user_id: str) -> int:
        """
        Calculate optimal polling interval based on the configured polling strategy.
        
        Args:
            user_id: The user ID
            
        Returns:
            Recommended polling interval in minutes
        """
        # Default interval (5 minutes)
        default_interval = 5
        
        async def operation():
            # Get metrics history
            metrics = await self.get_sync_metrics(user_id)
            
            if not metrics:
                return default_interval
            
            # Use the strategy to calculate the optimal interval
            return await self.polling_strategy.calculate_polling_interval_minutes(metrics)
                
        return await self._redis_operation(
            operation,
            default_interval,
            f"Error calculating polling interval for user {user_id}"
        )
    
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
        key = self._get_user_key(user_id, "status")
        status_data = {
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        if details:
            status_data["details"] = details
            
        async def operation():
            redis_client = await self.redis
            await redis_client.set(key, json.dumps(status_data))
            logger.info(f"Set sync status to '{status}' for user {user_id}")
            return True
            
        return await self._redis_operation(
            operation,
            False,
            f"Failed to set sync status for user {user_id}"
        )
    
    async def get_sync_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current sync status for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Status dictionary or None if not found
        """
        key = self._get_user_key(user_id, "status")
        
        async def operation():
            redis_client = await self.redis
            status_json = await redis_client.get(key)
            if status_json:
                return json.loads(status_json)
            return None
            
        return await self._redis_operation(
            operation,
            None,
            f"Failed to get sync status for user {user_id}"
        )