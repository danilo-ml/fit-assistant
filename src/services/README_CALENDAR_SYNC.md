# Calendar Sync Service

## Overview

The `CalendarSyncService` provides bidirectional synchronization between FitAgent training sessions and external calendar providers (Google Calendar and Microsoft Outlook). This service handles OAuth token management, retry logic, and graceful degradation to ensure session operations are never blocked by calendar sync failures.

## Features

- **Multi-Provider Support**: Google Calendar API v3 and Microsoft Graph API (Outlook)
- **Automatic Token Refresh**: Handles OAuth token expiration and refresh automatically
- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s) for transient failures
- **Graceful Degradation**: Calendar sync failures don't block session operations
- **Secure Token Storage**: OAuth refresh tokens encrypted with AWS KMS

## Requirements

Validates requirements: 4.3, 4.4, 4.5, 4.6, 4.7

## Usage

### Initialization

```python
from src.services.calendar_sync import CalendarSyncService

# Initialize with default settings
calendar_service = CalendarSyncService()

# Or with custom DynamoDB client
from src.models.dynamodb_client import DynamoDBClient

dynamodb_client = DynamoDBClient(table_name="custom-table")
calendar_service = CalendarSyncService(dynamodb_client=dynamodb_client)
```

### Creating Calendar Events

When a training session is scheduled, create a corresponding calendar event:

```python
from datetime import datetime

result = calendar_service.create_event(
    trainer_id="trainer-123",
    session_id="session-456",
    student_name="John Doe",
    session_datetime=datetime(2024, 1, 20, 14, 0),
    duration_minutes=60,
    location="Gym A"  # Optional
)

if result:
    # Calendar event created successfully
    calendar_event_id = result["calendar_event_id"]
    calendar_provider = result["calendar_provider"]
    
    # Store these in the session record for future updates/deletes
    print(f"Event created: {calendar_event_id} on {calendar_provider}")
else:
    # No calendar connected or sync failed
    # Session was still created successfully
    print("Session created without calendar sync")
```

### Updating Calendar Events

When a training session is rescheduled, update the calendar event:

```python
from datetime import datetime

success = calendar_service.update_event(
    trainer_id="trainer-123",
    session_id="session-456",
    calendar_event_id="google_event_123",
    calendar_provider="google",
    student_name="John Doe",
    session_datetime=datetime(2024, 1, 21, 15, 0),  # New time
    duration_minutes=60,
    location="Gym B"  # Optional
)

if success:
    print("Calendar event updated successfully")
else:
    print("Calendar sync failed, but session was updated")
```

### Deleting Calendar Events

When a training session is cancelled, delete the calendar event:

```python
success = calendar_service.delete_event(
    trainer_id="trainer-123",
    session_id="session-456",
    calendar_event_id="google_event_123",
    calendar_provider="google"
)

if success:
    print("Calendar event deleted successfully")
else:
    print("Calendar sync failed, but session was cancelled")
```

## Integration with Session Tools

The calendar sync service should be integrated into session management tools:

```python
from src.services.calendar_sync import CalendarSyncService
from src.models.dynamodb_client import DynamoDBClient

def schedule_session(trainer_id: str, student_name: str, **kwargs):
    """Schedule a training session with calendar sync."""
    
    # Create session in DynamoDB
    session_id = create_session_in_db(trainer_id, student_name, **kwargs)
    
    # Sync to calendar (graceful degradation)
    calendar_service = CalendarSyncService()
    calendar_result = calendar_service.create_event(
        trainer_id=trainer_id,
        session_id=session_id,
        student_name=student_name,
        session_datetime=kwargs["session_datetime"],
        duration_minutes=kwargs["duration_minutes"],
        location=kwargs.get("location")
    )
    
    # Update session with calendar info if sync succeeded
    if calendar_result:
        update_session_calendar_info(
            session_id=session_id,
            calendar_event_id=calendar_result["calendar_event_id"],
            calendar_provider=calendar_result["calendar_provider"]
        )
    
    return {
        "success": True,
        "session_id": session_id,
        "calendar_synced": calendar_result is not None
    }
```

## OAuth Configuration

Before using the calendar sync service, trainers must connect their calendar through the OAuth flow:

### 1. Generate OAuth URL

```python
from src.tools.calendar_tools import connect_calendar

result = connect_calendar(
    trainer_id="trainer-123",
    provider="google"  # or "outlook"
)

if result["success"]:
    oauth_url = result["data"]["oauth_url"]
    # Send this URL to the trainer via WhatsApp
    print(f"Visit this URL to authorize: {oauth_url}")
```

### 2. OAuth Callback

After the trainer authorizes, the OAuth callback handler will:
- Exchange the authorization code for tokens
- Encrypt the refresh token using KMS
- Store the encrypted token in DynamoDB

### 3. Calendar Config Storage

The calendar configuration is stored in DynamoDB:

```python
{
    "PK": "TRAINER#trainer-123",
    "SK": "CALENDAR_CONFIG",
    "provider": "google",  # or "outlook"
    "encrypted_refresh_token": "base64_encrypted_token",
    "calendar_id": "primary",
    "connected_at": "2024-01-15T10:30:00Z"
}
```

## Error Handling

### Graceful Degradation

The service implements graceful degradation - calendar sync failures never block session operations:

```python
try:
    result = calendar_service.create_event(...)
    # If this fails, it returns None instead of raising
except Exception:
    # This should never happen - exceptions are caught internally
    pass
```

### Retry Logic

All calendar API calls use retry logic with exponential backoff:

- **Attempt 1**: Immediate
- **Attempt 2**: After 1 second
- **Attempt 3**: After 2 seconds (total 3 seconds delay)

If all attempts fail, the operation returns `None` or `False` instead of raising an exception.

### Token Refresh

When a calendar API call returns 401 Unauthorized, the service automatically:

1. Refreshes the access token using the stored refresh token
2. Retries the operation with the new access token
3. Updates the stored refresh token if a new one is provided (Outlook only)

### Logging

All operations are logged with structured JSON logging:

```python
# Success
logger.info(
    "Calendar event created successfully",
    trainer_id="trainer-123",
    session_id="session-456",
    calendar_event_id="google_event_123",
    provider="google"
)

# Failure (graceful degradation)
logger.error(
    "Calendar sync failed, continuing without sync",
    trainer_id="trainer-123",
    session_id="session-456",
    error="Network timeout",
    error_type="RequestException"
)
```

## API Differences

### Google Calendar API v3

- **Base URL**: `https://www.googleapis.com/calendar/v3`
- **Event Structure**:
  ```json
  {
    "summary": "Training Session with John Doe",
    "description": "Session ID: session-456",
    "start": {
      "dateTime": "2024-01-20T14:00:00",
      "timeZone": "UTC"
    },
    "end": {
      "dateTime": "2024-01-20T15:00:00",
      "timeZone": "UTC"
    },
    "location": "Gym A"
  }
  ```
- **Token Refresh**: Returns only access token
- **Calendar ID**: Usually "primary"

### Microsoft Graph API (Outlook)

- **Base URL**: `https://graph.microsoft.com/v1.0/me/events`
- **Event Structure**:
  ```json
  {
    "subject": "Training Session with John Doe",
    "body": {
      "contentType": "Text",
      "content": "Session ID: session-456"
    },
    "start": {
      "dateTime": "2024-01-20T14:00:00",
      "timeZone": "UTC"
    },
    "end": {
      "dateTime": "2024-01-20T15:00:00",
      "timeZone": "UTC"
    },
    "location": {
      "displayName": "Gym A"
    }
  }
  ```
- **Token Refresh**: May return new refresh token (must be stored)
- **HTTP Methods**: Uses PATCH for updates (not PUT)

## Testing

### Unit Tests

Run the comprehensive unit test suite:

```bash
pytest tests/unit/test_calendar_sync.py -v
```

Tests cover:
- Calendar config retrieval
- OAuth token refresh (Google and Outlook)
- Event creation, update, and deletion
- Retry logic with exponential backoff
- Graceful degradation on failures
- 401 Unauthorized handling

### Integration Tests

For integration testing with real calendar APIs, use the mocked OAuth flow:

```python
import pytest
from unittest.mock import patch

@patch("src.services.calendar_sync.requests.post")
def test_calendar_sync_integration(mock_post):
    """Test full calendar sync flow with mocked API."""
    # Mock OAuth token refresh
    mock_post.return_value.json.return_value = {
        "access_token": "test_token"
    }
    
    # Test event creation
    service = CalendarSyncService()
    result = service.create_event(...)
    
    assert result is not None
```

## Performance Considerations

### Sync Timing

Calendar sync operations should complete within 30 seconds (requirement 4.3, 4.4, 4.5):

- **Without retries**: ~500ms per operation
- **With 3 retries**: Up to ~7 seconds (1s + 2s + 4s delays)
- **Token refresh**: Additional ~1 second

### Async Considerations

For production use, consider making calendar sync asynchronous:

```python
# Option 1: Queue to SQS for async processing
sqs.send_message(
    QueueUrl=calendar_sync_queue_url,
    MessageBody=json.dumps({
        "operation": "create_event",
        "trainer_id": trainer_id,
        "session_id": session_id,
        # ... other params
    })
)

# Option 2: Lambda async invocation
lambda_client.invoke(
    FunctionName="calendar-sync-function",
    InvocationType="Event",  # Async
    Payload=json.dumps({...})
)
```

## Security

### Token Encryption

OAuth refresh tokens are encrypted using AWS KMS before storage:

```python
from src.utils.encryption import encrypt_oauth_token_base64

encrypted_token = encrypt_oauth_token_base64(refresh_token)
# Store encrypted_token in DynamoDB
```

### Token Decryption

Tokens are decrypted only when needed for API calls:

```python
from src.utils.encryption import decrypt_oauth_token_base64

refresh_token = decrypt_oauth_token_base64(encrypted_token)
# Use refresh_token to get access token
```

### Logging Privacy

Sensitive data is never logged:
- OAuth tokens (access or refresh)
- Full calendar event IDs (truncated in logs)
- Personal information from calendar events

## Troubleshooting

### Calendar Not Syncing

1. **Check if calendar is connected**:
   ```python
   config = calendar_service._get_calendar_config(trainer_id)
   if not config:
       print("No calendar connected")
   ```

2. **Check logs for errors**:
   ```bash
   grep "Calendar sync failed" /var/log/fitagent.log
   ```

3. **Verify OAuth credentials**:
   - Google: `settings.google_client_id` and `settings.google_client_secret`
   - Outlook: `settings.outlook_client_id` and `settings.outlook_client_secret`

### Token Refresh Failures

If token refresh consistently fails:

1. Check if refresh token is still valid (may have been revoked)
2. Verify OAuth client credentials are correct
3. Check if OAuth scopes are sufficient
4. Ask trainer to reconnect their calendar

### API Rate Limits

Both Google and Microsoft have rate limits:

- **Google Calendar**: 1,000,000 queries per day
- **Microsoft Graph**: Varies by subscription

If hitting rate limits, consider:
- Implementing request throttling
- Caching calendar data
- Batching operations

## Future Enhancements

Potential improvements for the calendar sync service:

1. **Batch Operations**: Sync multiple events in a single API call
2. **Webhook Support**: Receive calendar updates from providers
3. **Conflict Resolution**: Handle external calendar changes
4. **Additional Providers**: Apple Calendar, Outlook.com, etc.
5. **Sync Status Dashboard**: Show sync health per trainer
6. **Manual Retry**: Allow trainers to manually retry failed syncs
