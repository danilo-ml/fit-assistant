# Local E2E WhatsApp Testing Guide

This guide explains how to test the FitAgent WhatsApp messaging flow locally without needing actual Twilio webhooks or AWS Bedrock.

## Prerequisites

✅ Docker and Docker Compose installed
✅ Local services running (`docker-compose up -d`)
✅ Python 3.12+ with requests library (for Python script)

## Testing Methods

### Method 1: Python Test Script (Recommended)

The easiest way to test the complete flow:

```bash
# Run the automated test script
python scripts/test_whatsapp_local.py
```

This script will:
- Check if services are running
- Run 6 test scenarios simulating different user interactions
- Display responses and results
- Show useful debugging commands

**Test Scenarios Included:**
1. Trainer onboarding
2. Register a student
3. View all students
4. Schedule a training session
5. Student query for upcoming sessions
6. Register a payment

### Method 2: Bash Script

For quick command-line testing:

```bash
# Make executable (first time only)
chmod +x scripts/test_whatsapp_local.sh

# Run tests
./scripts/test_whatsapp_local.sh
```

### Method 3: Manual cURL Commands

Test individual messages:

```bash
# Test a trainer message
curl -X POST http://localhost:8000/test/process-message \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "phone_number=+1234567890" \
  -d "message=Hello, I want to register as a trainer" \
  -d "message_sid=TEST123"

# Test a student message
curl -X POST http://localhost:8000/test/process-message \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "phone_number=+1987654321" \
  -d "message=What are my upcoming sessions?" \
  -d "message_sid=TEST456"
```

### Method 4: API Documentation UI

Use the interactive Swagger UI:

1. Open http://localhost:8000/docs in your browser
2. Navigate to `/test/process-message` endpoint
3. Click "Try it out"
4. Fill in the form:
   - `phone_number`: +1234567890
   - `message`: Your test message
   - `message_sid`: (optional) TEST123
5. Click "Execute"

## Understanding the Flow

### What Happens When You Send a Test Message:

```
1. POST /test/process-message
   ↓
2. Creates SQS event format
   ↓
3. Calls message_processor Lambda handler
   ↓
4. Routes message based on phone number
   ↓
5. Processes with AI agent (or conversation handler)
   ↓
6. Stores data in DynamoDB (LocalStack)
   ↓
7. Returns response
```

### Bypassed Components (for local testing):

- ❌ Twilio webhook signature validation
- ❌ Actual SQS queue (simulated in-memory)
- ❌ AWS Bedrock AI calls (will use mock/fallback)
- ❌ Twilio SMS sending (logged but not sent)

### Active Components:

- ✅ Message routing logic
- ✅ DynamoDB operations (via LocalStack)
- ✅ Business logic (tools, services)
- ✅ Data validation
- ✅ Error handling

## Verifying Results

### Check DynamoDB Data

```bash
# List all items in the table
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb scan --table-name fitagent-main --region us-east-1

# Query specific trainer
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb query --table-name fitagent-main \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"TRAINER#<trainer-id>"}}' \
  --region us-east-1
```

### Check Application Logs

```bash
# View API logs in real-time
docker logs -f fitagent-api

# View last 50 lines
docker logs fitagent-api --tail 50

# Search for specific phone number
docker logs fitagent-api 2>&1 | grep "+1234567890"
```

### Check LocalStack Logs

```bash
# View LocalStack logs
docker logs fitagent-localstack --tail 50

# Check for DynamoDB operations
docker logs fitagent-localstack 2>&1 | grep -i dynamodb
```

## Common Test Scenarios

### 1. New Trainer Registration

```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=I want to register as a trainer"
```

**Expected:** Trainer onboarding flow starts

### 2. Register a Student

```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=Register student John Doe, phone +1987654321, email john@example.com"
```

**Expected:** Student created and linked to trainer

### 3. Schedule a Session

```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=Schedule session with John tomorrow at 3pm for 1 hour"
```

**Expected:** Session created in DynamoDB

### 4. Student Queries Sessions

```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1987654321" \
  -d "message=What are my upcoming sessions?"
```

**Expected:** List of student's sessions returned

### 5. Register Payment

```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=Register payment from John for $50"
```

**Expected:** Payment record created

## Troubleshooting

### Services Not Running

```bash
# Check service status
docker ps --filter "name=fitagent"

# Start services
docker-compose up -d

# Restart services
docker-compose restart
```

### API Not Responding

```bash
# Check API health
curl http://localhost:8000/health

# View API logs for errors
docker logs fitagent-api --tail 100

# Restart API
docker-compose restart api
```

### LocalStack Issues

```bash
# Check LocalStack health
curl http://localhost:4566/_localstack/health

# Restart LocalStack
docker-compose restart localstack

# View initialization logs
docker logs fitagent-localstack | grep "✓"
```

### Database Empty

```bash
# Verify table exists
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb list-tables --region us-east-1

# Check if data was written
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb scan --table-name fitagent-main \
  --select COUNT --region us-east-1
```

## Testing with Real Twilio (Optional)

To test with actual Twilio webhooks:

1. **Expose local endpoint:**
   ```bash
   # Using ngrok
   ngrok http 8000
   ```

2. **Configure Twilio webhook:**
   - Go to Twilio Console
   - Set webhook URL to: `https://your-ngrok-url.ngrok.io/webhook`

3. **Send WhatsApp message:**
   - Send message to your Twilio WhatsApp number
   - Check logs: `docker logs -f fitagent-api`

**Note:** This requires valid Twilio credentials in `.env` file.

## Performance Testing

### Load Testing with Multiple Messages

```bash
# Send 10 messages rapidly
for i in {1..10}; do
  curl -X POST http://localhost:8000/test/process-message \
    -d "phone_number=+123456789$i" \
    -d "message=Test message $i" &
done
wait
```

### Measure Response Time

```bash
time curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=Hello"
```

## Clean Up

### Reset Database

```bash
# Delete all items (careful!)
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb delete-table --table-name fitagent-main --region us-east-1

# Restart LocalStack to recreate
docker-compose restart localstack
sleep 30  # Wait for initialization
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Next Steps

After local testing:
1. Run unit tests: `pytest tests/unit/`
2. Run integration tests: `pytest tests/integration/`
3. Deploy to staging: `./scripts/deploy_staging.sh`
4. Test with real Twilio webhooks in staging

## Useful Resources

- API Documentation: http://localhost:8000/docs
- LocalStack Dashboard: http://localhost:4566/_localstack/health
- DynamoDB Local: http://localhost:4566 (use AWS CLI with --endpoint-url)
