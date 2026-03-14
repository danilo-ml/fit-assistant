"""
Environment configuration using pydantic-settings.
Loads configuration from environment variables with sensible defaults.
Supports AWS Secrets Manager for production credentials.
"""

import json
import os
from typing import Optional, Dict, Any
from pydantic import field_validator
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
    
    # Secrets Manager Configuration (for production)
    twilio_secret_name: Optional[str] = None
    google_oauth_secret_name: Optional[str] = None
    outlook_oauth_secret_name: Optional[str] = None
    
    # Twilio Configuration (fallback for local/dev)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""
    
    # OAuth Configuration - Google (fallback for local/dev)
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    
    # OAuth Configuration - Microsoft (fallback for local/dev)
    outlook_client_id: Optional[str] = None
    outlook_client_secret: Optional[str] = None
    
    # OAuth Redirect URI (required for OAuth flow)
    oauth_redirect_uri: str = ""
    
    # AWS Bedrock Configuration
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    bedrock_region: str = "us-east-1"
    aws_bedrock_endpoint_url: Optional[str] = None  # Separate endpoint for Bedrock (use real AWS if None)
    
    # Application Configuration
    conversation_ttl_hours: int = 24
    max_message_history: int = 10
    session_reminder_default_hours: int = 24
    payment_reminder_default_day: int = 1
    notification_rate_limit: int = 10  # messages per second
    
    # API Configuration
    api_gateway_rate_limit: int = 100  # requests per minute per IP
    
    # Development/Testing Configuration
    skip_twilio_signature_validation: bool = False  # Set to True for local testing
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @field_validator('aws_bedrock_endpoint_url', 'aws_endpoint_url', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty string to None for endpoint URLs."""
        if v == '' or v is None:
            return None
        return v
    
    def _get_secrets_manager_client(self):
        """Get boto3 Secrets Manager client."""
        import boto3
        return boto3.client(
            'secretsmanager',
            region_name=self.aws_region,
            endpoint_url=self.aws_endpoint_url
        )
    
    def _get_secret(self, secret_name: str) -> Dict[str, Any]:
        """
        Retrieve secret from AWS Secrets Manager.
        
        In production, secrets are fetched fresh on each call to ensure
        updated credentials are loaded after Secrets Manager updates.
        
        Args:
            secret_name: Name of the secret in Secrets Manager
            
        Returns:
            Dict containing secret values
        """
        try:
            client = self._get_secrets_manager_client()
            # Disable caching by fetching fresh on each call
            response = client.get_secret_value(SecretId=secret_name)
            return json.loads(response['SecretString'])
        except Exception as e:
            # Log error but don't crash - allow fallback to env vars
            print(f"Warning: Could not retrieve secret {secret_name}: {e}")
            return {}
    
    def reload_secrets(self):
        """
        Force reload of secrets from Secrets Manager.
        
        This method can be called to invalidate any cached credential values
        and force fresh retrieval from Secrets Manager. Useful when secrets
        are updated and Lambda needs to reload them without redeployment.
        
        Note: In the current implementation, secrets are fetched fresh on each
        get_*_credentials() call, so this method serves as a placeholder for
        future caching optimizations.
        """
        # Clear any cached credential values if they exist
        # Currently, credentials are fetched fresh on each call via _get_secret()
        # This method is here for future caching implementations
        pass
    
    def get_twilio_credentials(self) -> Dict[str, str]:
        """
        Get Twilio credentials from Secrets Manager or environment variables.
        
        Returns:
            Dict with account_sid, auth_token, whatsapp_number
        """
        if self.twilio_secret_name:
            secret = self._get_secret(self.twilio_secret_name)
            return {
                'account_sid': secret.get('account_sid', self.twilio_account_sid),
                'auth_token': secret.get('auth_token', self.twilio_auth_token),
                'whatsapp_number': secret.get('whatsapp_number', self.twilio_whatsapp_number)
            }
        
        return {
            'account_sid': self.twilio_account_sid,
            'auth_token': self.twilio_auth_token,
            'whatsapp_number': self.twilio_whatsapp_number
        }
    
    def get_google_oauth_credentials(self) -> Dict[str, str]:
        """
        Get Google OAuth credentials from Secrets Manager or environment variables.
        
        Returns:
            Dict with client_id, client_secret
        """
        if self.google_oauth_secret_name:
            secret = self._get_secret(self.google_oauth_secret_name)
            return {
                'client_id': secret.get('client_id', self.google_client_id or ''),
                'client_secret': secret.get('client_secret', self.google_client_secret or '')
            }
        
        return {
            'client_id': self.google_client_id or '',
            'client_secret': self.google_client_secret or ''
        }
    
    def get_outlook_oauth_credentials(self) -> Dict[str, str]:
        """
        Get Outlook OAuth credentials from Secrets Manager or environment variables.
        
        Returns:
            Dict with client_id, client_secret
        """
        if self.outlook_oauth_secret_name:
            secret = self._get_secret(self.outlook_oauth_secret_name)
            return {
                'client_id': secret.get('client_id', self.outlook_client_id or ''),
                'client_secret': secret.get('client_secret', self.outlook_client_secret or '')
            }
        
        return {
            'client_id': self.outlook_client_id or '',
            'client_secret': self.outlook_client_secret or ''
        }


def get_settings() -> Settings:
    """
    Get settings instance.
    
    In Lambda environments, this returns a Settings instance that fetches
    secrets fresh from AWS Secrets Manager on each credential access.
    The Settings object itself may be cached across Lambda invocations,
    but credentials are always fetched fresh via _get_secret().
    
    When secrets are updated in Secrets Manager, the deployment script
    updates the Lambda function's SECRETS_UPDATED environment variable,
    which forces Lambda to reload the function and create a new Settings instance.
    
    Returns:
        Settings instance with current configuration
    """
    return Settings()


# Global settings instance - fetches secrets fresh on each credential access
settings = get_settings()
