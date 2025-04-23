from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import RedirectResponse
from typing import Optional
from src.oauth_client import OAuthClient
from src.token_storage import RedisTokenStorage
from shared.models.token import Token
import os
import uuid

router = APIRouter()

# Dependency functions to get client instances
def get_oauth_client():
    """Create and return an OAuth client instance."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("REDIRECT_URI")
    
    if not all([client_id, client_secret, redirect_uri]):
        raise ValueError("Missing OAuth credentials in environment variables")
        
    return OAuthClient(client_id, client_secret, redirect_uri)


def get_token_storage():
    """Create and return a token storage instance."""
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    password = os.getenv("REDIS_PASSWORD")
    
    return RedisTokenStorage(host, port, db, password)


@router.get("/login")
async def login(redirect: bool = Query(False), user_id: str = Query(None)):
    """Get the OAuth authorization URL or redirect directly.
    
    Args:
        redirect: If true, redirects directly to Google auth. Otherwise returns the auth URL as JSON.
        user_id: Optional user identifier for the state parameter. If not provided, a random one will be generated.
    """
    oauth_client = get_oauth_client()
    
    # Generate a user ID if none was provided
    state = user_id or f"test_user_{uuid.uuid4().hex[:8]}"
    
    auth_url = oauth_client.get_authorization_url(state=state)
    
    # If redirect parameter is true, redirect to Google's authentication page
    if redirect:
        return RedirectResponse(url=auth_url)
    
    # Otherwise return the URL as before (for API clients)
    return {"auth_url": auth_url, "state": state}


@router.get("/callback")
async def callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None)
):
    """Handle the OAuth callback.
    
    Args:
        code: Authorization code from Google
        state: User ID passed during authorization
    """
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    
    if not state:
        raise HTTPException(status_code=400, detail="Missing user identifier")
    
    try:
        oauth_client = get_oauth_client()
        token_storage = get_token_storage()
        
        # Exchange code for token
        token = oauth_client.exchange_code_for_token(code)
        
        # Save token to storage
        token_storage.save_token(state, token)
        
        # Return token to client (in a real app you might redirect instead)
        return {
            "user_id": state,
            "access_token": token.access_token,
            "token_type": token.token_type,
            "expires_at": token.expires_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing callback: {str(e)}")


@router.get("/token/{user_id}")
async def get_token(user_id: str):
    """Get the stored token for a user.
    
    Args:
        user_id: User identifier
    """
    token_storage = get_token_storage()
    token = token_storage.get_token(user_id)
    
    if not token:
        raise HTTPException(status_code=404, detail=f"No token found for user {user_id}")
    
    return {
        "access_token": token.access_token,
        "token_type": token.token_type,
        "expires_at": token.expires_at.isoformat(),
        "scope": token.scope
    }


@router.post("/token/{user_id}/refresh")
async def refresh_token(user_id: str):
    """Refresh the access token for a user.
    
    Args:
        user_id: User identifier
    """
    token_storage = get_token_storage()
    oauth_client = get_oauth_client()
    
    # Get the current token
    token = token_storage.get_token(user_id)
    if not token:
        raise HTTPException(status_code=404, detail=f"No token found for user {user_id}")
    
    # Refresh the token
    new_token = oauth_client.refresh_token(token)
    
    # Save the new token
    token_storage.save_token(user_id, new_token)
    
    return {
        "access_token": new_token.access_token,
        "token_type": new_token.token_type,
        "expires_at": new_token.expires_at.isoformat(),
        "scope": new_token.scope
    }


@router.delete("/token/{user_id}")
async def revoke_token(user_id: str):
    """Revoke and delete a token.
    
    Args:
        user_id: User identifier
    """
    token_storage = get_token_storage()
    success = token_storage.delete_token(user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"No token found for user {user_id}")
    
    return {"success": True, "message": f"Token revoked for user {user_id}"}