"""
Unit tests for calendar tool functions.

Tests the connect_calendar tool which generates OAuth2 authorization URLs
for Google Calendar and Microsoft Outlook integration.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import urllib.parse

from src.tools.calendar_tools import connect_calendar


class TestConnectCalendar:
    """Test suite for connect_calendar tool function."""

    @patch("src.tools.calendar_tools.dynamodb_client")
    @patch("src.tools.calendar_tools.settings")
    def test_connect_google_calendar_success(self, mock_settings, mock_db):
        """Test successful Google Calendar OAuth URL generation."""
        # Setup mocks
        trainer_id = "test_trainer_123"
        mock_db.get_trainer.return_value = {
            "trainer_id": trainer_id,
            "name": "John Trainer",
            "entity_type": "TRAINER",
        }
        
        # Mock DynamoDB put_item for state token storage
        mock_db.dynamodb = MagicMock()
        mock_db.dynamodb.put_item = MagicMock()
        
        # Mock settings
        mock_settings.dynamodb_table = "fitagent-main"
        mock_settings.google_client_id = "test_google_client_id"
        mock_settings.google_client_secret = "test_google_client_secret"
        mock_settings.oauth_redirect_uri = "https://example.com/oauth/callback"

        # Execute
        result = connect_calendar(trainer_id=trainer_id, provider="google")

        # Verify success
        assert result["success"] is True
        assert "data" in result
        assert "oauth_url" in result["data"]
        assert "provider" in result["data"]
        assert "expires_in" in result["data"]

        # Verify provider
        assert result["data"]["provider"] == "google"
        assert result["data"]["expires_in"] == 600

        # Verify OAuth URL structure
        oauth_url = result["data"]["oauth_url"]
        assert oauth_url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")

        # Parse URL parameters
        parsed_url = urllib.parse.urlparse(oauth_url)
        params = urllib.parse.parse_qs(parsed_url.query)

        # Verify required OAuth parameters
        assert params["client_id"][0] == "test_google_client_id"
        assert params["redirect_uri"][0] == "https://example.com/oauth/callback"
        assert params["response_type"][0] == "code"
        assert params["scope"][0] == "https://www.googleapis.com/auth/calendar"
        assert "state" in params
        assert params["access_type"][0] == "offline"
        assert params["prompt"][0] == "consent"

        # Verify state token was stored in DynamoDB
        mock_db.dynamodb.put_item.assert_called_once()

    @patch("src.tools.calendar_tools.dynamodb_client")
    @patch("src.tools.calendar_tools.settings")
    def test_connect_outlook_calendar_success(self, mock_settings, mock_db):
        """Test successful Outlook Calendar OAuth URL generation."""
        # Setup mocks
        trainer_id = "test_trainer_123"
        mock_db.get_trainer.return_value = {
            "trainer_id": trainer_id,
            "name": "John Trainer",
            "entity_type": "TRAINER",
        }
        
        mock_db.dynamodb = MagicMock()
        mock_db.dynamodb.put_item = MagicMock()
        
        mock_settings.dynamodb_table = "fitagent-main"
        mock_settings.outlook_client_id = "test_outlook_client_id"
        mock_settings.outlook_client_secret = "test_outlook_client_secret"
        mock_settings.oauth_redirect_uri = "https://example.com/oauth/callback"

        # Execute
        result = connect_calendar(trainer_id=trainer_id, provider="outlook")

        # Verify success
        assert result["success"] is True
        assert "data" in result
        assert "oauth_url" in result["data"]

        # Verify provider
        assert result["data"]["provider"] == "outlook"
        assert result["data"]["expires_in"] == 600

        # Verify OAuth URL structure
        oauth_url = result["data"]["oauth_url"]
        assert oauth_url.startswith(
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
        )

        # Parse URL parameters
        parsed_url = urllib.parse.urlparse(oauth_url)
        params = urllib.parse.parse_qs(parsed_url.query)

        # Verify required OAuth parameters
        assert params["client_id"][0] == "test_outlook_client_id"
        assert params["redirect_uri"][0] == "https://example.com/oauth/callback"
        assert params["response_type"][0] == "code"
        assert params["scope"][0] == "Calendars.ReadWrite offline_access"
        assert "state" in params
        assert params["response_mode"][0] == "query"

        # Verify state token was stored
        mock_db.dynamodb.put_item.assert_called_once()

    @patch("src.tools.calendar_tools.dynamodb_client")
    def test_connect_calendar_invalid_provider(self, mock_db):
        """Test error handling for invalid provider."""
        trainer_id = "test_trainer_123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        
        result = connect_calendar(trainer_id=trainer_id, provider="invalid_provider")

        assert result["success"] is False
        assert "error" in result
        assert "Invalid provider" in result["error"]
        assert "google" in result["error"]
        assert "outlook" in result["error"]

    @patch("src.tools.calendar_tools.dynamodb_client")
    def test_connect_calendar_trainer_not_found(self, mock_db):
        """Test error handling when trainer doesn't exist."""
        mock_db.get_trainer.return_value = None
        
        result = connect_calendar(trainer_id="nonexistent_trainer", provider="google")

        assert result["success"] is False
        assert "error" in result
        assert "Trainer not found" in result["error"]

    @patch("src.tools.calendar_tools.dynamodb_client")
    @patch("src.tools.calendar_tools.settings")
    def test_connect_calendar_google_not_configured(self, mock_settings, mock_db):
        """Test error handling when Google OAuth is not configured."""
        trainer_id = "test_trainer_123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        
        mock_settings.google_client_id = None
        mock_settings.google_client_secret = None

        result = connect_calendar(trainer_id=trainer_id, provider="google")

        assert result["success"] is False
        assert "error" in result
        assert "Google Calendar integration is not configured" in result["error"]

    @patch("src.tools.calendar_tools.dynamodb_client")
    @patch("src.tools.calendar_tools.settings")
    def test_connect_calendar_outlook_not_configured(self, mock_settings, mock_db):
        """Test error handling when Outlook OAuth is not configured."""
        trainer_id = "test_trainer_123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        
        mock_settings.outlook_client_id = None
        mock_settings.outlook_client_secret = None

        result = connect_calendar(trainer_id=trainer_id, provider="outlook")

        assert result["success"] is False
        assert "error" in result
        assert "Outlook Calendar integration is not configured" in result["error"]

    @patch("src.tools.calendar_tools.dynamodb_client")
    @patch("src.tools.calendar_tools.settings")
    def test_connect_calendar_case_insensitive_provider(self, mock_settings, mock_db):
        """Test that provider parameter is case-insensitive."""
        trainer_id = "test_trainer_123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.dynamodb = MagicMock()
        mock_db.dynamodb.put_item = MagicMock()
        
        mock_settings.dynamodb_table = "fitagent-main"
        mock_settings.google_client_id = "test_google_client_id"
        mock_settings.google_client_secret = "test_google_client_secret"
        mock_settings.oauth_redirect_uri = "https://example.com/oauth/callback"

        # Test with uppercase
        result = connect_calendar(trainer_id=trainer_id, provider="GOOGLE")

        assert result["success"] is True
        assert result["data"]["provider"] == "google"

    @patch("src.tools.calendar_tools.dynamodb_client")
    @patch("src.tools.calendar_tools.settings")
    def test_connect_calendar_input_sanitization(self, mock_settings, mock_db):
        """Test that provider input is sanitized."""
        trainer_id = "test_trainer_123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.dynamodb = MagicMock()
        mock_db.dynamodb.put_item = MagicMock()
        
        mock_settings.dynamodb_table = "fitagent-main"
        mock_settings.google_client_id = "test_google_client_id"
        mock_settings.google_client_secret = "test_google_client_secret"
        mock_settings.oauth_redirect_uri = "https://example.com/oauth/callback"

        # Test with HTML tags (should be sanitized)
        result = connect_calendar(
            trainer_id=trainer_id, provider="<script>google</script>"
        )

        # Should still work after sanitization
        assert result["success"] is True
        assert result["data"]["provider"] == "google"

    @patch("src.tools.calendar_tools.dynamodb_client")
    @patch("src.tools.calendar_tools.settings")
    def test_connect_calendar_state_token_uniqueness(self, mock_settings, mock_db):
        """Test that each OAuth flow generates a unique state token."""
        trainer_id = "test_trainer_123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.dynamodb = MagicMock()
        mock_db.dynamodb.put_item = MagicMock()
        
        mock_settings.dynamodb_table = "fitagent-main"
        mock_settings.google_client_id = "test_google_client_id"
        mock_settings.google_client_secret = "test_google_client_secret"
        mock_settings.oauth_redirect_uri = "https://example.com/oauth/callback"

        # Generate two OAuth URLs
        result1 = connect_calendar(trainer_id=trainer_id, provider="google")
        result2 = connect_calendar(trainer_id=trainer_id, provider="google")

        # Extract state tokens from URLs
        url1 = result1["data"]["oauth_url"]
        url2 = result2["data"]["oauth_url"]

        params1 = urllib.parse.parse_qs(urllib.parse.urlparse(url1).query)
        params2 = urllib.parse.parse_qs(urllib.parse.urlparse(url2).query)

        state1 = params1["state"][0]
        state2 = params2["state"][0]

        # Verify state tokens are unique
        assert state1 != state2

