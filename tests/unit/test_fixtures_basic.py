"""
Basic tests to verify fixture system works correctly.

These tests validate that the entity factories, AWS client fixtures,
and mock fixtures are properly configured and functional.
"""

import pytest
from datetime import datetime, timedelta

from tests.fixtures.factories import (
    TrainerFactory,
    StudentFactory,
    SessionFactory,
    PaymentFactory,
    ConversationStateFactory,
    TrainerConfigFactory,
    NotificationFactory,
    MenuContextFactory
)


@pytest.mark.unit
def test_trainer_factory_creates_valid_trainer():
    """Test TrainerFactory creates valid Trainer entities."""
    trainer = TrainerFactory.create()
    
    assert trainer.trainer_id is not None
    assert trainer.phone_number.startswith("+55")
    assert trainer.name == "Test Trainer"
    assert trainer.email is not None
    assert trainer.business_name == "Test Fitness"


@pytest.mark.unit
def test_trainer_factory_with_custom_values():
    """Test TrainerFactory accepts custom values."""
    trainer = TrainerFactory.create(
        name="Custom Trainer",
        email="custom@test.com",
        phone_number="+5511987654321"
    )
    
    assert trainer.name == "Custom Trainer"
    assert trainer.email == "custom@test.com"
    assert trainer.phone_number == "+5511987654321"


@pytest.mark.unit
def test_student_factory_creates_valid_student():
    """Test StudentFactory creates valid Student entities."""
    student = StudentFactory.create()
    
    assert student.student_id is not None
    assert student.phone_number.startswith("+55")
    assert student.name == "Test Student"
    assert student.email is not None
    assert student.training_goal == "Perder peso"


@pytest.mark.unit
def test_session_factory_creates_valid_session():
    """Test SessionFactory creates valid Session entities."""
    session = SessionFactory.create()
    
    assert session.session_id is not None
    assert session.trainer_id is not None
    assert session.student_id is not None
    assert session.student_name == "Test Student"
    assert session.duration_minutes == 60
    assert session.status == "scheduled"
    assert session.session_datetime > datetime.utcnow()


@pytest.mark.unit
def test_payment_factory_creates_valid_payment():
    """Test PaymentFactory creates valid Payment entities."""
    payment = PaymentFactory.create()
    
    assert payment.payment_id is not None
    assert payment.trainer_id is not None
    assert payment.student_id is not None
    assert payment.student_name == "Test Student"
    assert payment.amount == 100.00
    assert payment.currency == "BRL"
    assert payment.payment_status == "pending"


@pytest.mark.unit
def test_conversation_state_factory_creates_valid_state():
    """Test ConversationStateFactory creates valid ConversationState entities."""
    state = ConversationStateFactory.create()
    
    assert state.phone_number.startswith("+55")
    assert state.state == "UNKNOWN"
    assert state.context == {}
    assert state.message_history == []
    assert state.ttl > int(datetime.utcnow().timestamp())


@pytest.mark.unit
def test_trainer_config_factory_creates_valid_config():
    """Test TrainerConfigFactory creates valid TrainerConfig entities."""
    config = TrainerConfigFactory.create()
    
    assert config.trainer_id is not None
    assert config.reminder_hours == 24
    assert config.payment_reminder_day == 1
    assert config.payment_reminders_enabled is True
    assert config.session_reminders_enabled is True
    assert config.timezone == "America/Sao_Paulo"


@pytest.mark.unit
def test_notification_factory_creates_valid_notification():
    """Test NotificationFactory creates valid Notification entities."""
    notification = NotificationFactory.create()
    
    assert notification.notification_id is not None
    assert notification.trainer_id is not None
    assert notification.message == "Test notification"
    assert notification.recipient_count == 0
    assert notification.status == "queued"
    assert notification.recipients == []


@pytest.mark.unit
def test_menu_context_factory_creates_valid_context():
    """Test MenuContextFactory creates valid MenuContext entities."""
    context = MenuContextFactory.create()
    
    assert context.phone_number.startswith("+55")
    assert context.user_id is not None
    assert context.user_type == "TRAINER"
    assert context.menu_enabled is True
    assert context.current_menu == "main"
    assert context.navigation_stack == []


@pytest.mark.unit
def test_mock_twilio_client(mock_twilio):
    """Test MockTwilioClient tracks messages."""
    result = mock_twilio.send_message(
        to="+5511999999999",
        from_="+5511888888888",
        body="Test message"
    )
    
    assert result["sid"] is not None
    assert result["to"] == "+5511999999999"
    assert result["body"] == "Test message"
    assert len(mock_twilio.messages_sent) == 1


@pytest.mark.unit
def test_mock_calendar_client(mock_calendar):
    """Test MockCalendarClient tracks events."""
    event = mock_calendar.create_event({
        "summary": "Test Session",
        "start": {"dateTime": "2024-12-01T10:00:00Z"},
        "end": {"dateTime": "2024-12-01T11:00:00Z"}
    })
    
    assert event["id"] is not None
    assert event["summary"] == "Test Session"
    assert len(mock_calendar.events) == 1


@pytest.mark.unit
def test_dynamodb_client_fixture(dynamodb_client):
    """Test DynamoDB client fixture creates table."""
    response = dynamodb_client.describe_table(TableName="fitagent-main")
    assert response["Table"]["TableName"] == "fitagent-main"


@pytest.mark.unit
def test_s3_client_fixture(s3_client):
    """Test S3 client fixture creates bucket."""
    response = s3_client.list_buckets()
    bucket_names = [b["Name"] for b in response["Buckets"]]
    assert "fitagent-receipts-local" in bucket_names


@pytest.mark.unit
def test_sqs_client_fixture(sqs_client):
    """Test SQS client fixture creates queues."""
    response = sqs_client.list_queues()
    queue_urls = response.get("QueueUrls", [])
    
    assert any("fitagent-messages.fifo" in url for url in queue_urls)
    assert any("fitagent-notifications.fifo" in url for url in queue_urls)
