"""
Unit tests for webhook_handler Lambda function.

Tests cover:
- Twilio signature validation
- SQS message enqueueing
- TwiML response generation
- Error handling
- Media URL extraction
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
from src.handlers.webhook_handler import (
    lambda_handler,
    _parse_form_body,
    _reconstruct_url,
    _extract_media_urls,
    _enqueue_to_sqs,
    _success_response,
    _error_response
)


# ==================== Fixtures ====================

@pytest.fixture
def valid_webhook_event():
    """Valid Twilio webhook event."""
    return {
        'httpMethod': 'POST',
        'headers': {
            'X-Twilio-Signature': 'valid_signature',
            'Host': 'api.example.com',
            'X-Forwarded-Proto': 'https'
        },
        'body': 'MessageSid=SM123456&From=whatsapp%3A%2B1234567890&To=whatsapp%3A%2B0987654321&Body=Hello+World&NumMedia=0',
        'requestContext': {
            'requestId': 'test-request-123',
            'domainName': 'api.example.com',
            'path': '/webhook'
        }
    }


@pytest.fixture
def webhook_event_with_media():
    """Webhook event with media attachments."""
    return {
        'httpMethod': 'POST',
        'headers': {
            'X-Twilio-Signature': 'valid_signature',
            'Host': 'api.example.com'
        },
        'body': 'MessageSid=SM123456&From=whatsapp%3A%2B1234567890&Body=Check+this+out&NumMedia=2&MediaUrl0=https%3A%2F%2Fexample.com%2Fimage.jpg&MediaContentType0=image%2Fjpeg&MediaUrl1=https%3A%2F%2Fexample.com%2Fdoc.pdf&MediaContentType1=application%2Fpdf',
        'requestContext': {
            'requestId': 'test-request-456',
            'domainName': 'api.example.com',
            'path': '/webhook'
        }
    }


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client."""
    with patch('src.handlers.webhook_handler.sqs_client') as mock:
        mock.send_message.return_value = {
            'MessageId': 'sqs-msg-123'
        }
        yield mock


@pytest.fixture
def mock_twilio_client():
    """Mock Twilio client."""
    with patch('src.handlers.webhook_handler.twilio_client') as mock:
        mock.validate_signature.return_value = True
        yield mock


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = 'webhook_handler'
    context.request_id = 'lambda-request-123'
    return context


# ==================== Helper Function Tests ====================

def test_parse_form_body_simple():
    """Test parsing simple form-encoded body."""
    body = 'key1=value1&key2=value2&key3=value3'
    result = _parse_form_body(body)
    
    assert result == {
        'key1': 'value1',
        'key2': 'value2',
        'key3': 'value3'
    }


def test_parse_form_body_url_encoded():
    """Test parsing URL-encoded values."""
    body = 'From=whatsapp%3A%2B1234567890&Body=Hello+World'
    result = _parse_form_body(body)
    
    assert result['From'] == 'whatsapp:+1234567890'
    assert result['Body'] == 'Hello World'


def test_parse_form_body_empty():
    """Test parsing empty body."""
    result = _parse_form_body('')
    assert result == {}


def test_parse_form_body_special_characters():
    """Test parsing body with special characters."""
    body = 'Body=Hello%21+How+are+you%3F&Special=%40%23%24%25'
    result = _parse_form_body(body)
    
    assert result['Body'] == 'Hello! How are you?'
    assert result['Special'] == '@#$%'


def test_reconstruct_url_with_all_headers():
    """Test URL reconstruction with all headers present."""
    event = {
        'headers': {
            'X-Forwarded-Proto': 'https',
            'Host': 'api.example.com'
        },
        'requestContext': {
            'domainName': 'api.example.com',
            'path': '/webhook'
        }
    }
    
    url = _reconstruct_url(event)
    assert url == 'https://api.example.com/webhook'


def test_reconstruct_url_defaults():
    """Test URL reconstruction with missing headers."""
    event = {
        'headers': {},
        'requestContext': {
            'domainName': 'api.example.com'
        }
    }
    
    url = _reconstruct_url(event)
    assert url == 'https://api.example.com/webhook'


def test_extract_media_urls_no_media():
    """Test media extraction with no media."""
    params = {'NumMedia': '0'}
    result = _extract_media_urls(params)
    
    assert result == []


def test_extract_media_urls_single_media():
    """Test media extraction with single media."""
    params = {
        'NumMedia': '1',
        'MediaUrl0': 'https://example.com/image.jpg',
        'MediaContentType0': 'image/jpeg'
    }
    result = _extract_media_urls(params)
    
    assert len(result) == 1
    assert result[0]['url'] == 'https://example.com/image.jpg'
    assert result[0]['content_type'] == 'image/jpeg'


def test_extract_media_urls_multiple_media():
    """Test media extraction with multiple media."""
    params = {
        'NumMedia': '3',
        'MediaUrl0': 'https://example.com/image1.jpg',
        'MediaContentType0': 'image/jpeg',
        'MediaUrl1': 'https://example.com/image2.png',
        'MediaContentType1': 'image/png',
        'MediaUrl2': 'https://example.com/doc.pdf',
        'MediaContentType2': 'application/pdf'
    }
    result = _extract_media_urls(params)
    
    assert len(result) == 3
    assert result[0]['content_type'] == 'image/jpeg'
    assert result[1]['content_type'] == 'image/png'
    assert result[2]['content_type'] == 'application/pdf'


def test_extract_media_urls_missing_content_type():
    """Test media extraction with missing content type."""
    params = {
        'NumMedia': '1',
        'MediaUrl0': 'https://example.com/file.bin'
    }
    result = _extract_media_urls(params)
    
    assert len(result) == 1
    assert result[0]['content_type'] == 'application/octet-stream'


def test_success_response():
    """Test successful TwiML response generation."""
    response = _success_response()
    
    assert response['statusCode'] == 200
    assert response['headers']['Content-Type'] == 'text/xml'
    assert '<?xml version="1.0" encoding="UTF-8"?>' in response['body']
    assert '<Response></Response>' in response['body']


def test_error_response():
    """Test error response generation."""
    response = _error_response(400, 'Bad Request')
    
    assert response['statusCode'] == 400
    assert response['headers']['Content-Type'] == 'application/json'
    
    body = json.loads(response['body'])
    assert body['error'] == 'Bad Request'


# ==================== SQS Enqueue Tests ====================

def test_enqueue_to_sqs_success(mock_sqs_client):
    """Test successful SQS message enqueueing."""
    message_body = {
        'message_sid': 'SM123',
        'from': '+1234567890',
        'body': 'Test message'
    }
    
    _enqueue_to_sqs(message_body, 'request-123')
    
    # Verify SQS client was called correctly
    mock_sqs_client.send_message.assert_called_once()
    call_args = mock_sqs_client.send_message.call_args
    
    assert 'QueueUrl' in call_args.kwargs
    assert 'MessageBody' in call_args.kwargs
    assert 'MessageAttributes' in call_args.kwargs
    
    # Verify message body
    sent_body = json.loads(call_args.kwargs['MessageBody'])
    assert sent_body['message_sid'] == 'SM123'
    assert sent_body['from'] == '+1234567890'
    
    # Verify message attributes
    attrs = call_args.kwargs['MessageAttributes']
    assert attrs['request_id']['StringValue'] == 'request-123'
    assert attrs['message_sid']['StringValue'] == 'SM123'


def test_enqueue_to_sqs_failure(mock_sqs_client):
    """Test SQS enqueueing failure handling."""
    mock_sqs_client.send_message.side_effect = ClientError(
        {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
        'SendMessage'
    )
    
    message_body = {'message_sid': 'SM123'}
    
    with pytest.raises(ClientError):
        _enqueue_to_sqs(message_body, 'request-123')


# ==================== Lambda Handler Tests ====================

def test_lambda_handler_success(valid_webhook_event, lambda_context, mock_sqs_client, mock_twilio_client):
    """Test successful webhook processing."""
    response = lambda_handler(valid_webhook_event, lambda_context)
    
    # Verify response
    assert response['statusCode'] == 200
    assert response['headers']['Content-Type'] == 'text/xml'
    assert '<Response></Response>' in response['body']
    
    # Verify Twilio signature was validated
    mock_twilio_client.validate_signature.assert_called_once()
    
    # Verify message was enqueued to SQS
    mock_sqs_client.send_message.assert_called_once()
    call_args = mock_sqs_client.send_message.call_args
    
    # Verify enqueued message content
    message_body = json.loads(call_args.kwargs['MessageBody'])
    assert message_body['message_sid'] == 'SM123456'
    assert message_body['from'] == '+1234567890'
    assert message_body['to'] == '+0987654321'
    assert message_body['body'] == 'Hello World'
    assert message_body['num_media'] == 0
    assert message_body['media_urls'] == []


def test_lambda_handler_with_media(webhook_event_with_media, lambda_context, mock_sqs_client, mock_twilio_client):
    """Test webhook processing with media attachments."""
    response = lambda_handler(webhook_event_with_media, lambda_context)
    
    assert response['statusCode'] == 200
    
    # Verify enqueued message includes media
    call_args = mock_sqs_client.send_message.call_args
    message_body = json.loads(call_args.kwargs['MessageBody'])
    
    assert message_body['num_media'] == 2
    assert len(message_body['media_urls']) == 2
    assert message_body['media_urls'][0]['url'] == 'https://example.com/image.jpg'
    assert message_body['media_urls'][0]['content_type'] == 'image/jpeg'
    assert message_body['media_urls'][1]['url'] == 'https://example.com/doc.pdf'
    assert message_body['media_urls'][1]['content_type'] == 'application/pdf'


def test_lambda_handler_missing_signature(valid_webhook_event, lambda_context, mock_sqs_client):
    """Test webhook rejection when signature is missing."""
    # Remove signature header
    valid_webhook_event['headers'].pop('X-Twilio-Signature')
    
    response = lambda_handler(valid_webhook_event, lambda_context)
    
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'Missing X-Twilio-Signature header' in body['error']
    
    # Verify message was NOT enqueued
    mock_sqs_client.send_message.assert_not_called()


def test_lambda_handler_invalid_signature(valid_webhook_event, lambda_context, mock_sqs_client, mock_twilio_client):
    """Test webhook rejection when signature is invalid."""
    # Mock invalid signature
    mock_twilio_client.validate_signature.return_value = False
    
    response = lambda_handler(valid_webhook_event, lambda_context)
    
    assert response['statusCode'] == 403
    body = json.loads(response['body'])
    assert 'Invalid Twilio signature' in body['error']
    
    # Verify message was NOT enqueued
    mock_sqs_client.send_message.assert_not_called()


def test_lambda_handler_sqs_failure(valid_webhook_event, lambda_context, mock_sqs_client, mock_twilio_client):
    """Test webhook handler when SQS enqueueing fails."""
    # Mock SQS failure
    mock_sqs_client.send_message.side_effect = ClientError(
        {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
        'SendMessage'
    )
    
    response = lambda_handler(valid_webhook_event, lambda_context)
    
    # Should still return 200 to prevent Twilio retries
    assert response['statusCode'] == 200
    assert '<Response></Response>' in response['body']


def test_lambda_handler_empty_body(lambda_context, mock_sqs_client, mock_twilio_client):
    """Test webhook handler with empty body."""
    event = {
        'httpMethod': 'POST',
        'headers': {
            'X-Twilio-Signature': 'valid_signature',
            'Host': 'api.example.com'
        },
        'body': '',
        'requestContext': {
            'requestId': 'test-request-789',
            'domainName': 'api.example.com',
            'path': '/webhook'
        }
    }
    
    response = lambda_handler(event, lambda_context)
    
    # Should still process and return 200
    assert response['statusCode'] == 200


def test_lambda_handler_malformed_body(lambda_context, mock_sqs_client, mock_twilio_client):
    """Test webhook handler with malformed body."""
    event = {
        'httpMethod': 'POST',
        'headers': {
            'X-Twilio-Signature': 'valid_signature',
            'Host': 'api.example.com'
        },
        'body': 'invalid&&&malformed===data',
        'requestContext': {
            'requestId': 'test-request-999',
            'domainName': 'api.example.com',
            'path': '/webhook'
        }
    }
    
    response = lambda_handler(event, lambda_context)
    
    # Should handle gracefully and return 200
    assert response['statusCode'] == 200


def test_lambda_handler_case_insensitive_headers(valid_webhook_event, lambda_context, mock_sqs_client, mock_twilio_client):
    """Test webhook handler with lowercase signature header."""
    # Use lowercase header name
    valid_webhook_event['headers']['x-twilio-signature'] = valid_webhook_event['headers'].pop('X-Twilio-Signature')
    
    response = lambda_handler(valid_webhook_event, lambda_context)
    
    assert response['statusCode'] == 200
    mock_twilio_client.validate_signature.assert_called_once()


def test_lambda_handler_request_id_propagation(valid_webhook_event, lambda_context, mock_sqs_client, mock_twilio_client):
    """Test that request_id is propagated to SQS message."""
    response = lambda_handler(valid_webhook_event, lambda_context)
    
    assert response['statusCode'] == 200
    
    # Verify request_id in message attributes
    call_args = mock_sqs_client.send_message.call_args
    attrs = call_args.kwargs['MessageAttributes']
    assert attrs['request_id']['StringValue'] == 'test-request-123'
    
    # Verify request_id in message body
    message_body = json.loads(call_args.kwargs['MessageBody'])
    assert message_body['request_id'] == 'test-request-123'


def test_lambda_handler_phone_number_extraction(valid_webhook_event, lambda_context, mock_sqs_client, mock_twilio_client):
    """Test that phone numbers are correctly extracted without whatsapp: prefix."""
    response = lambda_handler(valid_webhook_event, lambda_context)
    
    assert response['statusCode'] == 200
    
    # Verify phone numbers in message body
    call_args = mock_sqs_client.send_message.call_args
    message_body = json.loads(call_args.kwargs['MessageBody'])
    
    # Should strip whatsapp: prefix
    assert message_body['from'] == '+1234567890'
    assert message_body['to'] == '+0987654321'
    assert 'whatsapp:' not in message_body['from']
    assert 'whatsapp:' not in message_body['to']
