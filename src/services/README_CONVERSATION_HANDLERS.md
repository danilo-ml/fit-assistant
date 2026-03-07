# Conversation Handlers

This module implements conversation handlers for different user types in the FitAgent WhatsApp assistant.

## Overview

The conversation handlers process messages based on user type and conversation state:

- **OnboardingHandler**: Manages trainer registration flow for new users
- **TrainerHandler**: Handles trainer interactions with AI agent integration
- **StudentHandler**: Manages student session viewing and confirmation

## Architecture

```
Message Processor
    ↓
Message Router (identifies user type)
    ↓
┌─────────────────┬──────────────────┬─────────────────┐
│ OnboardingHandler│  TrainerHandler  │ StudentHandler  │
│  (New Users)    │  (AI Agent)      │  (Sessions)     │
└─────────────────┴──────────────────┴─────────────────┘
```

## OnboardingHandler

Manages the trainer registration flow for unregistered phone numbers.

### Flow

1. **Welcome Message**: Ask if user is trainer or student
2. **User Type Selection**: Route based on selection
3. **Trainer Registration**: Collect name, email, business name
4. **Account Creation**: Create trainer record in DynamoDB
5. **Transition**: Move to trainer menu

### Example Conversation

```
User: Hello
Bot: Welcome to FitAgent! 👋
     Are you a:
     1️⃣ Personal Trainer
     2️⃣ Student

User: 1
Bot: Great! Let's get you set up as a trainer. 💪
     What's your full name?

User: John Doe
Bot: Nice to meet you, John Doe! 👋
     What's your email address?

User: john@example.com
Bot: Perfect! What's your business name?

User: Fitness Pro
Bot: 🎉 Welcome to FitAgent, John Doe!
     Your account is now active...
```

### State Management

The handler uses conversation state to track progress through registration:

- `step: user_type` - Waiting for trainer/student selection
- `step: trainer_name` - Collecting trainer name
- `step: trainer_email` - Collecting email
- `step: trainer_business` - Collecting business name (final step)

### Validation

- **Phone Number**: E.164 format validation
- **Email**: Basic format check (contains @ and .)
- **Name/Business**: Minimum 2 characters

## TrainerHandler

Handles trainer messages using AI agent for natural language understanding and tool execution.

### Features

- **Natural Language Processing**: Uses AWS Bedrock (Claude) for understanding
- **Tool Execution**: Executes trainer tools (register student, schedule session, etc.)
- **Conversation Context**: Maintains history for multi-turn interactions
- **Error Handling**: Graceful degradation with user-friendly messages

### Example Conversation

```
User: Schedule a session with Sarah tomorrow at 2pm for 60 minutes
Bot: I've scheduled a 60-minute session with Sarah for tomorrow at 2:00 PM.
     Would you like me to send her a confirmation?

User: Yes please
Bot: I've sent a confirmation message to Sarah. She'll receive a reminder
     24 hours before the session.
```

### AI Agent Integration

The handler:
1. Retrieves conversation history from state manager
2. Passes message and context to AIAgent
3. AIAgent determines which tools to call
4. Tools execute and return results
5. AIAgent generates natural language response
6. Handler updates conversation state

### Conversation History

- Maintains last 5 messages for context
- Stored in DynamoDB with 24-hour TTL
- Converted to Bedrock format for AI processing

## StudentHandler

Handles student messages for session viewing and attendance management.

### Features

- **View Sessions**: Show upcoming sessions (next 30 days)
- **Confirm Attendance**: Mark attendance as confirmed
- **Cancel Sessions**: Cancel with trainer notification
- **Simple Interface**: Keyword-based routing for simplicity

### Example Conversation

```
User: Show my sessions
Bot: Hi Sarah! 👋
     Your upcoming sessions:
     
     1. Monday, January 22 at 02:00 PM
        Trainer: John Doe
        Duration: 60 minutes
        Location: Gym A
        ⏳ Pending confirmation
     
     2. Wednesday, January 24 at 03:00 PM
        Trainer: Jane Smith
        Duration: 45 minutes
        ✅ Confirmed

User: confirm
Bot: To confirm a session, please view your upcoming sessions first,
     then I can help you confirm a specific one.
```

### Session Display

Sessions are displayed with:
- Date and time (formatted for readability)
- Trainer name
- Duration
- Location (if provided)
- Confirmation status (✅ Confirmed / ⏳ Pending)

### Keyword Detection

The handler uses simple keyword matching:
- `session`, `schedule`, `upcoming`, `next` → View sessions
- `confirm`, `yes`, `attending` → Confirm attendance
- `cancel`, `can't make`, `cannot` → Cancel session

## Usage

### Initialization

```python
from src.services.conversation_handlers import (
    OnboardingHandler,
    TrainerHandler,
    StudentHandler,
)

# Initialize handlers
onboarding_handler = OnboardingHandler()
trainer_handler = TrainerHandler()
student_handler = StudentHandler()
```

### Processing Messages

```python
# Onboarding
response = onboarding_handler.handle_message(
    phone_number="+14155551234",
    message_body={"body": "Hello"},
    request_id="req-123"
)

# Trainer
response = trainer_handler.handle_message(
    trainer_id="trainer-123",
    user_data={"name": "John", "phone_number": "+14155551234"},
    message_body={"body": "Schedule a session with Sarah"},
    request_id="req-123"
)

# Student
response = student_handler.handle_message(
    student_id="student-123",
    user_data={"name": "Sarah", "phone_number": "+14155551234"},
    message_body={"body": "Show my sessions"},
    request_id="req-123"
)
```

## Dependencies

- **AIAgent**: Natural language processing and tool execution
- **ConversationStateManager**: Conversation state persistence
- **DynamoDBClient**: Data operations
- **PhoneNumberValidator**: Phone number validation

## Error Handling

All handlers implement graceful error handling:

1. **Validation Errors**: User-friendly messages with suggestions
2. **AI Agent Errors**: Fallback to simple error message
3. **Database Errors**: Retry-friendly error responses
4. **Unexpected Errors**: Generic error message with logging

## Testing

Comprehensive test coverage includes:

- **Unit Tests**: `tests/unit/test_conversation_handlers.py`
  - Onboarding flow steps
  - Trainer AI agent integration
  - Student session viewing
  
- **Integration Tests**: `tests/integration/test_message_processor_integration.py`
  - Complete message flow
  - Handler routing
  - Error handling

Run tests:
```bash
pytest tests/unit/test_conversation_handlers.py -v
pytest tests/integration/test_message_processor_integration.py -v
```

## Future Enhancements

### OnboardingHandler
- Support for student self-registration (with trainer approval)
- Multi-language support
- Business verification

### TrainerHandler
- Voice message support
- Image recognition for receipts
- Advanced scheduling (recurring sessions)

### StudentHandler
- Session feedback/ratings
- Payment history viewing
- Direct messaging with trainer

## Requirements Validation

This implementation validates the following requirements:

- **Requirement 1.1-1.5**: Trainer registration and onboarding
- **Requirement 6.3-6.5**: Message routing to appropriate handlers
- **Requirement 7.1-7.5**: Student session viewing and confirmation
- **Requirement 11.1-11.6**: Conversation state management
- **Requirement 12.1-12.6**: AI agent tool execution

## Related Documentation

- [Message Router](./README_MESSAGE_ROUTER.md)
- [AI Agent](./README_AI_AGENT.md)
- [Message Processor](../handlers/README_MESSAGE_PROCESSOR.md)
