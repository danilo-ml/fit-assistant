# Data Models and Database Layer

This directory contains the data models and database abstraction layer for FitAgent.

## Files

### `entities.py`
Pydantic models for all FitAgent entities with DynamoDB serialization/deserialization:
- `Trainer` - Personal trainer entity
- `Student` - Student/client entity  
- `TrainerStudentLink` - Many-to-many relationship between trainers and students
- `Session` - Training session entity
- `Payment` - Payment record entity
- `ConversationState` - WhatsApp conversation state with TTL
- `TrainerConfig` - Trainer configuration (reminders, timezone, etc.)
- `CalendarConfig` - Calendar integration configuration (OAuth tokens)
- `Notification` - Broadcast notification entity
- `Reminder` - Reminder delivery record

All models include:
- Field validation (phone numbers, dates, amounts, etc.)
- `to_dynamodb()` method for serialization
- `from_dynamodb()` class method for deserialization

### `dynamodb_client.py`
High-level DynamoDB client abstraction supporting all access patterns.

## DynamoDB Client Features

### Core Operations
- `get_item(pk, sk)` - Get single item by primary key
- `put_item(item)` - Create or update item
- `delete_item(pk, sk)` - Delete item
- `query(...)` - Query with key conditions and filters
- `batch_get_items(keys)` - Batch retrieve multiple items
- `batch_write_items(items)` - Batch write multiple items

### Trainer Operations
- `get_trainer(trainer_id)` - Get trainer by ID
- `put_trainer(trainer)` - Create/update trainer
- `get_trainer_config(trainer_id)` - Get trainer configuration
- `put_trainer_config(config)` - Create/update configuration
- `get_calendar_config(trainer_id)` - Get calendar configuration
- `put_calendar_config(config)` - Create/update calendar config

### Student Operations
- `get_student(student_id)` - Get student by ID
- `put_student(student)` - Create/update student

### Trainer-Student Links
- `get_trainer_student_link(trainer_id, student_id)` - Get link
- `put_trainer_student_link(link)` - Create/update link
- `get_trainer_students(trainer_id)` - Get all students for trainer
- `get_student_trainers(student_id)` - Get all trainers for student

### Session Operations
- `get_session(trainer_id, session_id)` - Get session by ID
- `put_session(session)` - Create/update session
- `get_trainer_sessions(trainer_id)` - Get all sessions for trainer
- `get_sessions_by_date_range(trainer_id, start, end, status_filter)` - Query sessions by date using GSI
- `get_upcoming_sessions(trainer_id, days_ahead, status_filter)` - Get upcoming sessions
- `get_student_sessions(student_id, start, end)` - Get sessions for student

### Payment Operations
- `get_payment(trainer_id, payment_id)` - Get payment by ID
- `put_payment(payment)` - Create/update payment
- `get_trainer_payments(trainer_id)` - Get all payments for trainer
- `get_payments_by_status(trainer_id, status, start_date, end_date)` - Query payments by status using GSI
- `get_student_payments(trainer_id, student_id, status)` - Get payments for specific student

### Conversation State Operations
- `get_conversation_state(phone_number)` - Get conversation state
- `put_conversation_state(state)` - Create/update state
- `delete_conversation_state(phone_number)` - Delete state

### Phone Number Lookup (GSI)
- `lookup_by_phone_number(phone_number)` - Identify user by phone using phone-number-index GSI

### Notification Operations
- `get_notification(trainer_id, notification_id)` - Get notification
- `put_notification(notification)` - Create/update notification
- `get_trainer_notifications(trainer_id, limit)` - Get notifications for trainer

### Reminder Operations
- `get_reminder(session_id, reminder_id)` - Get reminder
- `put_reminder(reminder)` - Create/update reminder
- `get_session_reminders(session_id)` - Get all reminders for session

## Global Secondary Indexes (GSIs)

### phone-number-index
- **Purpose**: User identification and routing
- **Keys**: `phone_number` (PK), `entity_type` (SK)
- **Usage**: `lookup_by_phone_number()`

### session-date-index
- **Purpose**: Calendar queries and reminder scheduling
- **Keys**: `trainer_id` (PK), `session_datetime` (SK)
- **Usage**: `get_sessions_by_date_range()`, `get_upcoming_sessions()`

### payment-status-index
- **Purpose**: Payment tracking and filtering
- **Keys**: `trainer_id` (PK), `payment_status` (SK)
- **Usage**: `get_payments_by_status()`

## Data Serialization

The client automatically handles:
- **Float ↔ Decimal conversion**: Python floats are converted to DynamoDB Decimal and back
- **Nested objects**: Recursive serialization/deserialization
- **Lists**: Element-wise conversion for nested structures

## Usage Examples

See `examples/dynamodb_client_usage.py` for comprehensive usage examples including:
- Complete trainer workflow (create trainer, register students, schedule sessions)
- Phone number lookup for user identification
- Session conflict detection
- Student session viewing
- Batch operations

## Testing

Comprehensive unit tests in `tests/unit/test_dynamodb_client.py`:
- 25 test cases covering all operations
- Uses moto for DynamoDB mocking
- Tests all GSI queries
- Validates serialization/deserialization
- Tests batch operations

Run tests:
```bash
pytest tests/unit/test_dynamodb_client.py -v
```

## Requirements Coverage

This implementation satisfies requirements:
- **14.1**: Single-table design with composite primary key (PK, SK)
- **14.2**: GSI for phone number lookups (phone-number-index)
- **14.3**: GSI for session date queries (session-date-index)
- **14.4**: Single-item reads within 50ms at p99 (DynamoDB native performance)
- **14.5**: Query operations returning up to 100 items within 200ms at p99
