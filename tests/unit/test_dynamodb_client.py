"""
Unit tests for DynamoDB client abstraction layer.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from moto import mock_aws
import boto3
from src.models.dynamodb_client import DynamoDBClient
from src.models.entities import (
    Trainer, Student, TrainerStudentLink, Session, Payment,
    ConversationState, TrainerConfig, MessageHistoryEntry
)


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table for testing."""
    with mock_aws():
        # Create DynamoDB resource
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create table with GSIs
        table = dynamodb.create_table(
            TableName='fitagent-test',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                {'AttributeName': 'phone_number', 'AttributeType': 'S'},
                {'AttributeName': 'entity_type', 'AttributeType': 'S'},
                {'AttributeName': 'trainer_id', 'AttributeType': 'S'},
                {'AttributeName': 'session_datetime', 'AttributeType': 'S'},
                {'AttributeName': 'payment_status', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'phone-number-index',
                    'KeySchema': [
                        {'AttributeName': 'phone_number', 'KeyType': 'HASH'},
                        {'AttributeName': 'entity_type', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                },
                {
                    'IndexName': 'session-date-index',
                    'KeySchema': [
                        {'AttributeName': 'trainer_id', 'KeyType': 'HASH'},
                        {'AttributeName': 'session_datetime', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                },
                {
                    'IndexName': 'payment-status-index',
                    'KeySchema': [
                        {'AttributeName': 'trainer_id', 'KeyType': 'HASH'},
                        {'AttributeName': 'payment_status', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        yield table


@pytest.fixture
def db_client(dynamodb_table):
    """Create DynamoDB client instance."""
    return DynamoDBClient(table_name='fitagent-test')


class TestCoreOperations:
    """Test core CRUD operations."""
    
    def test_put_and_get_item(self, db_client):
        """Test putting and getting an item."""
        item = {
            'PK': 'TEST#123',
            'SK': 'METADATA',
            'name': 'Test Item',
            'value': 42
        }
        
        # Put item
        result = db_client.put_item(item)
        assert result == item
        
        # Get item
        retrieved = db_client.get_item('TEST#123', 'METADATA')
        assert retrieved is not None
        assert retrieved['name'] == 'Test Item'
        assert retrieved['value'] == 42
    
    def test_get_nonexistent_item(self, db_client):
        """Test getting an item that doesn't exist."""
        result = db_client.get_item('NONEXISTENT#123', 'METADATA')
        assert result is None
    
    def test_delete_item(self, db_client):
        """Test deleting an item."""
        item = {
            'PK': 'TEST#456',
            'SK': 'METADATA',
            'name': 'To Delete'
        }
        
        # Put and verify
        db_client.put_item(item)
        assert db_client.get_item('TEST#456', 'METADATA') is not None
        
        # Delete and verify
        result = db_client.delete_item('TEST#456', 'METADATA')
        assert result is True
        assert db_client.get_item('TEST#456', 'METADATA') is None
    
    def test_decimal_serialization(self, db_client):
        """Test that floats are properly serialized to Decimal."""
        item = {
            'PK': 'TEST#789',
            'SK': 'METADATA',
            'amount': 99.99,
            'nested': {'price': 49.50}
        }
        
        db_client.put_item(item)
        retrieved = db_client.get_item('TEST#789', 'METADATA')
        
        assert retrieved['amount'] == 99.99
        assert retrieved['nested']['price'] == 49.50


class TestTrainerOperations:
    """Test trainer-related operations."""
    
    def test_put_and_get_trainer(self, db_client):
        """Test creating and retrieving a trainer."""
        trainer = Trainer(
            name='John Doe',
            email='john@example.com',
            business_name='Fit Training',
            phone_number='+12345678901'
        )
        
        db_client.put_trainer(trainer.to_dynamodb())
        retrieved = db_client.get_trainer(trainer.trainer_id)
        
        assert retrieved is not None
        assert retrieved['name'] == 'John Doe'
        assert retrieved['email'] == 'john@example.com'
        assert retrieved['trainer_id'] == trainer.trainer_id
    
    def test_put_and_get_trainer_config(self, db_client):
        """Test creating and retrieving trainer configuration."""
        config = TrainerConfig(
            trainer_id='trainer123',
            reminder_hours=48,
            payment_reminder_day=15
        )
        
        db_client.put_trainer_config(config.to_dynamodb())
        retrieved = db_client.get_trainer_config('trainer123')
        
        assert retrieved is not None
        assert retrieved['reminder_hours'] == 48
        assert retrieved['payment_reminder_day'] == 15


class TestStudentOperations:
    """Test student-related operations."""
    
    def test_put_and_get_student(self, db_client):
        """Test creating and retrieving a student."""
        student = Student(
            name='Jane Smith',
            email='jane@example.com',
            phone_number='+19876543210',
            training_goal='Weight loss'
        )
        
        db_client.put_student(student.to_dynamodb())
        retrieved = db_client.get_student(student.student_id)
        
        assert retrieved is not None
        assert retrieved['name'] == 'Jane Smith'
        assert retrieved['training_goal'] == 'Weight loss'


class TestTrainerStudentLinks:
    """Test trainer-student relationship operations."""
    
    def test_create_and_get_link(self, db_client):
        """Test creating and retrieving a trainer-student link."""
        link = TrainerStudentLink(
            trainer_id='trainer123',
            student_id='student456'
        )
        
        db_client.put_trainer_student_link(link.to_dynamodb())
        retrieved = db_client.get_trainer_student_link('trainer123', 'student456')
        
        assert retrieved is not None
        assert retrieved['trainer_id'] == 'trainer123'
        assert retrieved['student_id'] == 'student456'
        assert retrieved['status'] == 'active'
    
    def test_get_trainer_students(self, db_client):
        """Test getting all students for a trainer."""
        # Create trainer-student links
        for i in range(3):
            link = TrainerStudentLink(
                trainer_id='trainer123',
                student_id=f'student{i}'
            )
            db_client.put_trainer_student_link(link.to_dynamodb())
        
        # Get all students
        students = db_client.get_trainer_students('trainer123')
        assert len(students) == 3
        assert all(s['trainer_id'] == 'trainer123' for s in students)


class TestSessionOperations:
    """Test session-related operations."""
    
    def test_put_and_get_session(self, db_client):
        """Test creating and retrieving a session."""
        session = Session(
            trainer_id='trainer123',
            student_id='student456',
            student_name='Jane Smith',
            session_datetime=datetime(2024, 6, 15, 14, 0, 0),
            duration_minutes=60,
            location='Gym A'
        )
        
        db_client.put_session(session.to_dynamodb())
        retrieved = db_client.get_session('trainer123', session.session_id)
        
        assert retrieved is not None
        assert retrieved['student_name'] == 'Jane Smith'
        assert retrieved['duration_minutes'] == 60
        assert retrieved['location'] == 'Gym A'
    
    def test_get_sessions_by_date_range(self, db_client):
        """Test querying sessions by date range using GSI."""
        trainer_id = 'trainer123'
        base_date = datetime(2024, 6, 15, 10, 0, 0)
        
        # Create sessions across different dates
        for i in range(5):
            session = Session(
                trainer_id=trainer_id,
                student_id=f'student{i}',
                student_name=f'Student {i}',
                session_datetime=base_date + timedelta(days=i),
                duration_minutes=60
            )
            db_client.put_session(session.to_dynamodb())
        
        # Query sessions in middle 3 days
        start = base_date + timedelta(days=1)
        end = base_date + timedelta(days=3, hours=23)
        sessions = db_client.get_sessions_by_date_range(trainer_id, start, end)
        
        assert len(sessions) == 3
        assert all(s['trainer_id'] == trainer_id for s in sessions)
    
    def test_get_sessions_with_status_filter(self, db_client):
        """Test querying sessions with status filter."""
        trainer_id = 'trainer123'
        base_date = datetime(2024, 6, 15, 10, 0, 0)
        
        # Create sessions with different statuses
        for i, status in enumerate(['scheduled', 'confirmed', 'cancelled']):
            session = Session(
                trainer_id=trainer_id,
                student_id=f'student{i}',
                student_name=f'Student {i}',
                session_datetime=base_date + timedelta(hours=i),
                duration_minutes=60,
                status=status
            )
            db_client.put_session(session.to_dynamodb())
        
        # Query only scheduled and confirmed
        sessions = db_client.get_sessions_by_date_range(
            trainer_id,
            base_date - timedelta(hours=1),
            base_date + timedelta(days=1),
            status_filter=['scheduled', 'confirmed']
        )
        
        assert len(sessions) == 2
        assert all(s['status'] in ['scheduled', 'confirmed'] for s in sessions)
    
    def test_get_upcoming_sessions(self, db_client):
        """Test getting upcoming sessions."""
        trainer_id = 'trainer123'
        now = datetime.utcnow()
        
        # Create past and future sessions
        past_session = Session(
            trainer_id=trainer_id,
            student_id='student1',
            student_name='Student 1',
            session_datetime=now - timedelta(days=1),
            duration_minutes=60
        )
        future_session = Session(
            trainer_id=trainer_id,
            student_id='student2',
            student_name='Student 2',
            session_datetime=now + timedelta(days=5),
            duration_minutes=60
        )
        
        db_client.put_session(past_session.to_dynamodb())
        db_client.put_session(future_session.to_dynamodb())
        
        # Get upcoming sessions
        upcoming = db_client.get_upcoming_sessions(trainer_id, days_ahead=30)
        
        assert len(upcoming) == 1
        assert upcoming[0]['student_name'] == 'Student 2'


class TestPaymentOperations:
    """Test payment-related operations."""
    
    def test_put_and_get_payment(self, db_client):
        """Test creating and retrieving a payment."""
        payment = Payment(
            trainer_id='trainer123',
            student_id='student456',
            student_name='Jane Smith',
            amount=100.00,
            payment_date='2024-06-15'
        )
        
        db_client.put_payment(payment.to_dynamodb())
        retrieved = db_client.get_payment('trainer123', payment.payment_id)
        
        assert retrieved is not None
        assert retrieved['amount'] == 100.00
        assert retrieved['payment_status'] == 'pending'
    
    def test_get_payments_by_status(self, db_client):
        """Test querying payments by status using GSI."""
        trainer_id = 'trainer123'
        
        # Create payments with different statuses
        for i in range(3):
            payment = Payment(
                trainer_id=trainer_id,
                student_id=f'student{i}',
                student_name=f'Student {i}',
                amount=100.00,
                payment_date='2024-06-15',
                payment_status='pending' if i < 2 else 'confirmed'
            )
            db_client.put_payment(payment.to_dynamodb())
        
        # Query pending payments
        pending = db_client.get_payments_by_status(trainer_id, 'pending')
        assert len(pending) == 2
        assert all(p['payment_status'] == 'pending' for p in pending)
        
        # Query confirmed payments
        confirmed = db_client.get_payments_by_status(trainer_id, 'confirmed')
        assert len(confirmed) == 1
        assert confirmed[0]['payment_status'] == 'confirmed'
    
    def test_get_student_payments(self, db_client):
        """Test getting payments for a specific student."""
        trainer_id = 'trainer123'
        student_id = 'student456'
        
        # Create payments for different students
        for i in range(3):
            payment = Payment(
                trainer_id=trainer_id,
                student_id='student456' if i < 2 else 'student789',
                student_name=f'Student {i}',
                amount=100.00,
                payment_date='2024-06-15'
            )
            db_client.put_payment(payment.to_dynamodb())
        
        # Get payments for specific student
        payments = db_client.get_student_payments(trainer_id, student_id)
        assert len(payments) == 2
        assert all(p['student_id'] == student_id for p in payments)


class TestConversationState:
    """Test conversation state operations."""
    
    def test_put_and_get_conversation_state(self, db_client):
        """Test creating and retrieving conversation state."""
        ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        state = ConversationState(
            phone_number='+12345678901',
            state='TRAINER_MENU',
            user_id='trainer123',
            user_type='TRAINER',
            ttl=ttl
        )
        
        db_client.put_conversation_state(state.to_dynamodb())
        retrieved = db_client.get_conversation_state('+12345678901')
        
        assert retrieved is not None
        assert retrieved['state'] == 'TRAINER_MENU'
        assert retrieved['user_id'] == 'trainer123'
    
    def test_delete_conversation_state(self, db_client):
        """Test deleting conversation state."""
        ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        state = ConversationState(
            phone_number='+12345678901',
            state='UNKNOWN',
            ttl=ttl
        )
        
        db_client.put_conversation_state(state.to_dynamodb())
        assert db_client.get_conversation_state('+12345678901') is not None
        
        db_client.delete_conversation_state('+12345678901')
        assert db_client.get_conversation_state('+12345678901') is None


class TestPhoneNumberLookup:
    """Test phone number lookup using GSI."""
    
    def test_lookup_trainer_by_phone(self, db_client):
        """Test looking up a trainer by phone number."""
        trainer = Trainer(
            name='John Doe',
            email='john@example.com',
            business_name='Fit Training',
            phone_number='+12345678901'
        )
        
        db_client.put_trainer(trainer.to_dynamodb())
        
        # Lookup by phone
        result = db_client.lookup_by_phone_number('+12345678901')
        assert result is not None
        assert result['entity_type'] == 'TRAINER'
        assert result['name'] == 'John Doe'
    
    def test_lookup_student_by_phone(self, db_client):
        """Test looking up a student by phone number."""
        student = Student(
            name='Jane Smith',
            email='jane@example.com',
            phone_number='+19876543210',
            training_goal='Weight loss'
        )
        
        db_client.put_student(student.to_dynamodb())
        
        # Lookup by phone
        result = db_client.lookup_by_phone_number('+19876543210')
        assert result is not None
        assert result['entity_type'] == 'STUDENT'
        assert result['name'] == 'Jane Smith'
    
    def test_lookup_nonexistent_phone(self, db_client):
        """Test looking up a phone number that doesn't exist."""
        result = db_client.lookup_by_phone_number('+15555555555')
        assert result is None


class TestBatchOperations:
    """Test batch operations."""
    
    def test_batch_get_items(self, db_client):
        """Test batch getting multiple items."""
        # Create multiple items
        items = []
        for i in range(3):
            item = {
                'PK': f'TEST#{i}',
                'SK': 'METADATA',
                'name': f'Item {i}'
            }
            db_client.put_item(item)
            items.append(item)
        
        # Batch get
        keys = [{'PK': f'TEST#{i}', 'SK': 'METADATA'} for i in range(3)]
        results = db_client.batch_get_items(keys)
        
        assert len(results) == 3
        assert all(r['name'] in [f'Item {i}' for i in range(3)] for r in results)
    
    def test_batch_write_items(self, db_client):
        """Test batch writing multiple items."""
        items = [
            {'PK': f'BATCH#{i}', 'SK': 'METADATA', 'value': i}
            for i in range(5)
        ]
        
        result = db_client.batch_write_items(items)
        assert result is True
        
        # Verify items were written
        for i in range(5):
            retrieved = db_client.get_item(f'BATCH#{i}', 'METADATA')
            assert retrieved is not None
            assert retrieved['value'] == i


class TestQueryOperations:
    """Test generic query operations."""
    
    def test_query_with_begins_with(self, db_client):
        """Test querying with begins_with condition."""
        # Create items with same PK but different SK prefixes
        for i in range(3):
            db_client.put_item({
                'PK': 'TRAINER#123',
                'SK': f'SESSION#{i}',
                'session_id': f'session{i}'
            })
            db_client.put_item({
                'PK': 'TRAINER#123',
                'SK': f'PAYMENT#{i}',
                'payment_id': f'payment{i}'
            })
        
        # Query only sessions
        from boto3.dynamodb.conditions import Key
        sessions = db_client.query(
            key_condition_expression=Key('PK').eq('TRAINER#123') & Key('SK').begins_with('SESSION#')
        )
        
        assert len(sessions) == 3
        assert all('session_id' in s for s in sessions)
    
    def test_query_with_limit(self, db_client):
        """Test querying with limit."""
        # Create multiple items
        for i in range(10):
            db_client.put_item({
                'PK': 'TRAINER#456',
                'SK': f'SESSION#{i:02d}',
                'index': i
            })
        
        # Query with limit
        from boto3.dynamodb.conditions import Key
        results = db_client.query(
            key_condition_expression=Key('PK').eq('TRAINER#456') & Key('SK').begins_with('SESSION#'),
            limit=5
        )
        
        assert len(results) == 5
