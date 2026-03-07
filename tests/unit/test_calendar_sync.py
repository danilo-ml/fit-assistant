"""
Unit tests for CalendarSyncService.

Tests cover:
- Calendar event creation for both Google and Outlook
- Calendar event updates for both providers
- Calendar event deletion for both providers
- OAuth token refresh logic
- Retry logic with exponential backoff
- Graceful degradation on failures
- Token refresh on 401 Unauthorized

Requirements: 4.3, 4.4, 4.5, 4.6, 4.7
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import requests

from src.services.calendar_sync import (
    CalendarSyncService,
    CalendarSyncError,
    TokenRefreshError,
)
from src.utils.retry import ExternalServiceError


@pytest.fixture
def mock_dynamodb_client():
    """Mock DynamoDB client."""
    client = Mock()
    client.dynamodb = Mock()
    return client


@pytest.fixture
def calendar_service(mock_dynamodb_client):
    """Create CalendarSyncService with mocked dependencies."""
    return CalendarSyncService(dynamodb_client=mock_dynamodb_client)


@pytest.fixture
def google_calendar_config():
    """Sample Google Calendar configuration."""
    return {
        "provider": "google",
        "encrypted_refresh_token": "encrypted_google_token_base64",
        "calendar_id": "primary",
    }


@pytest.fixture
def outlook_calendar_config():
    """Sample Outlook Calendar configuration."""
    return {
        "provider": "outlook",
        "encrypted_refresh_token": "encrypted_outlook_token_base64",
        "calendar_id": "primary",
    }


class TestCalendarConfigRetrieval:
    """Test calendar configuration retrieval."""

    def test_get_calendar_config_success(self, calendar_service, mock_dynamodb_client):
        """Test successful calendar config retrieval."""
        mock_dynamodb_client.dynamodb.get_item.return_value = {
            "Item": {
                "provider": {"S": "google"},
                "encrypted_refresh_token": {"S": "encrypted_token"},
                "calendar_id": {"S": "primary"},
            }
        }

        config = calendar_service._get_calendar_config("trainer-123")

        assert config is not None
        assert config["provider"] == "google"
        assert config["encrypted_refresh_token"] == "encrypted_token"
        assert config["calendar_id"] == "primary"

    def test_get_calendar_config_not_found(self, calendar_service, mock_dynamodb_client):
        """Test calendar config retrieval when not configured."""
        mock_dynamodb_client.dynamodb.get_item.return_value = {}

        config = calendar_service._get_calendar_config("trainer-123")

        assert config is None

    def test_get_calendar_config_error(self, calendar_service, mock_dynamodb_client):
        """Test calendar config retrieval with DynamoDB error."""
        mock_dynamodb_client.dynamodb.get_item.side_effect = Exception("DynamoDB error")

        config = calendar_service._get_calendar_config("trainer-123")

        assert config is None


class TestTokenRefresh:
    """Test OAuth token refresh logic."""

    @patch("src.services.calendar_sync.requests.post")
    def test_refresh_google_token_success(self, mock_post, calendar_service):
        """Test successful Google token refresh."""
        mock_response = Mock()
        mock_response.json.return_value = {"access_token": "new_google_token"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        access_token = calendar_service._refresh_google_token("refresh_token_123")

        assert access_token == "new_google_token"
        mock_post.assert_called_once()

    @patch("src.services.calendar_sync.requests.post")
    def test_refresh_google_token_failure(self, mock_post, calendar_service):
        """Test Google token refresh failure."""
        mock_post.side_effect = requests.RequestException("Network error")

        with pytest.raises(TokenRefreshError):
            calendar_service._refresh_google_token("refresh_token_123")

    @patch("src.services.calendar_sync.requests.post")
    def test_refresh_google_token_no_access_token(self, mock_post, calendar_service):
        """Test Google token refresh with missing access token."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        with pytest.raises(TokenRefreshError):
            calendar_service._refresh_google_token("refresh_token_123")

    @patch("src.services.calendar_sync.requests.post")
    @patch("src.services.calendar_sync.encrypt_oauth_token_base64")
    def test_refresh_outlook_token_success(
        self, mock_encrypt, mock_post, calendar_service, mock_dynamodb_client
    ):
        """Test successful Outlook token refresh."""
        mock_response = Mock()
        mock_response.json.return_value = {"access_token": "new_outlook_token"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        access_token = calendar_service._refresh_outlook_token(
            "refresh_token_123", "trainer-123"
        )

        assert access_token == "new_outlook_token"
        mock_post.assert_called_once()

    @patch("src.services.calendar_sync.requests.post")
    @patch("src.services.calendar_sync.encrypt_oauth_token_base64")
    def test_refresh_outlook_token_with_new_refresh_token(
        self, mock_encrypt, mock_post, calendar_service, mock_dynamodb_client
    ):
        """Test Outlook token refresh that returns new refresh token."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new_outlook_token",
            "refresh_token": "new_refresh_token",
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        mock_encrypt.return_value = "encrypted_new_token"

        access_token = calendar_service._refresh_outlook_token(
            "old_refresh_token", "trainer-123"
        )

        assert access_token == "new_outlook_token"
        mock_encrypt.assert_called_once_with("new_refresh_token")
        mock_dynamodb_client.dynamodb.update_item.assert_called_once()

    @patch("src.services.calendar_sync.requests.post")
    def test_refresh_outlook_token_failure(self, mock_post, calendar_service):
        """Test Outlook token refresh failure."""
        mock_post.side_effect = requests.RequestException("Network error")

        with pytest.raises(TokenRefreshError):
            calendar_service._refresh_outlook_token("refresh_token_123", "trainer-123")


class TestGoogleCalendarOperations:
    """Test Google Calendar API operations."""

    @patch("src.services.calendar_sync.requests.post")
    def test_google_create_event_success(self, mock_post, calendar_service):
        """Test successful Google Calendar event creation."""
        mock_response = Mock()
        mock_response.json.return_value = {"id": "google_event_123"}
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        event_data = {
            "summary": "Training Session",
            "start": {"dateTime": "2024-01-20T14:00:00"},
            "end": {"dateTime": "2024-01-20T15:00:00"},
        }

        event_id = calendar_service._google_create_event(
            "access_token", "primary", event_data
        )

        assert event_id == "google_event_123"
        mock_post.assert_called_once()

    @patch("src.services.calendar_sync.requests.post")
    def test_google_create_event_unauthorized(self, mock_post, calendar_service):
        """Test Google Calendar event creation with 401 Unauthorized."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        event_data = {"summary": "Training Session"}

        with pytest.raises(ExternalServiceError) as exc_info:
            calendar_service._google_create_event("access_token", "primary", event_data)

        assert "Unauthorized" in str(exc_info.value)

    @patch("src.services.calendar_sync.requests.post")
    def test_google_create_event_retry_logic(self, mock_post, calendar_service):
        """Test Google Calendar event creation retry logic."""
        # First two attempts fail, third succeeds
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status.side_effect = requests.RequestException(
            "Temporary error"
        )
        mock_response_fail.status_code = 500

        mock_response_success = Mock()
        mock_response_success.json.return_value = {"id": "google_event_123"}
        mock_response_success.raise_for_status = Mock()
        mock_response_success.status_code = 200

        mock_post.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success,
        ]

        event_data = {"summary": "Training Session"}

        event_id = calendar_service._google_create_event(
            "access_token", "primary", event_data
        )

        assert event_id == "google_event_123"
        assert mock_post.call_count == 3

    @patch("src.services.calendar_sync.requests.put")
    def test_google_update_event_success(self, mock_put, calendar_service):
        """Test successful Google Calendar event update."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        event_data = {
            "summary": "Updated Training Session",
            "start": {"dateTime": "2024-01-21T14:00:00"},
            "end": {"dateTime": "2024-01-21T15:00:00"},
        }

        calendar_service._google_update_event(
            "access_token", "primary", "event_123", event_data
        )

        mock_put.assert_called_once()

    @patch("src.services.calendar_sync.requests.delete")
    def test_google_delete_event_success(self, mock_delete, calendar_service):
        """Test successful Google Calendar event deletion."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        calendar_service._google_delete_event("access_token", "primary", "event_123")

        mock_delete.assert_called_once()

    @patch("src.services.calendar_sync.requests.delete")
    def test_google_delete_event_already_deleted(self, mock_delete, calendar_service):
        """Test Google Calendar event deletion when already deleted (404)."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_delete.return_value = mock_response

        # Should not raise exception for 404
        calendar_service._google_delete_event("access_token", "primary", "event_123")

        mock_delete.assert_called_once()


class TestOutlookCalendarOperations:
    """Test Outlook Calendar API operations."""

    @patch("src.services.calendar_sync.requests.post")
    def test_outlook_create_event_success(self, mock_post, calendar_service):
        """Test successful Outlook Calendar event creation."""
        mock_response = Mock()
        mock_response.json.return_value = {"id": "outlook_event_123"}
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        event_data = {
            "subject": "Training Session",
            "start": {"dateTime": "2024-01-20T14:00:00", "timeZone": "UTC"},
            "end": {"dateTime": "2024-01-20T15:00:00", "timeZone": "UTC"},
        }

        event_id = calendar_service._outlook_create_event("access_token", event_data)

        assert event_id == "outlook_event_123"
        mock_post.assert_called_once()

    @patch("src.services.calendar_sync.requests.post")
    def test_outlook_create_event_unauthorized(self, mock_post, calendar_service):
        """Test Outlook Calendar event creation with 401 Unauthorized."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        event_data = {"subject": "Training Session"}

        with pytest.raises(ExternalServiceError) as exc_info:
            calendar_service._outlook_create_event("access_token", event_data)

        assert "Unauthorized" in str(exc_info.value)

    @patch("src.services.calendar_sync.requests.patch")
    def test_outlook_update_event_success(self, mock_patch, calendar_service):
        """Test successful Outlook Calendar event update."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_patch.return_value = mock_response

        event_data = {
            "subject": "Updated Training Session",
            "start": {"dateTime": "2024-01-21T14:00:00", "timeZone": "UTC"},
            "end": {"dateTime": "2024-01-21T15:00:00", "timeZone": "UTC"},
        }

        calendar_service._outlook_update_event("access_token", "event_123", event_data)

        mock_patch.assert_called_once()

    @patch("src.services.calendar_sync.requests.delete")
    def test_outlook_delete_event_success(self, mock_delete, calendar_service):
        """Test successful Outlook Calendar event deletion."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        calendar_service._outlook_delete_event("access_token", "event_123")

        mock_delete.assert_called_once()

    @patch("src.services.calendar_sync.requests.delete")
    def test_outlook_delete_event_already_deleted(self, mock_delete, calendar_service):
        """Test Outlook Calendar event deletion when already deleted (404)."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_delete.return_value = mock_response

        # Should not raise exception for 404
        calendar_service._outlook_delete_event("access_token", "event_123")

        mock_delete.assert_called_once()


class TestCreateEvent:
    """Test high-level create_event method."""

    @patch("src.services.calendar_sync.decrypt_oauth_token_base64")
    def test_create_event_google_success(
        self,
        mock_decrypt,
        calendar_service,
        mock_dynamodb_client,
        google_calendar_config,
    ):
        """Test successful event creation with Google Calendar."""
        # Mock config retrieval
        calendar_service._get_calendar_config = Mock(return_value=google_calendar_config)

        # Mock token refresh
        mock_decrypt.return_value = "refresh_token"
        calendar_service._refresh_google_token = Mock(return_value="access_token")

        # Mock event creation
        calendar_service._google_create_event = Mock(return_value="google_event_123")

        session_datetime = datetime(2024, 1, 20, 14, 0)
        result = calendar_service.create_event(
            trainer_id="trainer-123",
            session_id="session-456",
            student_name="John Doe",
            session_datetime=session_datetime,
            duration_minutes=60,
            location="Gym A",
        )

        assert result is not None
        assert result["calendar_event_id"] == "google_event_123"
        assert result["calendar_provider"] == "google"
        calendar_service._google_create_event.assert_called_once()

    @patch("src.services.calendar_sync.decrypt_oauth_token_base64")
    def test_create_event_outlook_success(
        self,
        mock_decrypt,
        calendar_service,
        mock_dynamodb_client,
        outlook_calendar_config,
    ):
        """Test successful event creation with Outlook Calendar."""
        # Mock config retrieval
        calendar_service._get_calendar_config = Mock(return_value=outlook_calendar_config)

        # Mock token refresh
        mock_decrypt.return_value = "refresh_token"
        calendar_service._refresh_outlook_token = Mock(return_value="access_token")

        # Mock event creation
        calendar_service._outlook_create_event = Mock(return_value="outlook_event_123")

        session_datetime = datetime(2024, 1, 20, 14, 0)
        result = calendar_service.create_event(
            trainer_id="trainer-123",
            session_id="session-456",
            student_name="John Doe",
            session_datetime=session_datetime,
            duration_minutes=60,
        )

        assert result is not None
        assert result["calendar_event_id"] == "outlook_event_123"
        assert result["calendar_provider"] == "outlook"
        calendar_service._outlook_create_event.assert_called_once()

    def test_create_event_no_calendar_connected(self, calendar_service):
        """Test event creation when no calendar is connected."""
        calendar_service._get_calendar_config = Mock(return_value=None)

        session_datetime = datetime(2024, 1, 20, 14, 0)
        result = calendar_service.create_event(
            trainer_id="trainer-123",
            session_id="session-456",
            student_name="John Doe",
            session_datetime=session_datetime,
            duration_minutes=60,
        )

        assert result is None

    @patch("src.services.calendar_sync.decrypt_oauth_token_base64")
    def test_create_event_graceful_degradation(
        self,
        mock_decrypt,
        calendar_service,
        google_calendar_config,
    ):
        """Test graceful degradation when event creation fails."""
        # Mock config retrieval
        calendar_service._get_calendar_config = Mock(return_value=google_calendar_config)

        # Mock token refresh
        mock_decrypt.return_value = "refresh_token"
        calendar_service._refresh_google_token = Mock(return_value="access_token")

        # Mock event creation failure
        calendar_service._google_create_event = Mock(
            side_effect=ExternalServiceError("Google Calendar", "create_event", "API error")
        )

        session_datetime = datetime(2024, 1, 20, 14, 0)
        result = calendar_service.create_event(
            trainer_id="trainer-123",
            session_id="session-456",
            student_name="John Doe",
            session_datetime=session_datetime,
            duration_minutes=60,
        )

        # Should return None instead of raising exception
        assert result is None


class TestUpdateEvent:
    """Test high-level update_event method."""

    @patch("src.services.calendar_sync.decrypt_oauth_token_base64")
    def test_update_event_google_success(
        self,
        mock_decrypt,
        calendar_service,
        google_calendar_config,
    ):
        """Test successful event update with Google Calendar."""
        # Mock config retrieval
        calendar_service._get_calendar_config = Mock(return_value=google_calendar_config)

        # Mock token refresh
        mock_decrypt.return_value = "refresh_token"
        calendar_service._refresh_google_token = Mock(return_value="access_token")

        # Mock event update
        calendar_service._google_update_event = Mock()

        session_datetime = datetime(2024, 1, 21, 14, 0)
        success = calendar_service.update_event(
            trainer_id="trainer-123",
            session_id="session-456",
            calendar_event_id="google_event_123",
            calendar_provider="google",
            student_name="John Doe",
            session_datetime=session_datetime,
            duration_minutes=60,
        )

        assert success is True
        calendar_service._google_update_event.assert_called_once()

    @patch("src.services.calendar_sync.decrypt_oauth_token_base64")
    def test_update_event_outlook_success(
        self,
        mock_decrypt,
        calendar_service,
        outlook_calendar_config,
    ):
        """Test successful event update with Outlook Calendar."""
        # Mock config retrieval
        calendar_service._get_calendar_config = Mock(return_value=outlook_calendar_config)

        # Mock token refresh
        mock_decrypt.return_value = "refresh_token"
        calendar_service._refresh_outlook_token = Mock(return_value="access_token")

        # Mock event update
        calendar_service._outlook_update_event = Mock()

        session_datetime = datetime(2024, 1, 21, 14, 0)
        success = calendar_service.update_event(
            trainer_id="trainer-123",
            session_id="session-456",
            calendar_event_id="outlook_event_123",
            calendar_provider="outlook",
            student_name="John Doe",
            session_datetime=session_datetime,
            duration_minutes=60,
        )

        assert success is True
        calendar_service._outlook_update_event.assert_called_once()

    def test_update_event_no_calendar_connected(self, calendar_service):
        """Test event update when no calendar is connected."""
        calendar_service._get_calendar_config = Mock(return_value=None)

        session_datetime = datetime(2024, 1, 21, 14, 0)
        success = calendar_service.update_event(
            trainer_id="trainer-123",
            session_id="session-456",
            calendar_event_id="event_123",
            calendar_provider="google",
            student_name="John Doe",
            session_datetime=session_datetime,
            duration_minutes=60,
        )

        assert success is False

    @patch("src.services.calendar_sync.decrypt_oauth_token_base64")
    def test_update_event_graceful_degradation(
        self,
        mock_decrypt,
        calendar_service,
        google_calendar_config,
    ):
        """Test graceful degradation when event update fails."""
        # Mock config retrieval
        calendar_service._get_calendar_config = Mock(return_value=google_calendar_config)

        # Mock token refresh
        mock_decrypt.return_value = "refresh_token"
        calendar_service._refresh_google_token = Mock(return_value="access_token")

        # Mock event update failure
        calendar_service._google_update_event = Mock(
            side_effect=ExternalServiceError("Google Calendar", "update_event", "API error")
        )

        session_datetime = datetime(2024, 1, 21, 14, 0)
        success = calendar_service.update_event(
            trainer_id="trainer-123",
            session_id="session-456",
            calendar_event_id="google_event_123",
            calendar_provider="google",
            student_name="John Doe",
            session_datetime=session_datetime,
            duration_minutes=60,
        )

        # Should return False instead of raising exception
        assert success is False


class TestDeleteEvent:
    """Test high-level delete_event method."""

    @patch("src.services.calendar_sync.decrypt_oauth_token_base64")
    def test_delete_event_google_success(
        self,
        mock_decrypt,
        calendar_service,
        google_calendar_config,
    ):
        """Test successful event deletion with Google Calendar."""
        # Mock config retrieval
        calendar_service._get_calendar_config = Mock(return_value=google_calendar_config)

        # Mock token refresh
        mock_decrypt.return_value = "refresh_token"
        calendar_service._refresh_google_token = Mock(return_value="access_token")

        # Mock event deletion
        calendar_service._google_delete_event = Mock()

        success = calendar_service.delete_event(
            trainer_id="trainer-123",
            session_id="session-456",
            calendar_event_id="google_event_123",
            calendar_provider="google",
        )

        assert success is True
        calendar_service._google_delete_event.assert_called_once()

    @patch("src.services.calendar_sync.decrypt_oauth_token_base64")
    def test_delete_event_outlook_success(
        self,
        mock_decrypt,
        calendar_service,
        outlook_calendar_config,
    ):
        """Test successful event deletion with Outlook Calendar."""
        # Mock config retrieval
        calendar_service._get_calendar_config = Mock(return_value=outlook_calendar_config)

        # Mock token refresh
        mock_decrypt.return_value = "refresh_token"
        calendar_service._refresh_outlook_token = Mock(return_value="access_token")

        # Mock event deletion
        calendar_service._outlook_delete_event = Mock()

        success = calendar_service.delete_event(
            trainer_id="trainer-123",
            session_id="session-456",
            calendar_event_id="outlook_event_123",
            calendar_provider="outlook",
        )

        assert success is True
        calendar_service._outlook_delete_event.assert_called_once()

    def test_delete_event_no_calendar_connected(self, calendar_service):
        """Test event deletion when no calendar is connected."""
        calendar_service._get_calendar_config = Mock(return_value=None)

        success = calendar_service.delete_event(
            trainer_id="trainer-123",
            session_id="session-456",
            calendar_event_id="event_123",
            calendar_provider="google",
        )

        assert success is False

    @patch("src.services.calendar_sync.decrypt_oauth_token_base64")
    def test_delete_event_graceful_degradation(
        self,
        mock_decrypt,
        calendar_service,
        google_calendar_config,
    ):
        """Test graceful degradation when event deletion fails."""
        # Mock config retrieval
        calendar_service._get_calendar_config = Mock(return_value=google_calendar_config)

        # Mock token refresh
        mock_decrypt.return_value = "refresh_token"
        calendar_service._refresh_google_token = Mock(return_value="access_token")

        # Mock event deletion failure
        calendar_service._google_delete_event = Mock(
            side_effect=ExternalServiceError("Google Calendar", "delete_event", "API error")
        )

        success = calendar_service.delete_event(
            trainer_id="trainer-123",
            session_id="session-456",
            calendar_event_id="google_event_123",
            calendar_provider="google",
        )

        # Should return False instead of raising exception
        assert success is False
