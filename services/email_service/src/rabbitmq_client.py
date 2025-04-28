import logging
import json
import asyncio
from typing import Dict, Any, Optional
import aio_pika
from shared.models.email import EmailMessage
from shared.exceptions import ExternalServiceError, ConfigurationError, GmailAutomationError

logger = logging.getLogger(__name__)

class RabbitMQClient:
    """
    Client for RabbitMQ messaging to publish emails to the Classification Service.
    Uses aio_pika for asyncio-compatible RabbitMQ integration.
    """
    def __init__(self, connection_url: str, exchange_name: str = "email_exchange", max_retries: int = 5, retry_delay: int = 5):
        self.connection_url = connection_url
        self.exchange_name = exchange_name
        self.connection = None
        self.channel = None
        self.exchange = None
        self._initialized = False
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def initialize(self):
        """Initialize the RabbitMQ connection with retry logic."""
        if self._initialized:
            return
        
        if not self.connection_url:
            logger.error("Missing RabbitMQ connection URL")
            raise ConfigurationError("RabbitMQ connection URL is required")
            
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                # Connect to RabbitMQ
                logger.info(f"Attempting to connect to RabbitMQ at {self.connection_url} (attempt {retry_count + 1}/{self.max_retries})")
                self.connection = await aio_pika.connect_robust(self.connection_url)
                
                # Create channel
                self.channel = await self.connection.channel()
                
                # Declare exchange
                self.exchange = await self.channel.declare_exchange(
                    self.exchange_name,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True
                )
                
                # Declare queues
                await self.channel.declare_queue(
                    "email_classification_queue",
                    durable=True
                )
                
                logger.info(f"RabbitMQ client initialized with exchange: {self.exchange_name}")
                self._initialized = True
                return
                
            except aio_pika.exceptions.AMQPConnectionError as e:
                retry_count += 1
                if retry_count >= self.max_retries:
                    logger.error(f"Failed to connect to RabbitMQ after {self.max_retries} attempts: {str(e)}")
                    raise ConfigurationError(f"Unable to connect to RabbitMQ: {e}") from e
                
                logger.warning(f"RabbitMQ connection attempt {retry_count} failed: {str(e)}. Retrying in {self.retry_delay} seconds...")
                await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Unexpected error during RabbitMQ initialization: {str(e)}")
                raise ConfigurationError(f"Failed to initialize RabbitMQ client: {e}") from e
    
    async def close(self):
        """Close the RabbitMQ connection."""
        if self.connection and not self.connection.is_closed:
            try:
                await self.connection.close()
                self._initialized = False
                logger.info("RabbitMQ connection closed")
            except Exception as e:
                logger.warning(f"Error closing RabbitMQ connection: {e}")
                # No need to re-raise as this is cleanup
    
    async def _ensure_initialized(self):
        """Ensure the RabbitMQ client is initialized before use."""
        if not self._initialized:
            await self.initialize()
        
        if not self._initialized or not self.exchange:
            raise ConfigurationError("RabbitMQ client initialization failed")
    
    async def publish_email(self, email: EmailMessage, routing_key: str = "email.new"):
        """
        Publish an email message to the RabbitMQ exchange.
        
        Args:
            email: The normalized EmailMessage to publish
            routing_key: The routing key for message routing (default: email.new)
        """
        await self._ensure_initialized()
        
        try:
            # Convert EmailMessage to dict and then to JSON
            email_dict = email.model_dump()
            # Convert datetime to ISO format string for JSON serialization
            if isinstance(email_dict.get('date'), object) and hasattr(email_dict['date'], 'isoformat'):
                email_dict['date'] = email_dict['date'].isoformat()
                
            email_json = json.dumps(email_dict)
            
            # Create message
            message = aio_pika.Message(
                body=email_json.encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json"
            )
            
            # Publish message
            await self.exchange.publish(
                message,
                routing_key=routing_key
            )
            
            logger.info(f"Published email with ID {email.id} to RabbitMQ with routing key {routing_key}")
            
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to serialize email for RabbitMQ: {str(e)}")
            raise ExternalServiceError(f"Failed to serialize email for publishing: {e}") from e
        except aio_pika.exceptions.AMQPException as e:
            logger.error(f"AMQP error during email publishing: {str(e)}")
            raise ExternalServiceError(f"RabbitMQ error during message publishing: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error publishing email to RabbitMQ: {str(e)}")
            raise GmailAutomationError(f"Unexpected error during message publishing: {e}") from e
    
    async def publish_batch(self, emails: list[EmailMessage], routing_key: str = "email.batch"):
        """
        Publish a batch of emails to RabbitMQ.
        
        Args:
            emails: List of EmailMessage objects to publish
            routing_key: The routing key for message routing (default: email.batch)
        """
        await self._ensure_initialized()
        
        try:
            # Convert list of emails to list of dicts
            email_dicts = []
            for email in emails:
                email_dict = email.model_dump()
                # Convert datetime to ISO format string for JSON serialization
                if isinstance(email_dict.get('date'), object) and hasattr(email_dict['date'], 'isoformat'):
                    email_dict['date'] = email_dict['date'].isoformat()
                email_dicts.append(email_dict)
                
            # Convert to JSON
            batch_json = json.dumps({"emails": email_dicts})
            
            # Create message
            message = aio_pika.Message(
                body=batch_json.encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json"
            )
            
            # Publish message
            await self.exchange.publish(
                message,
                routing_key=routing_key
            )
            
            logger.info(f"Published batch of {len(emails)} emails to RabbitMQ with routing key {routing_key}")
            
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to serialize email batch for RabbitMQ: {str(e)}")
            raise ExternalServiceError(f"Failed to serialize email batch for publishing: {e}") from e
        except aio_pika.exceptions.AMQPException as e:
            logger.error(f"AMQP error during batch publishing: {str(e)}")
            raise ExternalServiceError(f"RabbitMQ error during batch publishing: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error publishing batch to RabbitMQ: {str(e)}")
            raise GmailAutomationError(f"Unexpected error during batch publishing: {e}") from e