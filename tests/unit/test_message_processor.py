"""
Unit tests for message processor Lambda function.

Tests message processing, routing, error handling, and retry logic.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.handlers.message_processor import (
    lambda_handler,
    _process_message,
    _handle_onboarding,
    _handle_trainer,
    _handle_student,
    _send_response,
)
from src.services.message_router import HandlerType


@pytest.fixture
def sqs_event():
    """Sample SQS event with one message record."""
    return {
        "Records": [
            {
                "messageId": "msg-123",
                "receiptHandle": "receipt-handle-123",
                "body": json.dumps({
                    "message_sid": "SM123456",
                    "from": "+1234567890",
                    "to": "+0987654321",
                    "body": "Hello, I want to schedule a session",
                    "num_media": 0,
                    "media_urls": [],
                    "timestamp": "2024-01-15T10:30:00Z",
                    "request_id": "req-123",
                }),
                "attributes": {
                    "ApproximateReceiveCount": "1",
                },
                "messageAttributes": {
                    "request_id": {
                        "stringValue": "req-123",
                        "dataType": "String",
                    },
                    "message_sid": {
                        "stringValue": "SM123456",
                        "dataType": "String",
                    },
                },
            }
        ]
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = "message-processor"
    context.request_id = "lambda-req-123"
    return context


@pytest.fixture
def mock_message_router():
    """Mock MessageRouter."""
    with patch("src.handlers.message_processor.message_router") as mock:
        yield mock


@pytest.fixture
def mock_twilio_client():
    """Mock TwilioClient."""
    with patch("src.handlers.message_processor.twilio_client") as mock:
        yield mock


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    def test_successful_message_processing(
        self, sqs_event, lambda_context, mock_message_router, mock_twilio_client
    ):
        """Test successful processing of a message."""
        # Setup mocks
        mock_message_router.route_message.return_value = {
            "handler_type": HandlerType.TRAINER,
            "user_id": "trainer-123",
            "entity_type": "TRAINER",
            "user_data": {"name": "John Trainer", "trainer_id": "trainer-123"},
        }
        
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM789",
            "status": "queued",
        }

        # Execute
        result = lambda_handler(sqs_event, lambda_context)

        # Verify
        assert result["batchItemFailures"] == []
        mock_message_router.route_message.assert_called_once()
        mock_twilio_client.send_message.assert_called_once()

    def test_multiple_records_processing(
        self, sqs_event, lambda_context, mock_message_router, mock_twilio_client
    ):
        """Test processing multiple SQS records."""
        # Add another record
        sqs_event["Records"].append({
            "messageId": "msg-456",
            "receiptHandle": "receipt-handle-456",
            "body": json.dumps({
                "message_sid": "SM789",
                "from": "+9876543210",
                "to": "+0987654321",
                "body": "View my sessions",
                "num_media": 0,
                "media_urls": [],
                "timestamp": "2024-01-15T10:31:00Z",
                "request_id": "req-456",
            }),
            "attributes": {"ApproximateReceiveCount": "1"},
            "messageAttributes": {
                "request_id": {"stringValue": "req-456", "dataType": "String"}
            },
        })

        # Setup mocks
        mock_message_router.route_message.side_effect = [
            {
                "handler_type": HandlerType.TRAINER,
                "user_id": "trainer-123",
                "entity_type": "TRAINER",
                "user_data": {"name": "John Trainer"},
            },
            {
                "handler_type": HandlerType.STUDENT,
                "user_id": "student-456",
                "entity_type": "STUDENT",
                "user_data": {"name": "Jane Student"},
            },
        ]
        
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "queued",
        }

        # Execute
        result = lambda_handler(sqs_event, lambda_context)

        # Verify
        assert result["batchItemFailures"] == []
        assert mock_message_router.route_message.call_count == 2
        assert mock_twilio_client.send_message.call_count == 2

    def test_partial_batch_failure(
        self, sqs_event, lambda_context, mock_message_router, mock_twilio_client
    ):
        """Test partial batch failure handling."""
        # Add another record
        sqs_event["Records"].append({
            "messageId": "msg-456",
            "receiptHandle": "receipt-handle-456",
            "body": json.dumps({
                "message_sid": "SM789",
                "from": "+9876543210",
                "to": "+0987654321",
                "body": "Test message",
                "num_media": 0,
                "media_urls": [],
                "timestamp": "2024-01-15T10:31:00Z",
                "request_id": "req-456",
            }),
            "attributes": {"ApproximateReceiveCount": "1"},
            "messageAttributes": {
                "request_id": {"stringValue": "req-456", "dataType": "String"}
            },
        })

        # First message succeeds, second fails
        mock_message_router.route_message.side_effect = [
            {
                "handler_type": HandlerType.TRAINER,
                "user_id": "trainer-123",
                "entity_type": "TRAINER",
                "user_data": {"name": "John Trainer"},
            },
            Exception("Routing failed"),
        ]
        
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "queued",
        }

        # Execute
        result = lambda_handler(sqs_event, lambda_context)

        # Verify - second message should be in failures
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-456"

    def test_max_retries_logging(
        self, sqs_event, lambda_context, mock_message_router, mock_twilio_client
    ):
        """Test logging when message reaches max retries."""
        # Set receive count to 3 (final retry)
        sqs_event["Records"][0]["attributes"]["ApproximateReceiveCount"] = "3"

        # Setup mock to fail
        mock_message_router.route_message.side_effect = Exception("Processing failed")

        # Execute
        result = lambda_handler(sqs_event, lambda_context)

        # Verify failure is recorded
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-123"

    def test_invalid_json_body(
        self, sqs_event, lambda_context, mock_message_router, mock_twilio_client
    ):
        """Test handling of invalid JSON in message body."""
        # Set invalid JSON
        sqs_event["Records"][0]["body"] = "invalid json {"

        # Execute
        result = lambda_handler(sqs_event, lambda_context)

        # Verify failure is recorded
        assert len(result["batchItemFailures"]) == 1


class TestProcessMessage:
    """Tests for _process_message function."""

    def test_onboarding_routing(self, mock_message_router):
        """Test routing to onboarding handler."""
        mock_message_router.route_message.return_value = {
            "handler_type": HandlerType.ONBOARDING,
            "user_id": None,
            "entity_type": None,
            "user_data": None,
        }

        message_body = {
            "message_sid": "SM123",
            "from": "+1234567890",
            "body": "Hello",
        }

        result = _process_message("+1234567890", message_body, "req-123")

        assert "Welcome to FitAgent" in result
        mock_message_router.route_message.assert_called_once()

    def test_trainer_routing(self, mock_message_router):
        """Test routing to trainer handler."""
        mock_message_router.route_message.return_value = {
            "handler_type": HandlerType.TRAINER,
            "user_id": "trainer-123",
            "entity_type": "TRAINER",
            "user_data": {
                "name": "John Trainer",
                "trainer_id": "trainer-123",
            },
        }

        message_body = {
            "message_sid": "SM123",
            "from": "+1234567890",
            "body": "Schedule a session",
        }

        result = _process_message("+1234567890", message_body, "req-123")

        assert "John Trainer" in result
        assert "Register students" in result

    def test_student_routing(self, mock_message_router):
        """Test routing to student handler."""
        mock_message_router.route_message.return_value = {
            "handler_type": HandlerType.STUDENT,
            "user_id": "student-456",
            "entity_type": "STUDENT",
            "user_data": {
                "name": "Jane Student",
                "student_id": "student-456",
            },
        }

        message_body = {
            "message_sid": "SM123",
            "from": "+9876543210",
            "body": "View my sessions",
        }

        result = _process_message("+9876543210", message_body, "req-123")

        assert "Jane Student" in result
        assert "View upcoming sessions" in result


class TestHandlerFunctions:
    """Tests for individual handler functions."""

    def test_handle_onboarding(self):
        """Test onboarding handler returns welcome message."""
        message_body = {"body": "Hello"}
        
        result = _handle_onboarding("+1234567890", message_body, "req-123")

        assert "Welcome to FitAgent" in result
        assert "Personal Trainer" in result
        assert "Student" in result

    def test_handle_trainer(self):
        """Test trainer handler returns appropriate response."""
        user_data = {
            "name": "John Trainer",
            "trainer_id": "trainer-123",
        }
        message_body = {"body": "Help me schedule"}

        result = _handle_trainer("trainer-123", user_data, message_body, "req-123")

        assert "John Trainer" in result
        assert "Register students" in result
        assert "Schedule sessions" in result

    def test_handle_student(self):
        """Test student handler returns appropriate response."""
        user_data = {
            "name": "Jane Student",
            "student_id": "student-456",
        }
        message_body = {"body": "Show my sessions"}

        result = _handle_student("student-456", user_data, message_body, "req-123")

        assert "Jane Student" in result
        assert "View upcoming sessions" in result
        assert "Confirm attendance" in result


class TestSendResponse:
    """Tests for _send_response function."""

    def test_successful_send(self, mock_twilio_client):
        """Test successful message sending."""
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "queued",
        }

        # Should not raise exception
        _send_response(
            to="+1234567890",
            body="Test response",
            request_id="req-123",
            message_sid="SM123",
        )

        mock_twilio_client.send_message.assert_called_once_with(
            to="+1234567890",
            body="Test response",
        )

    def test_send_failure(self, mock_twilio_client):
        """Test handling of send failure."""
        mock_twilio_client.send_message.side_effect = Exception("Twilio API error")

        # Should raise exception
        with pytest.raises(Exception, match="Twilio API error"):
            _send_response(
                to="+1234567890",
                body="Test response",
                request_id="req-123",
                message_sid="SM123",
            )
