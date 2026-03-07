"""
Example usage of the structured logging module.

This demonstrates how to use StructuredLogger in various scenarios
throughout the FitAgent application.
"""

from src.utils.logging import get_logger

# Initialize logger for your module
logger = get_logger(__name__)


def example_basic_logging():
    """Basic logging examples."""
    print("=== Basic Logging ===")
    
    # Simple info log
    logger.info("Application started")
    
    # Warning log
    logger.warning("Rate limit approaching")
    
    # Error log
    logger.error("Failed to connect to external service")


def example_with_request_id():
    """Logging with request ID for tracing."""
    print("\n=== Logging with Request ID ===")
    
    request_id = "req-abc-123"
    
    logger.info(
        "Processing webhook",
        request_id=request_id
    )
    
    logger.info(
        "Message routed successfully",
        request_id=request_id,
        route="trainer_handler"
    )


def example_with_phone_number():
    """Logging with phone number (automatically masked)."""
    print("\n=== Logging with Phone Number (Masked) ===")
    
    phone_number = "+1234567890"
    
    # Phone number will be automatically masked to ***7890
    logger.info(
        "User identified",
        request_id="req-xyz-789",
        phone_number=phone_number,
        user_type="trainer"
    )


def example_tool_execution():
    """Logging tool execution (Requirement 19.3)."""
    print("\n=== Tool Execution Logging ===")
    
    logger.info(
        "Tool executed",
        request_id="req-tool-456",
        phone_number="+1234567890",
        tool_name="schedule_session",
        parameters={
            "student_name": "John Doe",
            "date": "2024-01-20",
            "time": "14:00",
            "duration_minutes": 60
        },
        execution_time_ms=150
    )


def example_external_api_call():
    """Logging external API calls (Requirement 19.4)."""
    print("\n=== External API Call Logging ===")
    
    # Twilio API call
    logger.info(
        "External API call",
        request_id="req-api-123",
        api_name="twilio",
        endpoint="/Messages",
        method="POST",
        response_status=200,
        response_time_ms=250
    )
    
    # Google Calendar API call
    logger.info(
        "External API call",
        request_id="req-cal-456",
        api_name="google_calendar",
        endpoint="/calendar/v3/events",
        method="POST",
        response_status=201,
        response_time_ms=450
    )


def example_error_logging():
    """Error logging with context (Requirement 19.1, 19.2)."""
    print("\n=== Error Logging ===")
    
    try:
        # Simulate an error
        raise ValueError("Invalid session date format")
    except ValueError as e:
        logger.error(
            "Validation error occurred",
            request_id="req-err-789",
            phone_number="+1234567890",
            error_type=type(e).__name__,
            error_message=str(e),
            tool_name="schedule_session",
            parameters={"date": "invalid-date"}
        )


def example_lambda_handler_pattern():
    """Example of using structured logging in a Lambda handler."""
    print("\n=== Lambda Handler Pattern ===")
    
    def lambda_handler(event, context):
        """Example Lambda handler with structured logging."""
        request_id = context.request_id if hasattr(context, 'request_id') else "local-test"
        
        logger.info(
            "Lambda invoked",
            request_id=request_id,
            function_name=context.function_name if hasattr(context, 'function_name') else "local",
            event_type=event.get('type', 'unknown')
        )
        
        try:
            # Process event
            phone_number = event.get('phone_number')
            message = event.get('message')
            
            logger.info(
                "Processing message",
                request_id=request_id,
                phone_number=phone_number,
                message_length=len(message) if message else 0
            )
            
            # Simulate processing
            result = {"success": True, "message_id": "msg-123"}
            
            logger.info(
                "Message processed successfully",
                request_id=request_id,
                phone_number=phone_number,
                result=result
            )
            
            return {"statusCode": 200, "body": result}
            
        except Exception as e:
            logger.error(
                "Unexpected error in Lambda handler",
                request_id=request_id,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            raise
    
    # Simulate Lambda invocation
    class MockContext:
        request_id = "req-lambda-123"
        function_name = "message_processor"
    
    event = {
        "type": "whatsapp_message",
        "phone_number": "+1234567890",
        "message": "Hello, I want to schedule a session"
    }
    
    lambda_handler(event, MockContext())


def example_calendar_sync_logging():
    """Example of logging calendar sync operations."""
    print("\n=== Calendar Sync Logging ===")
    
    trainer_id = "trainer-uuid-123"
    session_id = "session-uuid-456"
    
    logger.info(
        "Calendar sync started",
        request_id="req-sync-789",
        trainer_id=trainer_id,
        session_id=session_id,
        provider="google"
    )
    
    logger.info(
        "External API call",
        request_id="req-sync-789",
        api_name="google_calendar",
        endpoint="/calendar/v3/events",
        method="POST",
        response_status=201,
        calendar_event_id="cal-event-123"
    )
    
    logger.info(
        "Calendar sync completed",
        request_id="req-sync-789",
        trainer_id=trainer_id,
        session_id=session_id,
        calendar_event_id="cal-event-123",
        sync_duration_ms=500
    )


def example_privacy_compliance():
    """Demonstrate privacy compliance features."""
    print("\n=== Privacy Compliance ===")
    
    # Phone numbers are automatically masked
    logger.info(
        "User action",
        phone_number="+1234567890",  # Will be logged as ***7890
        action="view_sessions"
    )
    
    # Never log sensitive data like OAuth tokens
    # BAD: logger.info("Token", oauth_token=token)
    # GOOD:
    logger.info(
        "OAuth token refreshed",
        request_id="req-oauth-123",
        provider="google",
        status="success"
        # Note: No token is logged
    )


if __name__ == "__main__":
    print("FitAgent Structured Logging Examples\n")
    print("=" * 60)
    
    example_basic_logging()
    example_with_request_id()
    example_with_phone_number()
    example_tool_execution()
    example_external_api_call()
    example_error_logging()
    example_lambda_handler_pattern()
    example_calendar_sync_logging()
    example_privacy_compliance()
    
    print("\n" + "=" * 60)
    print("\nAll examples completed!")
    print("\nNote: All logs are in JSON format for CloudWatch Insights queries.")
    print("Phone numbers are automatically masked for privacy compliance.")
