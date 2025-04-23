from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

from ..models.email import EmailData
from ..gmail_client import GmailClient
from ..main import EmailIngestionRequest, EmailIngestionStatus, EmailIngestionConfig

# Create router
router = APIRouter(
    prefix="/ingest",
    tags=["email-ingestion"],
)

# Service instances
active_ingestions = {}
logger = logging.getLogger(__name__)

# Dependency for active service
async def get_gmail_client():
    from ..main import gmail_client
    if gmail_client is None:
        raise HTTPException(status_code=503, detail="Gmail client not initialized")
    return gmail_client


@router.post("/start", response_model=EmailIngestionStatus)
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


@router.get("/status/{user_id}", response_model=EmailIngestionStatus)
async def get_ingestion_status(user_id: str):
    """Get the status of email ingestion for a user."""
    if user_id not in active_ingestions:
        raise HTTPException(status_code=404, detail="No active ingestion for user")
    
    return active_ingestions[user_id]


@router.post("/stop/{user_id}")
async def stop_ingestion(user_id: str):
    """Stop email ingestion for a user."""
    if user_id not in active_ingestions:
        raise HTTPException(status_code=404, detail="No active ingestion for user")
    
    # Update status to stopped
    active_ingestions[user_id].status = "stopped"
    
    # Remove from active ingestions
    status = active_ingestions.pop(user_id)
    
    return {"message": f"Ingestion stopped for user {user_id}"}


# Import the background tasks from main to avoid circular imports
from ..main import ingest_emails_background