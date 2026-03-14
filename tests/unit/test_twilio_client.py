"""
Unit tests for TwilioClient wrapper.
Tests send_message() and validate_signature() methods.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from twilio.base.exceptions import TwilioRestException

from src.services.twilio_client import TwilioClient


class TestTwilioClientInitialization:
    """Test TwilioClient initialization."""
    
    def test_init_with_default_settings(self):
        """Test initialization with settings from config."""
        with patch('src.services.twilio_client.settings') as mock_settings, \
             patch('src.services.twilio_client.Client'), \
             patch('src.services.twilio_client.RequestValidator'):
            mock_settings.twilio_account_sid = "AC123"
            mock_settings.twilio_auth_token = "token123"
            mock_settings.twilio_whatsapp_number = "+14155238886"
            mock_settings.get_twilio_credentials.return_value = {
                'account_sid': "AC123",
                'auth_token': "token123",
                'whatsapp_number': "+14155238886"
            }
            
            client = TwilioClient()
            
            assert client.account_sid == "AC123"
            assert client.auth_token == "token123"
            assert client.whatsapp_number == "+14155238886"
    
    def test_init_with_custom_credentials(self):
        """Test initialization with custom credentials."""
        with patch('src.services.twilio_client.Client'), \
             patch('src.services.twilio_client.RequestValidator'):
            client = TwilioClient(
                account_sid="AC456",
                auth_token="token456",
                whatsapp_number="+14155238887"
            )
            
            assert client.account_sid == "AC456"
            assert client.auth_token == "token456"
            assert client.whatsapp_number == "+14155238887"
    
    def test_init_creates_twilio_client(self):
        """Test that Twilio client is created during initialization."""
        with patch('src.services.twilio_client.Client') as mock_client:
            client = TwilioClient(
                account_sid="AC123",
                auth_token="token123",
                whatsapp_number="+14155238886"
            )
            
            mock_client.assert_called_once_with("AC123", "token123")
            assert client.client is not None
    
    def test_init_creates_request_validator(self):
        """Test that RequestValidator is created during initialization."""
        with patch('src.services.twilio_client.RequestValidator') as mock_validator:
            client = TwilioClient(
                account_sid="AC123",
                auth_token="token123",
                whatsapp_number="+14155238886"
            )
            
            mock_validator.assert_called_once_with("token123")
            assert client.validator is not None


class TestSendMessage:
    """Test send_message() method."""
    
    @pytest.fixture
    def mock_twilio_client(self):
        """Create a TwilioClient with mocked Twilio SDK."""
        with patch('src.services.twilio_client.Client') as mock_client:
            client = TwilioClient(
                account_sid="AC123",
                auth_token="token123",
                whatsapp_number="+14155238886"
            )
            yield client, mock_client
    
    def test_send_message_success(self, mock_twilio_client):
        """Test successful message sending."""
        client, mock_client = mock_twilio_client
        
        # Mock the message response
        mock_message = Mock()
        mock_message.sid = "SM123456"
        mock_message.status = "queued"
        mock_message.date_created = datetime(2024, 1, 15, 10, 30, 0)
        mock_message.date_sent = None
        mock_message.error_code = None
        mock_message.error_message = None
        
        client.client.messages.create = Mock(return_value=mock_message)
        
        # Send message (Portuguese example)
        result = client.send_message(
            to="+1234567890",
            body="Sua sessão está agendada para amanhã às 14h"
        )
        
        # Verify result
        assert result['message_sid'] == "SM123456"
        assert result['status'] == "queued"
        assert result['to'] == "+1234567890"
        assert result['from'] == "+14155238886"
        assert result['body'] == "Sua sessão está agendada para amanhã às 14h"
        assert result['date_created'] == "2024-01-15T10:30:00"
        assert result['date_sent'] is None
        assert result['error_code'] is None
        assert result['error_message'] is None
        
        # Verify Twilio API was called correctly
        client.client.messages.create.assert_called_once_with(
            from_='whatsapp:+14155238886',
            to='whatsapp:+1234567890',
            body="Sua sessão está agendada para amanhã às 14h"
        )
    
    def test_send_message_with_media(self, mock_twilio_client):
        """Test sending message with media attachment."""
        client, mock_client = mock_twilio_client
        
        mock_message = Mock()
        mock_message.sid = "SM123456"
        mock_message.status = "queued"
        mock_message.date_created = datetime(2024, 1, 15, 10, 30, 0)
        mock_message.date_sent = None
        mock_message.error_code = None
        mock_message.error_message = None
        
        client.client.messages.create = Mock(return_value=mock_message)
        
        # Send message with media
        result = client.send_message(
            to="+1234567890",
            body="Here is your receipt",
            media_url="https://example.com/receipt.jpg"
        )
        
        # Verify media_url was included
        client.client.messages.create.assert_called_once_with(
            from_='whatsapp:+14155238886',
            to='whatsapp:+1234567890',
            body="Here is your receipt",
            media_url=["https://example.com/receipt.jpg"]
        )
        
        assert result['message_sid'] == "SM123456"
    
    def test_send_message_formats_whatsapp_prefix(self, mock_twilio_client):
        """Test that phone numbers are formatted with whatsapp: prefix."""
        client, mock_client = mock_twilio_client
        
        mock_message = Mock()
        mock_message.sid = "SM123456"
        mock_message.status = "queued"
        mock_message.date_created = datetime(2024, 1, 15, 10, 30, 0)
        mock_message.date_sent = None
        mock_message.error_code = None
        mock_message.error_message = None
        
        client.client.messages.create = Mock(return_value=mock_message)
        
        # Send message (numbers without whatsapp: prefix)
        client.send_message(to="+1234567890", body="Test message")
        
        # Verify whatsapp: prefix was added
        call_args = client.client.messages.create.call_args
        assert call_args[1]['from_'] == 'whatsapp:+14155238886'
        assert call_args[1]['to'] == 'whatsapp:+1234567890'
    
    def test_send_message_preserves_existing_whatsapp_prefix(self, mock_twilio_client):
        """Test that existing whatsapp: prefix is not duplicated."""
        client, mock_client = mock_twilio_client
        
        mock_message = Mock()
        mock_message.sid = "SM123456"
        mock_message.status = "queued"
        mock_message.date_created = datetime(2024, 1, 15, 10, 30, 0)
        mock_message.date_sent = None
        mock_message.error_code = None
        mock_message.error_message = None
        
        client.client.messages.create = Mock(return_value=mock_message)
        
        # Send message with whatsapp: prefix already present
        client.send_message(to="whatsapp:+1234567890", body="Test message")
        
        # Verify prefix was not duplicated
        call_args = client.client.messages.create.call_args
        assert call_args[1]['to'] == 'whatsapp:+1234567890'
    
    def test_send_message_twilio_exception(self, mock_twilio_client):
        """Test handling of Twilio API exceptions."""
        client, mock_client = mock_twilio_client
        
        # Mock Twilio exception
        client.client.messages.create = Mock(
            side_effect=TwilioRestException(
                status=400,
                uri="/Messages",
                msg="Invalid phone number"
            )
        )
        
        # Verify exception is raised
        with pytest.raises(TwilioRestException):
            client.send_message(to="+invalid", body="Test message")
    
    def test_send_message_generic_exception(self, mock_twilio_client):
        """Test handling of generic exceptions."""
        client, mock_client = mock_twilio_client
        
        # Mock generic exception
        client.client.messages.create = Mock(
            side_effect=Exception("Network error")
        )
        
        # Verify exception is raised
        with pytest.raises(Exception) as exc_info:
            client.send_message(to="+1234567890", body="Test message")
        
        assert "Network error" in str(exc_info.value)


class TestValidateSignature:
    """Test validate_signature() method."""
    
    @pytest.fixture
    def mock_twilio_client(self):
        """Create a TwilioClient with mocked RequestValidator."""
        with patch('src.services.twilio_client.RequestValidator') as mock_validator:
            client = TwilioClient(
                account_sid="AC123",
                auth_token="token123",
                whatsapp_number="+14155238886"
            )
            yield client, mock_validator
    
    def test_validate_signature_success(self, mock_twilio_client):
        """Test successful signature validation."""
        client, mock_validator = mock_twilio_client
        
        # Mock validator to return True
        client.validator.validate = Mock(return_value=True)
        
        url = "https://example.com/webhook"
        params = {
            "MessageSid": "SM123",
            "From": "whatsapp:+1234567890",
            "Body": "Hello"
        }
        signature = "abc123signature"
        
        # Validate signature
        is_valid = client.validate_signature(url, params, signature)
        
        assert is_valid is True
        client.validator.validate.assert_called_once_with(url, params, signature)
    
    def test_validate_signature_failure(self, mock_twilio_client):
        """Test failed signature validation."""
        client, mock_validator = mock_twilio_client
        
        # Mock validator to return False
        client.validator.validate = Mock(return_value=False)
        
        url = "https://example.com/webhook"
        params = {"From": "whatsapp:+1234567890"}
        signature = "invalid_signature"
        
        # Validate signature
        is_valid = client.validate_signature(url, params, signature)
        
        assert is_valid is False
    
    def test_validate_signature_with_empty_signature(self, mock_twilio_client):
        """Test validation with empty signature."""
        client, mock_validator = mock_twilio_client
        
        client.validator.validate = Mock(return_value=False)
        
        url = "https://example.com/webhook"
        params = {"From": "whatsapp:+1234567890"}
        signature = ""
        
        # Validate signature
        is_valid = client.validate_signature(url, params, signature)
        
        assert is_valid is False
    
    def test_validate_signature_exception_handling(self, mock_twilio_client):
        """Test exception handling during signature validation."""
        client, mock_validator = mock_twilio_client
        
        # Mock validator to raise exception
        client.validator.validate = Mock(
            side_effect=Exception("Validation error")
        )
        
        url = "https://example.com/webhook"
        params = {"From": "whatsapp:+1234567890"}
        signature = "abc123"
        
        # Validate signature - should return False on exception
        is_valid = client.validate_signature(url, params, signature)
        
        assert is_valid is False
    
    def test_validate_signature_with_complex_params(self, mock_twilio_client):
        """Test validation with complex webhook parameters."""
        client, mock_validator = mock_twilio_client
        
        client.validator.validate = Mock(return_value=True)
        
        url = "https://example.com/webhook"
        params = {
            "MessageSid": "SM123456",
            "From": "whatsapp:+1234567890",
            "To": "whatsapp:+14155238886",
            "Body": "Schedule a session for tomorrow",
            "NumMedia": "0",
            "AccountSid": "AC123"
        }
        signature = "valid_signature_hash"
        
        # Validate signature
        is_valid = client.validate_signature(url, params, signature)
        
        assert is_valid is True
        client.validator.validate.assert_called_once_with(url, params, signature)


class TestFormatWhatsappNumber:
    """Test _format_whatsapp_number() static method."""
    
    def test_format_number_without_prefix(self):
        """Test formatting number without whatsapp: prefix."""
        result = TwilioClient._format_whatsapp_number("+1234567890")
        assert result == "whatsapp:+1234567890"
    
    def test_format_number_with_prefix(self):
        """Test formatting number that already has whatsapp: prefix."""
        result = TwilioClient._format_whatsapp_number("whatsapp:+1234567890")
        assert result == "whatsapp:+1234567890"
    
    def test_format_empty_number(self):
        """Test formatting empty phone number."""
        result = TwilioClient._format_whatsapp_number("")
        assert result == ""
    
    def test_format_none_number(self):
        """Test formatting None phone number."""
        result = TwilioClient._format_whatsapp_number(None)
        assert result is None


class TestTwilioClientIntegration:
    """Integration tests for TwilioClient."""
    
    def test_send_and_validate_workflow(self):
        """Test typical workflow of sending message and validating webhook."""
        with patch('src.services.twilio_client.Client') as mock_client_class:
            with patch('src.services.twilio_client.RequestValidator') as mock_validator_class:
                # Setup
                client = TwilioClient(
                    account_sid="AC123",
                    auth_token="token123",
                    whatsapp_number="+14155238886"
                )
                
                # Mock send message
                mock_message = Mock()
                mock_message.sid = "SM123456"
                mock_message.status = "sent"
                mock_message.date_created = datetime(2024, 1, 15, 10, 30, 0)
                mock_message.date_sent = datetime(2024, 1, 15, 10, 30, 5)
                mock_message.error_code = None
                mock_message.error_message = None
                
                client.client.messages.create = Mock(return_value=mock_message)
                
                # Send message
                send_result = client.send_message(
                    to="+1234567890",
                    body="Test message"
                )
                
                assert send_result['message_sid'] == "SM123456"
                assert send_result['status'] == "sent"
                
                # Mock validate signature
                client.validator.validate = Mock(return_value=True)
                
                # Validate webhook
                is_valid = client.validate_signature(
                    url="https://example.com/webhook",
                    params={"MessageSid": "SM123456"},
                    signature="valid_sig"
                )
                
                assert is_valid is True
