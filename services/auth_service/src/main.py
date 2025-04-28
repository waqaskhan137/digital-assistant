from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .routes import auth
from shared.exceptions import (
    GmailAutomationError,
    AuthenticationError,
    ConfigurationError,
    ExternalServiceError,
    SyncStateError,
    ResourceNotFoundError,
    ValidationError # Although not used yet, good to have handler
)
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("auth_service")

# --- Exception Handlers ---

async def configuration_error_handler(request: Request, exc: ConfigurationError):
    logger.error(f"Configuration error encountered: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Server configuration error: {exc}"}
    )

async def authentication_error_handler(request: Request, exc: AuthenticationError):
    logger.warning(f"Authentication error: {exc}") # Warning level might be appropriate
    return JSONResponse(
        status_code=401, # Or 403 depending on context, 401 is common for token issues
        content={"detail": f"Authentication failed: {exc}"}
    )

async def external_service_error_handler(request: Request, exc: ExternalServiceError):
    logger.error(f"External service error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=502, # Bad Gateway is suitable for upstream errors
        content={"detail": f"Error communicating with external service: {exc}"}
    )

async def sync_state_error_handler(request: Request, exc: SyncStateError):
    logger.error(f"Sync state (Redis) error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=503, # Service Unavailable if Redis is down
        content={"detail": f"Error accessing storage service: {exc}"}
    )

async def resource_not_found_error_handler(request: Request, exc: ResourceNotFoundError):
    logger.info(f"Resource not found: {exc}") # Info level might be sufficient
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

async def generic_gmail_automation_error_handler(request: Request, exc: GmailAutomationError):
    logger.error(f"Unhandled project error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"An unexpected server error occurred: {exc}"}
    )

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Auth Service starting up")
    
    # Verify required environment variables
    # Note: OAuthClient and RedisTokenStorage now raise ConfigurationError on init if vars are missing,
    # so this check here is somewhat redundant but provides early feedback during startup.
    required_vars = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "REDIRECT_URI", "REDIS_HOST"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        # Log clearly, but allow startup to proceed. Errors will be caught during dependency injection.
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)}. Service might fail on first request.")
    
    yield  # This is where FastAPI serves requests
    
    # Shutdown logic
    logger.info("Auth Service shutting down")

# Create FastAPI application
app = FastAPI(
    title="Auth Service",
    description="OAuth 2.0 authentication service for Gmail Automation",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Register Exception Handlers ---
app.add_exception_handler(ConfigurationError, configuration_error_handler)
app.add_exception_handler(AuthenticationError, authentication_error_handler)
app.add_exception_handler(ExternalServiceError, external_service_error_handler)
app.add_exception_handler(SyncStateError, sync_state_error_handler)
app.add_exception_handler(ResourceNotFoundError, resource_not_found_error_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(GmailAutomationError, generic_gmail_automation_error_handler)
# Note: We don't need a handler for generic Exception as FastAPI has a default one,
# but catching our base GmailAutomationError provides more specific logging/handling.

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "auth_service"}


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "service": "auth_service",
        "version": "0.1.0",
    }