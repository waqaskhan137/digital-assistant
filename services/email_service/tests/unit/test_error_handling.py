import pytest
import json
import base64
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime

from services.email_service.src.content_extractor import EmailContentExtractor
from services.email_service.src.email_normalizer import EmailNormalizer
from services.email_service.src.gmail_api_client import GmailApiClient
from services.email_service.src.rabbitmq_client import RabbitMQClient
from services.email_service.src.sync_state import SyncStateManager
from services.email_service.src.main import app

from shared.exceptions import (
    GmailAutomationError,
    AuthenticationError, 
    ConfigurationError,
    ExternalServiceError,
    SyncStateError,
    ResourceNotFoundError,
    ValidationError,
    RateLimitError,
    EmailProcessingError
)

@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    with TestClient(app) as client:
        yield client

@pytest.fixture
def content_extractor():
    """Create a ContentExtractor instance."""
    return EmailContentExtractor()

@pytest.fixture
def email_normalizer(content_extractor):
    """Create an EmailNormalizer with a content extractor."""
    return EmailNormalizer(content_extractor)

@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    return AsyncMock()

@pytest.fixture
def polling_strategy():
    """Create a mock polling strategy."""
    strategy = MagicMock()
    strategy.calculate_interval.return_value = 5
    return strategy

class TestContentExtractorErrorHandling:
    """Test error handling in EmailContentExtractor."""
    
    def test_extract_body_validation_errors(self, content_extractor):
        """Test that ValidationError is raised for invalid inputs."""
        # Test with None payload
        with pytest.raises(ValidationError):
            content_extractor.extract_body(None)
        
        # Test with non-dict payload
        with pytest.raises(ValidationError):
            content_extractor.extract_body("not a dict")
    
    def test_extract_body_base64_decode_errors(self, content_extractor):
        """Test handling of base64 decoding errors."""
        # Create payload with invalid base64 data
        payload = {
            "body": {"data": "invalid base64 data!!!"},
            "mimeType": "text/html"
        }
        
        # Should handle error gracefully and return empty strings
        html, text = content_extractor.extract_body(payload)
        assert html == ""
        assert text == ""
    
    def test_get_attachments_validation_errors(self, content_extractor):
        """Test that ValidationError is raised for invalid inputs in get_attachments."""
        # Test with None payload
        with pytest.raises(ValidationError):
            content_extractor.get_attachments(None)
        
        # Test with non-dict payload
        with pytest.raises(ValidationError):
            content_extractor.get_attachments("not a dict")


class TestEmailNormalizerErrorHandling:
    """Test error handling in EmailNormalizer."""
    
    def test_normalize_validation_errors(self, email_normalizer):
        """Test that ValidationError is raised for invalid inputs."""
        # Test with None message
        with pytest.raises(ValidationError):
            email_normalizer.normalize(None, "user123")
        
        # Test with non-dict message
        with pytest.raises(ValidationError):
            email_normalizer.normalize("not a dict", "user123")
        
        # Test with missing required id field
        with pytest.raises(ValidationError):
            email_normalizer.normalize({}, "user123")
    
    def test_normalize_batch_validation_errors(self, email_normalizer):
        """Test that ValidationError is raised for invalid batch inputs."""
        # Test with None batch
        with pytest.raises(ValidationError):
            email_normalizer.normalize_batch(None, "user123")
        
        # Test with non-list batch
        with pytest.raises(ValidationError):
            email_normalizer.normalize_batch("not a list", "user123")
    
    def test_normalize_partial_batch_failures(self, email_normalizer):
        """Test that batch normalization continues even if some messages fail."""
        # Create a batch with one valid and one invalid message
        messages = [
            {"id": "msg1", "payload": {}},  # Valid (minimal)
            {},  # Invalid (missing id)
            {"id": "msg2", "payload": {}}   # Valid (minimal)
        ]
        
        # Should process the valid messages and skip the invalid one
        normalized = email_normalizer.normalize_batch(messages, "user123")
        assert len(normalized) == 2
        assert normalized[0].id == "msg1"
        assert normalized[1].id == "msg2"


class TestSyncStateManagerErrorHandling:
    """Test error handling in SyncStateManager."""
    
    @pytest.mark.asyncio
    async def test_initialize_configuration_error(self, polling_strategy):
        """Test that ConfigurationError is raised for Redis connection issues."""
        # Create a SyncStateManager with invalid Redis URL
        sync_state_manager = SyncStateManager(
            redis_url="redis://invalid:6379/0",
            polling_strategy=polling_strategy
        )
        
        # Should raise ConfigurationError on initialization
        with pytest.raises(ConfigurationError):
            await sync_state_manager.initialize()
    
    @pytest.mark.asyncio
    async def test_redis_operation_error(self, polling_strategy, mock_redis):
        """Test that SyncStateError is raised for Redis operational issues."""
        # Create a SyncStateManager with mock Redis client
        sync_state_manager = SyncStateManager(
            redis_url="redis://localhost:6379/0",
            polling_strategy=polling_strategy
        )
        
        # Mock Redis get operation to fail
        sync_state_manager._redis = mock_redis
        sync_state_manager._initialized = True
        mock_redis.get.side_effect = Exception("Redis operation failed")
        
        # Should raise SyncStateError
        with pytest.raises(SyncStateError):
            await sync_state_manager.get_sync_state("user123")


class TestRabbitMQClientErrorHandling:
    """Test error handling in RabbitMQClient."""
    
    @pytest.mark.asyncio
    async def test_initialize_configuration_error(self):
        """Test that ConfigurationError is raised for connection issues."""
        # Create a RabbitMQClient with empty connection URL
        client = RabbitMQClient(connection_url="")
        
        # Should raise ConfigurationError
        with pytest.raises(ConfigurationError):
            await client.initialize()
    
    @pytest.mark.asyncio
    async def test_publish_external_service_error(self):
        """Test that ExternalServiceError is raised for publishing issues."""
        # Create a RabbitMQClient with mock connection/exchange
        client = RabbitMQClient(connection_url="amqp://guest:guest@localhost:5672/")
        client._initialized = True
        client.exchange = AsyncMock()
        client.exchange.publish.side_effect = Exception("Publish failed")
        
        # Create a minimal email message
        from shared.models.email import EmailMessage, EmailAddress
        email = EmailMessage(
            id="msg1",
            thread_id="thread1",
            user_id="user123",
            date=datetime.now(),
            subject="Test Subject",
            from_address=EmailAddress(email="test@example.com", name="Test Sender"),
            to_addresses=[],
            text_content="Test content"
        )
        
        # Should raise ExternalServiceError
        with pytest.raises(ExternalServiceError):
            await client.publish_email(email)


class TestAPIErrorHandling:
    """Test error handling at the API level."""
    
    def test_resource_not_found_error(self, test_client):
        """Test that ResourceNotFoundError results in 404 response."""
        # Make a request to an endpoint that would raise ResourceNotFoundError
        response = test_client.get("/ingest/status/nonexistent_user")
        
        # Should return 404 status code
        assert response.status_code == 404
        assert "detail" in response.json()
    
    def test_validation_error(self, test_client):
        """Test that ValidationError results in 400 response."""
        # Make a request with invalid data
        response = test_client.post(
            "/ingest/start",
            json={"user_id": ""}  # Empty user_id is invalid
        )
        
        # Should return 400 status code
        assert response.status_code == 400
        assert "detail" in response.json()


def test_exception_hierarchy():
    """Test the exception hierarchy relationships."""
    # Test that all exceptions inherit from the base GmailAutomationError
    assert issubclass(AuthenticationError, GmailAutomationError)
    assert issubclass(ConfigurationError, GmailAutomationError)
    assert issubclass(ValidationError, GmailAutomationError)
    assert issubclass(ExternalServiceError, GmailAutomationError)
    assert issubclass(ResourceNotFoundError, GmailAutomationError)
    assert issubclass(EmailProcessingError, GmailAutomationError)
    assert issubclass(SyncStateError, GmailAutomationError)
    
    # Test that RateLimitError is a subclass of ExternalServiceError
    assert issubclass(RateLimitError, ExternalServiceError)