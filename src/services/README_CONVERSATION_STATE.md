# ConversationStateManager

Manages conversation state for WhatsApp users in the FitAgent platform.

## Overview

The `ConversationStateManager` provides a high-level interface for managing conversation state in DynamoDB with automatic TTL-based expiration and message history management. It supports the conversation flow for both trainers and students through WhatsApp.

## Features

- **State Management**: Track conversation state per phone number (UNKNOWN, ONBOARDING, TRAINER_MENU, STUDENT_MENU)
- **Message History**: Maintain last 10 messages with automatic pruning
- **TTL Management**: Automatic state expiration after 24 hours (configurable)
- **User Identification**: Track user_id and user_type when identified
- **Context Storage**: Store arbitrary context data for multi-step actions
- **State Transitions**: Support for conversation flow transitions

## Requirements Validation

This implementation validates the following requirements:

- **Requirement 11.1**: Maintain conversation state per phone number in DynamoDB with TTL of 24 hours
- **Requirement 11.2**: Initialize conversation state to UNKNOWN when user starts conversation
- **Requirement 11.3**: Transition conversation state to TRAINER_MENU when trainer identified
- **Requirement 11.4**: Transition conversation state to STUDENT_MENU when student identified
- **Requirement 11.5**: Use conversation state to provide contextually appropriate responses
- **Requirement 11.6**: Expire conversation state after 24 hours without messages

## Usage

### Basic Initialization

```python
from src.services.conversation_state import ConversationStateManager

# Initialize with default settings (24-hour TTL)
manager = ConversationStateManager()

# Initialize with custom TTL
manager = ConversationStateManager(ttl_hours=48)

# Initialize with custom DynamoDB client
from src.models.dynamodb_client import DynamoDBClient
db_client = DynamoDBClient(table_name='custom-table')
manager = ConversationStateManager(dynamodb_client=db_client)
```

### State Retrieval

```python
# Get current state for a phone number
state = manager.get_state("+1234567890")

if state:
    print(f"State: {state.state}")
    print(f"User ID: {state.user_id}")
    print(f"User Type: {state.user_type}")
    print(f"Context: {state.context}")
    print(f"Messages: {len(state.message_history)}")
else:
    print("No state found")
```

### State Transitions

```python
# New user - initialize with UNKNOWN state
state = manager.transition_state(
    phone_number="+1234567890",
    new_state="UNKNOWN"
)

# Transition to ONBOARDING
state = manager.transition_state(
    phone_number="+1234567890",
    new_state="ONBOARDING"
)

# Transition to TRAINER_MENU with user identification
state = manager.transition_state(
    phone_number="+1234567890",
    new_state="TRAINER_MENU",
    user_id="trainer123",
    user_type="TRAINER"
)

# Transition to STUDENT_MENU with user identification
state = manager.transition_state(
    phone_number="+1234567890",
    new_state="STUDENT_MENU",
    user_id="student456",
    user_type="STUDENT"
)
```

### Message Management

```python
# Add a user message
state = manager.add_message(
    phone_number="+1234567890",
    role="user",
    content="I want to schedule a session"
)

# Add an assistant message
state = manager.add_message(
    phone_number="+1234567890",
    role="assistant",
    content="Sure! What's the student's name?"
)

# Get message history
history = manager.get_message_history("+1234567890")
for msg in history:
    print(f"{msg.role}: {msg.content} ({msg.timestamp})")
```

### Context Management

```python
# Update context for multi-step actions
state = manager.update_context(
    phone_number="+1234567890",
    context_updates={
        'action': 'schedule_session',
        'step': 'collect_student_name'
    }
)

# Add more context (merges with existing)
state = manager.update_context(
    phone_number="+1234567890",
    context_updates={
        'student_name': 'John Doe',
        'step': 'collect_date'
    }
)

# Access context
print(state.context)
# Output: {'action': 'schedule_session', 'step': 'collect_date', 'student_name': 'John Doe'}
```

### Complete State Update

```python
# Update state with all parameters at once
state = manager.update_state(
    phone_number="+1234567890",
    state="TRAINER_MENU",
    user_id="trainer123",
    user_type="TRAINER",
    context={'last_action': 'view_students'},
    message={'role': 'user', 'content': 'Show my students'}
)
```

### State Cleanup

```python
# Manual state cleanup (automatic cleanup via TTL after 24 hours)
success = manager.clear_state("+1234567890")
if success:
    print("State cleared")
else:
    print("State not found")
```

## State Flow Diagram

```
UNKNOWN
   |
   v
ONBOARDING
   |
   +---> TRAINER_MENU (when identified as trainer)
   |
   +---> STUDENT_MENU (when identified as student)
```

## Message History

The manager automatically maintains the last 10 messages in the conversation:

- Messages are stored with role (user/assistant), content, and timestamp
- When the 11th message is added, the oldest message is automatically removed
- Message history is preserved across state updates
- History can be retrieved using `get_message_history()`

## TTL (Time To Live)

- Default TTL: 24 hours from last update
- TTL is automatically recalculated on every state update
- DynamoDB automatically deletes expired states
- TTL can be customized during initialization

## Data Model

The conversation state is stored in DynamoDB with the following structure:

```python
{
    'PK': 'CONVERSATION#{phone_number}',
    'SK': 'STATE',
    'entity_type': 'CONVERSATION_STATE',
    'phone_number': '+1234567890',
    'state': 'TRAINER_MENU',
    'user_id': 'trainer123',
    'user_type': 'TRAINER',
    'context': {'last_action': 'view_students'},
    'message_history': [
        {
            'role': 'user',
            'content': 'Show my students',
            'timestamp': '2024-01-15T10:30:00Z'
        }
    ],
    'created_at': '2024-01-15T10:30:00Z',
    'updated_at': '2024-01-15T10:35:00Z',
    'ttl': 1705411800  # Unix timestamp
}
```

## Error Handling

The manager handles errors gracefully:

- Returns `None` when state is not found
- Returns `False` when deletion fails
- Preserves existing data when partial updates are made
- Validates phone numbers in E.164 format via Pydantic models

## Testing

Comprehensive unit tests are available in `tests/unit/test_conversation_state.py`:

```bash
# Run tests
pytest tests/unit/test_conversation_state.py -v

# Run with coverage
pytest tests/unit/test_conversation_state.py --cov=src.services.conversation_state
```

## Examples

See `examples/conversation_state_usage.py` for complete usage examples including:

- New user flow
- Trainer identification
- Message history management
- Context management for multi-step actions
- State retrieval and cleanup
- Student conversation flow

## Integration

The ConversationStateManager integrates with:

- **Message Router**: Retrieves state to determine user type and route messages
- **AI Agent**: Uses message history and context for conversation continuity
- **Onboarding Handler**: Manages state transitions during user registration
- **Trainer/Student Handlers**: Maintains context for multi-step actions

## Performance

- Single-item reads: < 50ms (p99)
- State updates: < 100ms (p99)
- Message history limited to 10 messages for optimal performance
- TTL-based cleanup prevents table bloat

## Best Practices

1. **Always check for existing state** before creating new state
2. **Use transition_state()** for simple state changes without messages
3. **Use add_message()** to add messages without changing state
4. **Use update_context()** to update context without adding messages
5. **Use update_state()** for complex updates with multiple changes
6. **Rely on TTL** for automatic cleanup rather than manual deletion
7. **Store minimal context** to keep state size small
8. **Use descriptive context keys** for clarity

## Dependencies

- `src.models.dynamodb_client`: DynamoDB abstraction layer
- `src.models.entities`: Pydantic models for type safety
- `boto3`: AWS SDK for DynamoDB operations
- `datetime`: TTL calculation and timestamp management
