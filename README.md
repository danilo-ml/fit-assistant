# FitAgent WhatsApp Assistant

A multi-tenant SaaS platform that enables personal trainers to manage their business through an AI-powered WhatsApp assistant. Built with AWS Strands for agentic orchestration, AWS Bedrock for LLM inference, and serverless event-driven architecture.

## Quick Links

- [Quickstart Guide](docs/QUICKSTART.md) - Get started in minutes
- [Local Testing Guide](docs/guides/LOCAL_TESTING_GUIDE.md) - Complete testing documentation
- [Architecture Documentation](docs/architecture/) - System design and technical details
- [API Reference](docs/api/ENDPOINTS.md) - REST API documentation
- [Contributing Guide](docs/development/CONTRIBUTING.md) - Development workflow
- [Troubleshooting](docs/development/TROUBLESHOOTING.md) - Common issues and solutions

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
│   │   ├── strands_agent_service.py # Strands Agents SDK integration
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

### Quick Setup (2 minutes)

```bash
# 1. Start local environment
make start

# 2. Verify it's working
curl http://localhost:8000/health

# 3. Run tests
make test
```

That's it! All services (API + LocalStack) are running in Docker.

See the [Quickstart Guide](docs/QUICKSTART.md) for detailed instructions.

### E2E Testing with Twilio Sandbox

For complete end-to-end testing with real WhatsApp messages:

```bash
# 1. Add Twilio credentials to .env
# TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER

# 2. Start everything (includes ngrok setup)
make e2e-twilio
```

The script will guide you through Twilio webhook configuration.

For detailed instructions, see:
- [Local Testing Guide](docs/guides/LOCAL_TESTING_GUIDE.md) - Complete documentation
- [Twilio Sandbox Setup](docs/guides/TWILIO_SANDBOX_SETUP.md) - Detailed Twilio configuration

## Documentation

Complete documentation is available in the [docs/](docs/) directory:

- **[Architecture](docs/architecture/)**: System design, multi-agent pattern, database schema
- **[Guides](docs/guides/)**: Step-by-step tutorials for common tasks
- **[API Reference](docs/api/)**: REST API endpoint documentation
- **[Development](docs/development/)**: Contributing guidelines, troubleshooting, environment variables
- **[Security](docs/security/)**: Security policies and best practices
- **[Deployment](docs/deployment/)**: Production and staging deployment guides

## Testing

All tests run inside Docker containers for consistency:

```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration
make test-property

# Run with coverage
make test-coverage
```

Coverage reports will be generated in `htmlcov/index.html`

## Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type check
make type-check

# Run all quality checks
make quality
```

## Deployment

See [CI/CD Setup Guide](docs/guides/CI_CD_SETUP.md) for GitHub Actions configuration with OIDC.

For manual deployment, see [Production Deployment Guide](docs/deployment/PRODUCTION_DEPLOYMENT.md).

## Architecture

See [Architecture Documentation](docs/architecture/) for detailed system design:
- [System Design](docs/architecture/SYSTEM_DESIGN.md) - Overall architecture and components
- [Multi-Agent Pattern](docs/architecture/MULTI_AGENT_PATTERN.md) - AWS Strands swarm orchestration
- [Database Schema](docs/architecture/DATABASE_SCHEMA.md) - DynamoDB single-table design

## Contributing

See [Contributing Guide](docs/development/CONTRIBUTING.md) for development workflow and standards.

## Security

See [Security Policy](docs/security/SECURITY_POLICY.md) for vulnerability reporting and security best practices.

## License

[Your License Here]

## Support

- [Troubleshooting Guide](docs/development/TROUBLESHOOTING.md)
- [GitHub Issues](https://github.com/your-org/fitagent/issues)
- Email: support@fitagent.com
