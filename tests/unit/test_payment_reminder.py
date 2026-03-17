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
