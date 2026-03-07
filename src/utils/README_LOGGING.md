# Structured Logging Module

## Overview

The structured logging module provides JSON-formatted logging with automatic phone number masking and support for contextual fields. It's designed for CloudWatch Insights queries and privacy compliance.

**Requirements**: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6

## Features

- **JSON Formatting**: All logs are output as valid JSON for easy parsing and querying
- **Phone Number Masking**: Automatic masking of phone numbers (shows last 4 digits only)
- **Request ID Support**: Built-in support for request tracing
- **Custom Fields**: Add any custom fields to log entries
- **Standard Log Levels**: INFO, WARNING, ERROR
- **CloudWatch Compatible**: Optimized for AWS CloudWatch Insights queries

## Quick Start

```python
from src.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)

# Basic logging
logger.info("Application started")

# Logging with context
logger.info(
    "Tool executed",
    request_id="req-123",
    phone_number="+1234567890",  # Automatically masked to ***7890
    tool_name="schedule_session"
)
```

## Usage Examples

### Basic Logging

```python
logger = get_logger(__name__)

logger.info("User registered successfully")
logger.warning("Rate limit approaching")
logger.error("Failed to connect to database")
```

### Logging with Request ID

```python
request_id = "req-abc-123"

logger.info(
    "Processing webhook",
    request_id=request_id
)
```

### Logging with Phone Number (Automatically Masked)

```python
# Phone number will be masked to ***7890
logger.info(
    "User identified",
    request_id="req-xyz-789",
    phone_number="+1234567890",
    user_type="trainer"
)
```

### Tool Execution Logging (Requirement 19.3)

```python
logger.info(
    "Tool executed",
    request_id="req-tool-456",
    phone_number="+1234567890",
    tool_name="schedule_session",
    parameters={
        "student_name": "John Doe",
        "date": "2024-01-20",
        "time": "14:00"
    },
    execution_time_ms=150
)
```

### External API Call Logging (Requirement 19.4)

```python
logger.info(
    "External API call",
    request_id="req-api-123",
    api_name="twilio",
    endpoint="/Messages",
    method="POST",
    response_status=200,
    response_time_ms=250
)
```

### Error Logging (Requirements 19.1, 19.2)

```python
try:
    # Some operation
    raise ValueError("Invalid input")
except ValueError as e:
    logger.error(
        "Validation error occurred",
        request_id="req-err-789",
        phone_number="+1234567890",
        error_type=type(e).__name__,
        error_message=str(e),
        tool_name="schedule_session"
    )
```

### Lambda Handler Pattern

```python
from src.utils.logging import get_logger

logger = get_logger(__name__)

def lambda_handler(event, context):
    request_id = context.request_id
    
    logger.info(
        "Lambda invoked",
        request_id=request_id,
        function_name=context.function_name
    )
    
    try:
        # Process event
        result = process(event)
        
        logger.info(
            "Lambda completed successfully",
            request_id=request_id,
            result=result
        )
        
        return {"statusCode": 200, "body": result}
        
    except Exception as e:
        logger.error(
            "Lambda error",
            request_id=request_id,
            error_type=type(e).__name__,
            error_message=str(e)
        )
        raise
```

## Log Output Format

All logs are output as JSON with the following structure:

```json
{
  "timestamp": "2024-01-15T10:30:00.123456Z",
  "level": "INFO",
  "message": "Tool executed",
  "service": "fitagent",
  "request_id": "req-abc-123",
  "phone_number": "***7890",
  "tool_name": "schedule_session",
  "parameters": {
    "student_name": "John Doe",
    "date": "2024-01-20"
  }
}
```

### Standard Fields

- `timestamp`: ISO 8601 format with UTC timezone
- `level`: Log level (INFO, WARNING, ERROR)
- `message`: Log message
- `service`: Always "fitagent"

### Optional Fields

- `request_id`: Request identifier for tracing
- `phone_number`: Masked phone number (last 4 digits only)
- Any custom fields you add

## Privacy Compliance (Requirement 19.6)

### Phone Number Masking

Phone numbers are automatically masked to show only the last 4 digits:

```python
logger.info("User action", phone_number="+1234567890")
# Output: "phone_number": "***7890"
```

### Sensitive Data Guidelines

**NEVER log sensitive information:**

❌ **Don't log:**
- OAuth tokens or refresh tokens
- API keys or secrets
- Full credit card numbers
- Passwords or credentials
- Full phone numbers (use the masking feature)

✅ **Do log:**
- Masked phone numbers (automatic)
- Request IDs
- Operation status
- Error types and messages (without sensitive details)
- API endpoint names (without tokens in URLs)

```python
# BAD - Don't do this
logger.info("Token refreshed", oauth_token=token)

# GOOD - Do this instead
logger.info(
    "OAuth token refreshed",
    request_id="req-oauth-123",
    provider="google",
    status="success"
)
```

## CloudWatch Insights Queries

The JSON format enables powerful CloudWatch Insights queries:

### Find all errors for a specific phone number

```
fields @timestamp, message, error_type, error_message
| filter phone_number = "***7890" and level = "ERROR"
| sort @timestamp desc
```

### Track tool execution times

```
fields @timestamp, tool_name, execution_time_ms
| filter tool_name = "schedule_session"
| stats avg(execution_time_ms), max(execution_time_ms), count() by tool_name
```

### Find all API calls with errors

```
fields @timestamp, api_name, endpoint, response_status
| filter api_name like /.*/ and response_status >= 400
| sort @timestamp desc
```

### Trace a specific request

```
fields @timestamp, message, level
| filter request_id = "req-abc-123"
| sort @timestamp asc
```

## Testing

The module includes comprehensive unit tests:

```bash
# Run logging tests
pytest tests/unit/test_logging.py -v

# Run with coverage
pytest tests/unit/test_logging.py --cov=src.utils.logging --cov-report=term
```

## Best Practices

1. **Always use request_id**: Include request_id in all logs for a request to enable tracing
2. **Use appropriate log levels**: INFO for normal operations, WARNING for concerning but non-critical issues, ERROR for failures
3. **Add context**: Include relevant fields like tool_name, api_name, phone_number (masked)
4. **Don't log sensitive data**: Never log OAuth tokens, API keys, or full credentials
5. **Use structured fields**: Add custom fields as keyword arguments rather than embedding in message strings
6. **Keep messages concise**: Use the message for a brief description, put details in custom fields

### Good Example

```python
logger.info(
    "Session scheduled",
    request_id=request_id,
    phone_number=phone_number,
    session_id=session_id,
    student_name=student_name,
    session_date=session_date
)
```

### Bad Example

```python
# Don't do this - hard to query, no structure
logger.info(f"Session {session_id} scheduled for {student_name} on {session_date} by {phone_number}")
```

## Integration with Other Modules

### With Validation Module

```python
from src.utils.logging import get_logger
from src.utils.validation import PhoneNumberValidator

logger = get_logger(__name__)
validator = PhoneNumberValidator()

try:
    validated_phone = validator.validate(phone_number)
    logger.info(
        "Phone number validated",
        request_id=request_id,
        phone_number=validated_phone
    )
except ValidationError as e:
    logger.error(
        "Phone validation failed",
        request_id=request_id,
        phone_number=phone_number,
        error_message=str(e)
    )
```

### With DynamoDB Client

```python
from src.utils.logging import get_logger
from src.models.dynamodb_client import DynamoDBClient

logger = get_logger(__name__)
db_client = DynamoDBClient()

logger.info(
    "Querying DynamoDB",
    request_id=request_id,
    table_name="fitagent-main",
    operation="get_item"
)

try:
    result = db_client.get_item(pk=pk, sk=sk)
    logger.info(
        "DynamoDB query successful",
        request_id=request_id,
        item_found=result is not None
    )
except Exception as e:
    logger.error(
        "DynamoDB query failed",
        request_id=request_id,
        error_type=type(e).__name__,
        error_message=str(e)
    )
```

## API Reference

### `StructuredLogger`

Main logger class that outputs JSON-formatted logs.

#### Methods

##### `__init__(name: str)`

Initialize the logger.

**Parameters:**
- `name`: Logger name (typically `__name__`)

##### `info(message: str, **kwargs)`

Log INFO level message.

**Parameters:**
- `message`: Log message
- `**kwargs`: Optional fields (request_id, phone_number, custom fields)

##### `warning(message: str, **kwargs)`

Log WARNING level message.

**Parameters:**
- `message`: Log message
- `**kwargs`: Optional fields (request_id, phone_number, custom fields)

##### `error(message: str, **kwargs)`

Log ERROR level message.

**Parameters:**
- `message`: Log message
- `**kwargs`: Optional fields (request_id, phone_number, custom fields)

### `get_logger(name: str) -> StructuredLogger`

Factory function to create a StructuredLogger instance.

**Parameters:**
- `name`: Logger name (typically `__name__`)

**Returns:**
- `StructuredLogger` instance

## Examples

See `examples/logging_usage.py` for comprehensive usage examples.

## Requirements Mapping

- **19.1**: Error logging with ERROR level
- **19.2**: Include request_id, phone_number (masked), and stack trace in error logs
- **19.3**: Log all AI agent tool executions with INFO level including tool name and parameters
- **19.4**: Log all external API calls with INFO level including response status
- **19.5**: Use structured JSON logging for CloudWatch Insights queries
- **19.6**: Do not log sensitive information (phone numbers masked, no OAuth tokens)
