"""
Unit tests for structured logging module.

Tests Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6
"""

import json
import logging
from datetime import datetime
from io import StringIO

import pytest

from src.utils.logging import StructuredLogger, get_logger


class TestStructuredLogger:
    """Test suite for StructuredLogger class."""
    
    @pytest.fixture
    def logger(self):
        """Create a StructuredLogger instance for testing."""
        return StructuredLogger('test_logger')
    
    @pytest.fixture
    def log_capture(self, logger):
        """Capture log output for assertions."""
        # Create a string buffer to capture logs
        log_buffer = StringIO()
        handler = logging.StreamHandler(log_buffer)
        handler.setFormatter(logging.Formatter('%(message)s'))
        
        # Clear existing handlers and add our capture handler
        logger.logger.handlers.clear()
        logger.logger.addHandler(handler)
        
        return log_buffer
    
    def test_logger_initialization(self, logger):
        """Test that logger initializes correctly."""
        assert logger.logger.name == 'test_logger'
        assert logger.logger.level == logging.INFO
    
    def test_info_log_basic(self, logger, log_capture):
        """Test basic INFO level logging."""
        logger.info('Test message')
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['level'] == 'INFO'
        assert log_entry['message'] == 'Test message'
        assert log_entry['service'] == 'fitagent'
        assert 'timestamp' in log_entry
    
    def test_warning_log_basic(self, logger, log_capture):
        """Test basic WARNING level logging."""
        logger.warning('Warning message')
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['level'] == 'WARNING'
        assert log_entry['message'] == 'Warning message'
    
    def test_error_log_basic(self, logger, log_capture):
        """Test basic ERROR level logging."""
        logger.error('Error message')
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['level'] == 'ERROR'
        assert log_entry['message'] == 'Error message'
    
    def test_log_with_request_id(self, logger, log_capture):
        """Test logging with request_id field."""
        logger.info('Test message', request_id='req-12345')
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['request_id'] == 'req-12345'
    
    def test_phone_number_masking(self, logger, log_capture):
        """Test that phone numbers are masked for privacy (Requirement 19.6)."""
        logger.info('User action', phone_number='+1234567890')
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        # Should show only last 4 digits
        assert log_entry['phone_number'] == '***7890'
        # Should not contain full phone number
        assert '+1234567890' not in log_output
    
    def test_phone_number_masking_short_number(self, logger, log_capture):
        """Test phone number masking with short numbers."""
        logger.info('User action', phone_number='123')
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        # Short numbers should be fully masked
        assert log_entry['phone_number'] == '***'
    
    def test_phone_number_masking_empty(self, logger, log_capture):
        """Test phone number masking with empty string."""
        logger.info('User action', phone_number='')
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        # Empty phone numbers should not be included in log
        assert 'phone_number' not in log_entry
    
    def test_custom_fields(self, logger, log_capture):
        """Test logging with custom fields."""
        logger.info(
            'Tool executed',
            tool_name='schedule_session',
            parameters={'student': 'John', 'date': '2024-01-20'}
        )
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['tool_name'] == 'schedule_session'
        assert log_entry['parameters'] == {'student': 'John', 'date': '2024-01-20'}
    
    def test_all_fields_combined(self, logger, log_capture):
        """Test logging with all fields combined."""
        logger.info(
            'Complete log entry',
            request_id='req-abc-123',
            phone_number='+1234567890',
            tool_name='register_student',
            status='success'
        )
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['level'] == 'INFO'
        assert log_entry['message'] == 'Complete log entry'
        assert log_entry['request_id'] == 'req-abc-123'
        assert log_entry['phone_number'] == '***7890'
        assert log_entry['tool_name'] == 'register_student'
        assert log_entry['status'] == 'success'
        assert log_entry['service'] == 'fitagent'
    
    def test_json_format_validity(self, logger, log_capture):
        """Test that all log entries are valid JSON (Requirement 19.5)."""
        logger.info('Message 1', field1='value1')
        logger.warning('Message 2', field2='value2')
        logger.error('Message 3', field3='value3')
        
        log_output = log_capture.getvalue()
        log_lines = log_output.strip().split('\n')
        
        # Each line should be valid JSON
        for line in log_lines:
            log_entry = json.loads(line)
            assert isinstance(log_entry, dict)
            assert 'timestamp' in log_entry
            assert 'level' in log_entry
            assert 'message' in log_entry
    
    def test_timestamp_format(self, logger, log_capture):
        """Test that timestamp is in ISO 8601 format."""
        logger.info('Test message')
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        # Should be able to parse as ISO format
        timestamp = log_entry['timestamp']
        assert timestamp.endswith('Z')
        # Verify it's a valid ISO format
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    
    def test_error_with_stack_trace(self, logger, log_capture):
        """Test error logging with stack trace (Requirement 19.2)."""
        try:
            raise ValueError('Test error')
        except ValueError as e:
            logger.error(
                'Error occurred',
                request_id='req-error-123',
                phone_number='+1234567890',
                error_type=type(e).__name__,
                error_message=str(e)
            )
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['level'] == 'ERROR'
        assert log_entry['request_id'] == 'req-error-123'
        assert log_entry['phone_number'] == '***7890'
        assert log_entry['error_type'] == 'ValueError'
        assert log_entry['error_message'] == 'Test error'
    
    def test_tool_execution_logging(self, logger, log_capture):
        """Test tool execution logging format (Requirement 19.3)."""
        logger.info(
            'Tool executed',
            request_id='req-tool-123',
            tool_name='schedule_session',
            parameters={
                'student_name': 'John Doe',
                'date': '2024-01-20',
                'time': '14:00'
            }
        )
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['tool_name'] == 'schedule_session'
        assert 'parameters' in log_entry
        assert log_entry['parameters']['student_name'] == 'John Doe'
    
    def test_external_api_call_logging(self, logger, log_capture):
        """Test external API call logging format (Requirement 19.4)."""
        logger.info(
            'External API call',
            request_id='req-api-123',
            api_name='twilio',
            endpoint='/Messages',
            method='POST',
            response_status=200
        )
        
        log_output = log_capture.getvalue()
        log_entry = json.loads(log_output.strip())
        
        assert log_entry['api_name'] == 'twilio'
        assert log_entry['endpoint'] == '/Messages'
        assert log_entry['method'] == 'POST'
        assert log_entry['response_status'] == 200
    
    def test_no_sensitive_data_in_logs(self, logger, log_capture):
        """Test that sensitive data is not logged in plain text (Requirement 19.6)."""
        # Simulate logging with OAuth token (should not be logged)
        logger.info(
            'Calendar sync',
            request_id='req-cal-123',
            phone_number='+1234567890',
            provider='google',
            # Note: In real usage, tokens should never be passed to logger
            status='success'
        )
        
        log_output = log_capture.getvalue()
        
        # Phone number should be masked
        assert '+1234567890' not in log_output
        assert '***7890' in log_output


class TestGetLogger:
    """Test suite for get_logger factory function."""
    
    def test_get_logger_returns_structured_logger(self):
        """Test that get_logger returns a StructuredLogger instance."""
        logger = get_logger('test_module')
        assert isinstance(logger, StructuredLogger)
        assert logger.logger.name == 'test_module'
    
    def test_get_logger_with_module_name(self):
        """Test get_logger with __name__ pattern."""
        logger = get_logger(__name__)
        assert isinstance(logger, StructuredLogger)
        assert logger.logger.name == __name__


class TestPhoneNumberMasking:
    """Test suite specifically for phone number masking logic."""
    
    @pytest.fixture
    def logger(self):
        return StructuredLogger('test_masking')
    
    def test_mask_various_formats(self, logger):
        """Test masking with various phone number formats."""
        test_cases = [
            ('+1234567890', '***7890'),
            ('1234567890', '***7890'),
            ('+44 20 1234 5678', '***5678'),
            ('(555) 123-4567', '***4567'),
            ('555-1234', '***1234'),
        ]
        
        for phone, expected_mask in test_cases:
            masked = logger._mask_phone_number(phone)
            assert masked == expected_mask, f"Failed for {phone}"
    
    def test_mask_edge_cases(self, logger):
        """Test masking edge cases."""
        assert logger._mask_phone_number('') is None
        assert logger._mask_phone_number('1') == '***'
        assert logger._mask_phone_number('12') == '***'
        assert logger._mask_phone_number('123') == '***'
        assert logger._mask_phone_number('1234') == '***1234'
        assert logger._mask_phone_number(None) is None
