# AWS Bedrock Setup Guide

This guide explains how to configure real AWS Bedrock for production-quality AI conversations instead of using the mock client.

## Why Use Real AWS Bedrock?

The mock Bedrock client provides basic rule-based responses for testing, but has limitations:
- Limited conversational understanding
- Cannot handle complex multi-turn conversations
- Requires manual pattern matching for each scenario
- No natural language understanding

Real AWS Bedrock with Claude 3 provides:
- Natural conversational AI
- Proper context understanding
- Intelligent tool calling
- Multi-turn conversation handling
- Better user experience

## Prerequisites

1. AWS Account with Bedrock access
2. AWS CLI installed
3. Bedrock model access enabled (Claude 3 Sonnet)

## Step 1: Enable Bedrock Model Access

1. Go to AWS Console → Bedrock → Model access
2. Request access to: `anthropic.claude-3-sonnet-20240229-v1:0`
3. Wait for approval (usually instant for Claude models)

## Step 2: Configure AWS Credentials

The system needs AWS credentials to access Bedrock. LocalStack (used for DynamoDB, S3, SQS) will continue working with test credentials, but Bedrock requires real AWS credentials.

### Option A: AWS CLI (Recommended)

```bash
# Configure AWS CLI with your credentials
aws configure

# Enter your credentials:
# AWS Access Key ID: YOUR_ACCESS_KEY
# AWS Secret Access Key: YOUR_SECRET_KEY
# Default region: us-east-1
# Default output format: json

# Verify it works
aws sts get-caller-identity
```

### Option B: Docker Environment Variables

Update `docker-compose.yml` to pass your AWS credentials to the container:

```yaml
services:
  sqs-processor:
    environment:
      # ... existing vars ...
      # Add your real AWS credentials for Bedrock
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
```

Then set them in your shell before starting Docker:

```bash
export AWS_ACCESS_KEY_ID=your_real_key
export AWS_SECRET_ACCESS_KEY=your_real_secret
make restart
```

### Option C: AWS Credentials File (Recommended for Development)

Create `~/.aws/credentials`:

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
```

Docker will automatically mount this file if you add to `docker-compose.yml`:

```yaml
services:
  sqs-processor:
    volumes:
      # ... existing volumes ...
      - ~/.aws:/root/.aws:ro  # Mount AWS credentials (read-only)
```

⚠️ **Security Warning**: Never commit real credentials to git. Use environment variables or AWS credentials file.

## Step 3: Configure Bedrock Settings

Your `.env` file should have:

```bash
# AWS Bedrock Configuration
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1
# Leave empty to use real AWS Bedrock
AWS_BEDROCK_ENDPOINT_URL=
# Set to false to use real Bedrock
USE_MOCK_BEDROCK=false
```

## Step 4: Verify Configuration

Run the diagnostic script to check everything is configured correctly:

```bash
# Check Bedrock configuration
python scripts/check_bedrock_config.py
```

This will verify:
- Environment variables are set correctly
- AWS credentials are configured
- Bedrock is accessible
- A test API call works

If all checks pass, you're ready to use Bedrock!

## Step 5: Test Conversational Flow

Try these test scenarios:

### Student Registration
```
User: "Quero cadastrar um novo aluno"
AI: "Claro! Para cadastrar o aluno, preciso de algumas informações..."
User: "Nome é João Silva"
AI: "Ótimo! E qual é o telefone do João?"
User: "+5511999999999"
AI: "Perfeito! Mais alguma informação..."
```

### Session Scheduling
```
User: "Agendar sessão com Maria"
AI: "Vou agendar uma sessão com Maria. Qual data e horário?"
User: "Amanhã às 14h"
AI: "Sessão agendada com Maria para [data] às 14:00!"
```

### List Students
```
User: "Listar meus alunos"
AI: "Aqui estão seus alunos cadastrados: [lista]"
```

## Troubleshooting

### Error: "Could not connect to the endpoint URL"

**Cause**: AWS credentials not configured or invalid region

**Solution**:
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Should return your AWS account info
```

### Error: "AccessDeniedException"

**Cause**: Your AWS account doesn't have Bedrock access

**Solution**:
1. Go to AWS Console → Bedrock → Model access
2. Request access to Claude 3 Sonnet
3. Wait for approval

### Error: "ValidationException: The provided model identifier is invalid"

**Cause**: Model ID is incorrect or not available in your region

**Solution**:
- Verify model ID: `anthropic.claude-3-sonnet-20240229-v1:0`
- Check model availability in your region (us-east-1 recommended)

### Still Using Mock Client

**Check**:
1. `.env` has `USE_MOCK_BEDROCK=false`
2. AWS credentials are configured (not 'test')
3. Restart Docker containers: `make restart`

## Cost Considerations

AWS Bedrock pricing (as of 2024):
- Claude 3 Sonnet: ~$3 per 1M input tokens, ~$15 per 1M output tokens
- Typical conversation: 500-2000 tokens
- Estimated cost: $0.01-0.05 per conversation

For development:
- Use AWS Free Tier if available
- Monitor usage in AWS Cost Explorer
- Set up billing alerts

## Production Deployment

For production, use IAM roles instead of access keys:

1. Create IAM role with Bedrock permissions
2. Attach role to Lambda functions
3. Remove AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from environment
4. AWS SDK will automatically use the IAM role

## Switching Back to Mock (for testing)

If you need to switch back to mock for testing:

```bash
# In .env
USE_MOCK_BEDROCK=true

# Restart
make restart
```

## Next Steps

- Test all conversation flows with real Bedrock
- Monitor Bedrock usage and costs
- Configure production IAM roles
- Set up CloudWatch logging for Bedrock calls
