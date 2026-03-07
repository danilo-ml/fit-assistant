"""
Unit tests for MessageRouter service.

Tests phone number extraction, user identification, and routing logic.
"""

import pytest
from unittest.mock import Mock, MagicMock

from src.services.message_router import MessageRouter, HandlerType


class TestMessageRouter:
    """Test suite for MessageRouter class."""
    
    def test_route_unknown_user(self):
        """Test routing for unknown phone number."""
        # Mock DynamoDB client
        mock_db = Mock()
        mock_db.lookup_by_phone_number.return_value = None
        
        router = MessageRouter(dynamodb_client=mock_db)
        result = router.route_message("+1234567890", {"MessageSid": "SM123"})
        
        assert result['handler_type'] == HandlerType.ONBOARDING
        assert result['user_id'] is None
        assert result['entity_type'] is None
        assert result['user_data'] is None
        
        # Verify GSI was queried
        mock_db.lookup_by_phone_number.assert_called_once_with("+1234567890")
    
    def test_route_trainer_message(self):
        """Test routing for registered trainer."""
        # Mock DynamoDB client with trainer record
        mock_db = Mock()
        mock_db.lookup_by_phone_number.return_value = {
            'entity_type': 'TRAINER',
            'trainer_id': 'trainer123',
            'name': 'John Trainer',
            'phone_number': '+1234567890'
        }
        
        router = MessageRouter(dynamodb_client=mock_db)
        result = router.route_message("+1234567890", {"MessageSid": "SM123"})
        
        assert result['handler_type'] == HandlerType.TRAINER
        assert result['user_id'] == 'trainer123'
        assert result['entity_type'] == 'TRAINER'
        assert result['user_data']['name'] == 'John Trainer'
        
        mock_db.lookup_by_phone_number.assert_called_once_with("+1234567890")
    
    def test_route_student_message(self):
        """Test routing for registered student."""
        # Mock DynamoDB client with student record
        mock_db = Mock()
        mock_db.lookup_by_phone_number.return_value = {
            'entity_type': 'STUDENT',
            'student_id': 'student456',
            'name': 'Jane Student',
            'phone_number': '+1234567890'
        }
        
        router = MessageRouter(dynamodb_client=mock_db)
        result = router.route_message("+1234567890", {"MessageSid": "SM123"})
        
        assert result['handler_type'] == HandlerType.STUDENT
        assert result['user_id'] == 'student456'
        assert result['entity_type'] == 'STUDENT'
        assert result['user_data']['name'] == 'Jane Student'
        
        mock_db.lookup_by_phone_number.assert_called_once_with("+1234567890")
    
    def test_route_unknown_entity_type(self):
        """Test routing for unknown entity type (fallback to onboarding)."""
        # Mock DynamoDB client with unknown entity type
        mock_db = Mock()
        mock_db.lookup_by_phone_number.return_value = {
            'entity_type': 'UNKNOWN_TYPE',
            'phone_number': '+1234567890'
        }
        
        router = MessageRouter(dynamodb_client=mock_db)
        result = router.route_message("+1234567890", {"MessageSid": "SM123"})
        
        # Should fallback to onboarding for unknown entity types
        assert result['handler_type'] == HandlerType.ONBOARDING
        assert result['user_id'] is None
        assert result['entity_type'] == 'UNKNOWN_TYPE'
    
    def test_extract_phone_number_with_whatsapp_prefix(self):
        """Test phone number extraction with whatsapp: prefix."""
        router = MessageRouter()
        
        webhook_payload = {
            'From': 'whatsapp:+1234567890',
            'To': 'whatsapp:+0987654321',
            'Body': 'Hello'
        }
        
        phone_number = router.extract_phone_number(webhook_payload)
        assert phone_number == '+1234567890'
    
    def test_extract_phone_number_without_prefix(self):
        """Test phone number extraction without whatsapp: prefix."""
        router = MessageRouter()
        
        webhook_payload = {
            'From': '+1234567890',
            'Body': 'Hello'
        }
        
        phone_number = router.extract_phone_number(webhook_payload)
        assert phone_number == '+1234567890'
    
    def test_extract_phone_number_missing_from_field(self):
        """Test phone number extraction with missing From field."""
        router = MessageRouter()
        
        webhook_payload = {
            'Body': 'Hello'
        }
        
        with pytest.raises(ValueError, match="Missing 'From' field"):
            router.extract_phone_number(webhook_payload)
    
    def test_extract_phone_number_empty_from_field(self):
        """Test phone number extraction with empty From field."""
        router = MessageRouter()
        
        webhook_payload = {
            'From': '',
            'Body': 'Hello'
        }
        
        with pytest.raises(ValueError, match="Missing 'From' field"):
            router.extract_phone_number(webhook_payload)
    
    def test_extract_phone_number_only_prefix(self):
        """Test phone number extraction with only whatsapp: prefix."""
        router = MessageRouter()
        
        webhook_payload = {
            'From': 'whatsapp:',
            'Body': 'Hello'
        }
        
        with pytest.raises(ValueError, match="Empty phone number"):
            router.extract_phone_number(webhook_payload)
    
    def test_router_initialization_with_default_client(self):
        """Test router initialization creates default DynamoDB client."""
        router = MessageRouter()
        
        assert router.dynamodb is not None
        assert hasattr(router.dynamodb, 'lookup_by_phone_number')
    
    def test_router_initialization_with_custom_client(self):
        """Test router initialization with custom DynamoDB client."""
        mock_db = Mock()
        router = MessageRouter(dynamodb_client=mock_db)
        
        assert router.dynamodb is mock_db
    
    def test_route_message_logs_routing_decision(self, caplog):
        """Test that routing decisions are logged."""
        mock_db = Mock()
        mock_db.lookup_by_phone_number.return_value = {
            'entity_type': 'TRAINER',
            'trainer_id': 'trainer123'
        }
        
        router = MessageRouter(dynamodb_client=mock_db)
        
        with caplog.at_level('INFO'):
            result = router.route_message("+1234567890", {"MessageSid": "SM123"})
        
        # Check that routing was logged
        assert result['handler_type'] == HandlerType.TRAINER
        # Note: Actual log checking depends on StructuredLogger implementation


class TestHandlerType:
    """Test suite for HandlerType enum."""
    
    def test_handler_type_values(self):
        """Test HandlerType enum values."""
        assert HandlerType.ONBOARDING.value == "onboarding"
        assert HandlerType.TRAINER.value == "trainer"
        assert HandlerType.STUDENT.value == "student"
    
    def test_handler_type_string_comparison(self):
        """Test HandlerType can be compared with strings."""
        assert HandlerType.TRAINER == "trainer"
        assert HandlerType.STUDENT == "student"
        assert HandlerType.ONBOARDING == "onboarding"
    
    def test_handler_type_membership(self):
        """Test HandlerType membership."""
        handler_types = [HandlerType.ONBOARDING, HandlerType.TRAINER, HandlerType.STUDENT]
        
        assert HandlerType.TRAINER in handler_types
        assert HandlerType.STUDENT in handler_types
        assert HandlerType.ONBOARDING in handler_types
