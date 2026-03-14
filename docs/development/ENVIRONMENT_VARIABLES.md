# Environment Variables Reference

Complete reference for all environment variables used in FitAgent.

## Environment Configuration

### ENVIRONMENT
- **Type**: String
- **Required**: Yes
- **Default**: `local`
- **Values**: `local`, `staging`, `production`
- **Description**: Deployment environment identifier
- **Example**: `ENVIRONMENT=production`

## AWS Configuration

### AWS_REGION
- **Type**: String
- **Required**: Yes
- **Default**: `us-east-1`
- **Description**: AWS region for all services
- **Example**: `AWS_REGION=us-east-1`

### AWS_ENDPOINT_URL
- **Type**: String (URL)
- **Required**: Local only
- **Default**: `http://localhost:4566`
- **Description**: LocalStack endpoint for local development
- **Example**: `AWS_ENDPOINT_URL=http://localhost:4566`
- **Note**: Only used in local environment

### AWS_ACCESS_KEY_ID
- **Type**: String
- **Required**: Local only
- **Default**: `test`
- **Description**: AWS access key (use "test" for LocalStack)
- **Example**: `AWS_ACCESS_KEY_ID=test`
- **Security**: Use IAM roles in production (OIDC)

### AWS_SECRET_ACCESS_KEY
- **Type**: String
- **Required**: Local only
- **Default**: `test`
- **Description**: AWS secret key (use "test" for LocalStack)
- **Example**: `AWS_SECRET_ACCESS_KEY=test`
- **Security**: Use IAM roles in production (OIDC)

## DynamoDB Configuration

### DYNAMODB_TABLE
- **Type**: String
- **Required**: Yes
- **Default**: `fitagent-main`
- **Description**: DynamoDB table name for all entities
- **Example**: `DYNAMODB_TABLE=fitagent-main`

## S3 Configuration

### S3_BUCKET
- **Type**: String
- **Required**: Yes
- **Default**: `fitagent-receipts-local`
- **Description**: S3 bucket for receipt storage
- **Example**: 
  - Local: `S3_BUCKET=fitagent-receipts-local`
  - Production: `S3_BUCKET=fitagent-receipts-prod`

## SQS Configuration

### SQS_QUEUE_URL
- **Type**: String (URL)
- **Required**: Yes
- **Default**: `http://localhost:4566/000000000000/fitagent-messages.fifo`
- **Description**: SQS FIFO queue URL for message processing
- **Example**: 
  - Local: `SQS_QUEUE_URL=http://localhost:4566/000000000000/fitagent-messages.fifo`
  - Production: `SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/fitagent-messages.fifo`

### NOTIFICATION_QUEUE_URL
- **Type**: String (URL)
- **Required**: Yes
- **Default**: `http://localhost:4566/000000000000/fitagent-notifications`
- **Description**: SQS queue URL for notification delivery
- **Example**: `NOTIFICATION_QUEUE_URL=http://localhost:4566/000000000000/fitagent-notifications`

### DLQ_URL
- **Type**: String (URL)
- **Required**: Yes
- **Default**: `http://localhost:4566/000000000000/fitagent-messages-dlq.fifo`
- **Description**: Dead-letter queue for failed messages (FIFO)
- **Example**: `DLQ_URL=http://localhost:4566/000000000000/fitagent-messages-dlq.fifo`

## KMS Configuration

### KMS_KEY_ALIAS
- **Type**: String
- **Required**: Yes
- **Default**: `alias/fitagent-oauth-key`
- **Description**: KMS key alias for OAuth token encryption
- **Example**: `KMS_KEY_ALIAS=alias/fitagent-oauth-key`

## Twilio Configuration

### TWILIO_ACCOUNT_SID
- **Type**: String
- **Required**: Yes
- **Format**: `AC` followed by 32 hex characters
- **Description**: Twilio account identifier
- **Example**: `TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- **Security**: Store in AWS Secrets Manager for production

### TWILIO_AUTH_TOKEN
- **Type**: String
- **Required**: Yes
- **Format**: 32 hex characters
- **Description**: Twilio authentication token
- **Example**: `TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- **Security**: Store in AWS Secrets Manager for production

### TWILIO_WHATSAPP_NUMBER
- **Type**: String (E.164 format)
- **Required**: Yes
- **Format**: `whatsapp:+[country][number]`
- **Description**: Twilio WhatsApp sender number
- **Example**: 
  - Sandbox: `TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886`
  - Production: `TWILIO_WHATSAPP_NUMBER=whatsapp:+15551234567`

## Google OAuth Configuration

### GOOGLE_CLIENT_ID
- **Type**: String
- **Required**: Yes (if using Google Calendar)
- **Format**: `[id].apps.googleusercontent.com`
- **Description**: Google OAuth 2.0 client ID
- **Example**: `GOOGLE_CLIENT_ID=123456789-abc.apps.googleusercontent.com`
- **Setup**: Create in Google Cloud Console > APIs & Services > Credentials

### GOOGLE_CLIENT_SECRET
- **Type**: String
- **Required**: Yes (if using Google Calendar)
- **Description**: Google OAuth 2.0 client secret
- **Example**: `GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx`
- **Security**: Store in AWS Secrets Manager for production

## Microsoft OAuth Configuration

### OUTLOOK_CLIENT_ID
- **Type**: String (UUID)
- **Required**: Yes (if using Outlook Calendar)
- **Description**: Microsoft Azure AD application ID
- **Example**: `OUTLOOK_CLIENT_ID=12345678-1234-1234-1234-123456789abc`
- **Setup**: Create in Azure Portal > App registrations

### OUTLOOK_CLIENT_SECRET
- **Type**: String
- **Required**: Yes (if using Outlook Calendar)
- **Description**: Microsoft Azure AD client secret
- **Example**: `OUTLOOK_CLIENT_SECRET=abc~xxxxxxxxxxxxxxxxxxxxxxxx`
- **Security**: Store in AWS Secrets Manager for production

## OAuth Configuration

### OAUTH_REDIRECT_URI
- **Type**: String (URL)
- **Required**: Yes
- **Description**: OAuth callback URL for calendar integrations
- **Example**: 
  - Local: `OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback`
  - Production: `OAUTH_REDIRECT_URI=https://api.fitagent.com/oauth/callback`
- **Note**: Must match OAuth provider configuration

## AWS Bedrock Configuration

### BEDROCK_MODEL_ID
- **Type**: String
- **Required**: Yes
- **Default**: `anthropic.claude-3-sonnet-20240229-v1:0`
- **Description**: Default Bedrock model ID for AI agent
- **Example**: `BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0`
- **Options**:
  - `anthropic.claude-3-sonnet-20240229-v1:0` (balanced)
  - `anthropic.claude-3-haiku-20240307-v1:0` (fast/cheap)
  - `amazon.nova-micro-v1:0` (cheapest)
  - `amazon.nova-lite-v1:0` (light tasks)
  - `amazon.nova-pro-v1:0` (complex tasks)

### BEDROCK_REGION
- **Type**: String
- **Required**: Yes
- **Default**: `us-east-1`
- **Description**: AWS region for Bedrock service
- **Example**: `BEDROCK_REGION=us-east-1`
- **Note**: Bedrock availability varies by region

## Application Settings

### CONVERSATION_TTL_HOURS
- **Type**: Integer
- **Required**: No
- **Default**: `24`
- **Description**: Hours before conversation state expires
- **Example**: `CONVERSATION_TTL_HOURS=24`
- **Range**: 1-168 (1 hour to 7 days)

### MAX_MESSAGE_HISTORY
- **Type**: Integer
- **Required**: No
- **Default**: `10`
- **Description**: Maximum messages to keep in conversation history
- **Example**: `MAX_MESSAGE_HISTORY=10`
- **Range**: 5-50

### SESSION_REMINDER_DEFAULT_HOURS
- **Type**: Integer
- **Required**: No
- **Default**: `24`
- **Description**: Default hours before session to send reminder
- **Example**: `SESSION_REMINDER_DEFAULT_HOURS=24`
- **Range**: 1-168

### PAYMENT_REMINDER_DEFAULT_DAY
- **Type**: Integer
- **Required**: No
- **Default**: `1`
- **Description**: Day of month to send payment reminders
- **Example**: `PAYMENT_REMINDER_DEFAULT_DAY=1`
- **Range**: 1-28

### NOTIFICATION_RATE_LIMIT
- **Type**: Integer
- **Required**: No
- **Default**: `10`
- **Description**: Maximum notifications per minute per trainer
- **Example**: `NOTIFICATION_RATE_LIMIT=10`
- **Range**: 1-100

## Environment-Specific Examples

### Local Development (.env)
```bash
ENVIRONMENT=local
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
DYNAMODB_TABLE=fitagent-main
S3_BUCKET=fitagent-receipts-local
SQS_QUEUE_URL=http://localhost:4566/000000000000/fitagent-messages.fifo
NOTIFICATION_QUEUE_URL=http://localhost:4566/000000000000/fitagent-notifications.fifo
DLQ_URL=http://localhost:4566/000000000000/fitagent-messages-dlq.fifo
KMS_KEY_ALIAS=alias/fitagent-oauth-key
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
GOOGLE_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx
OUTLOOK_CLIENT_ID=12345678-1234-1234-1234-123456789abc
OUTLOOK_CLIENT_SECRET=abc~xxxxxxxxxxxxxxxxxxxxxxxx
OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1
```

### Production (Lambda Environment Variables)
```bash
ENVIRONMENT=production
AWS_REGION=us-east-1
DYNAMODB_TABLE=fitagent-main
S3_BUCKET=fitagent-receipts-prod
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/fitagent-messages.fifo
NOTIFICATION_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/fitagent-notifications.fifo
DLQ_URL=https://sqs.us-east-1.amazonaws.com/123456789/fitagent-messages-dlq.fifo
KMS_KEY_ALIAS=alias/fitagent-oauth-key
OAUTH_REDIRECT_URI=https://api.fitagent.com/oauth/callback
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1
```

**Note**: Secrets (Twilio, OAuth) stored in AWS Secrets Manager and injected at runtime.

## Security Best Practices

1. **Never commit .env files**: Already in .gitignore
2. **Use AWS Secrets Manager**: Store sensitive values in production
3. **Rotate credentials**: Regularly rotate API keys and tokens
4. **Use IAM roles**: Prefer OIDC over access keys in production
5. **Encrypt at rest**: Use KMS for sensitive data
6. **Limit permissions**: Use least-privilege IAM policies
7. **Audit access**: Enable CloudTrail logging

## Validation

### Required Variables Check
```python
from src.config import settings

# Validates all required variables on import
# Raises ValidationError if missing
```

### Manual Validation
```bash
# Check all variables are set
python -c "from src.config import settings; print('✓ All variables valid')"

# Print current configuration
python -c "from src.config import settings; import json; print(json.dumps(settings.dict(), indent=2))"
```
