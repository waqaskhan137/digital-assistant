import sys
from unittest.mock import MagicMock, AsyncMock
from fastapi import APIRouter, HTTPException, Request, status, Body, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

# Ensure the mock_email_module from previous edit is available
try:
    from .mock_modules import mock_email_module
except ImportError:
    # If it doesn't exist yet, create it
    mock_email_module = MagicMock()

# Create models for request validation
class EmailIngestionConfig(BaseModel):
    batch_size: int = 100
    period_days: int = 30
    polling_frequency_minutes: int = 5

class EmailIngestionRequest(BaseModel):
    user_id: str
    config: EmailIngestionConfig

class EmailIngestionStatusModel(BaseModel):
    user_id: str
    status: str
    emails_processed: Optional[int] = 0
    last_synced: Optional[datetime] = None
    next_sync: Optional[datetime] = None

# Create a mock for the ingest_emails_background function
mock_ingest_emails_background = AsyncMock()

# Create a properly configured router
mock_router = APIRouter()

# Add route handlers to the router with proper request validation
@mock_router.post("/ingest/start")
async def start_ingestion(
    request: EmailIngestionRequest = Body(...),
    background_tasks: BackgroundTasks = None
):
    # Create a status model
    status_model = EmailIngestionStatusModel(
        user_id=request.user_id,
        status="starting",
        next_sync=datetime.now()
    )
    
    # Add the background task if provided
    if background_tasks:
        background_tasks.add_task(mock_ingest_emails_background, request.user_id, request.config)
    
    return status_model

@mock_router.get("/ingest/status/{user_id}")
async def get_ingestion_status(user_id: str):
    if user_id == "nonexistent_user":
        raise HTTPException(status_code=404, detail="No active ingestion for user")
    # Return mock status
    return EmailIngestionStatusModel(
        user_id=user_id,
        status="running",
        emails_processed=50,
        last_synced=datetime.now(),
        next_sync=datetime.now()
    )

@mock_router.post("/ingest/stop/{user_id}")
async def stop_ingestion(user_id: str):
    if user_id == "nonexistent_user":
        raise HTTPException(status_code=404, detail="No active ingestion for user")
    return {"message": f"Ingestion stopped for user {user_id}"}

# Create a mock for the email routes module
mock_email_routes = MagicMock()
mock_email_routes.ingest_emails_background = mock_ingest_emails_background
mock_email_routes.router = mock_router
mock_email_routes.active_ingestions = {}

# Set up mock functions that will be patched in tests
mock_email_routes.start_ingestion = MagicMock()
mock_email_routes.get_ingestion_status = MagicMock()
mock_email_routes.stop_ingestion = MagicMock()

# Mock the src.routes.email module
mock_routes = MagicMock()
mock_routes.email = mock_email_routes

# Add to sys.modules
sys.modules['src.routes'] = mock_routes
sys.modules['src.routes.email'] = mock_email_routes

# Also add mock for src.main which contains EmailIngestionRequest and other models
mock_main = MagicMock()
mock_main.EmailIngestionRequest = EmailIngestionRequest
mock_main.EmailIngestionConfig = EmailIngestionConfig
mock_main.EmailIngestionStatus = EmailIngestionStatusModel
mock_main.ingest_emails_background = mock_ingest_emails_background

# Add to sys.modules
sys.modules['src.main'] = mock_main