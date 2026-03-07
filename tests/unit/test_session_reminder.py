"""
Unit tests for session reminder Lambda function.

Tests session reminder querying, filtering, and delivery.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.handlers.session_reminder import (
    lambda_handler,
    _get_sessions_needing_reminders,
    _send_session_reminder,
)


@pytest.fixture
def eventbridge_event():
    """Sample EventBridge scheduled event."""
    return {
        "version": "0",
        "id": "event-123",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "time": "2024-01-15T10:00:00Z",
        "region": "us-east-1",
        "resources": ["arn:aws:events:us-east-1:123456789012:rule/session-reminders"],
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = "session-reminder"
    context.request_id = "lambda-req-123"
    return context


@pytest.fixture
def mock_dynamodb_client():
    """Mock DynamoDBClient."""
    with patch("src.handlers.session_reminder.dynamodb_client") as mock:
        yield mock


@pytest.fixture
def mock_twilio_client():
    """Mock TwilioClient."""
    with patch("src.handlers.session_reminder.twilio_client") as mock:
        yield mock


@pytest.fixture
def sample_session():
    """Sample session record."""
    future_time = datetime.utcnow() + timedelta(hours=24)
    return {
        "PK": "TRAINER#trainer-123",
        "SK": "SESSION#session-456",
        "entity_type": "SESSION",
        "session_id": "session-456",
        "trainer_id": "trainer-123",
        "student_id": "student-789",
        "student_name": "Jane Student",
        "session_datetime": future_time.isoformat(),
        "duration_minutes": 60,
        "location": "Gym A",
        "status": "scheduled",
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_trainer():
    """Sample trainer record."""
    return {
        "PK": "TRAINER#trainer-123",
        "SK": "METADATA",
        "entity_type": "TRAINER",
        "trainer_id": "trainer-123",
        "name": "John Trainer",
        "email": "john@example.com",
        "phone_number": "+1234567890",
    }


@pytest.fixture
def sample_student():
    """Sample student record."""
    return {
        "PK": "STUDENT#student-789",
        "SK": "METADATA",
        "entity_type": "STUDENT",
        "student_id": "student-789",
        "name": "Jane Student",
        "email": "jane@example.com",
        "phone_number": "+9876543210",
    }


@pytest.fixture
def sample_trainer_config():
    """Sample trainer configuration."""
    return {
        "PK": "TRAINER#trainer-123",
        "SK": "CONFIG",
        "entity_type": "TRAINER_CONFIG",
        "trainer_id": "trainer-123",
        "reminder_hours": 24,
        "session_reminders_enabled": True,
    }


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    def test_successful_reminder_processing(
        self,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_session,
        sample_trainer,
        sample_student,
        sample_trainer_config,
    ):
        """Test successful processing of session reminders."""
        # Setup mocks
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_session],
        }
        mock_dynamodb_client._deserialize_item.return_value = sample_session
        mock_dynamodb_client.get_trainer_config.return_value = sample_trainer_config
        mock_dynamodb_client.get_session_reminders.return_value = []
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_dynamodb_client.put_reminder.return_value = {}

        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }

        # Execute
        result = lambda_handler(eventbridge_event, lambda_context)

        # Verify
        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 1
        assert result["body"]["reminders_failed"] == 0
        mock_twilio_client.send_message.assert_called_once()
        mock_dynamodb_client.put_reminder.assert_called_once()

    def test_no_sessions_needing_reminders(
        self,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
    ):
        """Test when no sessions need reminders."""
        # Setup mocks - no sessions found
        mock_dynamodb_client.table.scan.return_value = {"Items": []}

        # Execute
        result = lambda_handler(eventbridge_event, lambda_context)

        # Verify
        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 0
        mock_twilio_client.send_message.assert_not_called()

    def test_reminders_disabled_for_trainer(
        self,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_session,
    ):
        """Test when reminders are disabled for a trainer."""
        # Setup mocks
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_session],
        }
        mock_dynamodb_client._deserialize_item.return_value = sample_session
        
        # Reminders disabled
        disabled_config = {
            "trainer_id": "trainer-123",
            "session_reminders_enabled": False,
        }
        mock_dynamodb_client.get_trainer_config.return_value = disabled_config
        mock_dynamodb_client.get_session_reminders.return_value = []

        # Execute
        result = lambda_handler(eventbridge_event, lambda_context)

        # Verify - no reminders sent
        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 0
        mock_twilio_client.send_message.assert_not_called()

    def test_reminder_already_sent(
        self,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_session,
        sample_trainer_config,
    ):
        """Test when reminder was already sent for a session."""
        # Setup mocks
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_session],
        }
        mock_dynamodb_client._deserialize_item.return_value = sample_session
        mock_dynamodb_client.get_trainer_config.return_value = sample_trainer_config
        
        # Reminder already sent
        existing_reminder = {
            "reminder_id": "reminder-123",
            "reminder_type": "session",
            "status": "sent",
        }
        mock_dynamodb_client.get_session_reminders.return_value = [existing_reminder]

        # Execute
        result = lambda_handler(eventbridge_event, lambda_context)

        # Verify - no new reminders sent
        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 0
        mock_twilio_client.send_message.assert_not_called()

    def test_cancelled_session_excluded(
        self,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_session,
    ):
        """Test that cancelled sessions are excluded from reminders."""
        # Setup mocks - session is cancelled
        cancelled_session = sample_session.copy()
        cancelled_session["status"] = "cancelled"
        
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [cancelled_session],
        }
        mock_dynamodb_client._deserialize_item.return_value = cancelled_session

        # Execute
        result = lambda_handler(eventbridge_event, lambda_context)

        # Verify - no reminders sent (filtered by scan)
        assert result["statusCode"] == 200
        mock_twilio_client.send_message.assert_not_called()

    def test_partial_failure_handling(
        self,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_session,
        sample_trainer,
        sample_student,
        sample_trainer_config,
    ):
        """Test handling when some reminders fail."""
        # Create two sessions
        future_time_1 = datetime.utcnow() + timedelta(hours=24)
        future_time_2 = datetime.utcnow() + timedelta(hours=24, minutes=30)
        
        session_1 = sample_session.copy()
        session_2 = sample_session.copy()
        session_2["session_id"] = "session-999"
        session_2["session_datetime"] = future_time_2.isoformat()
        session_2["student_id"] = "student-999"

        # Setup mocks
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [session_1, session_2],
        }
        mock_dynamodb_client._deserialize_item.side_effect = [session_1, session_2]
        mock_dynamodb_client.get_trainer_config.return_value = sample_trainer_config
        mock_dynamodb_client.get_session_reminders.return_value = []
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        
        # First student succeeds, second fails
        mock_dynamodb_client.get_student.side_effect = [
            sample_student,
            None,  # Student not found
        ]
        
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }

        # Execute
        result = lambda_handler(eventbridge_event, lambda_context)

        # Verify - one success, one failure
        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 1
        assert result["body"]["reminders_failed"] == 1


class TestSendSessionReminder:
    """Tests for _send_session_reminder function."""

    def test_successful_reminder_send(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_session,
        sample_trainer,
        sample_student,
    ):
        """Test successful reminder sending."""
        # Setup mocks
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }
        mock_dynamodb_client.put_reminder.return_value = {}

        current_time = datetime.utcnow()

        # Execute
        _send_session_reminder(sample_session, current_time)

        # Verify
        mock_twilio_client.send_message.assert_called_once()
        call_args = mock_twilio_client.send_message.call_args
        assert call_args[1]["to"] == sample_student["phone_number"]
        assert "Session Reminder" in call_args[1]["body"]
        assert "Jane Student" in call_args[1]["body"] or "John Trainer" in call_args[1]["body"]
        assert "Gym A" in call_args[1]["body"]

        mock_dynamodb_client.put_reminder.assert_called_once()

    def test_student_not_found(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_session,
    ):
        """Test error when student not found."""
        # Setup mocks
        mock_dynamodb_client.get_student.return_value = None

        current_time = datetime.utcnow()

        # Execute and verify exception
        with pytest.raises(ValueError, match="Student .* not found"):
            _send_session_reminder(sample_session, current_time)

        mock_twilio_client.send_message.assert_not_called()

    def test_student_missing_phone(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_session,
        sample_student,
    ):
        """Test error when student has no phone number."""
        # Setup mocks
        student_no_phone = sample_student.copy()
        student_no_phone["phone_number"] = None
        mock_dynamodb_client.get_student.return_value = student_no_phone

        current_time = datetime.utcnow()

        # Execute and verify exception
        with pytest.raises(ValueError, match="has no phone number"):
            _send_session_reminder(sample_session, current_time)

        mock_twilio_client.send_message.assert_not_called()

    def test_reminder_without_location(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_session,
        sample_trainer,
        sample_student,
    ):
        """Test reminder message without location."""
        # Setup mocks
        session_no_location = sample_session.copy()
        session_no_location["location"] = ""
        
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }
        mock_dynamodb_client.put_reminder.return_value = {}

        current_time = datetime.utcnow()

        # Execute
        _send_session_reminder(session_no_location, current_time)

        # Verify - location should not be in message
        call_args = mock_twilio_client.send_message.call_args
        assert "Location:" not in call_args[1]["body"]

    def test_reminder_delivery_status_tracking(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_session,
        sample_trainer,
        sample_student,
    ):
        """Test that delivery status is tracked correctly."""
        # Setup mocks
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "delivered",
        }
        mock_dynamodb_client.put_reminder.return_value = {}

        current_time = datetime.utcnow()

        # Execute
        _send_session_reminder(sample_session, current_time)

        # Verify reminder record
        call_args = mock_dynamodb_client.put_reminder.call_args
        reminder_record = call_args[0][0]
        
        assert reminder_record["status"] == "delivered"
        assert reminder_record["reminder_type"] == "session"
        assert reminder_record["session_id"] == sample_session["session_id"]
        assert "delivered_at" in reminder_record
