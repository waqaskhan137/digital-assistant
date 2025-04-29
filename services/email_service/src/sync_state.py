import logging
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable, TypeVar, cast, Coroutine
from datetime import datetime
import redis.asyncio as redis
import functools

from services.email_service.src.interfaces.polling_strategy import PollingStrategy
from services.email_service.src.strategies.volume_based_polling import VolumeBasedPollingStrategy
from shared.exceptions import SyncStateError, ConfigurationError, GmailAutomationError

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
        polling_strategy: PollingStrategy, # Depend on interface
        key_prefix: str = "email_sync:"
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self._redis = None
        self._initialized = False
        self.polling_strategy = polling_strategy # Use injected strategy
    
    async def initialize(self):
        """Initialize Redis connection."""
        if self._initialized:
            return
            
        try:
            self._redis = redis.from_url(
                self.redis_url, 
                decode_responses=True, 
                socket_connect_timeout=5
            )
            # Test connection
            await self._redis.ping()
            self._initialized = True
            logger.info("Sync state manager initialized with Redis")
        except (redis.ConnectionError, redis.RedisError) as e:
            logger.error(f"Failed to connect to Redis during initialization: {e}")
            raise ConfigurationError(f"Failed to connect to Redis: {e}") from e
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {str(e)}")
            raise ConfigurationError(f"Redis initialization failed: {e}") from e
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._initialized = False
            logger.info("Redis connection closed")
    
    async def _get_redis(self):
        """
        Get the Redis client, initializing if necessary.
        This method ensures Redis is always initialized before use.
        """
        if not self._initialized:
            await self.initialize()
        if not self._redis:
            raise ConfigurationError("Redis client is not available after initialization attempt.")
        return self._redis
    
    def _get_user_key(self, user_id: str, key_type: str) -> str:
        """Generate a Redis key for a user with a specific type."""
        return f"{self.key_prefix}{user_id}:{key_type}"
    
    async def _redis_operation(self, operation: Callable[[], Coroutine[Any, Any, T]], error_message: str) -> T:
        """
        Helper method to execute Redis operations with proper error handling.
        Raises SyncStateError for operational issues.
        Raises ConfigurationError if Redis is not initialized.
        """
        try:
            redis_client = await self._get_redis()
            return await operation(redis_client)
        except (redis.ConnectionError, redis.RedisError) as e:
            logger.error(f"{error_message} (Redis Error): {e}")
            raise SyncStateError(f"Redis error: {error_message}") from e
        except asyncio.TimeoutError as e:
            logger.error(f"{error_message} (TimeoutError): {e}")
            raise SyncStateError(f"Redis timeout: {error_message}") from e
        except ConfigurationError:
            raise
        except Exception as e:
            # Changed to raise SyncStateError instead of GmailAutomationError for tests
            logger.error(f"{error_message} (Unexpected Error): {e}")
            raise SyncStateError(f"Unexpected error during Redis operation: {error_message}") from e
    
    async def save_sync_state(self, user_id: str, sync_state: Dict[str, Any]) -> bool:
        """
        Save synchronization state for a user.
        
        Args:
            user_id: The user ID
            sync_state: Dictionary with sync state information
        
        Returns:
            True if successful, False otherwise
        """
        sync_state["last_updated"] = datetime.now().isoformat()
        key = self._get_user_key(user_id, "state")
        
        async def operation(redis_client):
            try:
                state_json = json.dumps(sync_state)
                await redis_client.set(key, state_json)
                logger.info(f"Saved sync state for user {user_id}")
                return True
            except TypeError as e:
                logger.error(f"Failed to serialize sync state for user {user_id}: {e}")
                raise SyncStateError(f"Invalid sync state data for user {user_id}") from e
            
        await self._redis_operation(
            operation, 
            f"Failed to save sync state for user {user_id}"
        )
        return True
    
    async def get_sync_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current synchronization state for a user.
        
        Args:
            user_id: The user ID
        
        Returns:
            Dict with sync state or None if not found
        """
        key = self._get_user_key(user_id, "state")
        
        async def operation(redis_client):
            state_json = await redis_client.get(key)
            if state_json:
                try:
                    return json.loads(state_json)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode sync state JSON for user {user_id}: {e}. Data: {state_json}")
                    raise SyncStateError(f"Corrupted sync state data found for user {user_id}") from e
            return None
            
        return await self._redis_operation(
            operation,
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
        
        async def operation(redis_client):
            try:
                data_json = json.dumps(data)
                await redis_client.set(key, data_json)
                logger.info(f"Saved last message ID {message_id} for user {user_id}")
                return True
            except TypeError as e:
                logger.error(f"Failed to serialize last message ID data for user {user_id}: {e}")
                raise SyncStateError(f"Invalid last message ID data for user {user_id}") from e
            
        await self._redis_operation(
            operation,
            f"Failed to save last message ID for user {user_id}"
        )
        return True
    
    async def get_last_message_id(self, user_id: str) -> Optional[str]:
        """
        Get the last successfully processed message ID for resumable syncs.
        
        Args:
            user_id: The user ID
            
        Returns:
            The last message ID or None if not found
        """
        key = self._get_user_key(user_id, "last_message")
        
        async def operation(redis_client):
            data_json = await redis_client.get(key)
            if data_json:
                try:
                    data = json.loads(data_json)
                    return data.get("message_id")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode last message ID JSON for user {user_id}: {e}. Data: {data_json}")
                    raise SyncStateError(f"Corrupted last message ID data found for user {user_id}") from e
            return None
            
        return await self._redis_operation(
            operation,
            f"Failed to get last message ID for user {user_id}"
        )
    
    async def update_sync_metrics_in_redis(self, user_id: str, metrics: Dict[str, Any]) -> bool:
        """
        Update metrics from a sync operation for adaptive polling (side effect: modifies Redis).
        
        Args:
            user_id: The user ID
            metrics: Dictionary with metrics (count, duration, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        metrics["timestamp"] = datetime.now().isoformat()
        key = self._get_user_key(user_id, "metrics")
        
        async def operation(redis_client):
            try:
                metrics_json = await redis_client.get(key)
                metrics_list = json.loads(metrics_json) if metrics_json else []
                
                metrics_list.append(metrics)
                if len(metrics_list) > 10:
                    metrics_list = metrics_list[-10:]
                
                await redis_client.set(key, json.dumps(metrics_list))
                logger.info(f"Recorded sync metrics for user {user_id}: {metrics}")
                return True
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode sync metrics JSON for user {user_id}: {e}. Data: {metrics_json}")
                raise SyncStateError(f"Corrupted sync metrics data found for user {user_id}") from e
            except TypeError as e:
                logger.error(f"Failed to serialize sync metrics for user {user_id}: {e}")
                raise SyncStateError(f"Invalid sync metrics data for user {user_id}") from e
            
        await self._redis_operation(
            operation,
            f"Failed to record sync metrics for user {user_id}"
        )
        return True
    
    async def get_sync_metrics(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get sync metrics history for adaptive polling decisions.
        
        Args:
            user_id: The user ID
            
        Returns:
            List of metrics dictionaries, newest first
        """
        key = self._get_user_key(user_id, "metrics")
        
        async def operation(redis_client):
            metrics_json = await redis_client.get(key)
            if metrics_json:
                try:
                    return json.loads(metrics_json)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode sync metrics JSON for user {user_id}: {e}. Data: {metrics_json}")
                    raise SyncStateError(f"Corrupted sync metrics data found for user {user_id}") from e
            return []
            
        return await self._redis_operation(
            operation,
            f"Failed to get sync metrics for user {user_id}"
        )
    
    async def calculate_optimal_polling_interval_minutes(
        self, 
        user_id: str,
        current_interval: int, # Pass current interval
        user_preference_minutes: Optional[int] = None # Pass user preference
    ) -> int:
        """
        Calculate optimal polling interval based on the configured polling strategy.
        
        Args:
            user_id: The user ID
            current_interval: The current polling interval in minutes.
            user_preference_minutes: Optional user-defined interval preference.
            
        Returns:
            Recommended polling interval in minutes
        """
        default_interval = 5
        
        try:
            metrics_list = await self.get_sync_metrics(user_id)
            latest_metrics = metrics_list[-1] if metrics_list else None
            
            # Use the correct parameter names expected by the polling strategy interface
            calculated_interval = await self.polling_strategy.calculate_polling_interval_minutes(
                metrics=latest_metrics
            )
            return calculated_interval
        except (SyncStateError, ConfigurationError) as e:
            logger.warning(f"Error getting sync metrics for polling interval calculation for user {user_id}: {e}. Using default {default_interval} min.")
            return default_interval
        except Exception as e:
            logger.error(f"Error calculating polling interval via strategy for user {user_id}: {e}. Using default {default_interval} min.")
            return default_interval
    
    async def set_sync_status_in_redis(self, user_id: str, status: str, details: Dict[str, Any] = None) -> bool:
        """
        Set the current sync status for a user (side effect: modifies Redis).
        
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
            
        async def operation(redis_client):
            try:
                status_json = json.dumps(status_data)
                await redis_client.set(key, status_json)
                logger.info(f"Set sync status to '{status}' for user {user_id}")
                return True
            except TypeError as e:
                logger.error(f"Failed to serialize sync status for user {user_id}: {e}")
                raise SyncStateError(f"Invalid sync status data for user {user_id}") from e
            
        await self._redis_operation(
            operation,
            f"Failed to set sync status for user {user_id}"
        )
        return True
    
    async def get_sync_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current sync status for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            Status dictionary or None if not found
        """
        key = self._get_user_key(user_id, "status")
        
        async def operation(redis_client):
            status_json = await redis_client.get(key)
            if status_json:
                try:
                    return json.loads(status_json)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode sync status JSON for user {user_id}: {e}. Data: {status_json}")
                    raise SyncStateError(f"Corrupted sync status data found for user {user_id}") from e
            return None
            
        return await self._redis_operation(
            operation,
            f"Failed to get sync status for user {user_id}"
        )