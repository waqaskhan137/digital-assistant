import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Literal
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr, conint
from typing import List as PyList  # Use typing.List directly instead of conlist
from redis import Redis

from .rate_limiter import TokenBucketRateLimiter
from .gmail_client import GmailClient
from .rabbitmq_client import RabbitMQClient
from .sync_state import SyncStateManager
from shared.models.email import EmailMessage
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

# Set up logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# --- Exception Handlers ---

async def configuration_error_handler(request: Request, exc: ConfigurationError):
    logger.error(f"Configuration error encountered: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Server configuration error: {exc}"}
    )

async def authentication_error_handler(request: Request, exc: AuthenticationError):
    logger.warning(f"Authentication error: {exc}")
    return JSONResponse(
        status_code=401,
        content={"detail": f"Authentication failed: {exc}"}
    )

async def external_service_error_handler(request: Request, exc: ExternalServiceError):
    logger.error(f"External service error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=502,
        content={"detail": f"Error communicating with external service: {exc}"}
    )

async def sync_state_error_handler(request: Request, exc: SyncStateError):
    logger.error(f"Sync state (Redis) error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=503,
        content={"detail": f"Error accessing state storage service: {exc}"}
    )

async def resource_not_found_error_handler(request: Request, exc: ResourceNotFoundError):
    logger.info(f"Resource not found: {exc}")
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)}
    )

async def validation_error_handler(request: Request, exc: ValidationError):
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": f"Invalid input: {exc}"}
    )

async def rate_limit_error_handler(request: Request, exc: RateLimitError):
    logger.warning(f"Rate limit error: {exc}")
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc}"}
    )

async def email_processing_error_handler(request: Request, exc: EmailProcessingError):
    logger.error(f"Email processing error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error processing email: {exc}"}
    )

async def generic_gmail_automation_error_handler(request: Request, exc: GmailAutomationError):
    logger.error(f"Unhandled project error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"An unexpected server error occurred: {exc}"}
    )

# Create FastAPI app
app = FastAPI(title="Email Ingestion Service")

# --- Register Exception Handlers ---
app.add_exception_handler(ConfigurationError, configuration_error_handler)
app.add_exception_handler(AuthenticationError, authentication_error_handler)
app.add_exception_handler(ExternalServiceError, external_service_error_handler)
app.add_exception_handler(SyncStateError, sync_state_error_handler)
app.add_exception_handler(ResourceNotFoundError, resource_not_found_error_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(RateLimitError, rate_limit_error_handler)
app.add_exception_handler(EmailProcessingError, email_processing_error_handler)
app.add_exception_handler(GmailAutomationError, generic_gmail_automation_error_handler)

# Configuration
REDIS_URL = "redis://redis:6379/0"
RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/"
EXCHANGE_NAME = "email_exchange"
BATCH_SIZE = 100
DEFAULT_PERIOD_DAYS = 30
DEFAULT_POLLING_INTERVAL_MINUTES = {
    "high": 2,      # High volume users
    "medium": 5,    # Medium volume users
    "low": 15       # Low volume users
}

# Enhanced Models with validation
class EmailIngestionConfig(BaseModel):
    """Configuration for email ingestion with enhanced validation."""
    batch_size: conint(gt=0, lt=1000) = Field(
        default=100, 
        description="Number of emails to process per batch. Must be between 1-1000."
    )
    period_days: conint(ge=1, le=90) = Field(
        default=30, 
        description="Number of days in the past to fetch emails from. Must be between 1-90 days."
    )
    polling_frequency_minutes: conint(ge=1, le=60) = Field(
        default=5, 
        description="Minutes between polling operations. Must be between 1-60 minutes."
    )
    include_labels: Optional[PyList[str]] = Field(
        default=None, 
        description="Optional list of Gmail labels to filter by. Maximum 10 labels."
    )
    
    @field_validator('include_labels')
    @classmethod
    def validate_labels(cls, v):
        """Validate that labels are properly formatted and don't exceed the maximum count."""
        if v is not None:
            # Check that we don't have too many labels
            if len(v) > 10:
                raise ValueError("Maximum of 10 labels allowed")
                
            # Check that labels don't contain characters that would break Gmail API queries
            for label in v:
                if not label or any(char in label for char in ['"', '\\', ':']):
                    raise ValueError(f"Label '{label}' contains invalid characters")
        return v
    
    @model_validator(mode='after')
    def check_configuration_logic(self) -> 'EmailIngestionConfig':
        """Validate combinations of configuration options."""
        # Example: If bypassing date filter, restrict batch size for safety
        if getattr(self, 'bypass_date_filter', False) and self.batch_size > 200:
            self.batch_size = 200  # Limit batch size when bypassing date filter
            
        return self


class EmailIngestionRequest(BaseModel):
    """Request to start email ingestion for a user with enhanced validation."""
    user_id: str = Field(..., min_length=3, description="User identifier, minimum 3 characters")
    config: Optional[EmailIngestionConfig] = None
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        """Validate user_id format."""
        if not v:
            raise ValueError("user_id is required")
        if not v.isalnum() and not '_' in v:
            raise ValueError("user_id must contain only alphanumeric characters and underscores")
        return v


class EmailIngestionStatus(BaseModel):
    """Status of ongoing email ingestion."""
    user_id: str
    status: Literal['starting', 'running', 'completed', 'stopped', 'error', 
                   'auth_error', 'service_error'] = 'starting'
    last_synced: Optional[datetime] = None
    emails_processed: int = 0
    next_sync: Optional[datetime] = None
    
    @field_validator('emails_processed')
    @classmethod
    def validate_emails_processed(cls, v):
        """Ensure emails_processed is non-negative."""
        if v < 0:
            raise ValueError("emails_processed cannot be negative")
        return v

# Service instances
rate_limiter = None
gmail_client = None
auth_client = None
rabbitmq_client = None
sync_state_manager = None
active_ingestions = {}


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    global rate_limiter, gmail_client, auth_client, rabbitmq_client, sync_state_manager
    
    try:
        # Import auth client (assuming it's in a different service)
        from shared.clients.auth_client import AuthClient
        
        # Create rate limiter
        rate_limiter = TokenBucketRateLimiter(
            redis_url=REDIS_URL,
            bucket_name="gmail-api",
            max_tokens=200,
            refill_rate=200,
            refill_time=1
        )
        
        # Create auth client
        auth_client = AuthClient()
        
        # Create Gmail client
        gmail_client = GmailClient(
            auth_client=auth_client,
            rate_limiter=rate_limiter,
            batch_size=BATCH_SIZE
        )
        
        # Create RabbitMQ client
        rabbitmq_client = RabbitMQClient(
            connection_url=RABBITMQ_URL,
            exchange_name=EXCHANGE_NAME
        )
        # Initializations that can raise exceptions should be done here
        # so they can be caught and logged, but won't prevent service startup
        # These will be initialized on demand when first used
        
        # Create sync state manager with appropriate initialization
        from services.email_service.src.strategies.volume_based_polling import VolumeBasedPollingStrategy
        polling_strategy = VolumeBasedPollingStrategy()
        
        sync_state_manager = SyncStateManager(
            redis_url=REDIS_URL,
            polling_strategy=polling_strategy,
            key_prefix="email_sync:"
        )
        
        logger.info("Email Service startup complete")
        
    except Exception as e:
        logger.error(f"Error during service startup: {e}", exc_info=True)
        # Don't raise here - allow the app to start even with initialization errors
        # Individual endpoint handlers will check component availability


@app.on_event("shutdown")
async def shutdown_event():
    # Clean up resources
    try:
        if rabbitmq_client:
            await rabbitmq_client.close()
        
        if sync_state_manager:
            await sync_state_manager.close()
            
        logger.info("Email Service shutdown complete")
    except Exception as e:
        logger.error(f"Error during service shutdown: {e}", exc_info=True)


# Dependency for active services
async def get_gmail_client():
    if gmail_client is None:
        raise ConfigurationError("Gmail client not initialized")
    return gmail_client

async def get_rabbitmq_client():
    if rabbitmq_client is None:
        raise ConfigurationError("RabbitMQ client not initialized")
    return rabbitmq_client

async def get_sync_state_manager():
    if sync_state_manager is None:
        raise ConfigurationError("Sync state manager not initialized")
    return sync_state_manager


# Routes
@app.post("/ingest/start", response_model=EmailIngestionStatus)
async def start_ingestion(
    request: EmailIngestionRequest,
    background_tasks: BackgroundTasks,
    client: GmailClient = Depends(get_gmail_client)
):
    """Start email ingestion for a user."""
    user_id = request.user_id
    
    # Validate user_id
    if not user_id:
        raise ValidationError("user_id is required")
    
    # Use default config if not provided
    config = request.config or EmailIngestionConfig()
    
    # Check if ingestion is already running for this user
    if user_id in active_ingestions:
        return active_ingestions[user_id]
    
    # Create ingestion status
    status = EmailIngestionStatus(
        user_id=user_id,
        status="starting",
        next_sync=datetime.now()
    )
    active_ingestions[user_id] = status
    
    # Start ingestion in background
    background_tasks.add_task(
        ingest_emails_background,
        user_id=user_id,
        client=client,
        config=config
    )
    
    return status

# Adding a direct endpoint for testing without date filtering
@app.post("/ingest/all", response_model=Dict[str, Any])
async def ingest_all_emails(
    request: EmailIngestionRequest,
    client: GmailClient = Depends(get_gmail_client)
):
    """
    Get all emails without date filtering (for testing).
    
    This endpoint is useful for verifying that the OAuth connection
    and Gmail API access are working correctly.
    """
    user_id = request.user_id
    
    # Validate user_id
    if not user_id:
        raise ValidationError("user_id is required")
        
    # Directly call get_all_emails to retrieve emails without date filtering
    try:
        emails = await client.get_all_emails(user_id=user_id, max_emails=50)
        
        return {
            "user_id": user_id,
            "emails_found": len(emails),
            "success": True,
            "message": f"Retrieved {len(emails)} emails without date filtering"
        }
    except AuthenticationError as e:
        # Let the exception handler middleware handle this
        raise
    except ExternalServiceError as e:
        # Let the exception handler middleware handle this
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching all emails for user {user_id}: {e}", exc_info=True)
        raise EmailProcessingError(f"Failed to fetch emails: {e}") from e

@app.get("/ingest/status/{user_id}", response_model=EmailIngestionStatus)
async def get_ingestion_status(user_id: str):
    """Get the status of email ingestion for a user."""
    if not user_id:
        raise ValidationError("user_id is required")
        
    if user_id not in active_ingestions:
        raise ResourceNotFoundError(f"No active ingestion found for user {user_id}")
    
    return active_ingestions[user_id]


@app.post("/ingest/stop/{user_id}")
async def stop_ingestion(user_id: str):
    """Stop email ingestion for a user."""
    if not user_id:
        raise ValidationError("user_id is required")
        
    if user_id not in active_ingestions:
        raise ResourceNotFoundError(f"No active ingestion found for user {user_id}")
    
    # Update status to stopped
    active_ingestions[user_id].status = "stopped"
    
    # Remove from active ingestions
    status = active_ingestions.pop(user_id)
    
    return {"message": f"Ingestion stopped for user {user_id}"}


# Background tasks
async def ingest_emails_background(
    user_id: str,
    client: GmailClient,
    config: EmailIngestionConfig
):
    """Background task to ingest emails."""
    try:
        # Update status to running
        active_ingestions[user_id].status = "running"
        
        # Get last sync state
        last_message_id = None
        if sync_state_manager:
            try:
                last_message_id = await sync_state_manager.get_last_message_id(user_id)
                sync_state = await sync_state_manager.get_sync_state(user_id)
                logger.info(f"Retrieved sync state for user {user_id}: {sync_state}")
            except (SyncStateError, ConfigurationError) as e:
                logger.warning(f"Error retrieving sync state for user {user_id}: {e}")
                # Continue with sync even if we can't get the state
        
        # Determine which method to use based on configuration
        if config.bypass_date_filter:
            # Use the get_all_emails method if date filtering is bypassed
            logger.info(f"Bypassing date filter for user {user_id} and fetching all emails")
            emails = await client.get_all_emails(
                user_id=user_id,
                max_emails=config.batch_size * 5  # Multiply by 5 to get a reasonable number of emails
            )
        else:
            # Calculate since date (default: 30 days or from last sync)
            since_date = datetime.now() - timedelta(days=config.period_days)
            
            # Log starting sync
            logger.info(f"Starting email sync for user {user_id} since {since_date}")
            
            # Get emails since date
            emails = await client.get_emails_since(
                user_id=user_id,
                since_date=since_date,
                include_labels=config.include_labels
            )
        
        logger.info(f"Found {len(emails)} emails to process for user {user_id}")
        
        # Process emails in batches
        for i in range(0, len(emails), config.batch_size):
            batch = emails[i:i+config.batch_size]
            
            # Update progress
            active_ingestions[user_id].emails_processed += len(batch)
            
            # Process batch
            await process_email_batch(user_id, batch)
            
            # Save last message ID for resumable syncs
            if sync_state_manager and batch:
                try:
                    last_message = batch[-1]
                    await sync_state_manager.save_last_message_id(user_id, last_message["id"])
                    
                    # Save sync metrics
                    sync_metrics = {
                        "batch_size": len(batch),
                        "total_processed": active_ingestions[user_id].emails_processed,
                        "timestamp": datetime.now().isoformat()
                    }
                    await sync_state_manager.update_sync_metrics_in_redis(user_id, sync_metrics)
                except (SyncStateError, ConfigurationError) as e:
                    logger.warning(f"Error saving sync state for user {user_id}: {e}")
                    # Continue processing even if we can't save state
        
        # Update status to completed
        active_ingestions[user_id].status = "completed"
        active_ingestions[user_id].last_synced = datetime.now()
        
        # Save completed sync state
        if sync_state_manager:
            try:
                sync_state = {
                    "last_sync": datetime.now().isoformat(),
                    "emails_processed": active_ingestions[user_id].emails_processed,
                    "status": "completed"
                }
                await sync_state_manager.save_sync_state(user_id, sync_state)
            except (SyncStateError, ConfigurationError) as e:
                logger.warning(f"Error saving final sync state for user {user_id}: {e}")
        
        # Schedule next sync based on configured polling frequency
        next_sync = datetime.now() + timedelta(minutes=config.polling_frequency_minutes)
        active_ingestions[user_id].next_sync = next_sync
        
        # Schedule next ingestion
        asyncio.create_task(
            schedule_next_ingestion(
                user_id=user_id,
                client=client, 
                config=config,
                next_sync=next_sync
            )
        )
        
    except AuthenticationError as e:
        logger.error(f"Authentication error during email ingestion for user {user_id}: {e}")
        active_ingestions[user_id].status = "auth_error"
        if sync_state_manager:
            try:
                error_state = {
                    "last_sync_attempt": datetime.now().isoformat(),
                    "status": "auth_error",
                    "error": str(e)
                }
                await sync_state_manager.save_sync_state(user_id, error_state)
            except Exception as save_error:
                logger.error(f"Failed to save error state: {save_error}")
    except (ExternalServiceError, SyncStateError) as e:
        logger.error(f"Service error during email ingestion for user {user_id}: {e}")
        active_ingestions[user_id].status = "service_error"
        if sync_state_manager:
            try:
                error_state = {
                    "last_sync_attempt": datetime.now().isoformat(),
                    "status": "service_error",
                    "error": str(e)
                }
                await sync_state_manager.save_sync_state(user_id, error_state)
            except Exception as save_error:
                logger.error(f"Failed to save error state: {save_error}")
    except Exception as e:
        logger.error(f"Unexpected error during email ingestion for user {user_id}: {e}", exc_info=True)
        active_ingestions[user_id].status = "error"
        # Save error in sync state
        if sync_state_manager:
            try:
                error_state = {
                    "last_sync_attempt": datetime.now().isoformat(),
                    "status": "error",
                    "error": str(e)
                }
                await sync_state_manager.save_sync_state(user_id, error_state)
            except Exception as save_error:
                logger.error(f"Failed to save error state: {save_error}")


async def process_email_batch(user_id: str, email_batch: List[Dict[str, Any]]):
    """Process a batch of emails and send to classification service."""
    try:
        logger.info(f"Processing batch of {len(email_batch)} emails for user {user_id}")
        
        # Normalize emails into shared model format
        normalized_messages = await gmail_client.normalize_messages(user_id, email_batch)
        
        # Publish to RabbitMQ
        if rabbitmq_client and normalized_messages:
            await rabbitmq_client.publish_batch(normalized_messages, routing_key="email.batch")
            logger.info(f"Published {len(normalized_messages)} emails to RabbitMQ")
        else:
            if not rabbitmq_client:
                logger.warning("RabbitMQ client not initialized, skipping publishing")
            elif not normalized_messages:
                logger.info("No normalized messages to publish")
        
    except AuthenticationError as e:
        logger.error(f"Authentication error processing email batch for user {user_id}: {e}")
        raise
    except ExternalServiceError as e:
        logger.error(f"External service error processing email batch for user {user_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing email batch for user {user_id}: {e}", exc_info=True)
        raise EmailProcessingError(f"Failed to process email batch: {e}") from e


async def schedule_next_ingestion(
    user_id: str,
    client: GmailClient,
    config: EmailIngestionConfig,
    next_sync: datetime
):
    """Schedule the next email ingestion run."""
    # Calculate seconds until next sync
    now = datetime.now()
    seconds_to_wait = (next_sync - now).total_seconds()
    
    if seconds_to_wait > 0:
        # Wait until next scheduled sync
        await asyncio.sleep(seconds_to_wait)
        
        # Check if ingestion was stopped
        if user_id not in active_ingestions or active_ingestions[user_id].status == "stopped":
            return
        
        # Start next ingestion cycle
        asyncio.create_task(
            ingest_emails_background(
                user_id=user_id,
                client=client,
                config=config
            )
        )