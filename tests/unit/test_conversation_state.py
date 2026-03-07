"""
Unit tests for ConversationStateManager.

Tests conversation state management including state transitions,
message history, TTL calculation, and context management.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from src.services.conversation_state import ConversationStateManager
from src.models.entities import ConversationState, MessageHistoryEntry


@pytest.fixture
def mock_dynamodb():
    """Create a mock DynamoDB client."""
    return Mock()


@pytest.fixture
def state_manager(mock_dynamodb):
    """Create ConversationStateManager with mock DynamoDB client."""
    return ConversationStateManager(dynamodb_client=mock_dynamodb, ttl_hours=24)


class TestGetState:
    """Tests for get_state method."""
    
    def test_get_state_existing(self, state_manager, mock_dynamodb):
        """Test retrieving existing conversation state."""
        # Arrange
        phone = "+1234567890"
        now = datetime.utcnow()
        ttl = int((now + timedelta(hours=24)).timestamp())
        
        mock_dynamodb.get_item.return_value = {
            'PK': f'CONVERSATION#{phone}',
            'SK': 'STATE',
            'entity_type': 'CONVERSATION_STATE',
            'phone_number': phone,
            'state': 'TRAINER_MENU',
            'user_id': 'trainer123',
            'user_type': 'TRAINER',
            'context': {'last_action': 'view_students'},
            'message_history': [
                {
                    'role': 'user',
                    'content': 'Show my students',
                    'timestamp': now.isoformat()
                }
            ],
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'ttl': ttl
        }
        
        # Act
        result = state_manager.get_state(phone)
        
        # Assert
        assert result is not None
        assert result.phone_number == phone
        assert result.state == 'TRAINER_MENU'
        assert result.user_id == 'trainer123'
        assert result.user_type == 'TRAINER'
        assert result.context == {'last_action': 'view_students'}
        assert len(result.message_history) == 1
        assert result.message_history[0].role == 'user'
        assert result.message_history[0].content == 'Show my students'
        
        mock_dynamodb.get_item.assert_called_once_with(
            pk=f'CONVERSATION#{phone}',
            sk='STATE'
        )
    
    def test_get_state_not_found(self, state_manager, mock_dynamodb):
        """Test retrieving non-existent conversation state."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        
        # Act
        result = state_manager.get_state(phone)
        
        # Assert
        assert result is None
        mock_dynamodb.get_item.assert_called_once()


class TestUpdateState:
    """Tests for update_state method."""
    
    def test_update_state_new_conversation(self, state_manager, mock_dynamodb):
        """Test creating new conversation state."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        # Act
        result = state_manager.update_state(
            phone_number=phone,
            state="UNKNOWN"
        )
        
        # Assert
        assert result.phone_number == phone
        assert result.state == "UNKNOWN"
        assert result.user_id is None
        assert result.user_type is None
        assert result.context == {}
        assert result.message_history == []
        assert result.ttl > int(datetime.utcnow().timestamp())
        
        mock_dynamodb.put_item.assert_called_once()
        saved_item = mock_dynamodb.put_item.call_args[0][0]
        assert saved_item['PK'] == f'CONVERSATION#{phone}'
        assert saved_item['SK'] == 'STATE'
        assert saved_item['state'] == 'UNKNOWN'
    
    def test_update_state_with_user_identification(self, state_manager, mock_dynamodb):
        """Test updating state with user identification."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        # Act
        result = state_manager.update_state(
            phone_number=phone,
            state="TRAINER_MENU",
            user_id="trainer123",
            user_type="TRAINER"
        )
        
        # Assert
        assert result.state == "TRAINER_MENU"
        assert result.user_id == "trainer123"
        assert result.user_type == "TRAINER"
        
        saved_item = mock_dynamodb.put_item.call_args[0][0]
        assert saved_item['user_id'] == "trainer123"
        assert saved_item['user_type'] == "TRAINER"
    
    def test_update_state_with_message(self, state_manager, mock_dynamodb):
        """Test updating state with message addition."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        # Act
        result = state_manager.update_state(
            phone_number=phone,
            state="ONBOARDING",
            message={'role': 'user', 'content': 'Hello'}
        )
        
        # Assert
        assert len(result.message_history) == 1
        assert result.message_history[0].role == 'user'
        assert result.message_history[0].content == 'Hello'
        assert isinstance(result.message_history[0].timestamp, datetime)
    
    def test_update_state_message_history_limit(self, state_manager, mock_dynamodb):
        """Test that message history is limited to 10 messages."""
        # Arrange
        phone = "+1234567890"
        now = datetime.utcnow()
        
        # Create existing state with 10 messages
        existing_messages = [
            MessageHistoryEntry(
                role='user' if i % 2 == 0 else 'assistant',
                content=f'Message {i}',
                timestamp=now
            )
            for i in range(10)
        ]
        
        existing_state = ConversationState(
            phone_number=phone,
            state='TRAINER_MENU',
            message_history=existing_messages,
            created_at=now,
            updated_at=now,
            ttl=int((now + timedelta(hours=24)).timestamp())
        )
        
        mock_dynamodb.get_item.return_value = existing_state.to_dynamodb()
        mock_dynamodb.put_item.return_value = None
        
        # Act - Add 11th message
        result = state_manager.update_state(
            phone_number=phone,
            state="TRAINER_MENU",
            message={'role': 'user', 'content': 'Message 11'}
        )
        
        # Assert - Should have only 10 messages (oldest dropped)
        assert len(result.message_history) == 10
        assert result.message_history[0].content == 'Message 1'  # First message dropped
        assert result.message_history[-1].content == 'Message 11'  # New message added
    
    def test_update_state_with_context(self, state_manager, mock_dynamodb):
        """Test updating state with context data."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        context = {
            'last_action': 'schedule_session',
            'pending_data': {'student_name': 'John Doe'}
        }
        
        # Act
        result = state_manager.update_state(
            phone_number=phone,
            state="TRAINER_MENU",
            context=context
        )
        
        # Assert
        assert result.context == context
        
        saved_item = mock_dynamodb.put_item.call_args[0][0]
        assert saved_item['context'] == context
    
    def test_update_state_ttl_calculation(self, state_manager, mock_dynamodb):
        """Test that TTL is calculated correctly (24 hours from now)."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        before_time = datetime.utcnow()
        
        # Act
        result = state_manager.update_state(
            phone_number=phone,
            state="UNKNOWN"
        )
        
        after_time = datetime.utcnow()
        
        # Assert - TTL should be approximately 24 hours from now
        expected_ttl_min = int((before_time + timedelta(hours=24)).timestamp())
        expected_ttl_max = int((after_time + timedelta(hours=24)).timestamp())
        
        assert expected_ttl_min <= result.ttl <= expected_ttl_max
    
    def test_update_state_preserves_existing_data(self, state_manager, mock_dynamodb):
        """Test that updating state preserves existing data when not overridden."""
        # Arrange
        phone = "+1234567890"
        now = datetime.utcnow()
        
        existing_state = ConversationState(
            phone_number=phone,
            state='TRAINER_MENU',
            user_id='trainer123',
            user_type='TRAINER',
            context={'existing': 'data'},
            message_history=[],
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
            ttl=int((now + timedelta(hours=23)).timestamp())
        )
        
        mock_dynamodb.get_item.return_value = existing_state.to_dynamodb()
        mock_dynamodb.put_item.return_value = None
        
        # Act - Update only state, should preserve user_id and user_type
        result = state_manager.update_state(
            phone_number=phone,
            state="TRAINER_MENU",
            context={'new': 'data'}
        )
        
        # Assert
        assert result.user_id == 'trainer123'
        assert result.user_type == 'TRAINER'
        assert result.context == {'existing': 'data', 'new': 'data'}  # Merged
        assert result.created_at == existing_state.created_at  # Preserved


class TestClearState:
    """Tests for clear_state method."""
    
    def test_clear_state_success(self, state_manager, mock_dynamodb):
        """Test clearing existing conversation state."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.delete_item.return_value = True
        
        # Act
        result = state_manager.clear_state(phone)
        
        # Assert
        assert result is True
        mock_dynamodb.delete_item.assert_called_once_with(
            pk=f'CONVERSATION#{phone}',
            sk='STATE'
        )
    
    def test_clear_state_not_found(self, state_manager, mock_dynamodb):
        """Test clearing non-existent conversation state."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.delete_item.return_value = False
        
        # Act
        result = state_manager.clear_state(phone)
        
        # Assert
        assert result is False


class TestTransitionState:
    """Tests for transition_state method."""
    
    def test_transition_to_onboarding(self, state_manager, mock_dynamodb):
        """Test transitioning from UNKNOWN to ONBOARDING."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        # Act
        result = state_manager.transition_state(
            phone_number=phone,
            new_state="ONBOARDING"
        )
        
        # Assert
        assert result.state == "ONBOARDING"
        assert result.user_id is None
        assert result.user_type is None
    
    def test_transition_to_trainer_menu(self, state_manager, mock_dynamodb):
        """Test transitioning to TRAINER_MENU with user identification."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        # Act
        result = state_manager.transition_state(
            phone_number=phone,
            new_state="TRAINER_MENU",
            user_id="trainer123",
            user_type="TRAINER"
        )
        
        # Assert
        assert result.state == "TRAINER_MENU"
        assert result.user_id == "trainer123"
        assert result.user_type == "TRAINER"
    
    def test_transition_to_student_menu(self, state_manager, mock_dynamodb):
        """Test transitioning to STUDENT_MENU with user identification."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        # Act
        result = state_manager.transition_state(
            phone_number=phone,
            new_state="STUDENT_MENU",
            user_id="student456",
            user_type="STUDENT"
        )
        
        # Assert
        assert result.state == "STUDENT_MENU"
        assert result.user_id == "student456"
        assert result.user_type == "STUDENT"


class TestAddMessage:
    """Tests for add_message method."""
    
    def test_add_message_to_existing_state(self, state_manager, mock_dynamodb):
        """Test adding message to existing conversation."""
        # Arrange
        phone = "+1234567890"
        now = datetime.utcnow()
        
        existing_state = ConversationState(
            phone_number=phone,
            state='TRAINER_MENU',
            user_id='trainer123',
            user_type='TRAINER',
            context={},
            message_history=[],
            created_at=now,
            updated_at=now,
            ttl=int((now + timedelta(hours=24)).timestamp())
        )
        
        mock_dynamodb.get_item.return_value = existing_state.to_dynamodb()
        mock_dynamodb.put_item.return_value = None
        
        # Act
        result = state_manager.add_message(
            phone_number=phone,
            role='user',
            content='Hello'
        )
        
        # Assert
        assert len(result.message_history) == 1
        assert result.message_history[0].role == 'user'
        assert result.message_history[0].content == 'Hello'
        assert result.state == 'TRAINER_MENU'  # State unchanged
    
    def test_add_message_creates_state_if_not_exists(self, state_manager, mock_dynamodb):
        """Test adding message creates UNKNOWN state if none exists."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        # Act
        result = state_manager.add_message(
            phone_number=phone,
            role='user',
            content='Hello'
        )
        
        # Assert
        assert result.state == 'UNKNOWN'
        assert len(result.message_history) == 1
        assert result.message_history[0].content == 'Hello'


class TestGetMessageHistory:
    """Tests for get_message_history method."""
    
    def test_get_message_history_existing(self, state_manager, mock_dynamodb):
        """Test retrieving message history."""
        # Arrange
        phone = "+1234567890"
        now = datetime.utcnow()
        
        messages = [
            MessageHistoryEntry(role='user', content='Hello', timestamp=now),
            MessageHistoryEntry(role='assistant', content='Hi there', timestamp=now)
        ]
        
        existing_state = ConversationState(
            phone_number=phone,
            state='TRAINER_MENU',
            message_history=messages,
            created_at=now,
            updated_at=now,
            ttl=int((now + timedelta(hours=24)).timestamp())
        )
        
        mock_dynamodb.get_item.return_value = existing_state.to_dynamodb()
        
        # Act
        result = state_manager.get_message_history(phone)
        
        # Assert
        assert len(result) == 2
        assert result[0].role == 'user'
        assert result[0].content == 'Hello'
        assert result[1].role == 'assistant'
        assert result[1].content == 'Hi there'
    
    def test_get_message_history_no_state(self, state_manager, mock_dynamodb):
        """Test retrieving message history when no state exists."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        
        # Act
        result = state_manager.get_message_history(phone)
        
        # Assert
        assert result == []


class TestUpdateContext:
    """Tests for update_context method."""
    
    def test_update_context_existing_state(self, state_manager, mock_dynamodb):
        """Test updating context on existing state."""
        # Arrange
        phone = "+1234567890"
        now = datetime.utcnow()
        
        existing_state = ConversationState(
            phone_number=phone,
            state='TRAINER_MENU',
            context={'existing': 'data'},
            message_history=[],
            created_at=now,
            updated_at=now,
            ttl=int((now + timedelta(hours=24)).timestamp())
        )
        
        mock_dynamodb.get_item.return_value = existing_state.to_dynamodb()
        mock_dynamodb.put_item.return_value = None
        
        # Act
        result = state_manager.update_context(
            phone_number=phone,
            context_updates={'new': 'value'}
        )
        
        # Assert
        assert result.context == {'existing': 'data', 'new': 'value'}
        assert result.state == 'TRAINER_MENU'  # State unchanged
    
    def test_update_context_creates_state_if_not_exists(self, state_manager, mock_dynamodb):
        """Test updating context creates UNKNOWN state if none exists."""
        # Arrange
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        # Act
        result = state_manager.update_context(
            phone_number=phone,
            context_updates={'key': 'value'}
        )
        
        # Assert
        assert result.state == 'UNKNOWN'
        assert result.context == {'key': 'value'}


class TestCustomTTL:
    """Tests for custom TTL configuration."""
    
    def test_custom_ttl_hours(self, mock_dynamodb):
        """Test ConversationStateManager with custom TTL."""
        # Arrange
        custom_ttl = 48
        manager = ConversationStateManager(
            dynamodb_client=mock_dynamodb,
            ttl_hours=custom_ttl
        )
        
        phone = "+1234567890"
        mock_dynamodb.get_item.return_value = None
        mock_dynamodb.put_item.return_value = None
        
        before_time = datetime.utcnow()
        
        # Act
        result = manager.update_state(
            phone_number=phone,
            state="UNKNOWN"
        )
        
        after_time = datetime.utcnow()
        
        # Assert - TTL should be approximately 48 hours from now
        expected_ttl_min = int((before_time + timedelta(hours=custom_ttl)).timestamp())
        expected_ttl_max = int((after_time + timedelta(hours=custom_ttl)).timestamp())
        
        assert expected_ttl_min <= result.ttl <= expected_ttl_max
