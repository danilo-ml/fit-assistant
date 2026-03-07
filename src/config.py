"""
Environment configuration using pydantic-settings.
Loads configuration from environment variables with sensible defaults.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Environment
    environment: str = "local"
    
    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_endpoint_url: Optional[str] = None  # For LocalStack
    aws_access_key_id: str = "test"  # For LocalStack
    aws_secret_access_key: str = "test"  # For LocalStack
    
    # DynamoDB Configuration
    dynamodb_table: str = "fitagent-main"
    
    # S3 Configuration
    s3_bucket: str = "fitagent-receipts"
    
    # SQS Configuration
    sqs_queue_url: str = ""
    notification_queue_url: str = ""
    dlq_url: str = ""
    
    # KMS Configuration
    kms_key_alias: str = "alias/fitagent-oauth-key"
    
    # Twilio Configuration
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""
    
    # OAuth Configuration - Google
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    
    # OAuth Configuration - Microsoft
    outlook_client_id: Optional[str] = None
    outlook_client_secret: Optional[str] = None
    
    # OAuth Redirect URI
    oauth_redirect_uri: str = ""
    
    # AWS Bedrock Configuration
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    bedrock_region: str = "us-east-1"
    
    # Multi-Agent Feature Flag
    enable_multi_agent: bool = False
    
    # Application Configuration
    conversation_ttl_hours: int = 24
    max_message_history: int = 10
    session_reminder_default_hours: int = 24
    payment_reminder_default_day: int = 1
    notification_rate_limit: int = 10  # messages per second
    
    # API Configuration
    api_gateway_rate_limit: int = 100  # requests per minute per IP
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
