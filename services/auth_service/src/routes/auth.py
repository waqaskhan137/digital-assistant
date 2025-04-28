from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import RedirectResponse
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator, root_validator, constr
from src.oauth_client import OAuthClient
from src.token_storage import RedisTokenStorage
from shared.models.token import Token
from shared.exceptions import (
    AuthenticationError, 
    ConfigurationError, 
    ExternalServiceError, 
    SyncStateError,
    ResourceNotFoundError,
    ValidationError,
    GmailAutomationError
)
import os
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# Enhanced request and response models
class AuthUrlResponse(BaseModel):
    """Response for the login endpoint."""
    auth_url: str = Field(..., description="Google OAuth authorization URL")
    state: str = Field(..., description="State parameter for OAuth security")


class TokenResponse(BaseModel):
    """Response containing an OAuth token."""
    user_id: str = Field(..., description="User identifier")
    access_token: str = Field(..., description="OAuth access token")
    token_type: str = Field(..., description="Token type (usually 'Bearer')")
    expires_at: str = Field(..., description="ISO format timestamp of token expiration")
    scope: Optional[str] = Field(None, description="OAuth scopes granted")


class TokenRevokeResponse(BaseModel):
    """Response for token revocation."""
    success: bool = Field(..., description="Whether the revocation was successful")
    message: str = Field(..., description="Confirmation message")


class CallbackRequest(BaseModel):
    """Request parameters for the OAuth callback."""
    code: constr(min_length=1) = Field(
        ..., 
        description="Authorization code from Google OAuth",
        example="4/0AWgavdd..."
    )
    state: constr(min_length=1) = Field(
        ..., 
        description="State parameter passed during authorization",
        example="user_123"
    )
    
    @validator('code')
    def validate_code(cls, v):
        if not v:
            raise ValueError("Authorization code is required")
        return v
    
    @validator('state')
    def validate_state(cls, v):
        if not v:
            raise ValueError("State parameter is required")
        return v


# Dependency functions to get client instances
def get_oauth_client():
    """Create and return an OAuth client instance."""
    # ConfigurationError will be raised by OAuthClient constructor if env vars are missing
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("REDIRECT_URI")
    return OAuthClient(client_id, client_secret, redirect_uri)


def get_token_storage():
    """Create and return a token storage instance."""
    # ConfigurationError or SyncStateError will be raised by RedisTokenStorage constructor
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    password = os.getenv("REDIS_PASSWORD")
    return RedisTokenStorage(host, port, db, password)


# Enhanced parameter validation
def validate_user_id(user_id: str) -> str:
    """Validate user_id format."""
    if not user_id:
        raise ValidationError("user_id is required")
    if not user_id.replace("_", "").isalnum():
        raise ValidationError("user_id must contain only alphanumeric characters and underscores")
    if len(user_id) < 3:
        raise ValidationError("user_id must be at least 3 characters long")
    return user_id


@router.get("/login", response_model=AuthUrlResponse)
async def login(
    redirect: bool = Query(
        False, 
        description="If true, redirects to Google auth. Otherwise returns the URL."
    ),
    user_id: Optional[str] = Query(
        None, 
        min_length=3, 
        regex="^[a-zA-Z0-9_]+$",
        description="Optional user identifier. If not provided, a random one will be generated."
    ),
    oauth_client: OAuthClient = Depends(get_oauth_client)
):
    """Get the OAuth authorization URL or redirect directly."""
    state = user_id or f"test_user_{uuid.uuid4().hex[:8]}"
    auth_url = oauth_client.get_authorization_url(state=state)
    
    # If redirect parameter is true, redirect to Google's authentication page
    if redirect:
        return RedirectResponse(url=auth_url)
    
    # Otherwise return the URL as before (for API clients)
    return AuthUrlResponse(auth_url=auth_url, state=state)


@router.get("/callback", response_model=TokenResponse)
async def callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    oauth_client: OAuthClient = Depends(get_oauth_client),
    token_storage: RedisTokenStorage = Depends(get_token_storage)
):
    """Handle the OAuth callback."""
    try:
        # Use Pydantic model for validation
        callback_params = CallbackRequest(code=code, state=state)
        
        token = oauth_client.exchange_code_for_token(callback_params.code)
        token_storage.save_token(callback_params.state, token)
        
        return TokenResponse(
            user_id=callback_params.state,
            access_token=token.access_token,
            token_type=token.token_type,
            expires_at=token.expires_at.isoformat(),
            scope=token.scope
        )
    except ValueError as e:
        # Convert Pydantic validation errors to our custom ValidationError
        raise ValidationError(str(e))
    except Exception as e:
        # Convert other exceptions to ExternalServiceError with proper logging
        logger.exception(f"Error in callback: {str(e)}")
        raise ExternalServiceError(f"Failed to exchange authorization code for token: {str(e)}")


@router.get("/token/{user_id}", response_model=TokenResponse)
async def get_token(
    user_id: str,
    token_storage: RedisTokenStorage = Depends(get_token_storage)
):
    """Get the stored token for a user."""
    # Validate user_id
    validated_user_id = validate_user_id(user_id)
    
    token = token_storage.get_token(validated_user_id)
    
    if not token:
        raise ResourceNotFoundError(f"No token found for user {validated_user_id}")
    
    return TokenResponse(
        user_id=validated_user_id,
        access_token=token.access_token,
        token_type=token.token_type,
        expires_at=token.expires_at.isoformat(),
        scope=token.scope
    )


@router.post("/token/{user_id}/refresh", response_model=TokenResponse)
async def refresh_token(
    user_id: str,
    token_storage: RedisTokenStorage = Depends(get_token_storage),
    oauth_client: OAuthClient = Depends(get_oauth_client)
):
    """Refresh the access token for a user."""
    # Validate user_id
    validated_user_id = validate_user_id(user_id)
    
    token = token_storage.get_token(validated_user_id)
    if not token:
        raise ResourceNotFoundError(f"No token found for user {validated_user_id}")
    
    new_token = oauth_client.refresh_token(token)
    token_storage.save_token(validated_user_id, new_token)
    
    return TokenResponse(
        user_id=validated_user_id,
        access_token=new_token.access_token,
        token_type=new_token.token_type,
        expires_at=new_token.expires_at.isoformat(),
        scope=new_token.scope
    )


@router.delete("/token/{user_id}", response_model=TokenRevokeResponse)
async def revoke_token(
    user_id: str,
    token_storage: RedisTokenStorage = Depends(get_token_storage)
):
    """Revoke and delete a token."""
    # Validate user_id
    validated_user_id = validate_user_id(user_id)
    
    success = token_storage.delete_token(validated_user_id)
    
    if not success:
        raise ResourceNotFoundError(f"No token found for user {validated_user_id} to delete")
    
    return TokenRevokeResponse(
        success=True, 
        message=f"Token revoked for user {validated_user_id}"
    )