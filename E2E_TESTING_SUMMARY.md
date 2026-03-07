# E2E WhatsApp Testing - Complete Setup Summary

## ✅ What Has Been Configured

### 1. Local Services Running
- **FastAPI Application** (port 8000) - API server with test endpoints
- **LocalStack** (port 4566) - AWS services emulation
  - DynamoDB with `fitagent-main` table
  - S3 bucket `fitagent-receipts-local`
  - SQS queues (messages, notifications, DLQ)
  - KMS key for encryption
  - Secrets Manager

### 2. Test Endpoints Created

#### `/test/process-message` (POST)
Directly processes WhatsApp messages without going through webhook/SQS.

**Parameters:**
- `phone_number` (required): Phone in E.164 format (e.g., +1234567890)
- `message` (required): Message text
- `message_sid` (optional): Message ID for tracking

**Example:**
```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=Hello, register me as a trainer"
```

#### `/webhook` (POST)
Simulates Twilio webhook (requires signature validation).

**Note:** For local testing, use `/test/process-message` instead.

### 3. Test Scripts Created

#### Python Script: `scripts/test_whatsapp_local.py`
- Automated test suite with 6 scenarios
- Checks service health
- Displays formatted results
- Shows debugging commands

**Usage:**
```bash
python scripts/test_whatsapp_local.py
```

#### Bash Script: `scripts/test_whatsapp_local.sh`
- Command-line test scenarios
- Color-coded output
- Service health checks

**Usage:**
```bash
chmod +x scripts/test_whatsapp_local.sh
./scripts/test_whatsapp_local.sh
```

### 4. Documentation Created

- **LOCAL_TESTING_GUIDE.md** - Comprehensive testing guide
- **QUICK_START.md** - Quick reference for common tasks
- **E2E_TESTING_SUMMARY.md** - This document

## 🎯 Testing Flow

### Complete E2E Flow (Simplified for Local Testing)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Test Script / cURL                                       │
│    POST /test/process-message                               │
│    { phone_number, message }                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. FastAPI Endpoint (src/main.py)                          │
│    - Creates SQS event format                               │
│    - Calls message_processor handler                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Message Processor (src/handlers/message_processor.py)   │
│    - Extracts message data                                  │
│    - Calls message router                                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Message Router (src/services/message_router.py)         │
│    - Looks up phone number in DynamoDB                      │
│    - Determines: trainer / student / onboarding             │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│ 5a. Trainer Flow │    │ 5b. Student Flow │
│  - AI Agent      │    │  - Simple Query  │
│  - Tools         │    │  - View Sessions │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Business Logic                                           │
│    - Student Tools (register, view)                         │
│    - Session Tools (schedule, reschedule, cancel)           │
│    - Payment Tools (register, view)                         │
│    - Calendar Tools (connect, sync)                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Data Layer                                               │
│    - DynamoDB Client (src/models/dynamodb_client.py)       │
│    - LocalStack DynamoDB (port 4566)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. Response                                                 │
│    - Success/Error status                                   │
│    - Data payload                                           │
│    - Logged to console                                      │
└─────────────────────────────────────────────────────────────┘
```

## 🧪 Test Scenarios

### Scenario 1: New Trainer Registration
```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=I want to register as a trainer"
```

**Expected Behavior:**
- Phone number not found in database
- Routes to onboarding handler
- Starts trainer registration conversation
- Creates conversation state in DynamoDB

### Scenario 2: Register Student
```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=Register student John Doe, phone +1987654321, email john@example.com"
```

**Expected Behavior:**
- Trainer identified from phone number
- AI agent processes request
- Calls `register_student` tool
- Creates student record in DynamoDB
- Links student to trainer

### Scenario 3: Schedule Session
```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=Schedule session with John tomorrow at 3pm for 1 hour"
```

**Expected Behavior:**
- Parses date/time from natural language
- Checks for conflicts
- Creates session in DynamoDB
- Optionally syncs to calendar (if connected)

### Scenario 4: Student Query
```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1987654321" \
  -d "message=What are my upcoming sessions?"
```

**Expected Behavior:**
- Student identified from phone number
- Queries sessions from DynamoDB
- Formats response with session details
- Returns via message processor

## 🔍 Debugging & Verification

### Check if Message Was Processed

```bash
# View API logs
docker logs fitagent-api 2>&1 | grep "+1234567890"

# Check for specific message
docker logs fitagent-api 2>&1 | grep "Hello"
```

### Verify Data in DynamoDB

```bash
# Count items in table
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb scan --table-name fitagent-main \
  --select COUNT --region us-east-1

# View all items
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb scan --table-name fitagent-main --region us-east-1

# Query specific trainer
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb query --table-name fitagent-main \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"TRAINER#<id>"}}' \
  --region us-east-1
```

### Check SQS Queues

```bash
# List queues
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  sqs list-queues --region us-east-1

# Get queue attributes
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/fitagent-messages \
  --attribute-names All --region us-east-1
```

## ⚠️ Known Limitations (Local Testing)

### What Works ✅
- Message routing logic
- DynamoDB operations (CRUD)
- Business logic (tools, services)
- Data validation
- Error handling
- Conversation state management
- Phone number lookup

### What's Mocked/Bypassed ⚠️
- **AWS Bedrock AI calls** - Will fail or use fallback logic
- **Twilio SMS sending** - Logged but not actually sent
- **Twilio signature validation** - Bypassed in test endpoint
- **Real SQS queuing** - Simulated in-memory
- **Calendar API calls** - Will fail without OAuth tokens
- **S3 media storage** - Uses LocalStack (works but not real S3)

### Workarounds
1. **AI Agent Testing**: Mock the AI responses or test individual tools directly
2. **SMS Sending**: Check logs for "would send" messages
3. **Calendar Sync**: Test with mock tokens or skip calendar tests
4. **Media Upload**: Use LocalStack S3 (works like real S3)

## 🚀 Next Steps

### 1. Run Automated Tests
```bash
# Run Python test script
python scripts/test_whatsapp_local.py

# Or bash script
./scripts/test_whatsapp_local.sh
```

### 2. Test Individual Components
```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run with coverage
pytest --cov=src --cov-report=html
```

### 3. Test with Real Twilio (Optional)
- Use ngrok to expose local endpoint
- Configure Twilio webhook URL
- Send real WhatsApp messages
- See [LOCAL_TESTING_GUIDE.md](LOCAL_TESTING_GUIDE.md) for details

### 4. Deploy to Staging
```bash
# Package Lambda
./scripts/package_lambda.sh

# Deploy to staging
./scripts/deploy_staging.sh
```

## 📚 Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **LocalStack Health**: http://localhost:4566/_localstack/health
- **Project README**: [README.md](README.md)
- **Testing Guide**: [LOCAL_TESTING_GUIDE.md](LOCAL_TESTING_GUIDE.md)
- **Quick Start**: [QUICK_START.md](QUICK_START.md)

## 🎉 Summary

You now have a complete local E2E testing environment for FitAgent WhatsApp messaging:

✅ Local services running (API + LocalStack)
✅ Test endpoints configured
✅ Test scripts ready to use
✅ DynamoDB with proper schema
✅ Documentation complete

**Start testing with:**
```bash
python scripts/test_whatsapp_local.py
```

Happy testing! 🚀
