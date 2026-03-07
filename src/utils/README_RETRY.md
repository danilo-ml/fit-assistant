# Retry Decorator with Exponential Backoff

This module provides a decorator for retrying failed operations with exponential backoff, primarily used for external API calls to services like Twilio, Google Calendar, and Microsoft Graph.

## Overview

The `retry_with_backoff` decorator automatically retries failed function calls with increasing delays between attempts. This is essential for handling transient failures in external services.

## Features

- **Configurable retry attempts**: Set maximum number of retry attempts
- **Exponential backoff**: Delays increase exponentially (1s, 2s, 4s, etc.)
- **Selective exception handling**: Only retry specific exception types
- **Automatic logging**: Logs all retry attempts and failures
- **Type-safe**: Full type hints for better IDE support

## Usage

### Basic Usage

```python
from src.utils.retry import retry_with_backoff

@retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
def call_external_api():
    """This function will retry up to 3 times with delays of 1s, 2s, 4s."""
    return api.make_request()
```

### Calendar API Integration

```python
from src.utils.retry import retry_with_backoff, ExternalServiceError
import requests

@retry_with_backoff(
    max_attempts=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    exceptions=(requests.RequestException, ExternalServiceError)
)
def sync_calendar_event(event_data: dict):
    """Sync event to calendar with retry logic."""
    try:
        response = calendar_api.create_event(event_data)
        return response
    except requests.RequestException as e:
        raise ExternalServiceError("Google Calendar", "create_event", str(e))
```

### Twilio WhatsApp Integration

```python
from src.utils.retry import retry_with_backoff
from twilio.base.exceptions import TwilioRestException

@retry_with_backoff(
    max_attempts=2,
    initial_delay=5.0,
    exceptions=(TwilioRestException,)
)
def send_whatsapp_message(phone: str, message: str):
    """Send WhatsApp message with retry on failure."""
    return twilio_client.messages.create(
        from_=f'whatsapp:{twilio_number}',
        to=f'whatsapp:{phone}',
        body=message
    )
```

### Custom Exception Handling

```python
from src.utils.retry import retry_with_backoff, RetryableError

class CalendarAPIError(RetryableError):
    """Custom exception for calendar API failures."""
    pass

@retry_with_backoff(
    max_attempts=5,
    initial_delay=0.5,
    backoff_factor=2.0,
    exceptions=(CalendarAPIError,)
)
def update_calendar_event(event_id: str, updates: dict):
    """Update calendar event with custom error handling."""
    if not calendar_api.is_available():
        raise CalendarAPIError("Calendar API temporarily unavailable")
    return calendar_api.update_event(event_id, updates)
```

## Parameters

### `retry_with_backoff` Decorator

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_attempts` | `int` | `3` | Maximum number of attempts (including initial call) |
| `initial_delay` | `float` | `1.0` | Initial delay in seconds before first retry |
| `backoff_factor` | `float` | `2.0` | Multiplier for delay after each attempt |
| `exceptions` | `Tuple[Type[Exception], ...]` | `(Exception,)` | Tuple of exception types to catch and retry |

## Delay Calculation

The delay between retries follows an exponential pattern:

- **Attempt 1**: No delay (initial call)
- **Attempt 2**: `initial_delay` seconds (e.g., 1s)
- **Attempt 3**: `initial_delay * backoff_factor` seconds (e.g., 2s)
- **Attempt 4**: `initial_delay * backoff_factor^2` seconds (e.g., 4s)
- And so on...

### Example with default parameters (max_attempts=3, initial_delay=1.0, backoff_factor=2.0):

```
Attempt 1: Call function
  ↓ (fails)
Wait 1.0 seconds
  ↓
Attempt 2: Call function
  ↓ (fails)
Wait 2.0 seconds
  ↓
Attempt 3: Call function
  ↓ (fails)
Raise exception
```

## Exception Classes

### `RetryableError`

Base exception class for errors that should trigger retry logic. Use this as a base class for custom exceptions representing transient failures.

```python
class RetryableError(Exception):
    """Base exception for retryable errors."""
    pass
```

### `ExternalServiceError`

Exception for external service failures (Twilio, Calendar APIs, etc.). Includes service name and operation context.

```python
class ExternalServiceError(RetryableError):
    def __init__(self, service: str, operation: str, message: str = ""):
        self.service = service
        self.operation = operation
        super().__init__(f"{service} {operation} failed: {message}")
```

**Usage:**

```python
raise ExternalServiceError("Twilio", "send_message", "Rate limit exceeded")
# Output: "Twilio send_message failed: Rate limit exceeded"
```

## Logging

The decorator automatically logs retry attempts and failures:

- **INFO**: Successful retry after previous failures
- **WARNING**: Each failed attempt with exception details
- **INFO**: Retry delay information
- **ERROR**: Final failure after all attempts exhausted

Example log output:

```
WARNING - Function sync_calendar_event failed on attempt 1/3: Connection timeout
INFO - Retrying sync_calendar_event in 1.00 seconds...
WARNING - Function sync_calendar_event failed on attempt 2/3: Connection timeout
INFO - Retrying sync_calendar_event in 2.00 seconds...
INFO - Function sync_calendar_event succeeded on attempt 3/3
```

## Best Practices

### 1. Choose Appropriate Exception Types

Only retry exceptions that represent transient failures:

```python
# Good: Retry network errors
@retry_with_backoff(exceptions=(requests.RequestException, TimeoutError))
def call_api():
    pass

# Bad: Don't retry validation errors
@retry_with_backoff(exceptions=(ValueError,))  # These won't succeed on retry
def validate_input():
    pass
```

### 2. Set Reasonable Retry Limits

Consider the operation's urgency and typical recovery time:

```python
# Quick operations: fewer retries, shorter delays
@retry_with_backoff(max_attempts=2, initial_delay=0.5)
def quick_api_call():
    pass

# Critical operations: more retries, longer delays
@retry_with_backoff(max_attempts=5, initial_delay=2.0)
def critical_sync_operation():
    pass
```

### 3. Use Custom Exceptions for Clarity

Create specific exception types for different failure scenarios:

```python
class CalendarSyncError(RetryableError):
    pass

class TwilioRateLimitError(RetryableError):
    pass

@retry_with_backoff(exceptions=(CalendarSyncError,))
def sync_calendar():
    pass

@retry_with_backoff(exceptions=(TwilioRateLimitError,))
def send_message():
    pass
```

### 4. Combine with Graceful Degradation

Don't let retry failures block critical operations:

```python
@retry_with_backoff(max_attempts=3)
def sync_to_calendar(session_data):
    """Sync session to calendar."""
    return calendar_api.create_event(session_data)

def schedule_session(session_data):
    """Schedule session with optional calendar sync."""
    # Save session to database (critical)
    session_id = db.save_session(session_data)
    
    # Try to sync to calendar (non-critical)
    try:
        sync_to_calendar(session_data)
    except Exception as e:
        logger.error(f"Calendar sync failed: {e}")
        # Continue without blocking session creation
    
    return session_id
```

## Requirements Validation

This implementation satisfies:

- **Requirement 4.6**: Calendar API calls retry up to 3 times with exponential backoff
- **Requirement 10.6**: Notification delivery retries with configurable delays
- **Requirement 13.5**: Message processing retries with exponential backoff

## Testing

See `tests/unit/test_retry.py` for comprehensive unit tests including:

- Successful retry after failures
- Exponential backoff timing
- Exception filtering
- Maximum attempts enforcement
- Logging verification
