"""Configuration for the Classification Service."""
import logging
import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

# Configure logging for the configuration module
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class Config(BaseModel):
    """Configuration settings for the Classification Service."""
    
    # RabbitMQ connection settings
    rabbitmq_host: str = Field(
        default="localhost",
        description="RabbitMQ host address"
    )
    rabbitmq_port: int = Field(
        default=5672,
        description="RabbitMQ port"
    )
    rabbitmq_user: str = Field(
        default="guest",
        description="RabbitMQ username"
    )
    rabbitmq_password: str = Field(
        default="guest",
        description="RabbitMQ password"
    )
    rabbitmq_vhost: str = Field(
        default="/",
        description="RabbitMQ virtual host"
    )
    
    # Queue names
    input_queue_name: str = Field(
        default="email_to_classify",
        description="Queue name for incoming emails to classify"
    )
    output_queue_name: str = Field(
        default="classification_results",
        description="Queue name for classification results"
    )
    
    # Application settings
    rules_config_path: Optional[str] = Field(
        default=None,
        description="Path to custom rules configuration file"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    # Calculated properties
    @property
    def rabbitmq_url(self) -> str:
        """Generate the RabbitMQ connection URL.
        
        Returns:
            Complete RabbitMQ connection URL
        """
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate the log level.
        
        Args:
            v: The log level value
            
        Returns:
            Validated log level
            
        Raises:
            ValueError: If the log level is invalid
        """
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            logger.warning(f"Invalid log level: {v}, defaulting to INFO")
            return "INFO"
        return v.upper()


def load_config() -> Config:
    """Load configuration from environment variables.
    
    Returns:
        Loaded configuration object
    """
    # Environment variable mappings
    env_mappings = {
        "RABBITMQ_HOST": "rabbitmq_host",
        "RABBITMQ_PORT": "rabbitmq_port",
        "RABBITMQ_USER": "rabbitmq_user",
        "RABBITMQ_PASSWORD": "rabbitmq_password",
        "RABBITMQ_VHOST": "rabbitmq_vhost",
        "CLASSIFICATION_INPUT_QUEUE": "input_queue_name",
        "CLASSIFICATION_OUTPUT_QUEUE": "output_queue_name",
        "RULES_CONFIG_PATH": "rules_config_path",
        "LOG_LEVEL": "log_level",
    }
    
    # Build configuration dictionary from environment variables
    config_values: Dict[str, Any] = {}
    for env_var, config_field in env_mappings.items():
        if env_var in os.environ:
            value = os.environ[env_var]
            
            # Convert to int if the field is rabbitmq_port
            if config_field == "rabbitmq_port":
                try:
                    value = int(value)
                except ValueError:
                    logger.error(f"Invalid port number: {value}, using default")
                    continue
            
            config_values[config_field] = value
            logger.debug(f"Loaded config {config_field}={value} from {env_var}")
    
    # Create and validate the config
    try:
        config = Config(**config_values)
        logger.info(f"Configuration loaded successfully: rabbitmq={config.rabbitmq_host}:{config.rabbitmq_port}")
        return config
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        logger.warning("Using default configuration values")
        return Config()


# Create a global config instance
config = load_config()