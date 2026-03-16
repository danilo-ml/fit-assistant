# Project Structure

## Directory Organization

```
.
├── src/                           # Source code
│   ├── handlers/                  # Lambda function entry points
│   │   ├── webhook_handler.py     # API Gateway webhook receiver
│   │   ├── message_processor.py   # SQS message processing
│   │   ├── session_reminder.py    # EventBridge session reminders
│   │   ├── payment_reminder.py    # EventBridge payment reminders
│   │   ├── notification_sender.py # SQS notification processing
│   │   ├── oauth_callback.py      # OAuth callback handler
│   │   └── session_confirmation.py # EventBridge session confirmation
│   │
│   ├── services/                  # Business logic services
│   │   ├── message_router.py      # Phone number routing logic
│   │   ├── strands_agent_service.py # Strands Agents SDK integration
│   │   ├── conversation_handlers.py # Onboarding, Trainer, Student handlers
│   │   ├── conversation_state.py  # Conversation state management
│   │   ├── menu_system.py         # Menu-based interaction system
│   │   ├── menu_context.py        # Menu state management
│   │   ├── menu_definitions.py    # Menu structure definitions
│   │   ├── menu_generator.py      # Menu text generation
│   │   ├── menu_processor.py      # Menu input processing
│   │   ├── calendar_sync.py       # Calendar API integration
│   │   ├── receipt_storage.py     # S3 media handling
│   │   ├── session_conflict.py    # Session conflict detection
│   │   ├── twilio_client.py       # Twilio API wrapper
│   │   ├── feature_flags.py       # Feature flag management
│   │   └── mock_bedrock.py        # Mock Bedrock for testing
│   │
│   ├── tools/                     # AI agent tool functions
│   │   ├── student_tools.py       # register_student, view_students, update_student
│   │   ├── session_tools.py       # schedule_session, reschedule_session, cancel_session, view_calendar
│   │   ├── payment_tools.py       # register_payment, view_payments
│   │   ├── calendar_tools.py      # connect_calendar, view_calendar
│   │   └── notification_tools.py  # send_notification
│   │
│   ├── models/                    # Data models and database
│   │   ├── entities.py            # Pydantic models for entities
│   │   └── dynamodb_client.py     # DynamoDB abstraction layer
│   │
│   ├── utils/                     # Utility functions
│   │   ├── validation.py          # Input validation utilities
│   │   ├── encryption.py          # KMS encryption helpers
│   │   ├── logging.py             # Structured logging setup
│   │   ├── retry.py               # Retry logic utilities
│   │   └── i18n.py                # Internationalization support
│   │
│   ├── config.py                  # Environment configuration
│   ├── main.py                    # Local development entry point
│   └── local_sqs_poller.py        # Local SQS polling for development
│
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests
│   │   ├── test_student_tools.py
│   │   ├── test_session_tools.py
│   │   ├── test_validation.py
│   │   └── ...
│   │
│   ├── integration/               # Integration tests
│   │   ├── test_webhook_flow.py
│   │   ├── test_calendar_sync.py
│   │   └── ...
│   │
│   ├── property/                  # Property-based tests
│   │   ├── test_session_properties.py
│   │   ├── test_payment_properties.py
│   │   └── ...
│   │
│   ├── smoke/                     # Smoke tests for quick validation
│   │   └── ...
│   │
│   └── conftest.py                # Shared pytest fixtures
│
├── examples/                      # Usage examples
│   ├── conversation_state_usage.py
│   ├── dynamodb_client_usage.py
│   ├── encryption_usage.py
│   ├── logging_usage.py
│   ├── retry_usage.py
│   └── session_conflict_usage.py
│
├── infrastructure/                # Infrastructure as Code
│   ├── template.yml               # CloudFormation template
│   └── parameters/                # Environment-specific parameters
│       ├── dev.json
│       ├── staging.json
│       └── production.json
│
├── localstack-init/               # LocalStack initialization
│   └── 01-setup.sh                # DynamoDB, S3, SQS setup script
│
├── .github/                       # GitHub Actions workflows
│   └── workflows/
│       ├── test.yml               # CI testing pipeline
│       └── deploy.yml             # CD deployment pipeline
│
├── docker-compose.yml             # Local development environment
├── Dockerfile                     # Container definition
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Development dependencies
├── .env.example                   # Environment variable template
├── pytest.ini                     # Pytest configuration
├── .flake8                        # Flake8 configuration
├── pyproject.toml                 # Black and mypy configuration
└── README.md                      # Project documentation
```

## Key Architectural Patterns

### Single-Table DynamoDB Design

All entities stored in one table (`fitagent-main`) with composite keys:
- **PK (Partition Key)**: Entity type + ID (e.g., `TRAINER#uuid`, `STUDENT#uuid`)
- **SK (Sort Key)**: Related entity or metadata (e.g., `METADATA`, `SESSION#uuid`, `STUDENT#uuid`)

### Global Secondary Indexes (GSIs)

1. **phone-number-index**: User identification and routing
   - PK: `phone_number`, SK: `entity_type`

2. **session-date-index**: Calendar queries and reminders
   - PK: `trainer_id`, SK: `session_datetime`

3. **payment-status-index**: Payment tracking
   - PK: `trainer_id`, SK: `payment_status#created_at`

### Lambda Handler Pattern

Each handler follows this structure:
```python
def lambda_handler(event, context):
    """Entry point with error handling."""
    try:
        # Process event
        result = process(event)
        return {'statusCode': 200, 'body': json.dumps(result)}
    except ValidationError as e:
        # User-facing errors
        return {'statusCode': 400, 'body': json.dumps({'error': str(e)})}
    except Exception as e:
        # System errors - let SQS retry
        logger.error("Unexpected error", error=str(e))
        raise
```

### Tool Function Pattern

AI agent tools follow this structure:
```python
def tool_function(trainer_id: str, **params) -> dict:
    """
    Tool description for AI agent.
    
    Args:
        trainer_id: Trainer identifier
        **params: Tool-specific parameters
    
    Returns:
        dict: {'success': bool, 'data': any, 'error': str (optional)}
    """
    # Validate inputs
    # Execute business logic
    # Return structured result
```

## Naming Conventions

### Files and Modules
- Snake case: `message_router.py`, `session_tools.py`
- Test files: `test_<module_name>.py`

### Functions and Variables
- Snake case: `schedule_session()`, `trainer_id`
- Private functions: `_internal_helper()`

### Classes
- Pascal case: `ConversationStateManager`, `PhoneNumberValidator`

### Constants
- Upper snake case: `MAX_RETRY_ATTEMPTS`, `DEFAULT_REMINDER_HOURS`

### DynamoDB Keys
- Entity prefixes: `TRAINER#`, `STUDENT#`, `SESSION#`, `PAYMENT#`
- Composite keys: `payment_status#created_at`

## Code Organization Principles

1. **Separation of Concerns**: Handlers orchestrate, services contain logic, tools are AI-callable
2. **Dependency Injection**: Pass clients/configs to functions rather than global state
3. **Error Boundaries**: Handle errors at handler level, propagate specific exceptions
4. **Testability**: All business logic in pure functions with mocked dependencies
5. **Type Hints**: Use Python type hints throughout for mypy validation
6. **Structured Logging**: JSON logs with context (request_id, phone_number, etc.)

## Import Conventions

```python
# Standard library
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List

# Third-party
import boto3
from pydantic import BaseModel

# Local
from src.models.entities import Trainer, Student
from src.utils.validation import PhoneNumberValidator
from src.config import settings
```

## Configuration Management

Environment-specific configuration in `src/config.py` using Pydantic:
```python
class Settings(BaseSettings):
    environment: str = "local"
    aws_region: str = "us-east-1"
    # ... other settings
    
    class Config:
        env_file = ".env"
```

Access via: `from src.config import settings`
