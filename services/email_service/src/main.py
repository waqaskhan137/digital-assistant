import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from redis import Redis

from .rate_limiter import TokenBucketRateLimiter
from .gmail_client import GmailClient
from .rabbitmq_client import RabbitMQClient
from .sync_state import SyncStateManager
from shared.models.email import EmailMessage

# Set up logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Email Ingestion Service")

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

# Models
class EmailIngestionConfig(BaseModel):
    """Configuration for email ingestion."""
    batch_size: int = 100
    period_days: int = 30
    polling_frequency_minutes: int = 5
    include_labels: Optional[List[str]] = None
    bypass_date_filter: bool = False  # New option to bypass date filtering


class EmailIngestionRequest(BaseModel):
    """Request to start email ingestion for a user."""
    user_id: str
    config: Optional[EmailIngestionConfig] = None


class EmailIngestionStatus(BaseModel):
    """Status of ongoing email ingestion."""
    user_id: str
    status: str
    last_synced: Optional[datetime] = None
    emails_processed: int = 0
    next_sync: Optional[datetime] = None


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
    await rabbitmq_client.initialize()
    
    # Create sync state manager
    sync_state_manager = SyncStateManager(
        redis_url=REDIS_URL,
        key_prefix="email_sync:"
    )
    await sync_state_manager.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    # Clean up resources
    if rabbitmq_client:
        await rabbitmq_client.close()
    
    if sync_state_manager:
        await sync_state_manager.close()


# Dependency for active services
async def get_gmail_client():
    if gmail_client is None:
        raise HTTPException(status_code=503, detail="Gmail client not initialized")
    return gmail_client

async def get_rabbitmq_client():
    if rabbitmq_client is None:
        raise HTTPException(status_code=503, detail="RabbitMQ client not initialized")
    return rabbitmq_client

async def get_sync_state_manager():
    if sync_state_manager is None:
        raise HTTPException(status_code=503, detail="Sync state manager not initialized")
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
    
    # Directly call get_all_emails to retrieve emails without date filtering
    emails = await client.get_all_emails(user_id=user_id, max_emails=50)
    
    return {
        "user_id": user_id,
        "emails_found": len(emails),
        "success": True,
        "message": f"Retrieved {len(emails)} emails without date filtering"
    }

@app.get("/ingest/status/{user_id}", response_model=EmailIngestionStatus)
async def get_ingestion_status(user_id: str):
    """Get the status of email ingestion for a user."""
    if user_id not in active_ingestions:
        raise HTTPException(status_code=404, detail="No active ingestion for user")
    
    return active_ingestions[user_id]


@app.post("/ingest/stop/{user_id}")
async def stop_ingestion(user_id: str):
    """Stop email ingestion for a user."""
    if user_id not in active_ingestions:
        raise HTTPException(status_code=404, detail="No active ingestion for user")
    
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
            last_message_id = await sync_state_manager.get_last_message_id(user_id)
            sync_state = await sync_state_manager.get_sync_state(user_id)
            logger.info(f"Retrieved sync state for user {user_id}: {sync_state}")
        
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
                last_message = batch[-1]
                await sync_state_manager.save_last_message_id(user_id, last_message["id"])
                
                # Save sync metrics
                sync_metrics = {
                    "batch_size": len(batch),
                    "total_processed": active_ingestions[user_id].emails_processed,
                    "timestamp": datetime.now().isoformat()
                }
                await sync_state_manager.record_sync_metrics(user_id, sync_metrics)
        
        # Update status to completed
        active_ingestions[user_id].status = "completed"
        active_ingestions[user_id].last_synced = datetime.now()
        
        # Save completed sync state
        if sync_state_manager:
            sync_state = {
                "last_sync": datetime.now().isoformat(),
                "emails_processed": active_ingestions[user_id].emails_processed,
                "status": "completed"
            }
            await sync_state_manager.save_sync_state(user_id, sync_state)
        
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
        
    except Exception as e:
        logger.error(f"Error during email ingestion for user {user_id}: {str(e)}")
        active_ingestions[user_id].status = "error"
        # Save error in sync state
        if sync_state_manager:
            error_state = {
                "last_sync_attempt": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }
            await sync_state_manager.save_sync_state(user_id, error_state)


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
        
    except Exception as e:
        logger.error(f"Error processing email batch for user {user_id}: {str(e)}")
        raise


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