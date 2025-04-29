"""RabbitMQ publisher for the Classification Service."""
import asyncio
import json
import logging
import traceback
from typing import Optional

import aio_pika
from aio_pika import Connection, Channel, Message, DeliveryMode

from shared.exceptions import ExternalServiceError
from .config import config
from .models import ClassificationResult

# Set up logging
logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """RabbitMQ publisher for sending classification results."""

    def __init__(self):
        """Initialize the RabbitMQ publisher."""
        self.connection: Optional[Connection] = None
        self.channel: Optional[Channel] = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        
    async def connect(self) -> None:
        """Establish connection to RabbitMQ and set up channel."""
        try:
            logger.info(f"Connecting publisher to RabbitMQ at {config.rabbitmq_host}")
            self.connection = await aio_pika.connect_robust(
                config.rabbitmq_url,
                reconnect_interval=5.0
            )
            
            # Reset reconnect attempts on successful connection
            self._reconnect_attempts = 0
            
            # Set up connection close callback using lambda function and create_task
            self.connection.add_close_callback(
                lambda conn, exc: asyncio.create_task(self._on_connection_closed(conn, exc))
            )
            
            self.channel = await self.connection.channel()
            
            # Declare the output queue
            await self.channel.declare_queue(
                config.output_queue_name,
                durable=True,
                auto_delete=False
            )
            
            logger.info(f"Publisher connected to RabbitMQ, queue: {config.output_queue_name}")
        except Exception as e:
            logger.error(f"Failed to connect publisher to RabbitMQ: {str(e)}")
            self._reconnect_attempts += 1
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                logger.critical("Maximum publisher reconnection attempts reached. Giving up.")
                raise ExternalServiceError(
                    f"Failed to connect publisher to RabbitMQ after multiple attempts: {str(e)}",
                    service="RabbitMQ"
                )
            raise ExternalServiceError(
                f"Failed to connect publisher to RabbitMQ: {str(e)}",
                service="RabbitMQ"
            )
    
    async def _on_connection_closed(self, connection: Connection, exception: Optional[Exception] = None) -> None:
        """Handle connection closed events.
        
        Args:
            connection: The closed connection
            exception: The exception that caused the closure, if any
        """
        if exception:
            logger.warning(f"Publisher RabbitMQ connection closed unexpectedly: {str(exception)}")
            try:
                logger.info("Attempting to reconnect publisher to RabbitMQ...")
                await self.connect()
            except Exception as e:
                logger.error(f"Failed to reconnect publisher to RabbitMQ: {str(e)}")
        else:
            logger.info("Publisher RabbitMQ connection closed normally")
    
    async def publish_result(self, result: ClassificationResult) -> None:
        """Publish a classification result to the output queue.
        
        Args:
            result: The classification result to publish
            
        Raises:
            ValueError: If RabbitMQ connection is not established
            ExternalServiceError: If there's an error publishing the message
        """
        if not self.channel:
            logger.error("Attempted to publish without an active RabbitMQ connection")
            
            # Try to reconnect once
            try:
                logger.info("Attempting to reconnect before publishing...")
                await self.connect()
            except Exception as e:
                logger.error(f"Reconnection failed: {str(e)}")
                raise ValueError("RabbitMQ connection not established. Call connect() first.")
        
        try:
            # Serialize the classification result
            message_body = json.dumps(result.model_dump()).encode()
            
            # Create a message with persistent delivery to survive broker restarts
            message = Message(
                body=message_body,
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
                message_id=result.email_id,
                headers={
                    "category": result.category.value,
                    "needs_reply": str(result.needs_reply).lower(),
                    "confidence": str(result.confidence)
                }
            )
            
            # Publish the message to the output queue
            await self.channel.default_exchange.publish(
                message=message,
                routing_key=config.output_queue_name
            )
            
            logger.info(
                f"Published classification result to {config.output_queue_name}: "
                f"email_id={result.email_id}, category={result.category}, "
                f"needs_reply={result.needs_reply}, confidence={result.confidence:.2f}"
            )
            
            if result.priority:
                logger.info(f"Priority level for this classification: {result.priority}")
                
        except Exception as e:
            logger.error(f"Failed to publish classification result: {str(e)}")
            logger.debug(f"Failed classification result: {result.model_dump_json()}")
            logger.debug(f"Publishing error details: {traceback.format_exc()}")
            raise ExternalServiceError(
                f"Failed to publish classification result: {str(e)}",
                service="RabbitMQ"
            )
    
    async def close(self) -> None:
        """Close the connection to RabbitMQ."""
        logger.info("Closing RabbitMQ publisher connection")
        if self.connection:
            await self.connection.close()
            self.connection = None
            self.channel = None


# Publisher instance to be used in lifespan events
publisher: Optional[RabbitMQPublisher] = None


async def setup_rabbitmq_publisher() -> RabbitMQPublisher:
    """Set up the RabbitMQ publisher.
    
    Returns:
        Configured RabbitMQPublisher instance
    """
    global publisher
    publisher = RabbitMQPublisher()
    await publisher.connect()
    return publisher