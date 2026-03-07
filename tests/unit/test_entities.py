"""
Unit tests for Pydantic entity models.

Tests serialization/deserialization to/from DynamoDB format and validation logic.
"""

import pytest
from datetime import datetime, timedelta
from src.models.entities import (
    Trainer,
    Student,
    TrainerStudentLink,
    Session,
    Payment,
    ConversationState,
    MessageHistoryEntry,
    TrainerConfig,
    CalendarConfig,
    Notification,
    NotificationRecipient,
    Reminder
)


class TestTrainer:
    """Test Trainer entity model."""
    
    def test_trainer_creation(self):
        """Test creating a trainer with valid data."""
        trainer = Trainer(
            name="John Doe",
            email="john@example.com",
            business_name="John's Fitness",
            phone_number="+1234567890"
        )
        
        assert trainer.name == "John Doe"
        assert trainer.email == "john@example.com"
        assert trainer.business_name == "John's Fitness"
        assert trainer.phone_number == "+1234567890"
        assert trainer.entity_type == "TRAINER"
        assert trainer.trainer_id is not None
    
    def test_trainer_to_dynamodb(self):
        """Test converting trainer to DynamoDB format."""
        trainer = Trainer(
            trainer_id="trainer-123",
            name="John Doe",
            email="john@example.com",
            business_name="John's Fitness",
            phone_number="+1234567890"
        )
        
        item = trainer.to_dynamodb()
        
        assert item['PK'] == 'TRAINER#trainer-123'
        assert item['SK'] == 'METADATA'
        assert item['entity_type'] == 'TRAINER'
        assert item['trainer_id'] == 'trainer-123'
        assert item['name'] == 'John Doe'
        assert item['phone_number'] == '+1234567890'
    
    def test_trainer_from_dynamodb(self):
        """Test creating trainer from DynamoDB item."""
        item = {
            'trainer_id': 'trainer-123',
            'name': 'John Doe',
            'email': 'john@example.com',
            'business_name': "John's Fitness",
            'phone_number': '+1234567890',
            'created_at': '2024-01-15T10:30:00',
            'updated_at': '2024-01-15T10:30:00'
        }
        
        trainer = Trainer.from_dynamodb(item)
        
        assert trainer.trainer_id == 'trainer-123'
        assert trainer.name == 'John Doe'
        assert trainer.phone_number == '+1234567890'
    
    def test_trainer_invalid_phone_number(self):
        """Test that invalid phone numbers are rejected."""
        with pytest.raises(ValueError, match="E.164 format"):
            Trainer(
                name="John Doe",
                email="john@example.com",
                business_name="John's Fitness",
                phone_number="1234567890"  # Missing +
            )


class TestStudent:
    """Test Student entity model."""
    
    def test_student_creation(self):
        """Test creating a student with valid data."""
        student = Student(
            name="Jane Smith",
            email="jane@example.com",
            phone_number="+19876543210",
            training_goal="Weight loss"
        )
        
        assert student.name == "Jane Smith"
        assert student.training_goal == "Weight loss"
        assert student.entity_type == "STUDENT"
        assert student.student_id is not None
    
    def test_student_to_dynamodb(self):
        """Test converting student to DynamoDB format."""
        student = Student(
            student_id="student-456",
            name="Jane Smith",
            email="jane@example.com",
            phone_number="+19876543210",
            training_goal="Weight loss"
        )
        
        item = student.to_dynamodb()
        
        assert item['PK'] == 'STUDENT#student-456'
        assert item['SK'] == 'METADATA'
        assert item['entity_type'] == 'STUDENT'
        assert item['student_id'] == 'student-456'
        assert item['training_goal'] == 'Weight loss'
    
    def test_student_from_dynamodb(self):
        """Test creating student from DynamoDB item."""
        item = {
            'student_id': 'student-456',
            'name': 'Jane Smith',
            'email': 'jane@example.com',
            'phone_number': '+19876543210',
            'training_goal': 'Weight loss',
            'created_at': '2024-01-15T10:30:00',
            'updated_at': '2024-01-15T10:30:00'
        }
        
        student = Student.from_dynamodb(item)
        
        assert student.student_id == 'student-456'
        assert student.name == 'Jane Smith'
        assert student.training_goal == 'Weight loss'


class TestTrainerStudentLink:
    """Test TrainerStudentLink entity model."""
    
    def test_link_creation(self):
        """Test creating a trainer-student link."""
        link = TrainerStudentLink(
            trainer_id="trainer-123",
            student_id="student-456"
        )
        
        assert link.trainer_id == "trainer-123"
        assert link.student_id == "student-456"
        assert link.status == "active"
        assert link.entity_type == "TRAINER_STUDENT_LINK"
    
    def test_link_to_dynamodb(self):
        """Test converting link to DynamoDB format."""
        link = TrainerStudentLink(
            trainer_id="trainer-123",
            student_id="student-456"
        )
        
        item = link.to_dynamodb()
        
        assert item['PK'] == 'TRAINER#trainer-123'
        assert item['SK'] == 'STUDENT#student-456'
        assert item['entity_type'] == 'TRAINER_STUDENT_LINK'


class TestSession:
    """Test Session entity model."""
    
    def test_session_creation(self):
        """Test creating a session with valid data."""
        session_time = datetime(2024, 1, 20, 14, 0, 0)
        session = Session(
            trainer_id="trainer-123",
            student_id="student-456",
            student_name="Jane Smith",
            session_datetime=session_time,
            duration_minutes=60
        )
        
        assert session.trainer_id == "trainer-123"
        assert session.student_id == "student-456"
        assert session.duration_minutes == 60
        assert session.status == "scheduled"
        assert session.student_confirmed is False
    
    def test_session_to_dynamodb(self):
        """Test converting session to DynamoDB format."""
        session_time = datetime(2024, 1, 20, 14, 0, 0)
        session = Session(
            session_id="session-789",
            trainer_id="trainer-123",
            student_id="student-456",
            student_name="Jane Smith",
            session_datetime=session_time,
            duration_minutes=60,
            location="Gym A"
        )
        
        item = session.to_dynamodb()
        
        assert item['PK'] == 'TRAINER#trainer-123'
        assert item['SK'] == 'SESSION#session-789'
        assert item['entity_type'] == 'SESSION'
        assert item['duration_minutes'] == 60
        assert item['location'] == 'Gym A'
        assert item['session_datetime'] == session_time.isoformat()
    
    def test_session_from_dynamodb(self):
        """Test creating session from DynamoDB item."""
        item = {
            'session_id': 'session-789',
            'trainer_id': 'trainer-123',
            'student_id': 'student-456',
            'student_name': 'Jane Smith',
            'session_datetime': '2024-01-20T14:00:00',
            'duration_minutes': 60,
            'status': 'scheduled',
            'student_confirmed': False,
            'created_at': '2024-01-15T10:30:00',
            'updated_at': '2024-01-15T10:30:00'
        }
        
        session = Session.from_dynamodb(item)
        
        assert session.session_id == 'session-789'
        assert session.duration_minutes == 60
        assert session.status == 'scheduled'
    
    def test_session_duration_validation(self):
        """Test that session duration is validated."""
        with pytest.raises(ValueError):
            Session(
                trainer_id="trainer-123",
                student_id="student-456",
                student_name="Jane Smith",
                session_datetime=datetime.now(),
                duration_minutes=10  # Too short (< 15)
            )


class TestPayment:
    """Test Payment entity model."""
    
    def test_payment_creation(self):
        """Test creating a payment record."""
        payment = Payment(
            trainer_id="trainer-123",
            student_id="student-456",
            student_name="Jane Smith",
            amount=100.00,
            payment_date="2024-01-15"
        )
        
        assert payment.trainer_id == "trainer-123"
        assert payment.amount == 100.00
        assert payment.payment_status == "pending"
        assert payment.currency == "USD"
    
    def test_payment_to_dynamodb(self):
        """Test converting payment to DynamoDB format."""
        payment = Payment(
            payment_id="payment-111",
            trainer_id="trainer-123",
            student_id="student-456",
            student_name="Jane Smith",
            amount=100.00,
            payment_date="2024-01-15",
            receipt_s3_key="receipts/trainer-123/student-456/receipt.jpg"
        )
        
        item = payment.to_dynamodb()
        
        assert item['PK'] == 'TRAINER#trainer-123'
        assert item['SK'] == 'PAYMENT#payment-111'
        assert item['entity_type'] == 'PAYMENT'
        assert item['amount'] == 100.00
        assert item['receipt_s3_key'] == 'receipts/trainer-123/student-456/receipt.jpg'
    
    def test_payment_from_dynamodb(self):
        """Test creating payment from DynamoDB item."""
        item = {
            'payment_id': 'payment-111',
            'trainer_id': 'trainer-123',
            'student_id': 'student-456',
            'student_name': 'Jane Smith',
            'amount': 100.00,
            'currency': 'USD',
            'payment_date': '2024-01-15',
            'payment_status': 'confirmed',
            'confirmed_at': '2024-01-16T09:00:00',
            'created_at': '2024-01-15T10:30:00',
            'updated_at': '2024-01-16T09:00:00'
        }
        
        payment = Payment.from_dynamodb(item)
        
        assert payment.payment_id == 'payment-111'
        assert payment.amount == 100.00
        assert payment.payment_status == 'confirmed'
        assert payment.confirmed_at is not None


class TestConversationState:
    """Test ConversationState entity model."""
    
    def test_conversation_state_creation(self):
        """Test creating a conversation state."""
        ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        state = ConversationState(
            phone_number="+1234567890",
            state="UNKNOWN",
            ttl=ttl
        )
        
        assert state.phone_number == "+1234567890"
        assert state.state == "UNKNOWN"
        assert state.entity_type == "CONVERSATION_STATE"
        assert len(state.message_history) == 0
    
    def test_conversation_state_to_dynamodb(self):
        """Test converting conversation state to DynamoDB format."""
        ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        msg = MessageHistoryEntry(
            role="user",
            content="Hello",
            timestamp=datetime.utcnow()
        )
        state = ConversationState(
            phone_number="+1234567890",
            state="TRAINER_MENU",
            user_id="trainer-123",
            user_type="TRAINER",
            message_history=[msg],
            ttl=ttl
        )
        
        item = state.to_dynamodb()
        
        assert item['PK'] == 'CONVERSATION#+1234567890'
        assert item['SK'] == 'STATE'
        assert item['entity_type'] == 'CONVERSATION_STATE'
        assert item['state'] == 'TRAINER_MENU'
        assert item['user_id'] == 'trainer-123'
        assert len(item['message_history']) == 1
        assert item['ttl'] == ttl
    
    def test_conversation_state_from_dynamodb(self):
        """Test creating conversation state from DynamoDB item."""
        ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        item = {
            'phone_number': '+1234567890',
            'state': 'TRAINER_MENU',
            'user_id': 'trainer-123',
            'user_type': 'TRAINER',
            'context': {'last_action': 'register_student'},
            'message_history': [
                {
                    'role': 'user',
                    'content': 'Hello',
                    'timestamp': '2024-01-15T10:30:00'
                }
            ],
            'created_at': '2024-01-15T10:30:00',
            'updated_at': '2024-01-15T10:30:00',
            'ttl': ttl
        }
        
        state = ConversationState.from_dynamodb(item)
        
        assert state.phone_number == '+1234567890'
        assert state.state == 'TRAINER_MENU'
        assert len(state.message_history) == 1
        assert state.message_history[0].role == 'user'


class TestTrainerConfig:
    """Test TrainerConfig entity model."""
    
    def test_trainer_config_creation(self):
        """Test creating trainer configuration."""
        config = TrainerConfig(
            trainer_id="trainer-123"
        )
        
        assert config.trainer_id == "trainer-123"
        assert config.reminder_hours == 24
        assert config.payment_reminder_day == 1
        assert config.payment_reminders_enabled is True
        assert config.session_reminders_enabled is True
    
    def test_trainer_config_to_dynamodb(self):
        """Test converting trainer config to DynamoDB format."""
        config = TrainerConfig(
            trainer_id="trainer-123",
            reminder_hours=48,
            payment_reminder_day=15
        )
        
        item = config.to_dynamodb()
        
        assert item['PK'] == 'TRAINER#trainer-123'
        assert item['SK'] == 'CONFIG'
        assert item['entity_type'] == 'TRAINER_CONFIG'
        assert item['reminder_hours'] == 48
        assert item['payment_reminder_day'] == 15
    
    def test_trainer_config_validation(self):
        """Test that config values are validated."""
        with pytest.raises(ValueError):
            TrainerConfig(
                trainer_id="trainer-123",
                reminder_hours=50  # Too high (> 48)
            )
        
        with pytest.raises(ValueError):
            TrainerConfig(
                trainer_id="trainer-123",
                payment_reminder_day=30  # Too high (> 28)
            )


class TestCalendarConfig:
    """Test CalendarConfig entity model."""
    
    def test_calendar_config_creation(self):
        """Test creating calendar configuration."""
        config = CalendarConfig(
            trainer_id="trainer-123",
            provider="google",
            encrypted_refresh_token=b"encrypted_token_data",
            scope="https://www.googleapis.com/auth/calendar"
        )
        
        assert config.trainer_id == "trainer-123"
        assert config.provider == "google"
        assert config.entity_type == "CALENDAR_CONFIG"
    
    def test_calendar_config_to_dynamodb(self):
        """Test converting calendar config to DynamoDB format."""
        config = CalendarConfig(
            trainer_id="trainer-123",
            provider="outlook",
            encrypted_refresh_token=b"encrypted_token_data",
            scope="Calendars.ReadWrite",
            calendar_id="primary"
        )
        
        item = config.to_dynamodb()
        
        assert item['PK'] == 'TRAINER#trainer-123'
        assert item['SK'] == 'CALENDAR_CONFIG'
        assert item['entity_type'] == 'CALENDAR_CONFIG'
        assert item['provider'] == 'outlook'
        assert item['calendar_id'] == 'primary'


class TestNotification:
    """Test Notification entity model."""
    
    def test_notification_creation(self):
        """Test creating a notification."""
        recipient = NotificationRecipient(
            student_id="student-456",
            phone_number="+19876543210"
        )
        notification = Notification(
            trainer_id="trainer-123",
            message="Class cancelled tomorrow",
            recipient_count=1,
            recipients=[recipient]
        )
        
        assert notification.trainer_id == "trainer-123"
        assert notification.message == "Class cancelled tomorrow"
        assert notification.status == "queued"
        assert len(notification.recipients) == 1
    
    def test_notification_to_dynamodb(self):
        """Test converting notification to DynamoDB format."""
        recipient = NotificationRecipient(
            student_id="student-456",
            phone_number="+19876543210",
            status="sent"
        )
        notification = Notification(
            notification_id="notif-999",
            trainer_id="trainer-123",
            message="Class cancelled tomorrow",
            recipient_count=1,
            recipients=[recipient]
        )
        
        item = notification.to_dynamodb()
        
        assert item['PK'] == 'TRAINER#trainer-123'
        assert item['SK'] == 'NOTIFICATION#notif-999'
        assert item['entity_type'] == 'NOTIFICATION'
        assert len(item['recipients']) == 1
        assert item['recipients'][0]['status'] == 'sent'


class TestReminder:
    """Test Reminder entity model."""
    
    def test_reminder_creation(self):
        """Test creating a reminder."""
        reminder = Reminder(
            session_id="session-789",
            reminder_type="session",
            recipient_phone="+1234567890",
            status="sent"
        )
        
        assert reminder.session_id == "session-789"
        assert reminder.reminder_type == "session"
        assert reminder.status == "sent"
        assert reminder.entity_type == "REMINDER"
    
    def test_reminder_to_dynamodb(self):
        """Test converting reminder to DynamoDB format."""
        reminder = Reminder(
            reminder_id="reminder-555",
            session_id="session-789",
            reminder_type="session",
            recipient_phone="+1234567890",
            status="delivered",
            delivered_at=datetime.utcnow()
        )
        
        item = reminder.to_dynamodb()
        
        assert item['PK'] == 'SESSION#session-789'
        assert item['SK'] == 'REMINDER#reminder-555'
        assert item['entity_type'] == 'REMINDER'
        assert item['status'] == 'delivered'
        assert 'delivered_at' in item
