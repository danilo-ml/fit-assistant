"""
AI agent tool functions for calendar integration.

This module provides tool functions that the AI agent can call to:
- Connect calendar (generate OAuth2 authorization URL)
- View calendar sessions (already implemented in session_tools.py)

All functions follow the tool function pattern:
- Accept trainer_id as first parameter
- Return dict with 'success', 'data', and optional 'error' keys
- Validate inputs before processing
- Handle errors gracefully
"""

from typing import Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
import urllib.parse

import requests

from models.dynamodb_client import DynamoDBClient
from utils.validation import InputSanitizer
from utils.encryption import decrypt_oauth_token_base64
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)

# Initialize DynamoDB client
dynamodb_client = DynamoDBClient(
    table_name=settings.dynamodb_table, endpoint_url=settings.aws_endpoint_url
)


def connect_calendar(trainer_id: str, provider: str) -> Dict[str, Any]:
    """
    Generate OAuth2 authorization URL for calendar connection.

    This tool:
    1. Validates that the trainer exists
    2. Validates the provider (google or outlook)
    3. Generates a unique state token for OAuth security
    4. Stores the state token in DynamoDB with 10-minute expiration
    5. Constructs the OAuth2 authorization URL with required parameters
    6. Returns the authorization URL for the trainer to visit

    The trainer will click the URL, authorize access, and be redirected back
    to the OAuth callback handler which will complete the token exchange.

    Args:
        trainer_id: Trainer identifier (required)
        provider: Calendar provider - "google" or "outlook" (required)

    Returns:
        dict: {
            'success': bool,
            'data': {
                'oauth_url': str,
                'provider': str,
                'expires_in': int (seconds until state token expires)
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> connect_calendar(trainer_id='abc123', provider='google')
        {
            'success': True,
            'data': {
                'oauth_url': 'https://accounts.google.com/o/oauth2/v2/auth?...',
                'provider': 'google',
                'expires_in': 600
            }
        }

        >>> connect_calendar(trainer_id='abc123', provider='outlook')
        {
            'success': True,
            'data': {
                'oauth_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize?...',
                'provider': 'outlook',
                'expires_in': 600
            }
        }

    Validates: Requirements 4.1
    """
    try:
        # Sanitize inputs
        sanitized_params = InputSanitizer.sanitize_tool_parameters(
            {"provider": provider}
        )
        provider = sanitized_params["provider"].lower()

        # Validate provider
        if provider not in ["google", "outlook"]:
            return {
                "success": False,
                "error": f"Invalid provider. Must be 'google' or 'outlook'. Got: {provider}",
            }

        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Check if OAuth credentials are configured for this provider
        if provider == "google":
            creds = settings.get_google_oauth_credentials()
            if not creds["client_id"] or not creds["client_secret"]:
                return {
                    "success": False,
                    "error": "Google Calendar integration is not configured. Please contact support.",
                }
            client_id = creds["client_id"]
        else:  # outlook
            creds = settings.get_outlook_oauth_credentials()
            if not creds["client_id"] or not creds["client_secret"]:
                return {
                    "success": False,
                    "error": "Outlook Calendar integration is not configured. Please contact support.",
                }
            client_id = creds["client_id"]

        # Generate unique state token for OAuth security
        state_token = uuid4().hex

        # Store state token in DynamoDB with 30-minute expiration
        # 30 minutes gives the user enough time to open the link,
        # log into Google/Outlook, and complete the authorization flow
        now = datetime.utcnow()
        ttl = int((now + timedelta(minutes=30)).timestamp())

        state_item = {
            "PK": f"OAUTH_STATE#{state_token}",
            "SK": "METADATA",
            "entity_type": "OAUTH_STATE",
            "state_token": state_token,
            "trainer_id": trainer_id,
            "provider": provider,
            "created_at": now.isoformat(),
            "ttl": ttl,
        }

        dynamodb_client.put_item(state_item)

        # Construct OAuth2 authorization URL based on provider
        if provider == "google":
            # Google Calendar OAuth2 parameters
            # Docs: https://developers.google.com/identity/protocols/oauth2/web-server
            auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
            scope = "https://www.googleapis.com/auth/calendar"
            params = {
                "client_id": client_id,
                "redirect_uri": settings.oauth_redirect_uri,
                "response_type": "code",
                "scope": scope,
                "state": state_token,
                "access_type": "offline",  # Request refresh token
                "prompt": "consent",  # Force consent screen to get refresh token
            }
        else:  # outlook
            # Microsoft Graph OAuth2 parameters
            # Docs: https://learn.microsoft.com/en-us/graph/auth-v2-user
            auth_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
            scope = "Calendars.ReadWrite offline_access"
            params = {
                "client_id": client_id,
                "redirect_uri": settings.oauth_redirect_uri,
                "response_type": "code",
                "scope": scope,
                "state": state_token,
                "response_mode": "query",
            }

        # Build the full OAuth URL with query parameters
        oauth_url = f"{auth_url}?{urllib.parse.urlencode(params)}"

        provider_name = "Google Calendar" if provider == "google" else "Outlook Calendar"

        return {
            "success": True,
            "data": {
                "oauth_url": oauth_url,
                "provider": provider,
                "expires_in": 1800,  # 30 minutes
            },
            "message": (
                f"Link de autorização do {provider_name} gerado com sucesso. "
                f"IMPORTANTE: Envie este link completo ao usuário para que ele clique e autorize: {oauth_url}"
            ),
        }

    except ValueError as e:
        # Validation errors
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        # Unexpected errors
        return {
            "success": False,
            "error": f"Failed to generate calendar authorization URL: {str(e)}",
        }


def disconnect_calendar(trainer_id: str) -> Dict[str, Any]:
    """
    Disconnect calendar and revoke OAuth token for a trainer.

    This tool:
    1. Retrieves the trainer's calendar configuration from DynamoDB
    2. Decrypts the stored refresh token
    3. Calls the Google OAuth2 revocation endpoint to revoke the token
    4. Deletes the calendar configuration from DynamoDB regardless of revocation outcome
    5. Logs any revocation failures but does not raise exceptions

    Args:
        trainer_id: Trainer identifier (required)

    Returns:
        dict: {
            'success': bool,
            'data': {'provider': str, 'disconnected': bool},
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> disconnect_calendar(trainer_id='abc123')
        {
            'success': True,
            'data': {'provider': 'google', 'disconnected': True}
        }

    Validates: Requirements 6.1, 6.2, 6.3, 6.4
    """
    try:
        # Retrieve calendar config from DynamoDB
        config = dynamodb_client.get_calendar_config(trainer_id)
        if not config:
            return {
                "success": False,
                "error": f"No calendar connected for trainer: {trainer_id}",
            }

        provider = config.get("provider", "google")

        # Decrypt refresh token
        encrypted_token = config.get("encrypted_refresh_token", "")
        refresh_token = decrypt_oauth_token_base64(encrypted_token)

        # Call Google revocation endpoint
        try:
            response = requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": refresh_token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            if response.status_code == 200:
                logger.info(
                    "Token revoked successfully",
                    trainer_id=trainer_id,
                    provider=provider,
                )
            else:
                logger.warning(
                    "Token revocation returned non-200 status",
                    trainer_id=trainer_id,
                    provider=provider,
                    status_code=response.status_code,
                )
        except Exception as e:
            logger.warning(
                "Token revocation request failed",
                trainer_id=trainer_id,
                provider=provider,
                error=str(e),
            )

        # Delete CALENDAR_CONFIG from DynamoDB regardless of revocation outcome
        dynamodb_client.delete_item(
            f"TRAINER#{trainer_id}", "CALENDAR_CONFIG"
        )

        logger.info(
            "Calendar disconnected",
            trainer_id=trainer_id,
            provider=provider,
        )

        return {
            "success": True,
            "data": {"provider": provider, "disconnected": True},
        }

    except Exception as e:
        logger.error(
            "Failed to disconnect calendar",
            trainer_id=trainer_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "success": False,
            "error": f"Failed to disconnect calendar: {str(e)}",
        }

def get_calendar_status(trainer_id: str) -> Dict[str, Any]:
    """
    Get the current calendar connection status for a trainer.

    This tool:
    1. Validates that the trainer exists in DynamoDB
    2. Retrieves the trainer's calendar configuration from DynamoDB
    3. Returns connection status with provider and connection date if connected
    4. Returns not-connected status if no calendar configuration exists

    Args:
        trainer_id: Trainer identifier (required)

    Returns:
        dict: {
            'success': bool,
            'data': {
                'connected': bool,
                'provider': str | None,
                'connected_at': str | None
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> get_calendar_status(trainer_id='abc123')  # Connected
        {
            'success': True,
            'data': {
                'connected': True,
                'provider': 'google',
                'connected_at': '2024-01-15T10:30:00'
            }
        }

        >>> get_calendar_status(trainer_id='abc123')  # Not connected
        {
            'success': True,
            'data': {
                'connected': False,
                'provider': None,
                'connected_at': None
            }
        }

    Validates: Requirements 7.1, 7.2, 7.3
    """
    try:
        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Retrieve calendar config from DynamoDB
        config = dynamodb_client.get_calendar_config(trainer_id)

        if config:
            return {
                "success": True,
                "data": {
                    "connected": True,
                    "provider": config.get("provider"),
                    "connected_at": config.get("connected_at"),
                },
            }
        else:
            return {
                "success": True,
                "data": {
                    "connected": False,
                    "provider": None,
                    "connected_at": None,
                },
            }

    except Exception as e:
        logger.error(
            "Failed to get calendar status",
            trainer_id=trainer_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "success": False,
            "error": f"Failed to get calendar status: {str(e)}",
        }

