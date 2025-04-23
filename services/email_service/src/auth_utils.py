"""
Utilities for handling Google API authentication credentials.
"""
import logging
import os
from typing import Dict, Any
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

def convert_token_to_credentials(token_dict: Dict[str, Any]) -> Credentials:
    """
    Convert a token dictionary to a Google OAuth credentials object.
    
    Args:
        token_dict: Dictionary containing OAuth token data from the Auth Service
        
    Returns:
        Google OAuth2 Credentials object
    """
    # If the token is already a Credentials object, return it
    if isinstance(token_dict, Credentials):
        return token_dict
    
    # Get client ID and secret from environment variables if not in token
    client_id = token_dict.get('client_id', os.getenv('GOOGLE_CLIENT_ID'))
    client_secret = token_dict.get('client_secret', os.getenv('GOOGLE_CLIENT_SECRET'))
    
    # Parse scopes if available
    scopes = token_dict.get('scope')
    if isinstance(scopes, str):
        scopes = scopes.split(' ')
    
    # Create a Credentials object from the token dictionary
    credentials = Credentials(
        token=token_dict.get('access_token'),
        refresh_token=token_dict.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes
    )
    
    return credentials