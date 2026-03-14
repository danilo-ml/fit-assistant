# Production Deployment Guide

This guide walks you through deploying FitAgent to production with secure credential management using AWS Secrets Manager.

## Overview

The production deployment uses AWS Secrets Manager to store sensitive credentials instead of hardcoding them in configuration files. This provides:

- **Security**: Credentials are encrypted at rest and in transit
- **Rotation**: Easy credential rotation without code changes
- **Audit**: CloudTrail logs all secret access
- **Separation**: Infrastructure and secrets are managed separately

## Prerequisites

1. **AWS CLI configured** with appropriate credentials
2. **IAM permissions** for:
   - CloudFormation (create/update stacks)
   - Lambda (create/update functions)
   - DynamoDB (create tables)
   - S3 (create buckets)
   - Secrets Manager (create/update secrets)
   - KMS (create keys)
   - IAM (create roles and policies)

3. **Credentials ready**:
   - Twilio Account SID, Auth Token, WhatsApp Number
   - Google OAuth Client ID and Secret (optional)
   - Microsoft Outlook OAuth Client ID and Secret (optional)

## Deployment Steps

### Step 1: Deploy Infrastructure

Run the production deployment script:

```bash
chmod +x scripts/deploy_production.sh
./scripts/deploy_production.sh
```

This script will:
- Validate the CloudFormation template
- Package the Lambda function code
- Deploy the infrastructure stack
- Create placeholder secrets in Secrets Manager
- Update Lambda function code

### Step 2: Update Secrets

After infrastructure deployment, update the secrets with real credentials:

#### Option A: Interactive Script (Recommended)

```bash
chmod +x scripts/update_secrets.sh
./scripts/update_secrets.sh production all
```

This will prompt you for each credential interactively.

#### Option B: Update Individual Secrets

Update Twilio credentials:
```bash
./scripts/update_secrets.sh production twilio
```

Update Google OAuth credentials:
```bash
./scripts/update_secrets.sh production google
```

Update Outlook OAuth credentials:
```bash
./scripts/update_secrets.sh production outlook
```

#### Option C: AWS CLI Directly

```bash
# Update Twilio credentials
aws secretsmanager update-secret \
  --secret-id fitagent/twilio/production \
  --secret-string '{"account_sid":"YOUR_SID","auth_token":"YOUR_TOKEN","whatsapp_number":"whatsapp:+1234567890"}' \
  --region us-east-1

# Update Google OAuth credentials
aws secretsmanager update-secret \
  --secret-id fitagent/google-oauth/production \
  --secret-string '{"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_CLIENT_SECRET"}' \
  --region us-east-1

# Update Outlook OAuth credentials
aws secretsmanager update-secret \
  --secret-id fitagent/outlook-oauth/production \
  --secret-string '{"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_CLIENT_SECRET"}' \
  --region us-east-1
```

### Step 3: Verify Deployment

Check that all resources were created:

```bash
# List stack resources
aws cloudformation describe-stack-resources \
  --stack-name fitagent-production \
  --region us-east-1

# Test Lambda function
aws lambda invoke \
  --function-name fitagent-message-processor-production \
  --payload '{"test": true}' \
  --region us-east-1 \
  response.json

# Verify secrets exist
aws secretsmanager list-secrets \
  --filters Key=name,Values=fitagent \
  --region us-east-1
```

### Step 4: Configure Twilio Webhook

Update your Twilio WhatsApp sandbox to point to the production API Gateway endpoint:

1. Get the API Gateway URL from CloudFormation outputs
2. In Twilio Console, configure webhook URL: `https://your-api-gateway-url/webhook`
3. Set HTTP method to POST

## Architecture Changes

### Before (Insecure)
```
Parameter Files → Environment Variables → Lambda
   ↓ (credentials in plaintext)
```

### After (Secure)
```
Secrets Manager → Lambda (retrieves at runtime)
   ↓ (encrypted, audited, rotatable)
```

## How It Works

### Configuration Loading

The `src/config.py` module now supports two modes:

1. **Local/Development**: Reads from environment variables (`.env` file)
2. **Production**: Reads from AWS Secrets Manager

```python
from src.config import settings

# Automatically retrieves from Secrets Manager if configured
twilio_creds = settings.get_twilio_credentials()
# Returns: {'account_sid': '...', 'auth_token': '...', 'whatsapp_number': '...'}
```

### Lambda Environment Variables

Lambda functions receive secret names (not values):

```yaml
Environment:
  Variables:
    TWILIO_SECRET_NAME: fitagent/twilio/production
    GOOGLE_OAUTH_SECRET_NAME: fitagent/google-oauth/production
    OUTLOOK_OAUTH_SECRET_NAME: fitagent/outlook-oauth/production
```

### Runtime Secret Retrieval

Secrets are retrieved at runtime with caching:

```python
# First call retrieves from Secrets Manager
creds = settings.get_twilio_credentials()

# Subsequent calls use cached value (within same Lambda execution)
creds = settings.get_twilio_credentials()  # Cached
```

## Security Best Practices

### 1. Least Privilege IAM

Lambda functions only have access to specific secrets:

```yaml
- Effect: Allow
  Action:
    - secretsmanager:GetSecretValue
  Resource:
    - arn:aws:secretsmanager:region:account:secret:fitagent/twilio/production
```

### 2. Encryption at Rest

All secrets are encrypted using AWS KMS:
- Secrets Manager: Automatic encryption
- DynamoDB: KMS encryption enabled
- S3: Server-side encryption enabled

### 3. Encryption in Transit

- All AWS API calls use TLS
- Secrets retrieved over encrypted connections
- No credentials in logs or CloudWatch

### 4. Audit Trail

All secret access is logged in CloudTrail:

```bash
# View secret access logs
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=fitagent/twilio/production \
  --region us-east-1
```

## Credential Rotation

To rotate credentials without downtime:

1. **Update secret in Secrets Manager**:
   ```bash
   ./scripts/update_secrets.sh production twilio
   ```

2. **Lambda automatically uses new credentials** on next invocation (cached values expire with Lambda execution context)

3. **No code deployment required**

## Troubleshooting

### Lambda Can't Access Secrets

Check IAM permissions:
```bash
aws iam get-role-policy \
  --role-name fitagent-message-processor-role-production \
  --policy-name SecretsManagerAccess
```

### Secrets Not Found

Verify secret exists:
```bash
aws secretsmanager describe-secret \
  --secret-id fitagent/twilio/production \
  --region us-east-1
```

### Invalid Credentials

Test secret retrieval:
```bash
aws secretsmanager get-secret-value \
  --secret-id fitagent/twilio/production \
  --region us-east-1 \
  --query SecretString \
  --output text
```

## Rollback

If deployment fails, rollback to previous version:

```bash
aws cloudformation cancel-update-stack \
  --stack-name fitagent-production \
  --region us-east-1
```

Or delete the stack entirely:

```bash
aws cloudformation delete-stack \
  --stack-name fitagent-production \
  --region us-east-1
```

## Cost Considerations

### Secrets Manager Pricing
- $0.40 per secret per month
- $0.05 per 10,000 API calls
- 3 secrets = ~$1.20/month + API calls

### Recommended: Use Secrets Caching
The config module implements caching to minimize API calls and costs.

## Monitoring

### CloudWatch Metrics

Monitor secret access:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/SecretsManager \
  --metric-name SecretRetrievalCount \
  --dimensions Name=SecretId,Value=fitagent/twilio/production \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

### CloudWatch Logs

View Lambda logs:
```bash
aws logs tail /aws/lambda/fitagent-message-processor-production --follow
```

## Next Steps

1. **Set up monitoring**: Configure CloudWatch alarms for errors
2. **Enable X-Ray**: Add tracing for performance monitoring
3. **Configure backups**: Set up DynamoDB point-in-time recovery
4. **Set up CI/CD**: Automate deployments with GitHub Actions
5. **Load testing**: Test with production-like traffic

## Support

For issues or questions:
- Check CloudWatch Logs for error messages
- Review CloudFormation events for deployment issues
- Verify IAM permissions for Lambda execution role
