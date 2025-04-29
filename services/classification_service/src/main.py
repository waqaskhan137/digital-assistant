"""Main FastAPI application for the Classification Service."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.exceptions import GmailAutomationError

from .config import config
from .consumer import consumer, setup_rabbitmq_consumer
from .publisher import publisher, setup_rabbitmq_publisher
from .core import EnhancedRuleBasedClassifier

# Configure logging
logging.basicConfig(
    level=config.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default configuration path for rules
DEFAULT_RULES_CONFIG = os.environ.get(
    "RULES_CONFIG_PATH", 
    os.path.join(os.path.dirname(__file__), "rules.json")
)

# Create the enhanced classifier
classifier = EnhancedRuleBasedClassifier(config_path=DEFAULT_RULES_CONFIG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Start up
    logger.info("Classification Service starting up")
    
    # Set up RabbitMQ publisher
    try:
        await setup_rabbitmq_publisher()
    except Exception as e:
        logger.error(f"Error setting up RabbitMQ publisher: {e}")
    
    # Set up RabbitMQ consumer
    try:
        # Pass our classifier as the callback along with the publisher
        await setup_rabbitmq_consumer(classifier.classify, publisher)
    except Exception as e:
        logger.error(f"Error setting up RabbitMQ consumer: {e}")
    
    yield
    
    # Shutdown
    logger.info("Classification Service shutting down")
    if publisher:
        await publisher.close()
    if consumer:
        await consumer.close()


# Create FastAPI application
app = FastAPI(
    title="Classification Service",
    description="Service for classifying emails and determining if they need a reply",
    version="0.1.0",
    lifespan=lifespan,
)


# Exception handler for custom exceptions
@app.exception_handler(GmailAutomationError)
async def custom_exception_handler(request: Request, exc: GmailAutomationError):
    """Handle custom exceptions and convert them to appropriate HTTP responses."""
    status_code = getattr(exc, "status_code", 500)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": exc.__class__.__name__,
            "message": str(exc),
            "details": getattr(exc, "details", None),
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "classification_service"}


@app.get("/rules")
async def list_rules():
    """List the current classification rules."""
    return {
        "classifier": classifier.name,
        "rules": [
            {
                "name": rule.name,
                "category": rule.category.value,
                "needs_reply": rule.needs_reply,
                "confidence": rule.confidence,
                "priority": rule.priority,
                "explanation": rule.explanation,
                "match_count": rule.match_count,
                "evaluation_count": rule.evaluation_count
            }
            for rule in classifier.rules
        ]
    }


@app.get("/rules/stats")
async def rule_statistics():
    """Get statistics about rule usage and match rates."""
    return {
        "classifier": classifier.name,
        "stats": classifier.get_rule_statistics()
    }