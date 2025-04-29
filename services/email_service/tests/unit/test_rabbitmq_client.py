import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import aio_pika
import pytest_asyncio

# Import our mock setup first to handle shared module dependencies
from services.email_service.tests.mock_modules import MockEmailMessage

# Now we can safely import the module
from services.email_service.src.rabbitmq_client import RabbitMQClient


class TestRabbitMQClient:
    """Test cases for the RabbitMQClient class."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create a mock RabbitMQ connection."""
        mock = AsyncMock()
        mock.is_closed = False
        mock.close = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_channel(self):
        """Create a mock RabbitMQ channel."""
        mock = AsyncMock()
        mock.declare_queue = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_exchange(self):
        """Create a mock RabbitMQ exchange."""
        mock = AsyncMock()
        mock.publish = AsyncMock()
        return mock
    
    @pytest_asyncio.fixture
    async def rabbitmq_client(self, mock_connection, mock_channel, mock_exchange):
        """Create a RabbitMQClient with mocked dependencies."""
        # Setup the mocks for initialization
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        
        # Patch aio_pika.connect_robust to return our mock connection
        with patch('aio_pika.connect_robust', AsyncMock(return_value=mock_connection)):
            # Patch EmailMessage
            with patch('services.email_service.src.rabbitmq_client.EmailMessage', MockEmailMessage):
                client = RabbitMQClient("amqp://guest:guest@localhost:5672/")
                await client.initialize()
                
                # Store mocks in client for access in tests
                client._mock_connection = mock_connection
                client._mock_channel = mock_channel
                client._mock_exchange = mock_exchange
                
                yield client
                await client.close()
    
    @pytest.mark.asyncio
    async def test_initialize(self, mock_connection, mock_channel, mock_exchange):
        """Test initializing the RabbitMQ client."""
        # Setup mocks
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        
        # Patch the aio_pika.connect_robust function
        with patch('aio_pika.connect_robust', AsyncMock(return_value=mock_connection)):
            # Create client
            client = RabbitMQClient(
                connection_url="amqp://guest:guest@localhost:5672/",
                exchange_name="test_exchange"
            )
            
            # Initialize client
            await client.initialize()
            
            # Verify it called connect_robust with the correct URL
            aio_pika.connect_robust.assert_called_once_with("amqp://guest:guest@localhost:5672/")
            
            # Verify channel creation
            mock_connection.channel.assert_called_once()
            
            # Verify exchange declaration
            mock_channel.declare_exchange.assert_called_once_with(
                "test_exchange",
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            # Verify queue declaration
            mock_channel.declare_queue.assert_called_once()
            
            # Verify initialization state
            assert client._initialized is True
            assert client.connection == mock_connection
            assert client.channel == mock_channel
            assert client.exchange == mock_exchange
    
    @pytest.mark.asyncio
    async def test_initialize_with_retry(self, mock_connection, mock_channel, mock_exchange):
        """Test initialization retry logic on connection failure."""
        # Setup mocks
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        
        # Create a connect function that fails once then succeeds
        connect_mock = AsyncMock()
        # On first call, raise an exception of type AMQPConnectionError
        connect_mock.side_effect = [
            aio_pika.exceptions.AMQPConnectionError("Connection refused"),  # First call fails
            mock_connection                                                # Second call succeeds
        ]
        
        # Patch asyncio.sleep to speed up the test
        with patch('asyncio.sleep', AsyncMock()):
            # Patch aio_pika.connect_robust with our mock
            with patch('aio_pika.connect_robust', connect_mock):
                # Create client with short retry delay for faster tests
                client = RabbitMQClient(
                    connection_url="amqp://guest:guest@localhost:5672/",
                    retry_delay=0.1
                )
                
                # Initialize client
                await client.initialize()
                
                # Verify connect was called twice (one failure, one success)
                assert connect_mock.call_count == 2
                
                # Verify client is initialized after retry
                assert client._initialized is True
                
                # Clean up
                await client.close()
    
    @pytest.mark.asyncio
    async def test_initialize_max_retries_exceeded(self):
        """Test that initialization fails after max retries are exceeded."""
        # Create a connect function that always fails with AMQPConnectionError
        connect_mock = AsyncMock(side_effect=aio_pika.exceptions.AMQPConnectionError("Connection refused"))
        
        # Patch asyncio.sleep to speed up the test
        with patch('asyncio.sleep', AsyncMock()):
            # Patch aio_pika.connect_robust with our mock
            with patch('aio_pika.connect_robust', connect_mock):
                # Create client with short retry delay and few retries
                client = RabbitMQClient(
                    connection_url="amqp://guest:guest@localhost:5672/",
                    max_retries=3,
                    retry_delay=0.1
                )
                
                # Initialize client should raise ConfigurationError
                with pytest.raises(Exception) as exc_info:
                    await client.initialize()
                
                # Verify the specific exception type
                assert "Unable to connect to RabbitMQ" in str(exc_info.value)
                
                # Verify connect was called max_retries times
                assert connect_mock.call_count == 3
                
                # Verify client is not initialized
                assert client._initialized is False
    
    @pytest.mark.asyncio
    async def test_close(self, rabbitmq_client):
        """Test closing the RabbitMQ connection."""
        mock_connection = rabbitmq_client._mock_connection
        
        # Close the connection
        await rabbitmq_client.close()
        
        # Verify connection was closed
        mock_connection.close.assert_called_once()
        
        # Verify client is no longer initialized
        assert rabbitmq_client._initialized is False
    
    @pytest.mark.asyncio
    async def test_publish_email(self, rabbitmq_client):
        """Test publishing a single email message."""
        # Create test email with patched EmailMessage
        with patch('services.email_service.src.rabbitmq_client.EmailMessage', MockEmailMessage):
            email = MockEmailMessage(
                id="test123",
                user_id="user123",
                thread_id="thread123",
                subject="Test Subject",
                from_email="sender@example.com",
                to="recipient@example.com",
                date=datetime(2025, 4, 24, 10, 0, 0),
                body_text="Test email body",
                body_html="<p>Test email body</p>",
                labels=["INBOX"],
                snippet="Test email body",
                has_attachments=False,
                raw_data={}
            )
            
            # Access the mock exchange
            mock_exchange = rabbitmq_client._mock_exchange
            
            # Call the method
            await rabbitmq_client.publish_email(email, routing_key="email.test")
            
            # Verify exchange publish was called
            mock_exchange.publish.assert_called_once()
            
            # Verify the message content
            call_args = mock_exchange.publish.call_args
            message = call_args[0][0]
            routing_key = call_args[1]["routing_key"]
            
            # Check message properties
            assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
            assert message.content_type == "application/json"
            
            # Decode and check message body
            message_body = json.loads(message.body.decode())
            assert message_body["id"] == "test123"
            assert message_body["user_id"] == "user123"
            assert message_body["subject"] == "Test Subject"
            assert "date" in message_body  # Date should be serialized to ISO format
            
            # Check routing key
            assert routing_key == "email.test"
    
    @pytest.mark.asyncio
    async def test_publish_batch(self, rabbitmq_client):
        """Test publishing a batch of email messages."""
        # Create test emails with patched EmailMessage
        with patch('services.email_service.src.rabbitmq_client.EmailMessage', MockEmailMessage):
            emails = [
                MockEmailMessage(
                    id=f"test{i}",
                    user_id="user123",
                    thread_id=f"thread{i}",
                    subject=f"Test Subject {i}",
                    from_email="sender@example.com",
                    to="recipient@example.com",
                    date=datetime(2025, 4, 24, 10, 0, 0),
                    body_text=f"Test email body {i}",
                    body_html=f"<p>Test email body {i}</p>",
                    labels=["INBOX"],
                    snippet=f"Test email body {i}",
                    has_attachments=False,
                    raw_data={}
                )
                for i in range(3)
            ]
            
            # Access the mock exchange
            mock_exchange = rabbitmq_client._mock_exchange
            
            # Call the method
            await rabbitmq_client.publish_batch(emails, routing_key="email.batch.test")
            
            # Verify exchange publish was called
            mock_exchange.publish.assert_called_once()
            
            # Verify the message content
            call_args = mock_exchange.publish.call_args
            message = call_args[0][0]
            routing_key = call_args[1]["routing_key"]
            
            # Check message properties
            assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
            assert message.content_type == "application/json"
            
            # Decode and check message body
            message_body = json.loads(message.body.decode())
            assert "emails" in message_body
            assert len(message_body["emails"]) == 3
            assert message_body["emails"][0]["id"] == "test0"
            assert message_body["emails"][1]["id"] == "test1"
            assert message_body["emails"][2]["id"] == "test2"
            
            # Check routing key
            assert routing_key == "email.batch.test"
    
    @pytest.mark.asyncio
    async def test_publish_email_not_initialized(self, mock_connection, mock_channel, mock_exchange):
        """Test publishing when client is not initialized calls initialize first."""
        # Setup mocks
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        
        # Patch the connections
        with patch('aio_pika.connect_robust', AsyncMock(return_value=mock_connection)):
            with patch('services.email_service.src.rabbitmq_client.EmailMessage', MockEmailMessage):
                # Create client but don't initialize
                client = RabbitMQClient("amqp://guest:guest@localhost:5672/")
                
                # Create test email
                email = MockEmailMessage(
                    id="test123",
                    user_id="user123",
                    thread_id="thread123",
                    subject="Test Subject",
                    from_email="sender@example.com",
                    to="recipient@example.com",
                    date=datetime(2025, 4, 24, 10, 0, 0),
                    body_text="Test email body",
                    body_html="<p>Test email body</p>",
                    labels=["INBOX"],
                    snippet="Test email body",
                    has_attachments=False,
                    raw_data={}
                )
                
                # Call publish without initializing first
                await client.publish_email(email)
                
                # Verify initialize was called implicitly
                aio_pika.connect_robust.assert_called_once()
                assert client._initialized is True
                
                # Verify message was published
                mock_exchange.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_error_handling(self, rabbitmq_client):
        """Test error handling during publish."""
        # Make the publish method raise an exception
        mock_exchange = rabbitmq_client._mock_exchange
        mock_exchange.publish.side_effect = Exception("Publish failed")
        
        # Create test email with patched EmailMessage
        with patch('services.email_service.src.rabbitmq_client.EmailMessage', MockEmailMessage):
            email = MockEmailMessage(
                id="test123",
                user_id="user123",
                thread_id="thread123",
                subject="Test Subject",
                from_email="sender@example.com",
                to="recipient@example.com",
                date=datetime(2025, 4, 24, 10, 0, 0),
                body_text="Test email body",
                body_html="<p>Test email body</p>",
                labels=["INBOX"],
                snippet="Test email body",
                has_attachments=False,
                raw_data={}
            )
            
            # Call publish should raise the exception
            with pytest.raises(Exception):
                await rabbitmq_client.publish_email(email)
            
            # Verify publish was attempted
            mock_exchange.publish.assert_called_once()