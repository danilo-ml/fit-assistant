# MessageRouter Service

## Overview

The `MessageRouter` class is responsible for identifying users by their phone number and routing WhatsApp messages to the appropriate handler (Onboarding, Trainer, or Student).

## Architecture

The router uses DynamoDB's `phone-number-index` Global Secondary Index (GSI) to perform fast phone number lookups and determine user type.

### Routing Logic

```
Phone Number → GSI Lookup → User Type → Handler
```

1. **Unknown User** → `OnboardingHandler` (for registration)
2. **Trainer** → `TrainerHandler` (for business management)
3. **Student** → `StudentHandler` (for session viewing)

## Performance

- **Target**: Complete routing within 200ms
- **GSI Query**: Single query with limit=1 for optimal performance
- **Caching**: Not implemented (DynamoDB provides sub-50ms p99 latency)

## Usage

### Basic Usage

```python
from src.services.message_router import MessageRouter

# Initialize router
router = MessageRouter()

# Route a message
result = router.route_message(
    phone_number="+1234567890",
    message=webhook_payload
)

# Check handler type
if result['handler_type'] == HandlerType.TRAINER:
    # Process with trainer handler
    trainer_id = result['user_id']
    process_trainer_message(trainer_id, message)
```

### Extract Phone Number from Webhook

```python
# Extract phone number from Twilio webhook payload
phone_number = router.extract_phone_number(webhook_payload)
# Returns: "+1234567890" (without 'whatsapp:' prefix)
```

## Return Format

The `route_message()` method returns a dictionary with:

```python
{
    'handler_type': HandlerType,  # ONBOARDING, TRAINER, or STUDENT
    'user_id': str | None,        # trainer_id or student_id if found
    'entity_type': str | None,    # 'TRAINER' or 'STUDENT' if found
    'user_data': dict | None      # Full user record from DynamoDB
}
```

## Handler Types

```python
class HandlerType(str, Enum):
    ONBOARDING = "onboarding"  # New/unknown users
    TRAINER = "trainer"        # Registered trainers
    STUDENT = "student"        # Registered students
```

## Integration with Message Processor

The MessageRouter is typically used in the message processor Lambda:

```python
def lambda_handler(event, context):
    """Process messages from SQS queue."""
    router = MessageRouter()
    
    for record in event['Records']:
        message = json.loads(record['body'])
        phone_number = router.extract_phone_number(message)
        
        # Route to appropriate handler
        routing_result = router.route_message(phone_number, message)
        
        if routing_result['handler_type'] == HandlerType.TRAINER:
            handle_trainer_message(routing_result, message)
        elif routing_result['handler_type'] == HandlerType.STUDENT:
            handle_student_message(routing_result, message)
        else:
            handle_onboarding_message(routing_result, message)
```

## Error Handling

### Phone Number Extraction Errors

```python
try:
    phone_number = router.extract_phone_number(webhook_payload)
except ValueError as e:
    logger.error("Failed to extract phone number", error=str(e))
    # Return error response
```

### DynamoDB Query Errors

DynamoDB errors are propagated to the caller for retry handling at the Lambda level.

## Logging

The router logs all routing decisions with structured JSON logs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Trainer identified, routing to trainer handler",
  "phone_number": "***7890",
  "trainer_id": "abc123"
}
```

Phone numbers are automatically masked (last 4 digits shown) for privacy.

## Testing

### Unit Tests

```python
def test_route_trainer_message():
    """Test routing for registered trainer."""
    mock_db = Mock()
    mock_db.lookup_by_phone_number.return_value = {
        'entity_type': 'TRAINER',
        'trainer_id': 'trainer123'
    }
    
    router = MessageRouter(dynamodb_client=mock_db)
    result = router.route_message("+1234567890", {})
    
    assert result['handler_type'] == HandlerType.TRAINER
    assert result['user_id'] == 'trainer123'
```

### Property-Based Tests

See `tests/property/test_message_routing.py` for property-based tests validating:
- Phone number extraction correctness
- User identification accuracy
- Routing consistency

## Requirements Validation

This implementation satisfies:

- **Requirement 6.1**: Extracts sender phone number from webhook payload
- **Requirement 6.2**: Queries DynamoDB GSI for user identification
- **Requirement 6.3**: Routes trainers to trainer handler
- **Requirement 6.4**: Routes students to student handler
- **Requirement 6.5**: Routes unknown users to onboarding handler
- **Requirement 6.6**: Completes routing within 200ms target

## Future Enhancements

1. **Caching**: Add Redis/ElastiCache for frequently accessed phone numbers
2. **Metrics**: CloudWatch metrics for routing latency and handler distribution
3. **Rate Limiting**: Per-phone-number rate limiting to prevent abuse
4. **Multi-Region**: Support for phone number lookup across regions
