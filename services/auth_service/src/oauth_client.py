import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta
import sys
import os
import uuid
import logging

# Add parent directory to path to allow importing shared module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.models.token import Token
from shared.exceptions import AuthenticationError, ExternalServiceError, ConfigurationError

logger = logging.getLogger(__name__)


class OAuthClient:
    """OAuth 2.0 client for Google API authentication."""

    def __init__(self, client_id, client_secret, redirect_uri):
        """Initialize the OAuth client.
        
        Args:
            client_id (str): Google OAuth client ID
            client_secret (str): Google OAuth client secret
            redirect_uri (str): Redirect URI for OAuth callback
        """
        if not all([client_id, client_secret, redirect_uri]):
            logger.error("Missing required OAuth configuration: client_id, client_secret, or redirect_uri")
            raise ConfigurationError("Missing required OAuth configuration.")
            
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = [
            "https://www.googleapis.com/auth/gmail.readonly", 
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.labels"
        ]
        self.auth_url = "https://accounts.google.com/o/oauth2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"

    def get_authorization_url(self, state=None):
        """Generate the authorization URL for OAuth consent flow.
        
        Args:
            state (str, optional): State parameter for OAuth security. If not provided,
                                 a default value will be used for testing purposes.
        
        Returns:
            str: The authorization URL
        """
        # Use provided state or generate a default one for testing
        if state is None:
            state = f"test_user_{uuid.uuid4().hex[:8]}"
            
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "state": state
        }
        return f"{self.auth_url}?{urlencode(params)}"

    def exchange_code_for_token(self, authorization_code):
        """Exchange the authorization code for an access token.
        
        Args:
            authorization_code (str): Authorization code from OAuth consent
            
        Returns:
            Token: Token object containing access and refresh tokens
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        
        try:
            response = requests.post(self.token_url, data=data, timeout=10) # Add timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            token_data = response.json()
            
            if "error" in token_data:
                error_description = token_data.get("error_description", "Unknown Google OAuth error")
                logger.error(f"Google OAuth error during token exchange: {error_description}")
                raise AuthenticationError(f"Google OAuth error: {error_description}")

            expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])
            
            return Token(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),  # May not be present in every response
                token_type=token_data["token_type"],
                expires_at=expires_at,
                scope=token_data["scope"]
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during token exchange: {e}")
            raise ExternalServiceError(f"Failed to communicate with Google OAuth service: {e}") from e
        except KeyError as e:
            logger.error(f"Missing expected key in Google token response: {e}. Response: {token_data}")
            raise ExternalServiceError(f"Unexpected response format from Google OAuth service.") from e
        except Exception as e:
            logger.error(f"Unexpected error during token exchange: {e}")
            raise GmailAutomationError(f"An unexpected error occurred during token exchange: {e}") from e

    def refresh_token(self, token):
        """Refresh an expired access token.
        
        Args:
            token (Token): The expired token containing a refresh token
            
        Returns:
            Token: A new token with updated access token and expiration
        """
        if not token.refresh_token:
            logger.warning("Attempted to refresh token without a refresh token.")
            raise AuthenticationError("Cannot refresh token without a valid refresh token.")
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": token.refresh_token,
            "grant_type": "refresh_token"
        }
        
        try:
            response = requests.post(self.token_url, data=data, timeout=10) # Add timeout
            response.raise_for_status()
            token_data = response.json()

            if "error" in token_data:
                error_description = token_data.get("error_description", "Unknown Google OAuth error")
                logger.error(f"Google OAuth error during token refresh: {error_description}")
                # If refresh fails, it's an authentication issue
                raise AuthenticationError(f"Google OAuth refresh error: {error_description}")

            expires_at = datetime.now() + timedelta(seconds=token_data["expires_in"])
            
            return Token(
                access_token=token_data["access_token"],
                refresh_token=token.refresh_token,  # Preserve the original refresh token
                token_type=token_data["token_type"],
                expires_at=expires_at,
                scope=token_data["scope"]
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during token refresh: {e}")
            raise ExternalServiceError(f"Failed to communicate with Google OAuth service during refresh: {e}") from e
        except KeyError as e:
            logger.error(f"Missing expected key in Google refresh token response: {e}. Response: {token_data}")
            raise ExternalServiceError(f"Unexpected response format from Google OAuth service during refresh.") from e
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            raise GmailAutomationError(f"An unexpected error occurred during token refresh: {e}") from e