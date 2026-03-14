"""
Integration tests for message processor with conversation handlers.

Tests the complete flow from SQS message to handler response.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.handlers.message_processor import (
    lambda_handler,
    _process_message,
    _handle_onboarding,
    _handle_trainer,
    _handle_student,
)


class TestMessageProcessorIntegration:
    """Integration tests for message processor with handlers."""
    
    @patch('src.handlers.message_processor.onboarding_handler')
    @patch('src.handlers.message_processor.message_router')
    def test_onboarding_flow_integration(self, mock_router, mock_onboarding):
        """
        Test complete onboarding flow through message processor.
        
        Language expectation: Portuguese
        Expected: Welcome message in Portuguese
        """
        # Arrange
        mock_router.route_message.return_value = {
            "handler_type": "onboarding",
            "user_id": None,
            "entity_type": None,
            "user_data": None,
        }
        
        mock_onboarding.handle_message.return_value = (
            "Bem-vindo ao FitAgent! Você é personal trainer ou aluno?"
        )
        
        phone_number = "+14155551234"
        message_body = {
            "from": phone_number,
            "body": "Hello",
            "message_sid": "SM123"
        }
        
        # Act
        response = _process_message(
            phone_number=phone_number,
            message_body=message_body,
            request_id="test-123"
        )
        
        # Assert - Expect Portuguese welcome message
        assert "Bem-vindo" in response or "FitAgent" in response
        mock_router.route_message.assert_called_once()
        mock_onboarding.handle_message.assert_called_once()
    
    @patch('src.handlers.message_processor.trainer_handler')
    @patch('src.handlers.message_processor.message_router')
    def test_trainer_flow_integration(self, mock_router, mock_trainer):
        """
        Test complete trainer flow through message processor.
        
        Language expectation: Portuguese
        Expected: Session scheduling confirmation in Portuguese
        """
        # Arrange
        trainer_id = "trainer-123"
        user_data = {
            "trainer_id": trainer_id,
            "name": "John Doe",
            "phone_number": "+14155551234"
        }
        
        mock_router.route_message.return_value = {
            "handler_type": "trainer",
            "user_id": trainer_id,
            "entity_type": "TRAINER",
            "user_data": user_data,
        }
        
        mock_trainer.handle_message.return_value = (
            "Agendei uma sessão com Sarah para amanhã às 14h."
        )
        
        phone_number = "+14155551234"
        message_body = {
            "from": phone_number,
            "body": "Schedule a session with Sarah tomorrow at 2pm",
            "message_sid": "SM123"
        }
        
        # Act
        response = _process_message(
            phone_number=phone_number,
            message_body=message_body,
            request_id="test-123"
        )
        
        # Assert - Expect Portuguese response
        assert "agendei" in response.lower() or "scheduled" in response.lower()
        mock_router.route_message.assert_called_once()
        mock_trainer.handle_message.assert_called_once_with(
            trainer_id=trainer_id,
            user_data=user_data,
            message_body=message_body,
            request_id="test-123"
        )
    
    @patch('src.handlers.message_processor.student_handler')
    @patch('src.handlers.message_processor.message_router')
    def test_student_flow_integration(self, mock_router, mock_student):
        """
        Test complete student flow through message processor.
        
        Language expectation: Portuguese
        Expected: Session list in Portuguese
        """
        # Arrange
        student_id = "student-123"
        user_data = {
            "student_id": student_id,
            "name": "Sarah",
            "phone_number": "+14155551234"
        }
        
        mock_router.route_message.return_value = {
            "handler_type": "student",
            "user_id": student_id,
            "entity_type": "STUDENT",
            "user_data": user_data,
        }
        
        mock_student.handle_message.return_value = (
            "Suas próximas sessões:\n1. Amanhã às 14:00 com John Doe"
        )
        
        phone_number = "+14155551234"
        message_body = {
            "from": phone_number,
            "body": "Show my sessions",
            "message_sid": "SM123"
        }
        
        # Act
        response = _process_message(
            phone_number=phone_number,
            message_body=message_body,
            request_id="test-123"
        )
        
        # Assert - Expect Portuguese response
        assert "próximas" in response.lower() or "upcoming sessions" in response.lower()
        mock_router.route_message.assert_called_once()
        mock_student.handle_message.assert_called_once_with(
            student_id=student_id,
            user_data=user_data,
            message_body=message_body,
            request_id="test-123"
        )
    
    @patch('src.handlers.message_processor.twilio_client')
    @patch('src.handlers.message_processor.message_router')
    @patch('src.handlers.message_processor.onboarding_handler')
    def test_lambda_handler_sqs_event(self, mock_onboarding, mock_router, mock_twilio):
        """
        Test lambda handler processes SQS event correctly.
        
        Language expectation: Portuguese
        Expected: Welcome message sent via Twilio in Portuguese
        """
        # Arrange
        mock_router.route_message.return_value = {
            "handler_type": "onboarding",
            "user_id": None,
            "entity_type": None,
            "user_data": None,
        }
        
        mock_onboarding.handle_message.return_value = "Bem-vindo!"
        mock_twilio.send_message.return_value = {
            "message_sid": "SM456",
            "status": "queued"
        }
        
        # Create SQS event
        event = {
            "Records": [
                {
                    "messageId": "msg-123",
                    "receiptHandle": "receipt-handle",
                    "body": json.dumps({
                        "from": "+14155551234",
                        "body": "Hello",
                        "message_sid": "SM123"
                    }),
                    "attributes": {
                        "ApproximateReceiveCount": "1"
                    },
                    "messageAttributes": {
                        "request_id": {"stringValue": "test-123"}
                    }
                }
            ]
        }
        
        context = Mock()
        context.function_name = "test-function"
        
        # Act
        result = lambda_handler(event, context)
        
        # Assert
        assert result["batchItemFailures"] == []
        mock_twilio.send_message.assert_called_once()
        
        # Verify Twilio was called with correct parameters
        call_args = mock_twilio.send_message.call_args
        assert call_args[1]["to"] == "+14155551234"
        assert call_args[1]["body"] == "Bem-vindo!"
    
    @patch('src.handlers.message_processor.message_router')
    def test_lambda_handler_handles_processing_errors(self, mock_router):
        """Test lambda handler handles processing errors correctly."""
        # Arrange
        mock_router.route_message.side_effect = Exception("Database error")
        
        # Create SQS event
        event = {
            "Records": [
                {
                    "messageId": "msg-123",
                    "receiptHandle": "receipt-handle",
                    "body": json.dumps({
                        "from": "+14155551234",
                        "body": "Hello",
                        "message_sid": "SM123"
                    }),
                    "attributes": {
                        "ApproximateReceiveCount": "1"
                    },
                    "messageAttributes": {
                        "request_id": {"stringValue": "test-123"}
                    }
                }
            ]
        }
        
        context = Mock()
        context.function_name = "test-function"
        
        # Act
        result = lambda_handler(event, context)
        
        # Assert - message should be marked as failed for retry
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
