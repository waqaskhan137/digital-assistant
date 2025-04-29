"""Tests for the RabbitMQ publisher."""
import json
import pytest
from unittest.mock import AsyncMock, patch

from src.publisher import RabbitMQPublisher, setup_rabbitmq_publisher
from src.models import ClassificationResult, EmailCategory
from shared.exceptions import ExternalServiceError


@pytest.mark.asyncio
async def test_publisher_initialization():
    """Test that the publisher initializes correctly."""
    # Initialize publisher
    publisher = RabbitMQPublisher()
    
    # Verify publisher initialized
    assert publisher is not None
    assert publisher.connection is None
    assert publisher.channel is None


@pytest.mark.asyncio
async def test_publisher_connect(mock_aio_pika):
    """Test that the publisher can connect to RabbitMQ."""
    # Create publisher
    publisher = RabbitMQPublisher()
    
    # Connect to RabbitMQ
    await publisher.connect()
    
    # Verify connection was established
    assert publisher.connection == mock_aio_pika["connection"]
    assert publisher.channel == mock_aio_pika["channel"]
    
    # Verify channel and queue were properly set up
    mock_aio_pika["connection"].channel.assert_called_once()
    mock_aio_pika["channel"].declare_queue.assert_called_once()


@pytest.mark.asyncio
async def test_publisher_connect_failure(mock_aio_pika):
    """Test that the publisher handles connection failures properly."""
    # Make the connect_robust method raise an exception
    mock_aio_pika["connect"].side_effect = Exception("Connection failure")
    
    # Create publisher
    publisher = RabbitMQPublisher()
    
    # Attempt to connect and verify it raises the expected exception
    with pytest.raises(ExternalServiceError) as exc_info:
        await publisher.connect()
    
    # Verify exception details
    assert "Failed to connect publisher to RabbitMQ" in str(exc_info.value)
    assert exc_info.value.service == "RabbitMQ"


@pytest.mark.asyncio
async def test_publish_result(mock_aio_pika):
    """Test that the publisher can publish a classification result."""
    # Create publisher and connect
    publisher = RabbitMQPublisher()
    
    # Mock channel
    mock_channel = mock_aio_pika["channel"]
    mock_exchange = AsyncMock()
    mock_channel.default_exchange = mock_exchange
    
    # Connect to RabbitMQ
    await publisher.connect()
    
    # Create a test classification result
    result = ClassificationResult(
        category=EmailCategory.IMPORTANT,
        needs_reply=True,
        confidence=0.9,
        email_id="test-email-id"
    )
    
    # Publish the result
    await publisher.publish_result(result)
    
    # Verify that publish was called on the exchange
    mock_exchange.publish.assert_called_once()
    
    # Check the message content and properties
    call_args = mock_exchange.publish.call_args
    assert call_args is not None
    
    message = call_args[1]["message"]
    decoded_body = json.loads(message.body.decode())
    assert decoded_body["category"] == EmailCategory.IMPORTANT.value
    assert decoded_body["needs_reply"] is True
    assert decoded_body["confidence"] == 0.9
    assert decoded_body["email_id"] == "test-email-id"


@pytest.mark.asyncio
async def test_publish_result_without_connection():
    """Test that publishing fails if there's no connection."""
    # Create publisher without connecting
    publisher = RabbitMQPublisher()
    
    # Create a test classification result
    result = ClassificationResult(
        category=EmailCategory.IMPORTANT,
        needs_reply=True,
        confidence=0.9
    )
    
    # Attempt to publish without a connection
    with pytest.raises(ValueError) as exc_info:
        await publisher.publish_result(result)
    
    # Verify exception message
    assert "RabbitMQ connection not established" in str(exc_info.value)


@pytest.mark.asyncio
async def test_publish_result_failure(mock_aio_pika):
    """Test that the publisher handles publishing failures properly."""
    # Create publisher and connect
    publisher = RabbitMQPublisher()
    
    # Mock channel and exchange
    mock_channel = mock_aio_pika["channel"]
    mock_exchange = AsyncMock()
    mock_channel.default_exchange = mock_exchange
    
    # Make the publish method raise an exception
    mock_exchange.publish.side_effect = Exception("Publishing failure")
    
    # Connect to RabbitMQ
    await publisher.connect()
    
    # Create a test classification result
    result = ClassificationResult(
        category=EmailCategory.IMPORTANT,
        needs_reply=True,
        confidence=0.9
    )
    
    # Attempt to publish and verify it raises the expected exception
    with pytest.raises(ExternalServiceError) as exc_info:
        await publisher.publish_result(result)
    
    # Verify exception details
    assert "Failed to publish classification result" in str(exc_info.value)
    assert exc_info.value.service == "RabbitMQ"


@pytest.mark.asyncio
async def test_setup_rabbitmq_publisher(mock_aio_pika):
    """Test the setup_rabbitmq_publisher helper function."""
    # Use the utility function to set up the publisher
    with patch("src.publisher.publisher", None) as mock_global_publisher:
        result = await setup_rabbitmq_publisher()
    
    # Verify the function returns a publisher
    assert result is not None
    assert isinstance(result, RabbitMQPublisher)
    
    # Verify connection was established
    mock_aio_pika["connection"].channel.assert_called_once()
    mock_aio_pika["channel"].declare_queue.assert_called_once()