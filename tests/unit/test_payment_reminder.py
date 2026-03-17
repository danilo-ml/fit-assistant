"""
Unit tests for payment reminder Lambda function.

Tests payment reminder querying, grouping, and delivery.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.handlers.payment_reminder import (
    lambda_handler,
    _get_all_active_students,
    _send_reminder,
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
    """Sample student record with payment_due_day."""
    return {
        "PK": "STUDENT#student-456",
        "SK": "METADATA",
        "entity_type": "STUDENT",
        "student_id": "student-456",
        "name": "Jane Student",
        "email": "jane@example.com",
        "phone_number": "+9876543210",
        "payment_due_day": 5,
    }


@pytest.fixture
def sample_link():
    """Sample active trainer-student link."""
    return {
        "PK": "TRAINER#trainer-123",
        "SK": "STUDENT#student-456",
        "entity_type": "TRAINER_STUDENT_LINK",
        "trainer_id": "trainer-123",
        "student_id": "student-456",
        "status": "active",
    }


class TestLambdaHandler:
    """Tests for lambda_handler function."""

    @patch("src.handlers.payment_reminder.datetime")
    def test_successful_reminder_on_due_day(
        self,
        mock_datetime,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_trainer,
        sample_student,
        sample_link,
    ):
        """Test successful reminder when today matches payment_due_day."""
        # Set today to day 5 to match student's payment_due_day
        mock_today = date(2024, 2, 5)
        mock_datetime.utcnow.return_value = datetime(2024, 2, 5, 10, 0, 0)

        # Scan returns active links
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_link],
        }
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }

        result = lambda_handler(eventbridge_event, lambda_context)

        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 1
        assert result["body"]["reminders_failed"] == 0
        mock_twilio_client.send_message.assert_called_once()

    @patch("src.handlers.payment_reminder.datetime")
    def test_advance_reminder_3_days_before(
        self,
        mock_datetime,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_trainer,
        sample_student,
        sample_link,
    ):
        """Test advance reminder sent 3 days before due day."""
        # Due day is 5, so advance reminder on day 2
        mock_datetime.utcnow.return_value = datetime(2024, 2, 2, 10, 0, 0)

        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_link],
        }
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = sample_trainer
        mock_twilio_client.send_message.return_value = {
            "message_sid": "SM999",
            "status": "sent",
        }

        result = lambda_handler(eventbridge_event, lambda_context)

        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 1

    @patch("src.handlers.payment_reminder.datetime")
    def test_no_reminder_when_not_due(
        self,
        mock_datetime,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_student,
        sample_link,
    ):
        """Test no reminder sent when today doesn't match due day or advance."""
        # Due day is 5, today is 10 — no match
        mock_datetime.utcnow.return_value = datetime(2024, 2, 10, 10, 0, 0)

        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_link],
        }
        mock_dynamodb_client.get_student.return_value = sample_student

        result = lambda_handler(eventbridge_event, lambda_context)

        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 0
        mock_twilio_client.send_message.assert_not_called()

    @patch("src.handlers.payment_reminder.datetime")
    def test_no_active_students(
        self,
        mock_datetime,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
    ):
        """Test when no active students exist."""
        mock_datetime.utcnow.return_value = datetime(2024, 2, 5, 10, 0, 0)
        mock_dynamodb_client.table.scan.return_value = {"Items": []}

        result = lambda_handler(eventbridge_event, lambda_context)

        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 0
        mock_twilio_client.send_message.assert_not_called()

    @patch("src.handlers.payment_reminder.datetime")
    def test_student_without_payment_due_day_skipped(
        self,
        mock_datetime,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_link,
    ):
        """Test that students without payment_due_day are skipped."""
        mock_datetime.utcnow.return_value = datetime(2024, 2, 5, 10, 0, 0)

        student_no_due = {
            "student_id": "student-456",
            "name": "Jane Student",
            "phone_number": "+9876543210",
        }
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_link],
        }
        mock_dynamodb_client.get_student.return_value = student_no_due

        result = lambda_handler(eventbridge_event, lambda_context)

        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 0
        mock_twilio_client.send_message.assert_not_called()

    @patch("src.handlers.payment_reminder.datetime")
    def test_student_without_phone_skipped(
        self,
        mock_datetime,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_link,
    ):
        """Test that students without phone number are skipped."""
        mock_datetime.utcnow.return_value = datetime(2024, 2, 5, 10, 0, 0)

        student_no_phone = {
            "student_id": "student-456",
            "name": "Jane Student",
            "payment_due_day": 5,
        }
        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_link],
        }
        mock_dynamodb_client.get_student.return_value = student_no_phone

        result = lambda_handler(eventbridge_event, lambda_context)

        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 0
        mock_twilio_client.send_message.assert_not_called()

    @patch("src.handlers.payment_reminder.datetime")
    def test_trainer_not_found_skipped(
        self,
        mock_datetime,
        eventbridge_event,
        lambda_context,
        mock_dynamodb_client,
        mock_twilio_client,
        sample_student,
        sample_link,
    ):
        """Test that trainers not found in DB are skipped."""
        mock_datetime.utcnow.return_value = datetime(2024, 2, 5, 10, 0, 0)

        mock_dynamodb_client.table.scan.return_value = {
            "Items": [sample_link],
        }
        mock_dynamodb_client.get_student.return_value = sample_student
        mock_dynamodb_client.get_trainer.return_value = None

        result = lambda_handler(eventbridge_event, lambda_context)

        assert result["statusCode"] == 200
        assert result["body"]["reminders_sent"] == 0
        mock_twilio_client.send_message.assert_not_called()


class TestGetAllActiveStudents:
    """Tests for _get_all_active_students function."""

    def test_returns_students_grouped_by_trainer(
        self, mock_dynamodb_client
    ):
        """Test that active students are grouped by trainer_id."""
        links = [
            {
                "entity_type": "TRAINER_STUDENT_LINK",
                "trainer_id": "trainer-1",
                "student_id": "student-1",
                "status": "active",
            },
            {
                "entity_type": "TRAINER_STUDENT_LINK",
                "trainer_id": "trainer-1",
                "student_id": "student-2",
                "status": "active",
            },
            {
                "entity_type": "TRAINER_STUDENT_LINK",
                "trainer_id": "trainer-2",
                "student_id": "student-3",
                "status": "active",
            },
        ]
        mock_dynamodb_client.table.scan.return_value = {"Items": links}
        mock_dynamodb_client.get_student.side_effect = [
            {"student_id": "student-1", "name": "S1"},
            {"student_id": "student-2", "name": "S2"},
            {"student_id": "student-3", "name": "S3"},
        ]

        result = _get_all_active_students()

        assert len(result) == 2
        assert len(result["trainer-1"]) == 2
        assert len(result["trainer-2"]) == 1

    def test_empty_scan_returns_empty_dict(self, mock_dynamodb_client):
        """Test empty result when no active links exist."""
        mock_dynamodb_client.table.scan.return_value = {"Items": []}

        result = _get_all_active_students()

        assert result == {}

    def test_skips_links_without_trainer_or_student_id(
        self, mock_dynamodb_client
    ):
        """Test that links missing trainer_id or student_id are skipped."""
        links = [
            {"entity_type": "TRAINER_STUDENT_LINK", "status": "active"},
            {
                "entity_type": "TRAINER_STUDENT_LINK",
                "trainer_id": "trainer-1",
                "status": "active",
            },
        ]
        mock_dynamodb_client.table.scan.return_value = {"Items": links}

        result = _get_all_active_students()

        assert result == {}
        mock_dynamodb_client.get_student.assert_not_called()

    def test_handles_pagination(self, mock_dynamodb_client):
        """Test that paginated scan results are handled."""
        link1 = {
            "entity_type": "TRAINER_STUDENT_LINK",
            "trainer_id": "trainer-1",
            "student_id": "student-1",
            "status": "active",
        }
        link2 = {
            "entity_type": "TRAINER_STUDENT_LINK",
            "trainer_id": "trainer-1",
            "student_id": "student-2",
            "status": "active",
        }
        mock_dynamodb_client.table.scan.side_effect = [
            {"Items": [link1], "LastEvaluatedKey": {"PK": "x"}},
            {"Items": [link2]},
        ]
        mock_dynamodb_client.get_student.side_effect = [
            {"student_id": "student-1", "name": "S1"},
            {"student_id": "student-2", "name": "S2"},
        ]

        result = _get_all_active_students()

        assert len(result["trainer-1"]) == 2
        assert mock_dynamodb_client.table.scan.call_count == 2


class TestSendReminder:
    """Tests for _send_reminder function."""

    def test_due_today_message_content(self, mock_twilio_client):
        """Test due-today reminder message content."""
        _send_reminder(
            student_phone="+9876543210",
            student_name="Jane Student",
            trainer_name="John Trainer",
            business_name="FitPro Training",
            due_day=5,
            reminder_type="due_today",
        )

        mock_twilio_client.send_message.assert_called_once()
        call_args = mock_twilio_client.send_message.call_args
        body = call_args[1]["body"]
        assert call_args[1]["to"] == "+9876543210"
        assert "Vencimento Hoje" in body
        assert "Jane Student" in body
        assert "John Trainer" in body
        assert "FitPro Training" in body

    def test_advance_message_content(self, mock_twilio_client):
        """Test advance reminder message content."""
        _send_reminder(
            student_phone="+9876543210",
            student_name="Jane Student",
            trainer_name="John Trainer",
            business_name="FitPro Training",
            due_day=5,
            reminder_type="advance",
        )

        mock_twilio_client.send_message.assert_called_once()
        call_args = mock_twilio_client.send_message.call_args
        body = call_args[1]["body"]
        assert "Lembrete de Pagamento" in body
        assert "dia 5" in body
        assert "FitPro Training" in body

    def test_message_without_business_name(self, mock_twilio_client):
        """Test reminder when trainer has no business name."""
        _send_reminder(
            student_phone="+9876543210",
            student_name="Jane Student",
            trainer_name="John Trainer",
            business_name="",
            due_day=5,
            reminder_type="due_today",
        )

        call_args = mock_twilio_client.send_message.call_args
        body = call_args[1]["body"]
        assert "John Trainer" in body
        assert "FitPro" not in body
