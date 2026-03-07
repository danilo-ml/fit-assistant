# FitAgent WhatsApp Assistant

A multi-tenant SaaS platform that enables personal trainers to manage their business through an AI-powered WhatsApp assistant. Built with AWS Strands for agentic orchestration, AWS Bedrock for LLM inference, and serverless event-driven architecture.

## Features

- **Multi-Agent Conversational AI**: Swarm-based architecture with 6 specialized agents (Coordinator, Student, Session, Payment, Calendar, Notification) using AWS Strands SDK
- **Natural Language Interface**: WhatsApp-based interaction using AWS Bedrock (Claude 3 and Amazon Nova models)
- **Multi-Tenant Architecture**: Isolated data per trainer with support for shared students
- **Session Management**: Scheduling, rescheduling, cancellation with conflict detection
- **Session Confirmation**: Automated attendance tracking via WhatsApp (YES/NO responses)
- **Calendar Integration**: Bidirectional sync with Google Calendar and Microsoft Outlook
- **Payment Tracking**: Receipt media storage in S3 with confirmation workflow
- **Automated Reminders**: EventBridge-scheduled notifications for sessions, payments, and confirmations
- **Message Routing**: Phone number-based user identification and context-aware routing
- **Gradual Rollout**: Feature flags for phased deployment and emergency rollback

## Technology Stack

### Backend Services
- **AWS Lambda**: Serverless compute for all business logic
- **AWS Bedrock**: LLM inference using Claude 3 and Amazon Nova models
- **AWS Strands**: Multi-agent orchestration using Swarm pattern
- **Python 3.12**: Primary programming language

#### Agent Model Configuration

Different agents use optimized models based on complexity:

| Agent | Model | Rationale |
|-------|-------|-----------|
| Coordinator | Amazon Nova Micro | Lightweight routing and intent analysis |
| Student | Amazon Nova Lite | Simple CRUD operations |
| Session | Amazon Nova Pro | Complex scheduling logic with conflict detection |
| Payment | Amazon Nova Lite | Simple CRUD operations |
| Calendar | Claude 3 Haiku | OAuth complexity and API integration |
| Notification | Amazon Nova Micro | Simple message queuing |

This configuration optimizes for both cost efficiency and performance.

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

## Project Structure

```
.
├── src/                           # Source code
│   ├── handlers/                  # Lambda function entry points
│   │   ├── webhook_handler.py     # API Gateway webhook receiver
│   │   ├── message_processor.py   # SQS message processing
│   │   ├── session_reminder.py    # EventBridge session reminders
│   │   ├── payment_reminder.py    # EventBridge payment reminders
│   │   ├── session_confirmation.py # EventBridge session confirmations (NEW)
│   │   ├── notification_sender.py # SQS notification processing
│   │   └── oauth_callback.py      # OAuth callback handler
│   ├── services/                  # Business logic services
│   │   ├── swarm_orchestrator.py  # Multi-agent orchestration (NEW)
│   │   ├── ai_agent.py            # Single agent (legacy)
│   │   ├── message_router.py      # Phone number routing logic
│   │   ├── calendar_sync.py       # Calendar API integration
│   │   ├── receipt_storage.py     # S3 media handling
│   │   └── twilio_client.py       # Twilio API wrapper
│   ├── tools/                     # AI agent tool functions
│   │   ├── student_tools.py       # register_student, view_students
│   │   ├── session_tools.py       # schedule_session, view_session_history (UPDATED)
│   │   ├── payment_tools.py       # register_payment, view_payments
│   │   ├── calendar_tools.py      # connect_calendar, view_calendar
│   │   └── notification_tools.py  # send_notification
│   ├── models/                    # Data models and database
│   │   ├── entities.py            # Pydantic models (Session model UPDATED)
│   │   └── dynamodb_client.py     # DynamoDB abstraction layer
│   ├── utils/                     # Utility functions
│   │   ├── validation.py          # Input validation utilities
│   │   ├── encryption.py          # KMS encryption helpers
│   │   └── logging.py             # Structured logging setup
│   └── config.py                  # Environment configuration
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests
│   ├── integration/               # Integration tests
│   ├── property/                  # Property-based tests
│   └── conftest.py                # Shared pytest fixtures
├── infrastructure/                # Infrastructure as Code
│   └── template.yml               # CloudFormation template (UPDATED)
├── localstack-init/               # LocalStack initialization
│   └── 01-setup.sh                # DynamoDB, S3, SQS setup script
├── docker-compose.yml             # Local development environment
├── Dockerfile                     # Container definition
├── requirements.txt               # Production dependencies (strands-agents added)
└── requirements-dev.txt           # Development dependencies
```

## Getting Started

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- AWS CLI (for deployment)
- Twilio account with WhatsApp enabled

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd fitagent-whatsapp-assistant
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your Twilio credentials and OAuth client IDs
   ```

3. **Start LocalStack and services**
   ```bash
   docker-compose up -d
   ```

   This will:
   - Start LocalStack with DynamoDB, S3, SQS, Lambda, API Gateway, EventBridge
   - Initialize DynamoDB tables with GSIs
   - Create S3 buckets with encryption
   - Set up SQS queues with dead-letter queues
   - Create KMS keys for OAuth token encryption

4. **Install dependencies (for local development without Docker)**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```

5. **Run tests**
   ```bash
   pytest
   ```

6. **Run with coverage**
   ```bash
   pytest --cov=src --cov-report=html --cov-report=term
   ```

### Running the API Server

**With Docker Compose:**
```bash
docker-compose up api
```

**Without Docker:**
```bash
export AWS_ENDPOINT_URL=http://localhost:4566
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

## Testing

### Run all tests
```bash
pytest
```

### Run specific test types
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Property-based tests
pytest tests/property/ -v
```

### Run with coverage
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

Coverage reports will be generated in `htmlcov/index.html`

## Code Quality

### Format code
```bash
black src/ tests/
isort src/ tests/
```

### Lint code
```bash
flake8 src/ tests/
```

### Type check
```bash
mypy src/
```

## Environment Variables

Required environment variables (see `.env.example` for full list):

- `AWS_REGION`, `AWS_ENDPOINT_URL` (LocalStack)
- `DYNAMODB_TABLE`, `S3_BUCKET`, `SQS_QUEUE_URL`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `OUTLOOK_CLIENT_ID`, `OUTLOOK_CLIENT_SECRET`
- `BEDROCK_MODEL_ID`, `BEDROCK_REGION`

## Deployment

Deployment is automated via GitHub Actions. See `.github/workflows/` for CI/CD pipelines.

### Feature Flags

The system supports gradual rollout of the multi-agent architecture via feature flags:

#### Global Feature Flag

Set the `ENABLE_MULTI_AGENT` environment variable:

```bash
# Enable multi-agent architecture
export ENABLE_MULTI_AGENT=true

# Disable (fallback to single-agent)
export ENABLE_MULTI_AGENT=false
```

When disabled, the system automatically falls back to the legacy single AIAgent class with no data migration required.

#### Per-Trainer Feature Flags

For granular control, feature flags can be stored per trainer in DynamoDB:

```python
# Enable multi-agent for specific trainer
db_client.put_item({
    'PK': 'TRAINER#trainer_abc123',
    'SK': 'FEATURE_FLAGS',
    'enable_multi_agent': True,
    'enable_session_confirmation': True
})
```

This allows:
- Canary deployments (10% of trainers)
- A/B testing
- Emergency rollback for specific trainers

### Phased Rollout Strategy

**Phase 1: Staging Validation (Week 1)**
- Deploy to staging environment with `ENABLE_MULTI_AGENT=true`
- Run integration tests and monitor metrics
- Validate all agent handoffs work correctly

**Phase 2: Canary Deployment (Week 2)**
- Enable for 10% of production trainers
- Monitor key metrics:
  - Response time (target: <10s)
  - Error rate (target: <1%)
  - Handoff count (typical: 2-3 per conversation)
  - Agent timeout violations

**Phase 3: Gradual Rollout (Week 3-4)**
- Week 3: Increase to 50% of trainers
- Week 4: Full rollout to 100%
- Keep feature flag for emergency rollback

**Phase 4: Session Confirmation (Week 5)**
- Deploy EventBridge rule for confirmation requests
- Enable `enable_session_confirmation` feature flag
- Monitor confirmation response rates

### Rollback Procedure

If issues are detected:

1. **Global Rollback**
   ```bash
   # Update environment variable
   aws lambda update-function-configuration \
     --function-name fitagent-message-processor \
     --environment Variables={ENABLE_MULTI_AGENT=false}
   ```

2. **Per-Trainer Rollback**
   ```python
   # Disable for specific trainer
   db_client.update_item(
       Key={'PK': 'TRAINER#trainer_abc123', 'SK': 'FEATURE_FLAGS'},
       UpdateExpression='SET enable_multi_agent = :val',
       ExpressionAttributeValues={':val': False}
   )
   ```

3. **Verification**
   - System automatically uses single AIAgent class
   - No data migration required (both architectures use same DynamoDB schema)
   - Existing conversations continue seamlessly

### Manual Deployment

1. **Package Lambda functions**
   ```bash
   zip -r lambda.zip src/ -x "*.pyc" -x "__pycache__/*"
   ```

2. **Deploy CloudFormation stack**
   ```bash
   aws cloudformation deploy \
     --template-file infrastructure/template.yml \
     --stack-name fitagent-production \
     --parameter-overrides \
       Environment=production \
       EnableMultiAgent=true \
       EnableSessionConfirmation=true \
     --capabilities CAPABILITY_IAM
   ```

3. **Verify deployment**
   ```bash
   # Check Lambda environment variables
   aws lambda get-function-configuration \
     --function-name fitagent-message-processor \
     --query 'Environment.Variables'
   
   # Check EventBridge rules
   aws events list-rules --name-prefix session-confirmation
   ```

### Monitoring

Key metrics to monitor during rollout:

- **Response Time**: CloudWatch metric `SwarmExecutionTime` (target: <10s)
- **Error Rate**: CloudWatch metric `SwarmErrorRate` (target: <1%)
- **Handoff Count**: CloudWatch metric `HandoffCount` (typical: 2-3)
- **Agent Timeouts**: CloudWatch metric `AgentTimeoutCount` (target: 0)
- **Confirmation Rate**: CloudWatch metric `SessionConfirmationRate` (target: >80%)

### Deployment Checklist

- [ ] Update `ENABLE_MULTI_AGENT` environment variable
- [ ] Deploy CloudFormation stack with new Lambda handlers
- [ ] Verify EventBridge rules are enabled
- [ ] Check DynamoDB GSI `session-confirmation-index` exists
- [ ] Test session confirmation flow end-to-end
- [ ] Monitor CloudWatch metrics for 24 hours
- [ ] Verify no increase in error rates
- [ ] Confirm response times within budget (<10s)

## Architecture

### Overview

FitAgent uses a serverless event-driven architecture with a Swarm-based multi-agent system for intelligent conversation handling. The system supports both single-agent (legacy) and multi-agent architectures via feature flags.

### Event Flow

1. **WhatsApp Message** → Twilio → API Gateway → SQS
2. **SQS** → Message Processor Lambda → Swarm Orchestrator
3. **Swarm Orchestrator** → Specialized Agents → Tool Functions
4. **Tool Functions** → DynamoDB/S3/Calendar APIs
5. **EventBridge** → Reminder/Confirmation Lambdas → Twilio → WhatsApp

### Multi-Agent Architecture (Swarm Pattern)

The system uses the **Swarm pattern** from AWS Strands SDK, where specialized agents autonomously collaborate through handoffs to handle different aspects of trainer business management.

#### Agent Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                        WhatsApp Message                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Coordinator Agent (Entry)                     │
│              Intent analysis & entity extraction                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │   Autonomous Handoffs via   │
              │    handoff_to_agent tool    │
              └──────────────┬──────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Student    │    │   Session    │    │   Payment    │
│    Agent     │    │    Agent     │    │    Agent     │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                    │
       │                   ▼                    │
       │           ┌──────────────┐            │
       │           │   Calendar   │            │
       │           │    Agent     │            │
       │           └──────────────┘            │
       │                                       │
       └───────────────────┬───────────────────┘
                           │
                           ▼
                  ┌──────────────┐
                  │ Notification │
                  │    Agent     │
                  └──────────────┘
```

#### Specialized Agents

| Agent | Role | Key Capabilities | Handoff Targets |
|-------|------|------------------|-----------------|
| **Coordinator** | Entry point, intent analysis | Entity extraction, routing decisions | All agents |
| **Student** | Student management | Register, update, view students | Session, Payment |
| **Session** | Session scheduling | Schedule, reschedule, cancel, conflict detection | Calendar, Payment |
| **Payment** | Payment tracking | Register payments, view history, statistics | None (terminal) |
| **Calendar** | Calendar integration | OAuth flow, Google/Outlook sync | None (terminal) |
| **Notification** | Broadcast messaging | Send notifications to student groups | None (terminal) |

#### Swarm Configuration

- **max_handoffs**: 5-7 (prevents infinite loops)
- **node_timeout**: 30s (individual agent execution limit)
- **execution_timeout**: 120s (total swarm execution limit)
- **response_time_budget**: 10s (typical conversations: 3-5s)

#### Shared Context

All agents share conversation context containing:
- Original user request
- Extracted entities (student names, dates, amounts)
- Handoff history (agent transitions)
- Agent contributions (data from previous agents)

This enables seamless collaboration without requiring users to repeat information across agent handoffs.

#### Invocation State

Multi-tenancy isolation is enforced through Invocation State (not visible to LLMs):
- `trainer_id`: Ensures data isolation per trainer
- Database clients and API connections
- Feature flags for gradual rollout

#### Example Handoff Flows

**Scenario 1: Schedule Session**
```
User: "Schedule a session with John tomorrow at 2pm for 60 minutes"
  ↓
Coordinator: Extracts entities (student_name="John", date="tomorrow", time="2pm", duration=60)
  ↓ handoff_to_agent(Session_Agent)
Session_Agent: Validates student exists, checks conflicts, creates session
  ↓ handoff_to_agent(Calendar_Agent)
Calendar_Agent: Syncs event to Google Calendar
  ↓ Response
"Session scheduled for tomorrow at 2pm and synced to your calendar"
```

**Scenario 2: Register Student then Schedule**
```
User: "Add new student Sarah, phone +14155551234, email sarah@example.com"
  ↓
Coordinator: Identifies student registration intent
  ↓ handoff_to_agent(Student_Agent)
Student_Agent: Registers student, stores in DynamoDB
  ↓ Response
"Sarah registered! Would you like to schedule a session?"

User: "Yes, tomorrow at 3pm"
  ↓
Coordinator: Retrieves previous context (student_name="Sarah")
  ↓ handoff_to_agent(Session_Agent)
Session_Agent: Schedules session using student from Shared_Context
  ↓ Response
"Session scheduled with Sarah for tomorrow at 3pm"
```

**Scenario 3: Session Confirmation Flow**
```
[1 hour after session ends]
System → Student: "Did your 60-minute training session with Mike on Monday, Jan 15 at 2:00 PM happen? Reply YES or NO"

Student: "YES"
  ↓
Message Processor: Detects confirmation response
  ↓
DynamoDB: Updates session status to "completed"
  ↓ Response
"Thanks for confirming! Session marked as completed."
```

### Session Confirmation Feature

Automated session attendance tracking through WhatsApp confirmations.

#### How It Works

1. **Automatic Trigger**: EventBridge rule runs every 5 minutes to check for sessions that ended 1 hour ago
2. **Confirmation Request**: System sends WhatsApp message to student: "Did your session with [Trainer] on [Date] at [Time] happen? Reply YES or NO"
3. **Student Response**: Student replies YES (completed) or NO (missed)
4. **Status Update**: Session status automatically updated in DynamoDB
5. **Analytics**: Attendance rate and session statistics available for trainers

#### Confirmation Statuses

- **scheduled**: Session is booked but not yet occurred
- **completed**: Student confirmed session happened (YES response)
- **missed**: Student confirmed session was missed (NO response)
- **pending_confirmation**: Session occurred but awaiting student response (24h timeout)
- **cancelled**: Session was cancelled before it occurred

#### Session Statistics

Trainers can view:
- Total sessions
- Completed sessions
- Missed sessions
- Pending confirmations
- Attendance rate (completed / (completed + missed))

#### Implementation

- **Lambda Handler**: `src/handlers/session_confirmation.py`
- **EventBridge Rule**: Triggers every 5 minutes (cron: `*/5 * * * ? *`)
- **DynamoDB GSI**: `session-confirmation-index` for efficient queries
- **Message Detection**: Message processor detects YES/NO responses and updates session status

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and ensure coverage ≥ 70%
4. Run code quality checks (black, flake8, mypy)
5. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions, please open a GitHub issue.
