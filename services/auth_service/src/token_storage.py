import json
import redis
from typing import Optional
from shared.models.token import Token
from shared.exceptions import SyncStateError, ConfigurationError, ValidationError
import logging

logger = logging.getLogger(__name__)


class RedisTokenStorage:
    """Storage class for managing OAuth tokens in Redis."""

    def __init__(self, host: str, port: int, db: int = 0, password: Optional[str] = None):
        """Initialize Redis connection.
        
        Args:
            host (str): Redis host
            port (int): Redis port
            db (int, optional): Redis database. Defaults to 0.
            password (Optional[str], optional): Redis password. Defaults to None.
        """
        try:
            self.redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=5 # Add timeout
            )
            self.redis.ping() # Verify connection
            logger.info(f"Connected to Redis at {host}:{port}/{db}")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Raise ConfigurationError as it's likely a setup issue
            raise ConfigurationError(f"Failed to connect to Redis: {e}") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during Redis initialization: {e}")
            raise ConfigurationError(f"Redis initialization failed: {e}") from e
            
        self.key_prefix = "token:"

    def save_token(self, user_id: str, token: Token) -> bool:
        """Save a token to Redis.
        
        Args:
            user_id (str): User identifier
            token (Token): Token to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        key = f"{self.key_prefix}{user_id}"
        try:
            token_json = token.model_dump_json()
            return bool(self.redis.set(key, token_json))
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error saving token for user {user_id}: {e}")
            raise SyncStateError(f"Failed to save token for user {user_id}") from e
        except Exception as e: # Catch potential JSON errors or others
            logger.error(f"Unexpected error saving token for user {user_id}: {e}")
            raise SyncStateError(f"Unexpected error saving token for user {user_id}") from e

    def get_token(self, user_id: str) -> Optional[Token]:
        """Retrieve a token from Redis.
        
        Args:
            user_id (str): User identifier
            
        Returns:
            Optional[Token]: Token if found, None otherwise
        """
        key = f"{self.key_prefix}{user_id}"
        try:
            token_json = self.redis.get(key)
            
            if token_json is None:
                return None
            
            # Validate the JSON structure before parsing
            return Token.model_validate_json(token_json)
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error getting token for user {user_id}: {e}")
            raise SyncStateError(f"Failed to get token for user {user_id}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode token JSON for user {user_id}: {e}. Data: {token_json}")
            # Corrupted data in storage
            raise SyncStateError(f"Corrupted token data found for user {user_id}") from e
        except Exception as e: # Catch Pydantic validation errors or others
            logger.error(f"Unexpected error getting token for user {user_id}: {e}")
            raise SyncStateError(f"Unexpected error getting token for user {user_id}") from e

    def delete_token(self, user_id: str) -> bool:
        """Delete a token from Redis.
        
        Args:
            user_id (str): User identifier
            
        Returns:
            bool: True if token was deleted, False if token didn't exist
        """
        key = f"{self.key_prefix}{user_id}"
        try:
            deleted_count = self.redis.delete(key)
            return deleted_count > 0
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error deleting token for user {user_id}: {e}")
            raise SyncStateError(f"Failed to delete token for user {user_id}") from e
        except Exception as e:
            logger.error(f"Unexpected error deleting token for user {user_id}: {e}")
            raise SyncStateError(f"Unexpected error deleting token for user {user_id}") from e