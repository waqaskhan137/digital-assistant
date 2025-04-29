"""Integration tests for the Classification Service."""
import json
from datetime import datetime
import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.main import app
from src.models import EmailCategory, ClassificationResult
from shared.models.email import EmailMessage, EmailAddress
from tests.conftest import DateTimeEncoder

@pytest.fixture
def test_client():
    """Create a FastAPI test client."""
    return TestClient(app)

@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    """Test the health check endpoint."""
    response = test_client.get("/health")
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "classification_service"}

@pytest.mark.asyncio
async def test_rules_endpoint(test_client):
    """Test the rules listing endpoint."""
    response = test_client.get("/rules")
    
    assert response.status_code == 200
    result = response.json()
    
    assert "classifier" in result
    assert result["classifier"] == "EnhancedRuleBasedClassifier"
    assert "rules" in result
    assert len(result["rules"]) > 0
    
    # Verify rule structure
    rule = result["rules"][0]
    assert "name" in rule
    assert "category" in rule
    assert "needs_reply" in rule
    assert "confidence" in rule

@pytest.mark.asyncio
async def test_end_to_end_classification_flow(sample_support_email):
    """Test the end-to-end flow of receiving and classifying an email."""
    # Mock the RabbitMQ consumer
    mock_consumer = AsyncMock()
    
    # Set up the app with our consumer
    with patch("src.main.consumer", mock_consumer):
        # Import the classifier directly from main
        from src.main import classifier
        
        # Classify the email directly
        result = await classifier.classify(sample_support_email)
        
        # Verify classification results
        assert result is not None
        assert isinstance(result, ClassificationResult)
        
        # A support email should match a support rule
        assert result.category == EmailCategory.SUPPORT
        assert result.needs_reply is True
        
        # Verify it has an email_id for correlation
        assert result.email_id == sample_support_email.id