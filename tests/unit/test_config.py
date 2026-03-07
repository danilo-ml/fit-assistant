"""
Unit tests for configuration loading.
Tests environment variable loading and defaults.
"""

import os
import pytest
from src.config import Settings


def test_settings_default_values():
    """Test that Settings loads with default values."""
    settings = Settings()
    
    assert settings.environment == "local"
    assert settings.aws_region == "us-east-1"
    assert settings.dynamodb_table == "fitagent-main"
    assert settings.conversation_ttl_hours == 24
    assert settings.max_message_history == 10
    assert settings.session_reminder_default_hours == 24
    assert settings.payment_reminder_default_day == 1
    assert settings.notification_rate_limit == 10


def test_settings_from_environment_variables(monkeypatch):
    """Test that Settings loads from environment variables."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("DYNAMODB_TABLE", "custom-table")
    monkeypatch.setenv("CONVERSATION_TTL_HOURS", "48")
    monkeypatch.setenv("MAX_MESSAGE_HISTORY", "20")
    
    settings = Settings()
    
    assert settings.environment == "production"
    assert settings.aws_region == "us-west-2"
    assert settings.dynamodb_table == "custom-table"
    assert settings.conversation_ttl_hours == 48
    assert settings.max_message_history == 20


def test_settings_aws_endpoint_url_optional(monkeypatch):
    """Test that AWS endpoint URL is optional (for LocalStack)."""
    # Prevent loading from .env file
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.aws_endpoint_url is None


def test_settings_oauth_credentials_optional(monkeypatch):
    """Test that OAuth credentials are optional."""
    # Prevent loading from .env file
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OUTLOOK_CLIENT_ID", raising=False)
    monkeypatch.delenv("OUTLOOK_CLIENT_SECRET", raising=False)
    settings = Settings(_env_file=None)
    assert settings.google_client_id is None
    assert settings.google_client_secret is None
    assert settings.outlook_client_id is None
    assert settings.outlook_client_secret is None


def test_settings_bedrock_configuration():
    """Test Bedrock configuration defaults."""
    settings = Settings()
    assert settings.bedrock_model_id == "anthropic.claude-3-sonnet-20240229-v1:0"
    assert settings.bedrock_region == "us-east-1"


def test_settings_case_insensitive_env_vars(monkeypatch):
    """Test that environment variables are case-insensitive."""
    monkeypatch.setenv("environment", "staging")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    
    settings = Settings()
    
    assert settings.environment == "staging"
    assert settings.aws_region == "eu-west-1"


def test_settings_twilio_configuration(monkeypatch):
    """Test Twilio configuration from environment."""
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123456")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token123")
    monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    
    settings = Settings()
    
    assert settings.twilio_account_sid == "AC123456"
    assert settings.twilio_auth_token == "token123"
    assert settings.twilio_whatsapp_number == "whatsapp:+14155238886"


def test_settings_sqs_configuration(monkeypatch):
    """Test SQS queue URL configuration."""
    monkeypatch.setenv("SQS_QUEUE_URL", "http://localhost:4566/000000000000/messages")
    monkeypatch.setenv("NOTIFICATION_QUEUE_URL", "http://localhost:4566/000000000000/notifications")
    monkeypatch.setenv("DLQ_URL", "http://localhost:4566/000000000000/dlq")
    
    settings = Settings()
    
    assert settings.sqs_queue_url == "http://localhost:4566/000000000000/messages"
    assert settings.notification_queue_url == "http://localhost:4566/000000000000/notifications"
    assert settings.dlq_url == "http://localhost:4566/000000000000/dlq"


def test_settings_rate_limiting_configuration():
    """Test rate limiting configuration defaults."""
    settings = Settings()
    
    assert settings.notification_rate_limit == 10
    assert settings.api_gateway_rate_limit == 100
