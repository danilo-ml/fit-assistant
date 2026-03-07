# KMS Encryption Utilities

This module provides utilities for encrypting and decrypting sensitive data using AWS KMS, specifically designed for OAuth refresh tokens stored in DynamoDB.

## Overview

The encryption utilities ensure that OAuth refresh tokens are encrypted at rest in DynamoDB, meeting security requirements 4.2 and 20.3.

## Usage

### Basic Usage with Convenience Functions

For most use cases, use the module-level convenience functions:

```python
from src.utils.encryption import (
    encrypt_oauth_token,
    decrypt_oauth_token,
    encrypt_oauth_token_base64,
    decrypt_oauth_token_base64
)

# Encrypt a refresh token (returns bytes)
refresh_token = "ya29.a0AfH6SMBx..."
encrypted_token = encrypt_oauth_token(refresh_token)

# Store in DynamoDB
dynamodb.put_item(
    Item={
        'PK': f'TRAINER#{trainer_id}',
        'SK': 'CALENDAR_CONFIG',
        'encrypted_refresh_token': encrypted_token,
        'provider': 'google'
    }
)

# Retrieve and decrypt
item = dynamodb.get_item(Key={'PK': pk, 'SK': sk})
encrypted_token = item['encrypted_refresh_token']
decrypted_token = decrypt_oauth_token(encrypted_token)
```

### Base64 Encoding (Alternative)

If you prefer to store encrypted tokens as strings in DynamoDB:

```python
# Encrypt to base64 string
encrypted_base64 = encrypt_oauth_token_base64(refresh_token)

# Store as string in DynamoDB
dynamodb.put_item(
    Item={
        'PK': f'TRAINER#{trainer_id}',
        'SK': 'CALENDAR_CONFIG',
        'encrypted_refresh_token': encrypted_base64,  # String instead of bytes
        'provider': 'google'
    }
)

# Decrypt from base64 string
decrypted_token = decrypt_oauth_token_base64(encrypted_base64)
```

### Advanced Usage with KMSEncryptionHelper

For more control, use the `KMSEncryptionHelper` class directly:

```python
from src.utils.encryption import KMSEncryptionHelper

# Create helper with custom configuration
helper = KMSEncryptionHelper(
    kms_key_alias='alias/my-custom-key',
    aws_region='us-west-2',
    aws_endpoint_url='http://localhost:4566'  # For LocalStack
)

# Encrypt and decrypt
encrypted = helper.encrypt("my-secret-token")
decrypted = helper.decrypt(encrypted)

# Or use base64 encoding
encrypted_base64 = helper.encrypt_to_base64("my-secret-token")
decrypted = helper.decrypt_from_base64(encrypted_base64)
```

## Configuration

The encryption utilities use settings from `src/config.py`:

```python
# Default KMS key alias
kms_key_alias: str = "alias/fitagent-oauth-key"

# AWS region
aws_region: str = "us-east-1"

# LocalStack endpoint (for local development)
aws_endpoint_url: Optional[str] = None
```

## Error Handling

All encryption operations may raise `EncryptionError`:

```python
from src.utils.encryption import EncryptionError, encrypt_oauth_token

try:
    encrypted = encrypt_oauth_token(refresh_token)
except EncryptionError as e:
    logger.error(f"Encryption failed: {e}")
    # Handle error appropriately
```

Common error scenarios:
- Empty plaintext/ciphertext
- KMS key not found
- Invalid ciphertext
- Invalid base64 encoding
- AWS permissions issues

## Example: Calendar OAuth Flow

Complete example of encrypting OAuth tokens during calendar connection:

```python
from src.utils.encryption import encrypt_oauth_token, decrypt_oauth_token
from src.models.dynamodb_client import DynamoDBClient

def store_calendar_tokens(trainer_id: str, provider: str, refresh_token: str):
    """Store encrypted OAuth refresh token."""
    # Encrypt the refresh token
    encrypted_token = encrypt_oauth_token(refresh_token)
    
    # Store in DynamoDB
    db_client = DynamoDBClient()
    db_client.put_item({
        'PK': f'TRAINER#{trainer_id}',
        'SK': 'CALENDAR_CONFIG',
        'entity_type': 'CALENDAR_CONFIG',
        'trainer_id': trainer_id,
        'provider': provider,
        'encrypted_refresh_token': encrypted_token,
        'connected_at': datetime.utcnow().isoformat()
    })

def retrieve_calendar_token(trainer_id: str) -> str:
    """Retrieve and decrypt OAuth refresh token."""
    # Get from DynamoDB
    db_client = DynamoDBClient()
    item = db_client.get_item(
        pk=f'TRAINER#{trainer_id}',
        sk='CALENDAR_CONFIG'
    )
    
    if not item:
        raise ValueError("Calendar not connected")
    
    # Decrypt the token
    encrypted_token = item['encrypted_refresh_token']
    return decrypt_oauth_token(encrypted_token)
```

## Local Development with LocalStack

For local development, ensure LocalStack has KMS enabled:

```bash
# In docker-compose.yml
services:
  localstack:
    environment:
      - SERVICES=dynamodb,s3,sqs,lambda,apigateway,events,secretsmanager,kms
```

Initialize KMS key in LocalStack:

```bash
# In localstack-init/01-setup.sh
awslocal kms create-key --description "FitAgent OAuth token encryption"
KEY_ID=$(awslocal kms list-keys --query 'Keys[0].KeyId' --output text)
awslocal kms create-alias --alias-name alias/fitagent-oauth-key --target-key-id $KEY_ID
```

## Security Considerations

1. **Never log decrypted tokens**: Always mask or omit sensitive data from logs
2. **Use HTTPS**: All API calls to external services should use HTTPS
3. **Rotate keys**: Implement KMS key rotation policies in production
4. **Least privilege**: Lambda functions should have minimal KMS permissions
5. **Audit**: Enable CloudTrail logging for KMS operations

## Testing

Unit tests use mocked KMS clients:

```python
from unittest.mock import Mock, patch
from src.utils.encryption import KMSEncryptionHelper

def test_encryption():
    with patch('boto3.client') as mock_boto:
        mock_kms = Mock()
        mock_boto.return_value = mock_kms
        
        mock_kms.encrypt.return_value = {
            'CiphertextBlob': b'encrypted-data'
        }
        
        helper = KMSEncryptionHelper()
        result = helper.encrypt("test-token")
        
        assert result == b'encrypted-data'
```

See `tests/unit/test_encryption.py` for comprehensive test examples.
