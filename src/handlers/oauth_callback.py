"""
OAuth callback handler Lambda function for calendar integration.

This handler receives OAuth redirect callbacks after users authorize calendar access.
It validates the state token, exchanges the authorization code for tokens,
encrypts and stores the refresh token, and sends a confirmation message via WhatsApp.

Supports both Google Calendar and Microsoft Outlook OAuth flows.

Requirements: 4.2, 20.3
"""

from typing import Dict, Any, Optional
from datetime import datetime
import requests
from botocore.exceptions import ClientError

from models.dynamodb_client import DynamoDBClient
from services.twilio_client import TwilioClient
from utils.encryption import encrypt_oauth_token_base64
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)

# Initialize clients
dynamodb_client = DynamoDBClient(
    table_name=settings.dynamodb_table, endpoint_url=settings.aws_endpoint_url
)
twilio_client = TwilioClient()


def _get_oauth_credentials(provider: str) -> Dict[str, str]:
    """
    Get OAuth credentials for the specified provider.
    
    Args:
        provider: 'google' or 'outlook'
        
    Returns:
        Dict with client_id and client_secret
    """
    if provider == "google":
        return settings.get_google_oauth_credentials()
    elif provider == "outlook":
        return settings.get_outlook_oauth_credentials()
    else:
        return {"client_id": "", "client_secret": ""}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for OAuth callback.

    Validates state token, exchanges authorization code for tokens,
    encrypts and stores refresh token, and sends confirmation via WhatsApp.

    Args:
        event: API Gateway event containing OAuth callback parameters
        context: Lambda context object

    Returns:
        API Gateway response with HTML page for user

    Example event structure:
        {
            "queryStringParameters": {
                "code": "authorization_code",
                "state": "state_token"
            },
            "requestContext": {
                "requestId": "abc-123"
            }
        }
    """
    request_id = event.get("requestContext", {}).get("requestId", "unknown")

    logger.info("OAuth callback received", request_id=request_id)

    try:
        # Extract query parameters
        params = event.get("queryStringParameters") or {}
        code = params.get("code")
        state = params.get("state")
        error = params.get("error")

        # Check for OAuth errors (user denied access, etc.)
        if error:
            error_description = params.get("error_description", "Unknown error")
            logger.warning(
                "OAuth authorization failed",
                request_id=request_id,
                error=error,
                error_description=error_description,
            )
            return _error_html_response(
                "Authorization Failed",
                f"Calendar authorization was not completed: {error_description}",
                terms_url=settings.terms_url,
                privacy_url=settings.privacy_url,
            )

        # Validate required parameters
        if not code or not state:
            logger.error(
                "Missing OAuth parameters", request_id=request_id, has_code=bool(code), has_state=bool(state)
            )
            return _error_html_response(
                "Invalid Request",
                "Missing required OAuth parameters (code or state).",
                terms_url=settings.terms_url,
                privacy_url=settings.privacy_url,
            )

        logger.info("Processing OAuth callback", request_id=request_id, state_token=state)

        # Validate state token and get trainer info
        state_data = _validate_state_token(state, request_id)
        if not state_data:
            logger.error("Invalid or expired state token", request_id=request_id, state_token=state)
            return _error_html_response(
                "Invalid Request",
                "The authorization link has expired or is invalid. Please request a new calendar connection link.",
                terms_url=settings.terms_url,
                privacy_url=settings.privacy_url,
            )

        trainer_id = state_data["trainer_id"]
        provider = state_data["provider"]

        logger.info(
            "State token validated",
            request_id=request_id,
            trainer_id=trainer_id,
            provider=provider,
        )

        # Exchange authorization code for tokens
        token_data = _exchange_code_for_tokens(code, provider, request_id)
        if not token_data:
            logger.error(
                "Token exchange failed",
                request_id=request_id,
                trainer_id=trainer_id,
                provider=provider,
            )
            return _error_html_response(
                "Authorization Failed",
                "Failed to complete calendar authorization. Please try again.",
                terms_url=settings.terms_url,
                privacy_url=settings.privacy_url,
            )

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        scope = token_data.get("scope", "")

        logger.info(
            "Tokens received",
            request_id=request_id,
            trainer_id=trainer_id,
            provider=provider,
            has_refresh_token=bool(refresh_token),
            has_access_token=bool(access_token),
            expires_in=expires_in,
        )

        # Encrypt refresh token
        if not refresh_token:
            logger.error(
                "No refresh token received",
                request_id=request_id,
                trainer_id=trainer_id,
                provider=provider,
            )
            return _error_html_response(
                "Authorization Incomplete",
                "Calendar authorization did not provide offline access. Please try again.",
                terms_url=settings.terms_url,
                privacy_url=settings.privacy_url,
            )

        encrypted_refresh_token = encrypt_oauth_token_base64(refresh_token)

        logger.info(
            "Refresh token encrypted",
            request_id=request_id,
            trainer_id=trainer_id,
            provider=provider,
        )

        # Store calendar configuration in DynamoDB
        _store_calendar_config(
            trainer_id=trainer_id,
            provider=provider,
            encrypted_refresh_token=encrypted_refresh_token,
            scope=scope,
            request_id=request_id,
        )

        logger.info(
            "Calendar config stored",
            request_id=request_id,
            trainer_id=trainer_id,
            provider=provider,
        )

        # Get trainer's phone number for confirmation message
        trainer = dynamodb_client.get_trainer(trainer_id)
        if trainer and trainer.get("phone_number"):
            phone_number = trainer["phone_number"]
            _send_confirmation_message(phone_number, provider, request_id)
            logger.info(
                "Confirmation message sent",
                request_id=request_id,
                trainer_id=trainer_id,
                phone_number=phone_number,
            )

        # Clean up state token
        _delete_state_token(state, request_id)

        # Return success HTML page
        return _success_html_response(
            provider,
            terms_url=settings.terms_url,
            privacy_url=settings.privacy_url,
        )

    except Exception as e:
        logger.error(
            "OAuth callback processing failed",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return _error_html_response(
            "Error",
            "An unexpected error occurred while processing your calendar authorization. Please try again.",
            terms_url=settings.terms_url,
            privacy_url=settings.privacy_url,
        )


def _validate_state_token(state: str, request_id: str) -> Optional[Dict[str, Any]]:
    """
    Validate state token against DynamoDB and return associated data.

    Args:
        state: State token from OAuth callback
        request_id: Request ID for tracing

    Returns:
        Dict with trainer_id and provider, or None if invalid/expired
    """
    try:
        # Query DynamoDB for state token using high-level resource API
        table = dynamodb_client.table
        response = table.get_item(
            Key={"PK": f"OAUTH_STATE#{state}", "SK": "METADATA"},
        )

        item = response.get("Item")
        if not item:
            logger.warning("State token not found", request_id=request_id, state_token=state)
            return None

        # High-level API returns native Python types
        state_data = {
            "trainer_id": item.get("trainer_id", ""),
            "provider": item.get("provider", ""),
            "created_at": item.get("created_at", ""),
        }

        # Check if state token has expired (TTL is handled by DynamoDB, but double-check)
        ttl = int(item.get("ttl", 0))
        current_timestamp = int(datetime.utcnow().timestamp())

        if ttl > 0 and current_timestamp > ttl:
            logger.warning(
                "State token expired",
                request_id=request_id,
                state_token=state,
                ttl=ttl,
                current_timestamp=current_timestamp,
            )
            return None

        return state_data

    except ClientError as e:
        logger.error(
            "Failed to validate state token",
            request_id=request_id,
            error=str(e),
            error_code=e.response["Error"]["Code"],
        )
        return None


def _exchange_code_for_tokens(
    code: str, provider: str, request_id: str
) -> Optional[Dict[str, Any]]:
    """
    Exchange authorization code for access and refresh tokens.

    Args:
        code: Authorization code from OAuth callback
        provider: Calendar provider ('google' or 'outlook')
        request_id: Request ID for tracing

    Returns:
        Dict with access_token, refresh_token, expires_in, scope, or None if failed
    """
    try:
        if provider == "google":
            # Google OAuth2 token endpoint
            token_url = "https://oauth2.googleapis.com/token"
            creds = _get_oauth_credentials("google")
            data = {
                "code": code,
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "redirect_uri": settings.oauth_redirect_uri,
                "grant_type": "authorization_code",
            }
        else:  # outlook
            # Microsoft OAuth2 token endpoint
            token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            creds = _get_oauth_credentials("outlook")
            data = {
                "code": code,
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "redirect_uri": settings.oauth_redirect_uri,
                "grant_type": "authorization_code",
            }

        logger.info(
            "Exchanging authorization code for tokens",
            request_id=request_id,
            provider=provider,
            token_url=token_url,
        )

        # Make token exchange request
        response = requests.post(token_url, data=data, timeout=10)

        if response.status_code != 200:
            logger.error(
                "Token exchange failed",
                request_id=request_id,
                provider=provider,
                status_code=response.status_code,
                response_body=response.text[:500],  # Log first 500 chars
            )
            return None

        token_data = response.json()

        return {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "scope": token_data.get("scope", ""),
        }

    except Exception as e:
        logger.error(
            "Unexpected error during token exchange",
            request_id=request_id,
            provider=provider,
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


def _store_calendar_config(
    trainer_id: str,
    provider: str,
    encrypted_refresh_token: str,
    scope: str,
    request_id: str,
) -> None:
    """
    Store calendar configuration in DynamoDB.

    Args:
        trainer_id: Trainer identifier
        provider: Calendar provider ('google' or 'outlook')
        encrypted_refresh_token: Base64-encoded encrypted refresh token
        scope: OAuth scope granted
        request_id: Request ID for tracing

    Raises:
        ClientError: If DynamoDB operation fails
    """
    now = datetime.utcnow()

    calendar_config = {
        "PK": f"TRAINER#{trainer_id}",
        "SK": "CALENDAR_CONFIG",
        "entity_type": "CALENDAR_CONFIG",
        "trainer_id": trainer_id,
        "provider": provider,
        "encrypted_refresh_token": encrypted_refresh_token,
        "scope": scope,
        "connected_at": now.isoformat(),
        "last_sync_at": now.isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    try:
        dynamodb_client.put_item(calendar_config)

        logger.info(
            "Calendar configuration stored successfully",
            request_id=request_id,
            trainer_id=trainer_id,
            provider=provider,
        )

    except ClientError as e:
        logger.error(
            "Failed to store calendar configuration",
            request_id=request_id,
            trainer_id=trainer_id,
            provider=provider,
            error=str(e),
            error_code=e.response["Error"]["Code"],
        )
        raise


def _send_confirmation_message(phone_number: str, provider: str, request_id: str) -> None:
    """
    Send WhatsApp confirmation message to trainer.

    Args:
        phone_number: Trainer's phone number in E.164 format
        provider: Calendar provider ('google' or 'outlook')
        request_id: Request ID for tracing
    """
    provider_name = "Google Calendar" if provider == "google" else "Outlook Calendar"

    message = (
        f"✅ {provider_name} conectado com sucesso!\n\n"
        f"Suas sessões de treino serão sincronizadas automaticamente com seu calendário. "
        f"Ao agendar, reagendar ou cancelar sessões, as alterações serão refletidas no seu calendário."
    )

    if settings.terms_url:
        message += (
            f"\n\nTermos de Serviço: {settings.terms_url}\n"
            f"Política de Privacidade: {settings.privacy_url}"
        )

    try:
        twilio_client.send_message(to=phone_number, body=message)

        logger.info(
            "Confirmation message sent",
            request_id=request_id,
            phone_number=phone_number,
            provider=provider,
        )

    except Exception as e:
        # Don't fail the OAuth flow if message sending fails
        logger.error(
            "Failed to send confirmation message",
            request_id=request_id,
            phone_number=phone_number,
            error=str(e),
        )


def _delete_state_token(state: str, request_id: str) -> None:
    """
    Delete state token from DynamoDB after successful OAuth flow.

    Args:
        state: State token to delete
        request_id: Request ID for tracing
    """
    try:
        table = dynamodb_client.table
        table.delete_item(
            Key={"PK": f"OAUTH_STATE#{state}", "SK": "METADATA"},
        )

        logger.info("State token deleted", request_id=request_id, state_token=state)

    except ClientError as e:
        # Don't fail the OAuth flow if cleanup fails
        logger.warning(
            "Failed to delete state token",
            request_id=request_id,
            state_token=state,
            error=str(e),
        )


def _success_html_response(provider: str, terms_url: str = "", privacy_url: str = "") -> Dict[str, Any]:
    """
    Generate success HTML response for OAuth callback.

    Args:
        provider: Calendar provider ('google' or 'outlook')
        terms_url: URL for Terms of Service page (empty to omit footer)
        privacy_url: URL for Privacy Policy page (empty to omit footer)

    Returns:
        API Gateway response with HTML page
    """
    provider_name = "Google Calendar" if provider == "google" else "Outlook Calendar"

    footer_html = ""
    if terms_url:
        footer_html = f"""
            <div class="footer-links">
                <a href="{terms_url}" target="_blank">Termos de Serviço</a>
                <span>|</span>
                <a href="{privacy_url}" target="_blank">Política de Privacidade</a>
            </div>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Calendário Conectado - FitAgent</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                background: white;
                padding: 3rem;
                border-radius: 1rem;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 500px;
                margin: 1rem;
            }}
            .success-icon {{
                font-size: 4rem;
                margin-bottom: 1rem;
            }}
            h1 {{
                color: #2d3748;
                margin-bottom: 1rem;
                font-size: 1.75rem;
            }}
            p {{
                color: #4a5568;
                line-height: 1.6;
                margin-bottom: 1.5rem;
            }}
            .provider {{
                color: #667eea;
                font-weight: 600;
            }}
            .close-message {{
                color: #718096;
                font-size: 0.875rem;
                margin-top: 2rem;
            }}
            .footer-links {{
                margin-top: 2rem;
                padding-top: 1rem;
                border-top: 1px solid #e2e8f0;
                font-size: 0.8rem;
                color: #718096;
            }}
            .footer-links a {{
                color: #667eea;
                text-decoration: none;
            }}
            .footer-links a:hover {{
                text-decoration: underline;
            }}
            .footer-links span {{
                margin: 0 0.5rem;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>Calendário Conectado com Sucesso!</h1>
            <p>
                Seu <span class="provider">{provider_name}</span> foi conectado ao FitAgent.
            </p>
            <p>
                Suas sessões de treino serão sincronizadas automaticamente com seu calendário.
                Você receberá uma mensagem de confirmação no WhatsApp em breve.
            </p>
            <p class="close-message">
                Você pode fechar esta janela e voltar ao WhatsApp.
            </p>{footer_html}
        </div>
    </body>
    </html>
    """

    return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html}


def _error_html_response(title: str, message: str, terms_url: str = "", privacy_url: str = "") -> Dict[str, Any]:
    """
    Generate error HTML response for OAuth callback.

    Args:
        title: Error title
        message: Error message
        terms_url: URL for Terms of Service page (empty to omit footer)
        privacy_url: URL for Privacy Policy page (empty to omit footer)

    Returns:
        API Gateway response with HTML page
    """
    footer_html = ""
    if terms_url:
        footer_html = f"""
            <div class="footer-links">
                <a href="{terms_url}" target="_blank">Termos de Serviço</a>
                <span>|</span>
                <a href="{privacy_url}" target="_blank">Política de Privacidade</a>
            </div>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - FitAgent</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            }}
            .container {{
                background: white;
                padding: 3rem;
                border-radius: 1rem;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 500px;
                margin: 1rem;
            }}
            .error-icon {{
                font-size: 4rem;
                margin-bottom: 1rem;
            }}
            h1 {{
                color: #2d3748;
                margin-bottom: 1rem;
                font-size: 1.75rem;
            }}
            p {{
                color: #4a5568;
                line-height: 1.6;
                margin-bottom: 1.5rem;
            }}
            .close-message {{
                color: #718096;
                font-size: 0.875rem;
                margin-top: 2rem;
            }}
            .footer-links {{
                margin-top: 2rem;
                padding-top: 1rem;
                border-top: 1px solid #e2e8f0;
                font-size: 0.8rem;
                color: #718096;
            }}
            .footer-links a {{
                color: #667eea;
                text-decoration: none;
            }}
            .footer-links a:hover {{
                text-decoration: underline;
            }}
            .footer-links span {{
                margin: 0 0.5rem;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="error-icon">❌</div>
            <h1>{title}</h1>
            <p>{message}</p>
            <p class="close-message">
                Você pode fechar esta janela e voltar ao WhatsApp para tentar novamente.
            </p>{footer_html}
        </div>
    </body>
    </html>
    """

    return {"statusCode": 400, "headers": {"Content-Type": "text/html"}, "body": html}
