import json
import redis
from typing import Optional
from shared.models.token import Token


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
        self.redis = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )
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
        token_json = token.model_dump_json()
        return bool(self.redis.set(key, token_json))

    def get_token(self, user_id: str) -> Optional[Token]:
        """Retrieve a token from Redis.
        
        Args:
            user_id (str): User identifier
            
        Returns:
            Optional[Token]: Token if found, None otherwise
        """
        key = f"{self.key_prefix}{user_id}"
        token_json = self.redis.get(key)
        
        if token_json is None:
            return None
            
        return Token.model_validate_json(token_json)

    def delete_token(self, user_id: str) -> bool:
        """Delete a token from Redis.
        
        Args:
            user_id (str): User identifier
            
        Returns:
            bool: True if token was deleted, False if token didn't exist
        """
        key = f"{self.key_prefix}{user_id}"
        deleted_count = self.redis.delete(key)
        return deleted_count > 0