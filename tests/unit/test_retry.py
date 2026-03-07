"""
Unit tests for retry decorator with exponential backoff.

Tests cover:
- Successful retry after failures
- Exponential backoff timing
- Exception filtering
- Maximum attempts enforcement
- Logging verification
- Custom exception handling
"""

import pytest
import time
from unittest.mock import Mock, patch
from src.utils.retry import (
    retry_with_backoff,
    RetryableError,
    ExternalServiceError
)


class TestRetryWithBackoff:
    """Test suite for retry_with_backoff decorator."""
    
    def test_successful_first_attempt(self):
        """Test that function succeeds on first attempt without retry."""
        mock_func = Mock(return_value="success")
        
        @retry_with_backoff(max_attempts=3)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_successful_after_retries(self):
        """Test that function succeeds after initial failures."""
        attempt_count = 0
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01, backoff_factor=2.0)
        def test_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = test_func()
        
        assert result == "success"
        assert attempt_count == 3
    
    def test_max_attempts_exhausted(self):
        """Test that exception is raised after max attempts."""
        attempt_count = 0
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Persistent failure")
        
        with pytest.raises(ValueError, match="Persistent failure"):
            test_func()
        
        assert attempt_count == 3
    
    def test_exponential_backoff_timing(self):
        """Test that delays follow exponential backoff pattern."""
        attempt_times = []
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.1, backoff_factor=2.0)
        def test_func():
            attempt_times.append(time.time())
            if len(attempt_times) < 3:
                raise Exception("Retry")
            return "success"
        
        test_func()
        
        # Verify we have 3 attempts
        assert len(attempt_times) == 3
        
        # Calculate actual delays
        delay1 = attempt_times[1] - attempt_times[0]
        delay2 = attempt_times[2] - attempt_times[1]
        
        # Verify exponential backoff (with tolerance for timing variations)
        assert 0.08 <= delay1 <= 0.15  # ~0.1 seconds
        assert 0.18 <= delay2 <= 0.25  # ~0.2 seconds
    
    def test_specific_exception_filtering(self):
        """Test that only specified exceptions trigger retry."""
        attempt_count = 0
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.01,
            exceptions=(ValueError,)
        )
        def test_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise ValueError("Retryable error")
            elif attempt_count == 2:
                raise TypeError("Non-retryable error")
            return "success"
        
        # Should retry ValueError but not TypeError
        with pytest.raises(TypeError, match="Non-retryable error"):
            test_func()
        
        assert attempt_count == 2
    
    def test_multiple_exception_types(self):
        """Test retry with multiple exception types."""
        attempt_count = 0
        
        @retry_with_backoff(
            max_attempts=4,
            initial_delay=0.01,
            exceptions=(ValueError, TypeError, KeyError)
        )
        def test_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise ValueError("Error 1")
            elif attempt_count == 2:
                raise TypeError("Error 2")
            elif attempt_count == 3:
                raise KeyError("Error 3")
            return "success"
        
        result = test_func()
        
        assert result == "success"
        assert attempt_count == 4
    
    def test_custom_backoff_factor(self):
        """Test custom backoff factor."""
        attempt_times = []
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.1,
            backoff_factor=3.0  # Triple delay each time
        )
        def test_func():
            attempt_times.append(time.time())
            if len(attempt_times) < 3:
                raise Exception("Retry")
            return "success"
        
        test_func()
        
        delay1 = attempt_times[1] - attempt_times[0]
        delay2 = attempt_times[2] - attempt_times[1]
        
        # Verify 3x backoff factor
        assert 0.08 <= delay1 <= 0.15  # ~0.1 seconds
        assert 0.28 <= delay2 <= 0.35  # ~0.3 seconds (0.1 * 3)
    
    def test_fixed_delay_with_backoff_factor_one(self):
        """Test fixed delay when backoff_factor is 1.0."""
        attempt_times = []
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.1,
            backoff_factor=1.0  # No exponential increase
        )
        def test_func():
            attempt_times.append(time.time())
            if len(attempt_times) < 3:
                raise Exception("Retry")
            return "success"
        
        test_func()
        
        delay1 = attempt_times[1] - attempt_times[0]
        delay2 = attempt_times[2] - attempt_times[1]
        
        # Both delays should be approximately equal
        assert 0.08 <= delay1 <= 0.15
        assert 0.08 <= delay2 <= 0.15
        assert abs(delay1 - delay2) < 0.05  # Similar delays
    
    def test_single_attempt_no_retry(self):
        """Test with max_attempts=1 (no retry)."""
        attempt_count = 0
        
        @retry_with_backoff(max_attempts=1, initial_delay=0.01)
        def test_func():
            nonlocal attempt_count
            attempt_count += 1
            raise Exception("Immediate failure")
        
        with pytest.raises(Exception, match="Immediate failure"):
            test_func()
        
        assert attempt_count == 1
    
    def test_function_with_arguments(self):
        """Test that decorated function preserves arguments."""
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def test_func(a, b, c=None):
            if c is None:
                raise ValueError("Missing c")
            return a + b + c
        
        result = test_func(1, 2, c=3)
        assert result == 6
    
    def test_function_with_kwargs(self):
        """Test that decorated function preserves keyword arguments."""
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def test_func(**kwargs):
            if "required" not in kwargs:
                raise KeyError("Missing required")
            return kwargs["required"]
        
        result = test_func(required="value", optional="extra")
        assert result == "value"
    
    def test_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""
        @retry_with_backoff(max_attempts=3)
        def test_func():
            """Test function docstring."""
            return "result"
        
        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test function docstring."
    
    @patch('src.utils.retry.logger')
    def test_logging_on_retry(self, mock_logger):
        """Test that retry attempts are logged."""
        attempt_count = 0
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception(f"Failure {attempt_count}")
            return "success"
        
        test_func()
        
        # Should log warnings for failures and info for success
        assert mock_logger.warning.call_count == 2
        assert mock_logger.info.call_count >= 2  # Retry messages + success message
    
    @patch('src.utils.retry.logger')
    def test_logging_on_final_failure(self, mock_logger):
        """Test that final failure is logged as error."""
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def test_func():
            raise Exception("Persistent failure")
        
        with pytest.raises(Exception):
            test_func()
        
        # Should log error for final failure
        assert mock_logger.error.call_count == 1
        assert mock_logger.warning.call_count == 2


class TestRetryableError:
    """Test suite for RetryableError exception class."""
    
    def test_retryable_error_creation(self):
        """Test creating RetryableError."""
        error = RetryableError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
    
    def test_retryable_error_inheritance(self):
        """Test that custom exceptions can inherit from RetryableError."""
        class CustomError(RetryableError):
            pass
        
        error = CustomError("Custom error")
        assert isinstance(error, RetryableError)
        assert isinstance(error, Exception)
    
    def test_retry_with_retryable_error(self):
        """Test retry with RetryableError."""
        attempt_count = 0
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.01,
            exceptions=(RetryableError,)
        )
        def test_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise RetryableError("Temporary issue")
            return "success"
        
        result = test_func()
        assert result == "success"
        assert attempt_count == 3


class TestExternalServiceError:
    """Test suite for ExternalServiceError exception class."""
    
    def test_external_service_error_creation(self):
        """Test creating ExternalServiceError with all parameters."""
        error = ExternalServiceError("Twilio", "send_message", "Rate limit exceeded")
        
        assert error.service == "Twilio"
        assert error.operation == "send_message"
        assert str(error) == "Twilio send_message failed: Rate limit exceeded"
    
    def test_external_service_error_without_message(self):
        """Test creating ExternalServiceError without message."""
        error = ExternalServiceError("Google Calendar", "create_event")
        
        assert error.service == "Google Calendar"
        assert error.operation == "create_event"
        assert str(error) == "Google Calendar create_event failed: "
    
    def test_external_service_error_inheritance(self):
        """Test that ExternalServiceError inherits from RetryableError."""
        error = ExternalServiceError("Service", "operation", "message")
        
        assert isinstance(error, ExternalServiceError)
        assert isinstance(error, RetryableError)
        assert isinstance(error, Exception)
    
    def test_retry_with_external_service_error(self):
        """Test retry with ExternalServiceError."""
        attempt_count = 0
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.01,
            exceptions=(ExternalServiceError,)
        )
        def test_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ExternalServiceError(
                    "Calendar API",
                    "sync_event",
                    "Connection timeout"
                )
            return "success"
        
        result = test_func()
        assert result == "success"
        assert attempt_count == 3


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    def test_calendar_sync_scenario(self):
        """Test calendar sync with retry logic."""
        sync_attempts = []
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.01,
            backoff_factor=2.0,
            exceptions=(ExternalServiceError,)
        )
        def sync_calendar_event(event_data):
            sync_attempts.append(time.time())
            
            # Simulate transient failure then success
            if len(sync_attempts) < 2:
                raise ExternalServiceError(
                    "Google Calendar",
                    "create_event",
                    "503 Service Unavailable"
                )
            
            return {"id": "event_123", "status": "confirmed"}
        
        result = sync_calendar_event({"title": "Training Session"})
        
        assert result["id"] == "event_123"
        assert len(sync_attempts) == 2
    
    def test_notification_delivery_scenario(self):
        """Test notification delivery with fixed delay retry."""
        delivery_attempts = []
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.05,  # Simulating 5-minute delay
            backoff_factor=1.0,  # Fixed delay
            exceptions=(ExternalServiceError,)
        )
        def deliver_notification(recipient, message):
            delivery_attempts.append(time.time())
            
            # Fail twice then succeed
            if len(delivery_attempts) < 3:
                raise ExternalServiceError(
                    "Twilio",
                    "send_message",
                    "Rate limit exceeded"
                )
            
            return {"status": "delivered", "sid": "SM123"}
        
        result = deliver_notification("+1234567890", "Reminder")
        
        assert result["status"] == "delivered"
        assert len(delivery_attempts) == 3
        
        # Verify fixed delays
        delay1 = delivery_attempts[1] - delivery_attempts[0]
        delay2 = delivery_attempts[2] - delivery_attempts[1]
        assert abs(delay1 - delay2) < 0.02  # Similar delays
    
    def test_graceful_degradation_scenario(self):
        """Test graceful degradation when calendar sync fails."""
        @retry_with_backoff(
            max_attempts=2,
            initial_delay=0.01,
            exceptions=(ExternalServiceError,)
        )
        def sync_to_calendar(session_data):
            raise ExternalServiceError(
                "Calendar API",
                "create_event",
                "Persistent failure"
            )
        
        def schedule_session(session_data):
            # Critical: Save to database
            session_id = "session_123"
            
            # Non-critical: Sync to calendar
            try:
                sync_to_calendar(session_data)
                calendar_synced = True
            except ExternalServiceError:
                calendar_synced = False
            
            return {
                "session_id": session_id,
                "calendar_synced": calendar_synced
            }
        
        result = schedule_session({"title": "Training"})
        
        # Session created despite calendar sync failure
        assert result["session_id"] == "session_123"
        assert result["calendar_synced"] is False
    
    def test_token_refresh_scenario(self):
        """Test OAuth token refresh with retry."""
        refresh_attempts = []
        
        @retry_with_backoff(
            max_attempts=2,
            initial_delay=0.01,
            exceptions=(Exception,)
        )
        def refresh_oauth_token(refresh_token):
            refresh_attempts.append(time.time())
            
            # Fail once then succeed
            if len(refresh_attempts) < 2:
                raise Exception("Network timeout")
            
            return {
                "access_token": "new_token",
                "expires_in": 3600
            }
        
        result = refresh_oauth_token("refresh_token_123")
        
        assert result["access_token"] == "new_token"
        assert len(refresh_attempts) == 2


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_initial_delay(self):
        """Test with zero initial delay."""
        @retry_with_backoff(max_attempts=2, initial_delay=0.0)
        def test_func():
            raise Exception("Fail")
        
        start_time = time.time()
        with pytest.raises(Exception):
            test_func()
        elapsed = time.time() - start_time
        
        # Should complete quickly with no delay
        assert elapsed < 0.1
    
    def test_very_large_backoff_factor(self):
        """Test with very large backoff factor."""
        attempt_times = []
        
        @retry_with_backoff(
            max_attempts=3,
            initial_delay=0.01,
            backoff_factor=10.0
        )
        def test_func():
            attempt_times.append(time.time())
            if len(attempt_times) < 3:
                raise Exception("Retry")
            return "success"
        
        test_func()
        
        delay1 = attempt_times[1] - attempt_times[0]
        delay2 = attempt_times[2] - attempt_times[1]
        
        # Second delay should be ~10x first delay
        assert delay2 > delay1 * 8  # Allow some tolerance
    
    def test_exception_with_no_message(self):
        """Test handling exception with no message."""
        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        def test_func():
            raise Exception()
        
        with pytest.raises(Exception):
            test_func()
    
    def test_return_none(self):
        """Test function that returns None."""
        @retry_with_backoff(max_attempts=2)
        def test_func():
            return None
        
        result = test_func()
        assert result is None
    
    def test_return_false(self):
        """Test function that returns False."""
        @retry_with_backoff(max_attempts=2)
        def test_func():
            return False
        
        result = test_func()
        assert result is False
