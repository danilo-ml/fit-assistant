"""
Unit tests for notification tool functions.

Tests the send_notification tool function including:
- Recipient selection (all, specific, upcoming_sessions)
- Message queueing to SQS
- Notification record creation
- Error handling
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from moto import mock_aws
import boto3

from src.tools.notification_tools import send_notification
from src.models.entities import Trainer, Student, TrainerStudentLink, Session
from src.config import settings


@pytest.fixture
def mock_dynamodb_client():
    """Mock DynamoDB client with test data."""
    with mock_aws():
        # Patch settings to not use endpoint_url for moto
        with patch('src.tools.notification_tools.settings') as mock_settings:
            mock_settings.dynamodb_table = settings.dynamodb_table
            mock_settings.aws_endpoint_url = None
            mock_settings.aws_region = 'us-east-1'
            mock_settings.notification_queue_url = 'http://test-queue'
            
            # Create table
            dynamodb = boto3.resource(
                'dynamodb',
                region_name='us-east-1'
            )
        
        table = dynamodb.create_table(
            TableName=settings.dynamodb_table,
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create test trainer
        trainer = Trainer(
            name="Test Trainer",
            email="trainer@example.com",
            business_name="Test Gym",
            phone_number="+14155551234"
        )
        table.put_item(Item=trainer.to_dynamodb())
        
        # Create test students
        students = []
        for i in range(3):
            student = Student(
                name=f"Student {i+1}",
                email=f"student{i+1}@example.com",
                phone_number=f"+1415555{1000+i}",
                training_goal="Test goal"
            )
            students.append(student)
            table.put_item(Item=student.to_dynamodb())
            
            # Create trainer-student link
            link = TrainerStudentLink(
                trainer_id=trainer.trainer_id,
                student_id=student.student_id,
                status="active"
            )
            table.put_item(Item=link.to_dynamodb())
        
        # Create test session for upcoming_sessions test
        session = Session(
            trainer_id=trainer.trainer_id,
            student_id=students[0].student_id,
            student_name=students[0].name,
            session_datetime=datetime.utcnow() + timedelta(days=2),
            duration_minutes=60,
            status="scheduled"
        )
        table.put_item(Item=session.to_dynamodb())
        
        yield {
            'trainer': trainer,
            'students': students,
            'session': session,
            'table': table
        }


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client."""
    with mock_aws():
        sqs = boto3.client(
            'sqs',
            region_name='us-east-1'
        )
        
        # Create notification queue
        queue_url = sqs.create_queue(QueueName='test-notifications')['QueueUrl']
        
        # Update settings with queue URL
        original_url = settings.notification_queue_url
        settings.notification_queue_url = queue_url
        
        yield sqs
        
        # Restore original URL
        settings.notification_queue_url = original_url


def test_send_notification_all_recipients(mock_dynamodb_client, mock_sqs_client):
    """Test sending notification to all students."""
    trainer = mock_dynamodb_client['trainer']
    students = mock_dynamodb_client['students']
    
    result = send_notification(
        trainer_id=trainer.trainer_id,
        message="Test notification to all",
        recipients="all"
    )
    
    assert result['success'] is True
    assert result['data']['recipient_count'] == 3
    assert result['data']['queued_count'] == 3
    assert len(result['data']['recipients']) == 3
    
    # Verify all students are included
    recipient_ids = {r['student_id'] for r in result['data']['recipients']}
    expected_ids = {s.student_id for s in students}
    assert recipient_ids == expected_ids
    
    # Verify messages were queued to SQS
    messages = mock_sqs_client.receive_message(
        QueueUrl=settings.notification_queue_url,
        MaxNumberOfMessages=10
    )
    assert 'Messages' in messages
    assert len(messages['Messages']) == 3


def test_send_notification_specific_recipients(mock_dynamodb_client, mock_sqs_client):
    """Test sending notification to specific students."""
    trainer = mock_dynamodb_client['trainer']
    students = mock_dynamodb_client['students']
    
    # Select first two students
    specific_ids = [students[0].student_id, students[1].student_id]
    
    result = send_notification(
        trainer_id=trainer.trainer_id,
        message="Test notification to specific students",
        recipients="specific",
        specific_student_ids=specific_ids
    )
    
    assert result['success'] is True
    assert result['data']['recipient_count'] == 2
    assert result['data']['queued_count'] == 2
    assert len(result['data']['recipients']) == 2
    
    # Verify correct students are included
    recipient_ids = {r['student_id'] for r in result['data']['recipients']}
    assert recipient_ids == set(specific_ids)


def test_send_notification_upcoming_sessions(mock_dynamodb_client, mock_sqs_client):
    """Test sending notification to students with upcoming sessions."""
    trainer = mock_dynamodb_client['trainer']
    students = mock_dynamodb_client['students']
    
    result = send_notification(
        trainer_id=trainer.trainer_id,
        message="Test notification to upcoming sessions",
        recipients="upcoming_sessions"
    )
    
    assert result['success'] is True
    assert result['data']['recipient_count'] == 1
    assert result['data']['queued_count'] == 1
    
    # Verify only student with upcoming session is included
    assert result['data']['recipients'][0]['student_id'] == students[0].student_id


def test_send_notification_missing_message():
    """Test error when message is missing."""
    result = send_notification(
        trainer_id="trainer123",
        message="",
        recipients="all"
    )
    
    assert result['success'] is False
    assert "message is required" in result['error'].lower()


def test_send_notification_invalid_recipients():
    """Test error when recipients option is invalid."""
    result = send_notification(
        trainer_id="trainer123",
        message="Test message",
        recipients="invalid_option"
    )
    
    assert result['success'] is False
    assert "invalid recipients option" in result['error'].lower()


def test_send_notification_specific_without_ids(mock_dynamodb_client, mock_sqs_client):
    """Test error when recipients='specific' but no student IDs provided."""
    trainer = mock_dynamodb_client['trainer']
    
    result = send_notification(
        trainer_id=trainer.trainer_id,
        message="Test message",
        recipients="specific",
        specific_student_ids=None
    )
    
    assert result['success'] is False
    assert "specific_student_ids is required" in result['error'].lower()


def test_send_notification_trainer_not_found(mock_sqs_client):
    """Test error when trainer doesn't exist."""
    result = send_notification(
        trainer_id="nonexistent_trainer",
        message="Test message",
        recipients="all"
    )
    
    assert result['success'] is False
    assert "trainer not found" in result['error'].lower()


def test_send_notification_no_recipients(mock_dynamodb_client, mock_sqs_client):
    """Test error when no recipients match criteria."""
    trainer = mock_dynamodb_client['trainer']
    
    # Try to send to specific student that doesn't exist
    result = send_notification(
        trainer_id=trainer.trainer_id,
        message="Test message",
        recipients="specific",
        specific_student_ids=["nonexistent_student"]
    )
    
    assert result['success'] is False
    assert "no recipients found" in result['error'].lower()


def test_send_notification_rate_limiting(mock_dynamodb_client, mock_sqs_client):
    """Test that rate limiting delays are applied correctly."""
    trainer = mock_dynamodb_client['trainer']
    
    # Create more students to test rate limiting
    table = mock_dynamodb_client['table']
    students = []
    for i in range(15):
        student = Student(
            name=f"Student {i+10}",
            email=f"student{i+10}@example.com",
            phone_number=f"+1415555{2000+i}",
            training_goal="Test goal"
        )
        students.append(student)
        table.put_item(Item=student.to_dynamodb())
        
        link = TrainerStudentLink(
            trainer_id=trainer.trainer_id,
            student_id=student.student_id,
            status="active"
        )
        table.put_item(Item=link.to_dynamodb())
    
    result = send_notification(
        trainer_id=trainer.trainer_id,
        message="Test rate limiting",
        recipients="all"
    )
    
    assert result['success'] is True
    # Should have 3 original + 15 new = 18 recipients
    assert result['data']['recipient_count'] == 18
    assert result['data']['queued_count'] == 18


def test_send_notification_creates_record(mock_dynamodb_client, mock_sqs_client):
    """Test that notification record is created in DynamoDB."""
    trainer = mock_dynamodb_client['trainer']
    table = mock_dynamodb_client['table']
    
    result = send_notification(
        trainer_id=trainer.trainer_id,
        message="Test notification record",
        recipients="all"
    )
    
    assert result['success'] is True
    notification_id = result['data']['notification_id']
    
    # Verify notification record exists in DynamoDB
    response = table.get_item(
        Key={
            'PK': f'TRAINER#{trainer.trainer_id}',
            'SK': f'NOTIFICATION#{notification_id}'
        }
    )
    
    assert 'Item' in response
    notification = response['Item']
    assert notification['entity_type'] == 'NOTIFICATION'
    assert notification['message'] == "Test notification record"
    assert notification['recipient_count'] == 3
    assert notification['status'] == 'queued'
    assert len(notification['recipients']) == 3


def test_send_notification_sanitizes_input(mock_dynamodb_client, mock_sqs_client):
    """Test that input is sanitized."""
    trainer = mock_dynamodb_client['trainer']
    
    # Try to send message with HTML tags
    result = send_notification(
        trainer_id=trainer.trainer_id,
        message="<script>alert('xss')</script>Test message",
        recipients="all"
    )
    
    assert result['success'] is True
    # Message should be sanitized (HTML tags removed)
    assert '<script>' not in result['data']['message']
