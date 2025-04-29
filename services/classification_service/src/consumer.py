"""RabbitMQ consumer for the Classification Service."""
import asyncio
import json
import logging
import traceback
from typing import Any, Callable, Dict, Optional

import aio_pika
from aio_pika import Connection, Channel, Queue, IncomingMessage

from shared.exceptions import ExternalServiceError, ValidationError
from shared.models.email import EmailMessage

from .config import config
from .models import ClassificationResult
from .publisher import RabbitMQPublisher

# Set up logging
logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    """RabbitMQ consumer for handling incoming email classification requests."""

    def __init__(
        self, 
        classifier_callback: Optional[Callable[[EmailMessage], ClassificationResult]] = None,
        publisher: Optional[RabbitMQPublisher] = None
    ):
        """Initialize the RabbitMQ consumer.
        
        Args:
            classifier_callback: Function to call with the deserialized email for classification
            publisher: RabbitMQPublisher instance for publishing results
        """
        self.connection: Optional[Connection] = None
        self.channel: Optional[Channel] = None
        self.queue: Optional[Queue] = None
        self.classifier_callback = classifier_callback
        self.publisher = publisher
        self._is_consuming = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        
    async def connect(self) -> None:
        """Establish connection to RabbitMQ and set up channel."""
        try:
            logger.info(f"Connecting to RabbitMQ at {config.rabbitmq_host}")
            self.connection = await aio_pika.connect_robust(
                config.rabbitmq_url,
                reconnect_interval=5.0  # Reconnect every 5 seconds on failure
            )
            
            # Reset reconnect attempts on successful connection
            self._reconnect_attempts = 0
            
            # Set up connection close callback
            # Instead of passing the async method directly, we use a regular function wrapper
            self.connection.add_close_callback(
                lambda conn, exc: asyncio.create_task(self._on_connection_closed(conn, exc))
            )
            
            self.channel = await self.connection.channel()
            
            # Declare the queue
            self.queue = await self.channel.declare_queue(
                config.input_queue_name,
                durable=True,
                auto_delete=False
            )
            
            logger.info(f"Connected to RabbitMQ, queue: {config.input_queue_name}")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            self._reconnect_attempts += 1
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                logger.critical("Maximum reconnection attempts reached. Giving up.")
                raise ExternalServiceError(
                    f"Failed to connect to RabbitMQ after multiple attempts: {str(e)}",
                    service="RabbitMQ"
                )
            raise ExternalServiceError(
                f"Failed to connect to RabbitMQ: {str(e)}",
                service="RabbitMQ"
            )
    
    async def _on_connection_closed(self, connection: Connection, exception: Optional[Exception] = None) -> None:
        """Handle connection closed events.
        
        Args:
            connection: The closed connection
            exception: The exception that caused the closure, if any
        """
        if exception:
            logger.warning(f"RabbitMQ connection closed unexpectedly: {str(exception)}")
            if self._is_consuming:
                try:
                    logger.info("Attempting to reconnect to RabbitMQ...")
                    await self.connect()
                    await self.start_consuming()
                except Exception as e:
                    logger.error(f"Failed to reconnect to RabbitMQ: {str(e)}")
        else:
            logger.info("RabbitMQ connection closed normally")
    
    async def start_consuming(self) -> None:
        """Start consuming messages from the queue."""
        if not self.queue:
            raise ValueError("RabbitMQ connection not established. Call connect() first.")
        
        logger.info(f"Starting to consume messages from queue: {config.input_queue_name}")
        await self.queue.consume(self._on_message)
        self._is_consuming = True
    
    async def _on_message(self, message: IncomingMessage) -> None:
        """Handle incoming messages.
        
        Args:
            message: The incoming message from RabbitMQ
        """
        message_id = message.message_id or "unknown"
        logger.debug(f"Received message: {message_id}")
        
        async with message.process():
            try:
                message_body = message.body.decode()
                logger.debug(f"Message content: {message_body[:1000]}")  # Log first 1000 chars of message
                
                # Deserialize the message
                try:
                    email_data = json.loads(message_body)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message as JSON: {str(e)}")
                    logger.debug(f"Invalid message content: {message_body[:100]}...")
                    raise ValidationError(f"Invalid JSON format in incoming message: {str(e)}")
                
                # Validate the email structure
                try:
                    email = EmailMessage.model_validate(email_data)
                except Exception as e:
                    logger.error(f"Failed to validate email structure: {str(e)}")
                    raise ValidationError(f"Invalid email message structure: {str(e)}")
                
                logger.info(f"Processing email: {email.subject} [ID: {email.id}]")
                
                # If we have a classifier callback, use it
                if self.classifier_callback:
                    try:
                        result = await self.classifier_callback(email)
                        logger.info(
                            f"Classification result for {email.id}: "
                            f"category={result.category}, needs_reply={result.needs_reply}, "
                            f"confidence={result.confidence:.2f}"
                        )
                        
                        # Publish result if we have a publisher
                        if self.publisher:
                            try:
                                await self.publisher.publish_result(result)
                                logger.info(f"Published classification result for email {email.id}")
                            except Exception as e:
                                logger.error(f"Failed to publish classification result: {str(e)}")
                                logger.debug(f"Classification result: {result.model_dump_json()}")
                                # Don't re-raise - we've already processed the message successfully
                                # Just log and continue
                    except Exception as e:
                        logger.error(f"Error during classification: {str(e)}")
                        logger.debug(f"Classification error details: {traceback.format_exc()}")
                        # Don't re-raise - we'll still acknowledge the message to avoid
                        # endless reprocessing of problematic messages
                else:
                    logger.warning("No classifier callback set, email was received but not classified")
                
            except ValidationError as e:
                # For validation errors, log and continue (acknowledge message)
                logger.error(f"Validation error processing message: {str(e)}")
            except Exception as e:
                # For unexpected errors, log detailed debugging information
                logger.exception(f"Unexpected error processing message: {str(e)}")
                logger.debug(f"Error details: {traceback.format_exc()}")
    
    async def close(self) -> None:
        """Close the connection to RabbitMQ."""
        logger.info("Closing RabbitMQ connection")
        self._is_consuming = False
        if self.connection:
            await self.connection.close()
            self.connection = None
            self.channel = None
            self.queue = None


# Consumer instance to be used in lifespan events
consumer: Optional[RabbitMQConsumer] = None


async def setup_rabbitmq_consumer(
    classifier_callback: Optional[Callable] = None,
    publisher: Optional[RabbitMQPublisher] = None
) -> RabbitMQConsumer:
    """Set up the RabbitMQ consumer.
    
    Args:
        classifier_callback: Function to call with the deserialized email for classification
        publisher: RabbitMQPublisher instance for publishing results
        
    Returns:
        Configured RabbitMQConsumer instance
    """
    global consumer
    consumer = RabbitMQConsumer(classifier_callback, publisher)
    await consumer.connect()
    await consumer.start_consuming()
    return consumer