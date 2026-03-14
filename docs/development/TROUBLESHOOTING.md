# Troubleshooting Guide

Common issues and solutions for FitAgent development and deployment.

## Local Development Issues

### LocalStack Not Starting

**Symptoms**: Docker container fails to start or exits immediately

**Solutions**:
```bash
# Check Docker is running
docker ps

# Check LocalStack logs
docker-compose logs localstack

# Remove old containers and restart
docker-compose down -v
docker-compose up -d

# Check port conflicts (4566)
lsof -i :4566
```

### DynamoDB Table Not Found

**Symptoms**: `ResourceNotFoundException` when querying DynamoDB

**Solutions**:
```bash
# Verify table exists
aws dynamodb list-tables --endpoint-url http://localhost:4566

# Recreate table
docker-compose down -v
docker-compose up -d

# Wait for initialization script
sleep 10

# Verify table created
aws dynamodb describe-table \
  --table-name fitagent-main \
  --endpoint-url http://localhost:4566
```

### S3 Bucket Not Found

**Symptoms**: `NoSuchBucket` error when uploading receipts

**Solutions**:
```bash
# List buckets
aws s3 ls --endpoint-url http://localhost:4566

# Create bucket manually
aws s3 mb s3://fitagent-receipts-local --endpoint-url http://localhost:4566

# Verify bucket exists
aws s3 ls s3://fitagent-receipts-local --endpoint-url http://localhost:4566
```

### Environment Variables Not Loaded

**Symptoms**: `KeyError` or `None` values for config

**Solutions**:
```bash
# Verify .env file exists
ls -la .env

# Check .env is loaded
python -c "from src.config import settings; print(settings.dynamodb_table)"

# Reload environment
source .venv/bin/activate
export $(cat .env | xargs)
```

## Testing Issues

### Tests Failing with Import Errors

**Symptoms**: `ModuleNotFoundError` when running tests

**Solutions**:
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Verify pytest installed
pytest --version

# Run from project root
cd /path/to/fitagent
pytest
```

### Mock AWS Services Not Working

**Symptoms**: Tests fail with AWS credential errors

**Solutions**:
```python
# Ensure moto is installed
pip install moto[all]

# Use proper fixtures in conftest.py
import pytest
from moto import mock_dynamodb, mock_s3

@pytest.fixture
def mock_aws():
    with mock_dynamodb(), mock_s3():
        yield
```

### Coverage Report Not Generated

**Symptoms**: No `htmlcov/` directory after running tests

**Solutions**:
```bash
# Install coverage
pip install coverage pytest-cov

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Check htmlcov directory
ls -la htmlcov/
```

## Twilio Integration Issues

### Webhook Not Receiving Messages

**Symptoms**: Messages sent to WhatsApp but no webhook calls

**Solutions**:
1. Verify ngrok is running:
```bash
ngrok http 8000
```

2. Check Twilio webhook URL is correct:
   - Go to Twilio Console > Messaging > Settings
   - Verify webhook URL: `https://your-ngrok-url.ngrok.io/webhook`

3. Check API server is running:
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Test webhook manually:
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+1234567890&Body=test"
```

### Twilio Signature Validation Failing

**Symptoms**: `403 Forbidden` or signature validation errors

**Solutions**:
```python
# Disable validation for local testing
# In src/handlers/webhook_handler.py
VALIDATE_SIGNATURE = os.getenv("ENVIRONMENT") != "local"

# Or set correct auth token in .env
TWILIO_AUTH_TOKEN=your_actual_auth_token
```

### Media Download Failing

**Symptoms**: Receipt images not downloading from Twilio

**Solutions**:
```python
# Check Twilio credentials
from twilio.rest import Client
client = Client(account_sid, auth_token)

# Test media download
media_url = "https://api.twilio.com/..."
response = requests.get(media_url, auth=(account_sid, auth_token))
print(response.status_code)
```

## AWS Bedrock Issues

### Model Not Available

**Symptoms**: `ValidationException` or model not found

**Solutions**:
```bash
# Check model ID is correct
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Verify model access in AWS Console
# Bedrock > Model access > Request access

# Test model invocation
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-sonnet-20240229-v1:0 \
  --body '{"prompt": "test"}' \
  --region us-east-1 \
  output.json
```

### Rate Limiting Errors

**Symptoms**: `ThrottlingException` from Bedrock

**Solutions**:
- Implement exponential backoff
- Request quota increase in AWS Console
- Use cheaper models for high-volume tasks
- Cache responses when possible

## Calendar Integration Issues

### OAuth Flow Not Working

**Symptoms**: Redirect fails or tokens not saved

**Solutions**:
1. Verify OAuth credentials:
```bash
# Check .env file
echo $GOOGLE_CLIENT_ID
echo $GOOGLE_CLIENT_SECRET
```

2. Check redirect URI matches:
   - Google Console: `http://localhost:8000/oauth/callback`
   - Code: `OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback`

3. Test OAuth URL generation:
```python
from src.services.calendar_sync import generate_oauth_url
url = generate_oauth_url("google", "trainer-id")
print(url)
```

### Calendar Sync Failing

**Symptoms**: Sessions not appearing in calendar

**Solutions**:
```python
# Check token is valid
from src.services.calendar_sync import get_calendar_client
client = get_calendar_client("trainer-id", "google")

# Test calendar API
events = client.events().list(calendarId='primary').execute()
print(events)

# Refresh token if expired
# Tokens auto-refresh in calendar_sync.py
```

## Deployment Issues

### CloudFormation Stack Fails

**Symptoms**: Stack creation fails with errors

**Solutions**:
```bash
# Validate template
aws cloudformation validate-template \
  --template-body file://infrastructure/template.yml

# Check stack events
aws cloudformation describe-stack-events \
  --stack-name fitagent-production

# View error details
aws cloudformation describe-stack-resources \
  --stack-name fitagent-production
```

### Lambda Function Errors

**Symptoms**: Function invocation fails in production

**Solutions**:
```bash
# Check CloudWatch logs
aws logs tail /aws/lambda/fitagent-webhook-handler --follow

# Test function directly
aws lambda invoke \
  --function-name fitagent-webhook-handler \
  --payload '{"test": "data"}' \
  output.json

# Check function configuration
aws lambda get-function-configuration \
  --function-name fitagent-webhook-handler
```

### OIDC Authentication Failing

**Symptoms**: GitHub Actions cannot deploy to AWS

**Solutions**:
1. Verify OIDC provider exists in AWS IAM
2. Check trust policy allows GitHub Actions
3. Verify role ARN in GitHub secrets
4. Check workflow permissions:
```yaml
permissions:
  id-token: write
  contents: read
```

## Performance Issues

### High Lambda Duration

**Symptoms**: Functions timing out or slow responses

**Solutions**:
- Increase Lambda memory (improves CPU)
- Optimize DynamoDB queries (use GSIs)
- Cache conversation state
- Use connection pooling for external APIs
- Profile code with AWS X-Ray

### DynamoDB Throttling

**Symptoms**: `ProvisionedThroughputExceededException`

**Solutions**:
```bash
# Switch to on-demand mode
aws dynamodb update-table \
  --table-name fitagent-main \
  --billing-mode PAY_PER_REQUEST

# Or increase provisioned capacity
aws dynamodb update-table \
  --table-name fitagent-main \
  --provisioned-throughput ReadCapacityUnits=10,WriteCapacityUnits=5
```

### SQS Queue Backing Up

**Symptoms**: Messages not processing fast enough

**Solutions**:
- Increase Lambda concurrency
- Optimize message processing logic
- Add more SQS consumers
- Check dead-letter queue for failed messages

## Data Issues

### Conversation State Lost

**Symptoms**: Agent doesn't remember context

**Solutions**:
```python
# Check TTL not expired
import time
current_time = int(time.time())
# TTL should be > current_time

# Verify conversation saved
from src.models.dynamodb_client import get_conversation_state
state = get_conversation_state("+1234567890")
print(state)
```

### Session Conflicts Not Detected

**Symptoms**: Double-booked sessions

**Solutions**:
```python
# Check session-date-index exists
aws dynamodb describe-table \
  --table-name fitagent-main \
  --query 'Table.GlobalSecondaryIndexes[?IndexName==`session-date-index`]'

# Verify conflict detection logic
from src.tools.session_tools import check_session_conflicts
conflicts = check_session_conflicts(trainer_id, datetime, duration)
print(conflicts)
```

## Getting More Help

### Enable Debug Logging
```python
# In src/utils/logging.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check System Status
```bash
# LocalStack health
curl http://localhost:4566/_localstack/health

# Docker containers
docker-compose ps

# Python environment
pip list | grep -E "boto3|moto|pytest"
```

### Collect Diagnostic Info
```bash
# System info
python --version
docker --version
aws --version

# Environment
env | grep -E "AWS|TWILIO|BEDROCK"

# Logs
docker-compose logs --tail=100 > logs.txt
```

### Report Issues
When reporting issues, include:
1. Error message and stack trace
2. Steps to reproduce
3. Environment (local/staging/production)
4. Relevant logs
5. What you've tried
