"""
Unit tests for OAuth callback handler.

Tests the OAuth callback Lambda function including:
- State token validation
- Authorization code exchange
- Token encryption and storage
- Confirmation message sending
- Error handling
"""

import json
import base64
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pytest

from src.handlers.oauth_callback import (
    lambda_handler,
    _validate_state_token,
    _exchange_code_for_tokens,
    _store_calendar_config,
    _send_confirmation_message,
    _delete_state_token,
)


@pytest.fixture
def mock_dynamodb_client():
    """Mock DynamoDB client."""
    with patch("src.handlers.oauth_callback.dynamodb_client") as mock:
        yield mock


@pytest.fixture
def mock_twilio_client():
    """Mock Twilio client."""
    with patch("src.handlers.oauth_callback.twilio_client") as mock:
        yield mock


@pytest.fixture
def mock_encryption():
    """Mock encryption function."""
    with patch("src.handlers.oauth_callback.encrypt_oauth_token_base64") as mock:
        mock.return_value = "encrypted_token_base64"
        yield mock


@pytest.fixture
def mock_requests():
    """Mock requests library."""
    with patch("src.handlers.oauth_callback.requests") as mock:
        yield mock


@pytest.fixture
def valid_google_callback_event():
    """Valid OAuth callback event for Google Calendar."""
    return {
        "queryStringParameters": {"code": "auth_code_123", "state": "state_token_abc"},
        "requestContext": {"requestId": "request-123"},
    }


@pytest.fixture
def valid_outlook_callback_event():
    """Valid OAuth callback event for Outlook Calendar."""
    return {
        "queryStringParameters": {"code": "auth_code_456", "state": "state_token_def"},
        "requestContext": {"requestId": "request-456"},
    }


@pytest.fixture
def error_callback_event():
    """OAuth callback event with error (user denied access)."""
    return {
        "queryStringParameters": {
            "error": "access_denied",
            "error_description": "User denied access",
            "state": "state_token_xyz",
        },
        "requestContext": {"requestId": "request-789"},
    }


@pytest.fixture
def valid_state_data():
    """Valid state token data from DynamoDB."""
    now = datetime.utcnow()
    ttl = int((now + timedelta(minutes=5)).timestamp())
    return {
        "Item": {
            "PK": {"S": "OAUTH_STATE#state_token_abc"},
            "SK": {"S": "METADATA"},
            "trainer_id": {"S": "trainer-123"},
            "provider": {"S": "google"},
            "created_at": {"S": now.isoformat()},
            "ttl": {"N": str(ttl)},
        }
    }


@pytest.fixture
def expired_state_data():
    """Expired state token data from DynamoDB."""
    past = datetime.utcnow() - timedelta(minutes=15)
    ttl = int((past + timedelta(minutes=10)).timestamp())
    return {
        "Item": {
            "PK": {"S": "OAUTH_STATE#state_token_expired"},
            "SK": {"S": "METADATA"},
            "trainer_id": {"S": "trainer-456"},
            "provider": {"S": "outlook"},
            "created_at": {"S": past.isoformat()},
            "ttl": {"N": str(ttl)},
        }
    }


@pytest.fixture
def google_token_response():
    """Mock Google OAuth token response."""
    return {
        "access_token": "google_access_token",
        "refresh_token": "google_refresh_token",
        "expires_in": 3600,
        "scope": "https://www.googleapis.com/auth/calendar",
        "token_type": "Bearer",
    }


@pytest.fixture
def outlook_token_response():
    """Mock Outlook OAuth token response."""
    return {
        "access_token": "outlook_access_token",
        "refresh_token": "outlook_refresh_token",
        "expires_in": 3600,
        "scope": "Calendars.ReadWrite offline_access",
        "token_type": "Bearer",
    }


class TestLambdaHandler:
    """Tests for the main lambda_handler function."""

    def test_successful_google_oauth_flow(
        self,
        valid_google_callback_event,
        valid_state_data,
        google_token_response,
        mock_dynamodb_client,
        mock_twilio_client,
        mock_encryption,
        mock_requests,
    ):
        """Test successful Google Calendar OAuth flow."""
        # Setup mocks
        mock_dynamodb_client.dynamodb.get_item.return_value = valid_state_data
        mock_dynamodb_client.get_trainer.return_value = {
            "trainer_id": "trainer-123",
            "phone_number": "+1234567890",
            "name": "John Trainer",
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = google_token_response
        mock_requests.post.return_value = mock_response

        # Execute
        response = lambda_handler(valid_google_callback_event, None)

        # Verify
        assert response["statusCode"] == 200
        assert "text/html" in response["headers"]["Content-Type"]
        assert "Calendar Connected Successfully" in response["body"]
        assert "Google Calendar" in response["body"]

        # Verify token exchange was called
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "oauth2.googleapis.com/token" in call_args[0][0]

        # Verify encryption was called
        mock_encryption.assert_called_once_with("google_refresh_token")

        # Verify calendar config was stored
        mock_dynamodb_client.dynamodb.put_item.assert_called()

        # Verify confirmation message was sent
        mock_twilio_client.send_message.assert_called_once()

    def test_successful_outlook_oauth_flow(
        self,
        valid_outlook_callback_event,
        outlook_token_response,
        mock_dynamodb_client,
        mock_twilio_client,
        mock_encryption,
        mock_requests,
    ):
        """Test successful Outlook Calendar OAuth flow."""
        # Setup mocks
        now = datetime.utcnow()
        ttl = int((now + timedelta(minutes=5)).timestamp())
        state_data = {
            "Item": {
                "PK": {"S": "OAUTH_STATE#state_token_def"},
                "SK": {"S": "METADATA"},
                "trainer_id": {"S": "trainer-456"},
                "provider": {"S": "outlook"},
                "created_at": {"S": now.isoformat()},
                "ttl": {"N": str(ttl)},
            }
        }

        mock_dynamodb_client.dynamodb.get_item.return_value = state_data
        mock_dynamodb_client.get_trainer.return_value = {
            "trainer_id": "trainer-456",
            "phone_number": "+9876543210",
            "name": "Jane Trainer",
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = outlook_token_response
        mock_requests.post.return_value = mock_response

        # Execute
        response = lambda_handler(valid_outlook_callback_event, None)

        # Verify
        assert response["statusCode"] == 200
        assert "Calendar Connected Successfully" in response["body"]
        assert "Outlook Calendar" in response["body"]

        # Verify token exchange was called with Outlook endpoint
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "login.microsoftonline.com" in call_args[0][0]

    def test_oauth_error_user_denied(self, error_callback_event):
        """
        Test OAuth callback when user denies access.
        
        Language expectation: Portuguese
        Expected: Error message in Portuguese
        """
        response = lambda_handler(error_callback_event, None)

        assert response["statusCode"] == 400
        assert ("Autorização Falhou" in response["body"] or "Authorization Failed" in response["body"])
        assert ("negou acesso" in response["body"] or "User denied access" in response["body"])

    def test_missing_code_parameter(self, mock_dynamodb_client):
        """Test OAuth callback with missing code parameter."""
        event = {
            "queryStringParameters": {"state": "state_token_abc"},
            "requestContext": {"requestId": "request-123"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        assert "Invalid Request" in response["body"]
        assert "Missing required OAuth parameters" in response["body"]

    def test_missing_state_parameter(self, mock_dynamodb_client):
        """Test OAuth callback with missing state parameter."""
        event = {
            "queryStringParameters": {"code": "auth_code_123"},
            "requestContext": {"requestId": "request-123"},
        }

        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        assert "Invalid Request" in response["body"]

    def test_invalid_state_token(
        self, valid_google_callback_event, mock_dynamodb_client
    ):
        """Test OAuth callback with invalid state token."""
        # State token not found in DynamoDB
        mock_dynamodb_client.dynamodb.get_item.return_value = {}

        response = lambda_handler(valid_google_callback_event, None)

        assert response["statusCode"] == 400
        assert "Invalid Request" in response["body"]
        assert "expired or is invalid" in response["body"]

    def test_expired_state_token(
        self, valid_google_callback_event, expired_state_data, mock_dynamodb_client
    ):
        """Test OAuth callback with expired state token."""
        mock_dynamodb_client.dynamodb.get_item.return_value = expired_state_data

        response = lambda_handler(valid_google_callback_event, None)

        assert response["statusCode"] == 400
        assert "expired or is invalid" in response["body"]

    def test_token_exchange_failure(
        self,
        valid_google_callback_event,
        valid_state_data,
        mock_dynamodb_client,
        mock_requests,
    ):
        """
        Test OAuth callback when token exchange fails.
        
        Language expectation: Portuguese
        Expected: Error message in Portuguese
        """
        mock_dynamodb_client.dynamodb.get_item.return_value = valid_state_data

        # Token exchange returns error
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid authorization code"
        mock_requests.post.return_value = mock_response

        response = lambda_handler(valid_google_callback_event, None)

        assert response["statusCode"] == 400
        assert ("Autorização Falhou" in response["body"] or "Authorization Failed" in response["body"])

    def test_missing_refresh_token(
        self,
        valid_google_callback_event,
        valid_state_data,
        mock_dynamodb_client,
        mock_requests,
    ):
        """Test OAuth callback when refresh token is not provided."""
        mock_dynamodb_client.dynamodb.get_item.return_value = valid_state_data

        # Token response without refresh token
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access_token_only",
            "expires_in": 3600,
        }
        mock_requests.post.return_value = mock_response

        response = lambda_handler(valid_google_callback_event, None)

        assert response["statusCode"] == 400
        assert "Authorization Incomplete" in response["body"]
        assert "offline access" in response["body"]


class TestValidateStateToken:
    """Tests for _validate_state_token function."""

    def test_valid_state_token(self, valid_state_data, mock_dynamodb_client):
        """Test validation of valid state token."""
        mock_dynamodb_client.dynamodb.get_item.return_value = valid_state_data

        result = _validate_state_token("state_token_abc", "request-123")

        assert result is not None
        assert result["trainer_id"] == "trainer-123"
        assert result["provider"] == "google"

    def test_state_token_not_found(self, mock_dynamodb_client):
        """Test validation when state token doesn't exist."""
        mock_dynamodb_client.dynamodb.get_item.return_value = {}

        result = _validate_state_token("nonexistent_token", "request-123")

        assert result is None

    def test_expired_state_token(self, expired_state_data, mock_dynamodb_client):
        """Test validation of expired state token."""
        mock_dynamodb_client.dynamodb.get_item.return_value = expired_state_data

        result = _validate_state_token("state_token_expired", "request-123")

        assert result is None


class TestExchangeCodeForTokens:
    """Tests for _exchange_code_for_tokens function."""

    def test_google_token_exchange_success(
        self, google_token_response, mock_requests
    ):
        """Test successful Google token exchange."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = google_token_response
        mock_requests.post.return_value = mock_response

        result = _exchange_code_for_tokens("auth_code", "google", "request-123")

        assert result is not None
        assert result["access_token"] == "google_access_token"
        assert result["refresh_token"] == "google_refresh_token"
        assert result["expires_in"] == 3600

        # Verify correct endpoint was called
        call_args = mock_requests.post.call_args
        assert "oauth2.googleapis.com/token" in call_args[0][0]

    def test_outlook_token_exchange_success(
        self, outlook_token_response, mock_requests
    ):
        """Test successful Outlook token exchange."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = outlook_token_response
        mock_requests.post.return_value = mock_response

        result = _exchange_code_for_tokens("auth_code", "outlook", "request-123")

        assert result is not None
        assert result["access_token"] == "outlook_access_token"
        assert result["refresh_token"] == "outlook_refresh_token"

        # Verify correct endpoint was called
        call_args = mock_requests.post.call_args
        assert "login.microsoftonline.com" in call_args[0][0]

    def test_token_exchange_http_error(self, mock_requests):
        """Test token exchange with HTTP error response."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid grant"
        mock_requests.post.return_value = mock_response

        result = _exchange_code_for_tokens("invalid_code", "google", "request-123")

        assert result is None

    def test_token_exchange_network_error(self, mock_requests):
        """Test token exchange with network error."""
        mock_requests.post.side_effect = Exception("Network error")

        result = _exchange_code_for_tokens("auth_code", "google", "request-123")

        assert result is None


class TestStoreCalendarConfig:
    """Tests for _store_calendar_config function."""

    def test_store_google_calendar_config(self, mock_dynamodb_client):
        """Test storing Google Calendar configuration."""
        _store_calendar_config(
            trainer_id="trainer-123",
            provider="google",
            encrypted_refresh_token="encrypted_token",
            scope="https://www.googleapis.com/auth/calendar",
            request_id="request-123",
        )

        # Verify put_item was called
        mock_dynamodb_client.dynamodb.put_item.assert_called_once()
        call_args = mock_dynamodb_client.dynamodb.put_item.call_args[1]

        item = call_args["Item"]
        assert item["PK"] == "TRAINER#trainer-123"
        assert item["SK"] == "CALENDAR_CONFIG"
        assert item["provider"] == "google"
        assert item["encrypted_refresh_token"] == "encrypted_token"
        assert item["scope"] == "https://www.googleapis.com/auth/calendar"

    def test_store_outlook_calendar_config(self, mock_dynamodb_client):
        """Test storing Outlook Calendar configuration."""
        _store_calendar_config(
            trainer_id="trainer-456",
            provider="outlook",
            encrypted_refresh_token="encrypted_token_outlook",
            scope="Calendars.ReadWrite offline_access",
            request_id="request-456",
        )

        call_args = mock_dynamodb_client.dynamodb.put_item.call_args[1]
        item = call_args["Item"]

        assert item["PK"] == "TRAINER#trainer-456"
        assert item["provider"] == "outlook"
        assert item["encrypted_refresh_token"] == "encrypted_token_outlook"


class TestSendConfirmationMessage:
    """Tests for _send_confirmation_message function."""

    def test_send_google_confirmation(self, mock_twilio_client):
        """Test sending Google Calendar confirmation message."""
        _send_confirmation_message("+1234567890", "google", "request-123")

        mock_twilio_client.send_message.assert_called_once()
        call_args = mock_twilio_client.send_message.call_args[1]

        assert call_args["to"] == "+1234567890"
        assert "Google Calendar" in call_args["body"]
        assert "connected successfully" in call_args["body"]

    def test_send_outlook_confirmation(self, mock_twilio_client):
        """Test sending Outlook Calendar confirmation message."""
        _send_confirmation_message("+9876543210", "outlook", "request-456")

        call_args = mock_twilio_client.send_message.call_args[1]

        assert call_args["to"] == "+9876543210"
        assert "Outlook Calendar" in call_args["body"]

    def test_send_confirmation_failure_does_not_raise(self, mock_twilio_client):
        """Test that confirmation message failure doesn't raise exception."""
        mock_twilio_client.send_message.side_effect = Exception("Twilio error")

        # Should not raise exception
        _send_confirmation_message("+1234567890", "google", "request-123")


class TestDeleteStateToken:
    """Tests for _delete_state_token function."""

    def test_delete_state_token_success(self, mock_dynamodb_client):
        """Test successful state token deletion."""
        _delete_state_token("state_token_abc", "request-123")

        mock_dynamodb_client.dynamodb.delete_item.assert_called_once()
        call_args = mock_dynamodb_client.dynamodb.delete_item.call_args[1]

        assert call_args["Key"]["PK"]["S"] == "OAUTH_STATE#state_token_abc"
        assert call_args["Key"]["SK"]["S"] == "METADATA"

    def test_delete_state_token_failure_does_not_raise(self, mock_dynamodb_client):
        """Test that state token deletion failure doesn't raise exception."""
        from botocore.exceptions import ClientError

        mock_dynamodb_client.dynamodb.delete_item.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DeleteItem",
        )

        # Should not raise exception
        _delete_state_token("state_token_abc", "request-123")
