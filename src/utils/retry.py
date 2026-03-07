"""
Retry decorator with exponential backoff for external API calls.

This module provides a decorator for retrying failed operations with
exponential backoff, primarily used for external API calls to services
like Twilio, Google Calendar, and Microsoft Graph.
"""

import time
import logging
from typing import Callable, Any, Optional, Type, Tuple
from functools import wraps

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    Decorator for retry logic with exponential backoff.
    
    Retries a function call if it raises one of the specified exceptions,
    with increasing delays between attempts. The delay follows the pattern:
    initial_delay, initial_delay * backoff_factor, initial_delay * backoff_factor^2, etc.
    
    Args:
        max_attempts: Maximum number of attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        backoff_factor: Multiplier for delay after each attempt (default: 2.0)
        exceptions: Tuple of exception types to catch and retry (default: (Exception,))
        
    Returns:
        Callable: Decorated function with retry logic
        
    Raises:
        The last exception raised if all retry attempts are exhausted
        
    Examples:
        >>> @retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
        ... def call_external_api():
        ...     return api.make_request()
        
        >>> # Custom exceptions to retry
        >>> @retry_with_backoff(
        ...     max_attempts=5,
        ...     initial_delay=0.5,
        ...     exceptions=(requests.RequestException, TimeoutError)
        ... )
        ... def call_calendar_api():
        ...     return calendar.create_event()
        
        >>> # For Twilio API calls
        >>> @retry_with_backoff(max_attempts=2, initial_delay=5.0)
        ... def send_whatsapp_message(phone: str, message: str):
        ...     return twilio_client.messages.create(to=phone, body=message)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                    
                    # Log successful retry if not first attempt
                    if attempt > 0:
                        logger.info(
                            f"Function {func.__name__} succeeded on attempt {attempt + 1}/{max_attempts}"
                        )
                    
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    # Log the failure
                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt + 1}/{max_attempts}: {str(e)}"
                    )
                    
                    # If not the last attempt, sleep and retry
                    if attempt < max_attempts - 1:
                        logger.info(
                            f"Retrying {func.__name__} in {delay:.2f} seconds..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        # Last attempt failed, log and raise
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts"
                        )
                        raise last_exception
            
            # This should never be reached, but included for type safety
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator


class RetryableError(Exception):
    """
    Base exception class for errors that should trigger retry logic.
    
    Use this as a base class for custom exceptions that represent
    transient failures that are likely to succeed on retry.
    
    Examples:
        >>> class CalendarAPIError(RetryableError):
        ...     pass
        ...
        >>> @retry_with_backoff(exceptions=(RetryableError,))
        ... def sync_calendar():
        ...     if api_unavailable():
        ...         raise CalendarAPIError("Calendar API temporarily unavailable")
    """
    pass


class ExternalServiceError(RetryableError):
    """
    Exception for external service failures (Twilio, Calendar APIs, etc.).
    
    This exception indicates a failure when communicating with an external
    service that may be transient and worth retrying.
    
    Attributes:
        service: Name of the external service (e.g., "Twilio", "Google Calendar")
        operation: Operation that failed (e.g., "send_message", "create_event")
        
    Examples:
        >>> raise ExternalServiceError("Twilio", "send_message", "Rate limit exceeded")
    """
    
    def __init__(self, service: str, operation: str, message: str = ""):
        self.service = service
        self.operation = operation
        super().__init__(f"{service} {operation} failed: {message}")
