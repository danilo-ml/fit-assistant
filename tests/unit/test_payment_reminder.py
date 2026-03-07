"""
Unit tests for payment reminder Lambda function.

Tests payment reminder querying, grouping, and delivery.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.handlers.payment_reminder import (
    lambda_handler,
    _get_unpaid_payments_previous_month,
    _group_payments_by_trainer_and_student,
    _send_payment_reminder,
)


@pytest.fixture
def eventbridge_event():
    """Sample EventBridge scheduled event."""
    return {
        "version": "0",
        "id": "event-456",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "time": "2024-02-01T10:00:00Z",
        "region": "us-east-1",
        "resources": ["arn:aws:events:us-east-1:123456789012:rule/payment-reminders"],
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = "payment-reminder"
    context.request_id = "lambda-req-456"
    return context


@pytest.fixture
def mock_dynamodb_client():
    """Mock DynamoDBClient."""
    with patch("src.handlers.payment_reminder.dynamodb_client") as mock:
        yield mock


@pytest.fixture
def mock_twilio_client():
    """Mock TwilioClient."""
    with patch("src.handlers.payment_reminder.twilio_client") as mock:
        yield mock


@pytest.fixture
def sample_payment():
    """Sample unpaid payment record."""
    return {
        "PK": "TRAINER#trainer-123",
        "SK": "PAYMENT#payment-789",
        "entity_type": "PAYMENT",
        "payment_id": "payment-789",
        "trainer_id": "trainer-123",
        "student_id": "student-456",
        "student_name": "Jane Student",
        "amount": 100.00,
        "currency": "USD",
        "payment_date": "2024-01-15",
        "payment_status": "pending",
        "session_id": "session-123",
        "created_at": "2024-01-15T10:00:00Z",
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
        "business_name": "FitPro Training",
        "email": "john@example.com",
        "phone_number": "+1234567890",
    }


@pytest.fixture
def sample_student():
    """Sample student record."""
    return {
        "PK": "STUDENT#student-456",
        "SK": "METADATA",
        "entity_type": "STUDENT",
        "student_id": "student-456",
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
        "payment_reminder_day": 1,
        "payment_reminders_enabled": True,
    }


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    def test_successful_reminder_processing(
        self,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_payment,
        sample_trainer,
        sample_student,
        sample_trainer_config,
    ):
        """Test successful processing of payment reminders."""
        # Setup mocks
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_payment],
        }
        mock_dynamodb_client._deserialize_item.return_value = sample_payment
        mock_dynamodb_client.get_trainer_config.return_value = sample_trainer_config
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_dynamodb_client.put_notification.return_value = {}

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
        mock_dynamodb_client.put_notification.assert_called_once()

    def test_no_unpaid_payments(
        self,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
    ):
        """Test when no unpaid payments exist."""
        # Setup mocks - no payments found
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
        sample_payment,
    ):
        """Test when payment reminders are disabled for a trainer."""
        # Setup mocks
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_payment],
        }
        mock_dynamodb_client._deserialize_item.return_value = sample_payment
        
        # Reminders disabled
        disabled_config = {
            "trainer_id": "trainer-123",
            "payment_reminders_enabled": False,
        }
        mock_dynamodb_client.get_trainer_config.return_value = disabled_config

        # Execute
        result = lambda_handler(eventbridge_event, lambda_context)

        # Verify - no reminders sent
        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 0
        mock_twilio_client.send_message.assert_not_called()

    def test_multiple_students_multiple_payments(
        self,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_payment,
        sample_trainer,
        sample_trainer_config,
    ):
        """Test handling multiple students with multiple unpaid payments."""
        # Create multiple payments for different students
        payment_1 = sample_payment.copy()
        payment_2 = sample_payment.copy()
        payment_2["payment_id"] = "payment-790"
        payment_2["amount"] = 150.00
        
        payment_3 = sample_payment.copy()
        payment_3["payment_id"] = "payment-791"
        payment_3["student_id"] = "student-999"
        payment_3["student_name"] = "Bob Student"
        payment_3["amount"] = 200.00

        # Setup mocks
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [payment_1, payment_2, payment_3],
        }
        mock_dynamodb_client._deserialize_item.side_effect = [
            payment_1,
            payment_2,
            payment_3,
        ]
        mock_dynamodb_client.get_trainer_config.return_value = sample_trainer_config
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        
        # Two different students
        student_1 = {
            "student_id": "student-456",
            "name": "Jane Student",
            "phone_number": "+9876543210",
        }
        student_2 = {
            "student_id": "student-999",
            "name": "Bob Student",
            "phone_number": "+5555555555",
        }
        mock_dynamodb_client.get_student.side_effect = [student_1, student_2]
        mock_dynamodb_client.put_notification.return_value = {}

        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }

        # Execute
        result = lambda_handler(eventbridge_event, lambda_context)

        # Verify - 2 reminders sent (one per student)
        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 2
        assert mock_twilio_client.send_message.call_count == 2

    def test_partial_failure_handling(
        self,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_payment,
        sample_trainer,
        sample_trainer_config,
    ):
        """Test handling when some reminders fail."""
        # Create payments for two students
        payment_1 = sample_payment.copy()
        payment_2 = sample_payment.copy()
        payment_2["payment_id"] = "payment-999"
        payment_2["student_id"] = "student-999"

        # Setup mocks
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [payment_1, payment_2],
        }
        mock_dynamodb_client._deserialize_item.side_effect = [payment_1, payment_2]
        mock_dynamodb_client.get_trainer_config.return_value = sample_trainer_config
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        
        # First student succeeds, second fails
        student_1 = {
            "student_id": "student-456",
            "name": "Jane Student",
            "phone_number": "+9876543210",
        }
        mock_dynamodb_client.get_student.side_effect = [
            student_1,
            None,  # Student not found
        ]
        
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }
        mock_dynamodb_client.put_notification.return_value = {}

        # Execute
        result = lambda_handler(eventbridge_event, lambda_context)

        # Verify - one success, one failure
        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 1
        assert result["body"]["reminders_failed"] == 1


class TestGroupPaymentsByTrainerAndStudent:
    """Tests for _group_payments_by_trainer_and_student function."""

    def test_single_trainer_single_student(self, sample_payment):
        """Test grouping with single trainer and student."""
        payments = [sample_payment]

        result = _group_payments_by_trainer_and_student(payments)

        assert len(result) == 1
        assert "trainer-123" in result
        assert "student-456" in result["trainer-123"]
        assert len(result["trainer-123"]["student-456"]) == 1

    def test_single_trainer_multiple_students(self, sample_payment):
        """Test grouping with single trainer and multiple students."""
        payment_1 = sample_payment.copy()
        payment_2 = sample_payment.copy()
        payment_2["payment_id"] = "payment-790"
        payment_2["student_id"] = "student-999"

        payments = [payment_1, payment_2]

        result = _group_payments_by_trainer_and_student(payments)

        assert len(result) == 1
        assert "trainer-123" in result
        assert len(result["trainer-123"]) == 2
        assert "student-456" in result["trainer-123"]
        assert "student-999" in result["trainer-123"]

    def test_multiple_trainers_multiple_students(self, sample_payment):
        """Test grouping with multiple trainers and students."""
        payment_1 = sample_payment.copy()
        payment_2 = sample_payment.copy()
        payment_2["payment_id"] = "payment-790"
        payment_2["trainer_id"] = "trainer-999"

        payments = [payment_1, payment_2]

        result = _group_payments_by_trainer_and_student(payments)

        assert len(result) == 2
        assert "trainer-123" in result
        assert "trainer-999" in result

    def test_multiple_payments_same_student(self, sample_payment):
        """Test grouping multiple payments for same student."""
        payment_1 = sample_payment.copy()
        payment_2 = sample_payment.copy()
        payment_2["payment_id"] = "payment-790"
        payment_2["amount"] = 150.00

        payments = [payment_1, payment_2]

        result = _group_payments_by_trainer_and_student(payments)

        assert len(result["trainer-123"]["student-456"]) == 2


class TestSendPaymentReminder:
    """Tests for _send_payment_reminder function."""

    def test_successful_reminder_send(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_payment,
        sample_trainer,
        sample_student,
    ):
        """Test successful payment reminder sending."""
        # Setup mocks
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }
        mock_dynamodb_client.put_notification.return_value = {}

        current_date = date(2024, 2, 1)
        payments = [sample_payment]

        # Execute
        _send_payment_reminder("trainer-123", "student-456", payments, current_date)

        # Verify
        mock_twilio_client.send_message.assert_called_once()
        call_args = mock_twilio_client.send_message.call_args
        assert call_args[1]["to"] == sample_student["phone_number"]
        assert "Payment Reminder" in call_args[1]["body"]
        assert "Jane Student" in call_args[1]["body"]
        assert "John Trainer" in call_args[1]["body"]
        assert "100.00" in call_args[1]["body"]
        assert "1 unpaid session" in call_args[1]["body"]

        mock_dynamodb_client.put_notification.assert_called_once()

    def test_multiple_unpaid_sessions(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_payment,
        sample_trainer,
        sample_student,
    ):
        """Test reminder with multiple unpaid sessions."""
        # Create multiple payments
        payment_1 = sample_payment.copy()
        payment_2 = sample_payment.copy()
        payment_2["payment_id"] = "payment-790"
        payment_2["amount"] = 150.00
        payment_3 = sample_payment.copy()
        payment_3["payment_id"] = "payment-791"
        payment_3["amount"] = 75.00

        payments = [payment_1, payment_2, payment_3]

        # Setup mocks
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }
        mock_dynamodb_client.put_notification.return_value = {}

        current_date = date(2024, 2, 1)

        # Execute
        _send_payment_reminder("trainer-123", "student-456", payments, current_date)

        # Verify
        call_args = mock_twilio_client.send_message.call_args
        message_body = call_args[1]["body"]
        
        # Total should be 325.00
        assert "325.00" in message_body
        assert "3 unpaid sessions" in message_body

    def test_student_not_found(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_payment,
    ):
        """Test error when student not found."""
        # Setup mocks
        mock_dynamodb_client.get_student.return_value = None

        current_date = date(2024, 2, 1)
        payments = [sample_payment]

        # Execute and verify exception
        with pytest.raises(ValueError, match="Student .* not found"):
            _send_payment_reminder("trainer-123", "student-456", payments, current_date)

        mock_twilio_client.send_message.assert_not_called()

    def test_student_missing_phone(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_payment,
        sample_student,
    ):
        """Test error when student has no phone number."""
        # Setup mocks
        student_no_phone = sample_student.copy()
        student_no_phone["phone_number"] = None
        mock_dynamodb_client.get_student.return_value = student_no_phone

        current_date = date(2024, 2, 1)
        payments = [sample_payment]

        # Execute and verify exception
        with pytest.raises(ValueError, match="has no phone number"):
            _send_payment_reminder("trainer-123", "student-456", payments, current_date)

        mock_twilio_client.send_message.assert_not_called()

    def test_reminder_with_business_name(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_payment,
        sample_trainer,
        sample_student,
    ):
        """Test reminder includes business name when available."""
        # Setup mocks
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }
        mock_dynamodb_client.put_notification.return_value = {}

        current_date = date(2024, 2, 1)
        payments = [sample_payment]

        # Execute
        _send_payment_reminder("trainer-123", "student-456", payments, current_date)

        # Verify business name in message
        call_args = mock_twilio_client.send_message.call_args
        assert "FitPro Training" in call_args[1]["body"]

    def test_notification_record_creation(
        self,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_payment,
        sample_trainer,
        sample_student,
    ):
        """Test that notification record is created correctly."""
        # Setup mocks
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "delivered",
        }
        mock_dynamodb_client.put_notification.return_value = {}

        current_date = date(2024, 2, 1)
        payments = [sample_payment]

        # Execute
        _send_payment_reminder("trainer-123", "student-456", payments, current_date)

        # Verify notification record
        call_args = mock_dynamodb_client.put_notification.call_args
        notification_record = call_args[0][0]
        
        assert notification_record["entity_type"] == "NOTIFICATION"
        assert notification_record["notification_type"] == "payment_reminder"
        assert notification_record["trainer_id"] == "trainer-123"
        assert notification_record["total_amount"] == 100.00
        assert notification_record["session_count"] == 1
        assert len(notification_record["payment_ids"]) == 1
        assert notification_record["status"] == "delivered"
        assert notification_record["recipients"][0]["student_id"] == "student-456"
