# Technology Stack

## Architecture

Serverless event-driven architecture on AWS with WhatsApp integration via Twilio.

## Core Technologies

### Backend Services
- **AWS Lambda**: Serverless compute for all business logic
- **AWS Bedrock**: LLM inference using Claude 3 (Sonnet/Haiku)
- **AWS Strands**: Agentic orchestration for conversational AI
- **Python 3.12**: Primary programming language

### Data & Storage
- **DynamoDB**: Single-table design for all entities with GSIs
- **S3**: Receipt media storage with presigned URLs
- **AWS Secrets Manager**: OAuth token storage
- **AWS KMS**: Encryption for sensitive data

### Messaging & Integration
- **Twilio WhatsApp API**: Message gateway
- **SQS**: Message queuing with dead-letter queues
- **EventBridge**: Scheduled reminders and automation
- **API Gateway**: Webhook endpoint

### External Integrations
- **Google Calendar API v3**: Calendar sync via OAuth2
- **Microsoft Graph API**: Outlook calendar sync via OAuth2

## Development Tools

### Local Development
- **LocalStack**: AWS service emulation (DynamoDB, S3, SQS, Lambda, API Gateway, EventBridge)
- **moto**: Additional AWS SDK mocking
- **Docker Compose**: Local environment orchestration
- **uvicorn**: Local API server

### Testing
- **pytest**: Testing framework
- **Hypothesis**: Property-based testing library
- **moto**: AWS service mocking for tests
- **coverage**: Code coverage reporting (70% minimum)

### Code Quality
- **flake8**: Linting
- **black**: Code formatting
- **mypy**: Type checking

### Infrastructure
- **CloudFormation**: Infrastructure as Code
- **GitHub Actions**: CI/CD pipeline

## Common Commands

### Local Development
```bash
# Start local environment (Docker Compose - STANDARD METHOD)
make start

# View logs
make logs

# Stop services
make stop

# Restart services
make restart

# Clean slate (remove volumes)
make clean
```

### Testing
```bash
# Run all tests (inside Docker container)
make test

# Run specific test types
make test-unit
make test-integration
make test-property

# Run with coverage report
make test-coverage
```

### Code Quality
```bash
# Format code
black src/

# Lint code
flake8 src/

# Type check
mypy src/
```

### Deployment
```bash
# Validate CloudFormation templates
aws cloudformation validate-template --template-body file://infrastructure/template.yml

# Deploy to staging
aws cloudformation deploy --template-file infrastructure/template.yml --stack-name fitagent-staging --parameter-overrides Environment=staging

# Package Lambda functions
zip -r lambda.zip src/ -x "*.pyc" -x "__pycache__/*"
```

## Project Structure

```
src/
├── handlers/          # Lambda entry points
├── services/          # Business logic services
├── tools/             # AI agent tool functions
├── models/            # Data models and DynamoDB client
├── utils/             # Utilities (validation, encryption, logging)
└── config.py          # Environment configuration

tests/
├── unit/              # Unit tests
├── integration/       # Integration tests
├── property/          # Property-based tests
└── conftest.py        # Shared fixtures

infrastructure/
├── template.yml       # CloudFormation template
└── parameters/        # Environment-specific parameters

localstack-init/       # LocalStack initialization scripts
```

## Environment Variables

Required for local development and deployment:
- `AWS_REGION`, `AWS_ENDPOINT_URL` (LocalStack)
- `DYNAMODB_TABLE`, `S3_BUCKET`, `SQS_QUEUE_URL`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `OUTLOOK_CLIENT_ID`, `OUTLOOK_CLIENT_SECRET`
- `BEDROCK_MODEL_ID`, `BEDROCK_REGION`
