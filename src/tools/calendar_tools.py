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

from models.dynamodb_client import DynamoDBClient
from utils.validation import InputSanitizer
from config import settings

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

        # Store state token in DynamoDB with 10-minute expiration
        # This will be validated during the OAuth callback
        now = datetime.utcnow()
        ttl = int((now + timedelta(minutes=10)).timestamp())

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
                "expires_in": 600,  # 10 minutes
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
