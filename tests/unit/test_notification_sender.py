"""
Unit tests for notification sender Lambda handler.

Tests the notification_sender handler including:
- Message processing from SQS
- WhatsApp message sending
- Retry logic (2 retries with 5-minute delays)
- Delivery status updates in DynamoDB
- Error handling
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from moto import mock_aws
import boto3

from src.handlers.notification_sender import (
    lambda_handler,
    _send_notification_message,
    _update_notification_status,
    _requeue_message,
)
from src.models.entities import Trainer, Student
from src.config import settings


@pytest.fixture
def mock_dynamodb_client():
    """Mock DynamoDB client with test data."""
    with mock_aws():
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
        
        # Create test student
        student = Student(
            name="Test Student",
            email="student@example.com",
            phone_number="+14155551000",
            training_goal="Test goal"
        )
        table.put_item(Item=student.to_dynamodb())
        
        # Create test notification record
        notification_id = "notif123"
        notification_record = {
            'PK': f'TRAINER#{trainer.trainer_id}',
            'SK': f'NOTIFICATION#{notification_id}',
            'entity_type': 'NOTIFICATION',
            'notification_id': notification_id,
            'trainer_id': trainer.trainer_id,
            'message': 'Test notification',
            'recipient_count': 1,
            'status': 'queued',
            'recipients': [
                {
                    'student_id': student.student_id,
                    'phone_number': student.phone_number,
                    'status': 'queued',
                }
            ],
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
        }
        table.put_item(Item=notification_record)
        
        yield {
            'trainer': trainer,
            'student': student,
            'notification_id': notification_id,
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


@pytest.fixture
def mock_twilio_client():
    """Mock Twilio client."""
    with patch('src.handlers.notification_sender.twilio_client') as mock:
        mock.send_message.return_value = {
            'message_sid': 'SM123456',
            'status': 'sent',
        }
        yield mock


def test_lambda_handler_success(mock_dynamodb_client, mock_sqs_client, mock_twilio_client):
    """Test successful notification sending."""
    trainer = mock_dynamodb_client['trainer']
    student = mock_dynamodb_client['student']
    notification_id = mock_dynamodb_client['notification_id']
    
    # Create SQS event
    event = {
        'Records': [
            {
                'messageId': 'msg123',
                'receiptHandle': 'receipt123',
                'body': json.dumps({
                    'notification_id': notification_id,
                    'trainer_id': trainer.trainer_id,
                    'recipient': {
                        'student_id': student.student_id,
                        'student_name': student.name,
                        'phone_number': student.phone_number,
                    },
                    'message': 'Test notification',
                    'attempt': 0,
                }),
                'attributes': {
                    'ApproximateReceiveCount': '1',
                }
            }
        ]
    }
    
    # Mock context
    context = Mock()
    context.function_name = 'test-function'
    
    # Execute handler
    result = lambda_handler(event, context)
    
    assert result['statusCode'] == 200
    assert result['body']['messages_processed'] == 1
    assert result['body']['messages_sent'] == 1
    assert result['body']['messages_failed'] == 0
    
    # Verify Twilio was called
    mock_twilio_client.send_message.assert_called_once()
    call_args = mock_twilio_client.send_message.call_args
    assert call_args[1]['to'] == student.phone_number
    assert 'Test notification' in call_args[1]['body']


def test_lambda_handler_retry_on_failure(mock_dynamodb_client, mock_sqs_client, mock_twilio_client):
    """Test retry logic when message sending fails."""
    trainer = mock_dynamodb_client['trainer']
    student = mock_dynamodb_client['student']
    notification_id = mock_dynamodb_client['notification_id']
    
    # Mock Twilio to fail
    mock_twilio_client.send_message.side_effect = Exception("Twilio error")
    
    # Create SQS event
    event = {
        'Records': [
            {
                'messageId': 'msg123',
                'receiptHandle': 'receipt123',
                'body': json.dumps({
                    'notification_id': notification_id,
                    'trainer_id': trainer.trainer_id,
                    'recipient': {
                        'student_id': student.student_id,
                        'student_name': student.name,
                        'phone_number': student.phone_number,
                    },
                    'message': 'Test notification',
                    'attempt': 0,
                }),
                'attributes': {
                    'ApproximateReceiveCount': '1',
                }
            }
        ]
    }
    
    context = Mock()
    context.function_name = 'test-function'
    
    # Execute handler
    result = lambda_handler(event, context)
    
    assert result['statusCode'] == 200
    assert result['body']['messages_retried'] == 1
    
    # Verify message was requeued
    messages = mock_sqs_client.receive_message(
        QueueUrl=settings.notification_queue_url,
        MaxNumberOfMessages=1
    )
    assert 'Messages' in messages
    requeued_body = json.loads(messages['Messages'][0]['Body'])
    assert requeued_body['attempt'] == 1


def test_lambda_handler_max_retries_exceeded(mock_dynamodb_client, mock_sqs_client, mock_twilio_client):
    """Test that message is marked as failed after max retries."""
    trainer = mock_dynamodb_client['trainer']
    student = mock_dynamodb_client['student']
    notification_id = mock_dynamodb_client['notification_id']
    
    # Mock Twilio to fail
    mock_twilio_client.send_message.side_effect = Exception("Twilio error")
    
    # Create SQS event with attempt=2 (max retries)
    event = {
        'Records': [
            {
                'messageId': 'msg123',
                'receiptHandle': 'receipt123',
                'body': json.dumps({
                    'notification_id': notification_id,
                    'trainer_id': trainer.trainer_id,
                    'recipient': {
                        'student_id': student.student_id,
                        'student_name': student.name,
                        'phone_number': student.phone_number,
                    },
                    'message': 'Test notification',
                    'attempt': 2,
                }),
                'attributes': {
                    'ApproximateReceiveCount': '3',
                }
            }
        ]
    }
    
    context = Mock()
    context.function_name = 'test-function'
    
    # Execute handler
    result = lambda_handler(event, context)
    
    assert result['statusCode'] == 200
    assert result['body']['messages_failed'] == 1
    assert result['body']['messages_retried'] == 0
    
    # Verify notification status was updated to failed
    table = mock_dynamodb_client['table']
    response = table.get_item(
        Key={
            'PK': f'TRAINER#{trainer.trainer_id}',
            'SK': f'NOTIFICATION#{notification_id}'
        }
    )
    notification = response['Item']
    assert notification['recipients'][0]['status'] == 'failed'


def test_send_notification_message_success(mock_dynamodb_client, mock_twilio_client):
    """Test successful message sending."""
    trainer = mock_dynamodb_client['trainer']
    student = mock_dynamodb_client['student']
    
    recipient = {
        'student_id': student.student_id,
        'student_name': student.name,
        'phone_number': student.phone_number,
    }
    
    result = _send_notification_message(
        trainer_id=trainer.trainer_id,
        recipient=recipient,
        message='Test message'
    )
    
    assert result['success'] is True
    assert result['message_sid'] == 'SM123456'
    
    # Verify Twilio was called with correct parameters
    mock_twilio_client.send_message.assert_called_once()
    call_args = mock_twilio_client.send_message.call_args
    assert call_args[1]['to'] == student.phone_number
    assert 'Test message' in call_args[1]['body']
    assert trainer.name in call_args[1]['body']


def test_send_notification_message_no_phone():
    """Test error when recipient has no phone number."""
    recipient = {
        'student_id': 'student123',
        'student_name': 'Test Student',
        'phone_number': None,
    }
    
    result = _send_notification_message(
        trainer_id='trainer123',
        recipient=recipient,
        message='Test message'
    )
    
    assert result['success'] is False
    assert 'no phone number' in result['error'].lower()


def test_update_notification_status_sent(mock_dynamodb_client):
    """Test updating notification status to sent."""
    trainer = mock_dynamodb_client['trainer']
    student = mock_dynamodb_client['student']
    notification_id = mock_dynamodb_client['notification_id']
    table = mock_dynamodb_client['table']
    
    recipient = {
        'student_id': student.student_id,
        'student_name': student.name,
        'phone_number': student.phone_number,
    }
    
    _update_notification_status(
        trainer_id=trainer.trainer_id,
        notification_id=notification_id,
        recipient=recipient,
        status='sent',
        message_sid='SM123456'
    )
    
    # Verify notification was updated
    response = table.get_item(
        Key={
            'PK': f'TRAINER#{trainer.trainer_id}',
            'SK': f'NOTIFICATION#{notification_id}'
        }
    )
    notification = response['Item']
    assert notification['recipients'][0]['status'] == 'sent'
    assert notification['recipients'][0]['message_sid'] == 'SM123456'
    assert 'sent_at' in notification['recipients'][0]
    assert notification['status'] == 'completed'


def test_update_notification_status_failed(mock_dynamodb_client):
    """Test updating notification status to failed."""
    trainer = mock_dynamodb_client['trainer']
    student = mock_dynamodb_client['student']
    notification_id = mock_dynamodb_client['notification_id']
    table = mock_dynamodb_client['table']
    
    recipient = {
        'student_id': student.student_id,
        'student_name': student.name,
        'phone_number': student.phone_number,
    }
    
    _update_notification_status(
        trainer_id=trainer.trainer_id,
        notification_id=notification_id,
        recipient=recipient,
        status='failed',
        error='Twilio error'
    )
    
    # Verify notification was updated
    response = table.get_item(
        Key={
            'PK': f'TRAINER#{trainer.trainer_id}',
            'SK': f'NOTIFICATION#{notification_id}'
        }
    )
    notification = response['Item']
    assert notification['recipients'][0]['status'] == 'failed'
    assert notification['recipients'][0]['error'] == 'Twilio error'
    assert 'failed_at' in notification['recipients'][0]
    assert notification['status'] == 'failed'


def test_requeue_message(mock_sqs_client):
    """Test message requeuing with delay."""
    message_body = {
        'notification_id': 'notif123',
        'trainer_id': 'trainer123',
        'recipient': {
            'student_id': 'student123',
            'student_name': 'Test Student',
            'phone_number': '+14155551000',
        },
        'message': 'Test message',
        'attempt': 0,
    }
    
    _requeue_message(
        message_body=message_body,
        attempt=1,
        delay_seconds=300
    )
    
    # Verify message was requeued
    messages = mock_sqs_client.receive_message(
        QueueUrl=settings.notification_queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=1
    )
    
    # Note: moto doesn't fully support DelaySeconds, so we just verify the message was sent
    # In production, the delay would be respected
    assert 'Messages' in messages
    requeued_body = json.loads(messages['Messages'][0]['Body'])
    assert requeued_body['attempt'] == 1


def test_lambda_handler_multiple_messages(mock_dynamodb_client, mock_sqs_client, mock_twilio_client):
    """Test processing multiple messages in one invocation."""
    trainer = mock_dynamodb_client['trainer']
    student = mock_dynamodb_client['student']
    notification_id = mock_dynamodb_client['notification_id']
    
    # Create SQS event with multiple records
    event = {
        'Records': [
            {
                'messageId': f'msg{i}',
                'receiptHandle': f'receipt{i}',
                'body': json.dumps({
                    'notification_id': notification_id,
                    'trainer_id': trainer.trainer_id,
                    'recipient': {
                        'student_id': student.student_id,
                        'student_name': student.name,
                        'phone_number': student.phone_number,
                    },
                    'message': f'Test notification {i}',
                    'attempt': 0,
                }),
                'attributes': {
                    'ApproximateReceiveCount': '1',
                }
            }
            for i in range(3)
        ]
    }
    
    context = Mock()
    context.function_name = 'test-function'
    
    # Execute handler
    result = lambda_handler(event, context)
    
    assert result['statusCode'] == 200
    assert result['body']['messages_processed'] == 3
    assert result['body']['messages_sent'] == 3
    
    # Verify Twilio was called 3 times
    assert mock_twilio_client.send_message.call_count == 3
