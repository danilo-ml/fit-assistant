"""
Example usage of the retry decorator with exponential backoff.

This file demonstrates various use cases for the retry_with_backoff decorator
in the FitAgent WhatsApp Assistant application.
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from src.utils.retry import retry_with_backoff, ExternalServiceError, RetryableError


# Example 1: Basic retry for external API calls
@retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
def call_external_api():
    """
    Basic example with default exponential backoff.
    Retries: 1s, 2s, 4s delays
    """
    response = requests.get("https://api.example.com/data")
    response.raise_for_status()
    return response.json()


# Example 2: Google Calendar API integration
@retry_with_backoff(
    max_attempts=3,
    initial_delay=1.0,
    backoff_factor=2.0,
    exceptions=(requests.RequestException, ExternalServiceError)
)
def sync_calendar_event(event_data: dict):
    """
    Sync event to Google Calendar with retry logic.
    Only retries on network errors and external service errors.
    """
    try:
        response = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            json=event_data,
            headers={"Authorization": "Bearer <token>"}
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise ExternalServiceError("Google Calendar", "create_event", str(e))


# Example 3: Microsoft Outlook Calendar API
@retry_with_backoff(
    max_attempts=3,
    initial_delay=1.0,
    exceptions=(requests.RequestException,)
)
def sync_outlook_event(event_data: dict):
    """
    Sync event to Microsoft Outlook Calendar.
    Retries on network failures.
    """
    response = requests.post(
        "https://graph.microsoft.com/v1.0/me/events",
        json=event_data,
        headers={"Authorization": "Bearer <token>"}
    )
    response.raise_for_status()
    return response.json()


# Example 4: Twilio WhatsApp message sending
@retry_with_backoff(
    max_attempts=2,
    initial_delay=5.0,
    backoff_factor=1.0,  # Fixed delay for rate limiting
    exceptions=(Exception,)
)
def send_whatsapp_message(phone: str, message: str):
    """
    Send WhatsApp message via Twilio with retry.
    Uses fixed 5-second delay for rate limit compliance.
    """
    from twilio.rest import Client
    
    client = Client("account_sid", "auth_token")
    message = client.messages.create(
        from_='whatsapp:+14155238886',
        to=f'whatsapp:{phone}',
        body=message
    )
    return message.sid


# Example 5: Custom exception handling
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
    """
    Update calendar event with custom error handling.
    More aggressive retry strategy (5 attempts starting at 0.5s).
    """
    # Simulate API availability check
    api_available = check_calendar_api_status()
    
    if not api_available:
        raise CalendarAPIError("Calendar API temporarily unavailable")
    
    response = requests.patch(
        f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}",
        json=updates,
        headers={"Authorization": "Bearer <token>"}
    )
    response.raise_for_status()
    return response.json()


def check_calendar_api_status():
    """Mock function to check API availability."""
    return True


# Example 6: Notification delivery with retry
@retry_with_backoff(
    max_attempts=3,
    initial_delay=5.0,  # 5-minute delays as per requirements
    backoff_factor=1.0,  # Fixed delay
    exceptions=(ExternalServiceError,)
)
def deliver_notification(recipient: str, message: str):
    """
    Deliver notification with retry logic.
    Retries up to 2 times with 5-minute delays (total 3 attempts).
    """
    try:
        # Send via Twilio
        result = send_whatsapp_message(recipient, message)
        return {"status": "delivered", "message_sid": result}
    except Exception as e:
        raise ExternalServiceError("Twilio", "send_notification", str(e))


# Example 7: Graceful degradation pattern
def schedule_session_with_calendar_sync(session_data: dict):
    """
    Schedule session with optional calendar sync.
    Demonstrates graceful degradation - calendar sync failure doesn't block session creation.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Critical operation: Save session to database
    session_id = save_session_to_database(session_data)
    logger.info(f"Session {session_id} saved to database")
    
    # Non-critical operation: Sync to calendar
    try:
        calendar_event = sync_calendar_event(session_data)
        logger.info(f"Session {session_id} synced to calendar: {calendar_event['id']}")
    except Exception as e:
        logger.error(f"Calendar sync failed for session {session_id}: {e}")
        # Continue without blocking - session is already saved
    
    return session_id


def save_session_to_database(session_data: dict):
    """Mock function to save session to DynamoDB."""
    import uuid
    return str(uuid.uuid4())


# Example 8: Token refresh with retry
@retry_with_backoff(
    max_attempts=2,
    initial_delay=1.0,
    exceptions=(requests.RequestException,)
)
def refresh_oauth_token(refresh_token: str):
    """
    Refresh OAuth token with retry.
    Only 2 attempts since token refresh is time-sensitive.
    """
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": "client_id",
            "client_secret": "client_secret",
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
    )
    response.raise_for_status()
    return response.json()


# Example 9: Combining multiple retry strategies
def sync_session_to_calendar(session_data: dict, provider: str):
    """
    Sync session to calendar with provider-specific retry strategies.
    """
    if provider == "google":
        return sync_calendar_event(session_data)
    elif provider == "outlook":
        return sync_outlook_event(session_data)
    else:
        raise ValueError(f"Unsupported calendar provider: {provider}")


# Example 10: Testing retry behavior
def demonstrate_retry_behavior():
    """
    Demonstrate retry behavior with a function that fails then succeeds.
    """
    import logging
    logging.basicConfig(level=logging.INFO)
    
    attempt_count = 0
    
    @retry_with_backoff(max_attempts=3, initial_delay=0.1, backoff_factor=2.0)
    def flaky_function():
        nonlocal attempt_count
        attempt_count += 1
        
        if attempt_count < 3:
            raise Exception(f"Attempt {attempt_count} failed")
        
        return f"Success on attempt {attempt_count}"
    
    try:
        result = flaky_function()
        print(f"Result: {result}")
        print(f"Total attempts: {attempt_count}")
    except Exception as e:
        print(f"Failed after {attempt_count} attempts: {e}")


if __name__ == "__main__":
    # Run demonstration
    print("Demonstrating retry behavior:")
    demonstrate_retry_behavior()
    
    print("\nRetry decorator examples loaded successfully!")
    print("See individual function docstrings for usage details.")
