"""
Unit tests for conversation handlers.

Tests the OnboardingHandler, TrainerHandler, and StudentHandler classes
for proper message routing and response generation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from src.services.conversation_handlers import (
    OnboardingHandler,
    TrainerHandler,
    StudentHandler,
)


class TestOnboardingHandler:
    """Test OnboardingHandler for trainer registration flow."""
    
    def test_welcome_message_for_new_user(self):
        """Test that new users receive welcome message."""
        # Arrange
        handler = OnboardingHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        handler.state_manager.get_state.return_value = None
        
        phone_number = "+14155551234"
        message_body = {"body": "Hello"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(phone_number, message_body, request_id)
        
        # Assert
        assert "Welcome to FitAgent" in response
        assert "Personal Trainer" in response
        assert "Student" in response
        handler.state_manager.update_state.assert_called_once()
    
    def test_trainer_selection_starts_registration(self):
        """Test that selecting trainer option starts registration flow."""
        # Arrange
        handler = OnboardingHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        handler.state_manager.get_state.return_value = {
            "state": "ONBOARDING",
            "context": {"step": "user_type"}
        }
        
        phone_number = "+14155551234"
        message_body = {"body": "1"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(phone_number, message_body, request_id)
        
        # Assert
        assert "trainer" in response.lower()
        assert "name" in response.lower()
        handler.state_manager.update_state.assert_called()
    
    def test_student_selection_provides_instructions(self):
        """Test that selecting student option provides instructions."""
        # Arrange
        handler = OnboardingHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        handler.state_manager.get_state.return_value = {
            "state": "ONBOARDING",
            "context": {"step": "user_type"}
        }
        
        phone_number = "+14155551234"
        message_body = {"body": "2"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(phone_number, message_body, request_id)
        
        # Assert
        assert "trainer" in response.lower()
        assert "registered by" in response.lower()
    
    def test_complete_trainer_registration_flow(self):
        """Test complete trainer registration creates trainer record."""
        # Arrange
        handler = OnboardingHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        handler.state_manager.get_state.return_value = {
            "state": "ONBOARDING",
            "context": {
                "step": "trainer_business",
                "trainer_name": "John Doe",
                "trainer_email": "john@example.com",
                "user_type": "trainer"
            }
        }
        
        phone_number = "+14155551234"
        message_body = {"body": "Fitness Pro"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(phone_number, message_body, request_id)
        
        # Assert
        assert "Welcome" in response
        assert "John Doe" in response
        handler.dynamodb.put_trainer.assert_called_once()
        
        # Verify trainer data
        trainer_data = handler.dynamodb.put_trainer.call_args[0][0]
        assert trainer_data.name == "John Doe"
        assert trainer_data.email == "john@example.com"
        assert trainer_data.business_name == "Fitness Pro"
        assert trainer_data.phone_number == "+14155551234"


class TestTrainerHandler:
    """Test TrainerHandler for AI agent integration."""
    
    def test_trainer_message_processed_by_ai_agent(self):
        """Test that trainer messages are processed by AI agent."""
        # Arrange
        mock_ai_agent = Mock()
        mock_ai_agent.process_message.return_value = {
            "success": True,
            "response": "I've scheduled the session for tomorrow at 2 PM.",
            "tool_calls": []
        }
        
        handler = TrainerHandler(ai_agent=mock_ai_agent)
        handler.state_manager = Mock()
        handler.state_manager.get_state.return_value = {
            "state": "TRAINER_MENU",
            "message_history": []
        }
        
        trainer_id = "trainer-123"
        user_data = {"phone_number": "+14155551234", "name": "John"}
        message_body = {"body": "Schedule a session with Sarah tomorrow at 2pm"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(trainer_id, user_data, message_body, request_id)
        
        # Assert
        assert "scheduled" in response.lower()
        mock_ai_agent.process_message.assert_called_once()
        
        # Verify AI agent was called with correct parameters
        call_args = mock_ai_agent.process_message.call_args
        assert call_args[1]["trainer_id"] == trainer_id
        assert "Sarah" in call_args[1]["message"]
    
    def test_trainer_handler_updates_conversation_state(self):
        """Test that conversation state is updated after processing."""
        # Arrange
        mock_ai_agent = Mock()
        mock_ai_agent.process_message.return_value = {
            "success": True,
            "response": "Done!",
            "tool_calls": []
        }
        
        mock_state_manager = Mock()
        mock_state_manager.get_state.return_value = {
            "state": "TRAINER_MENU",
            "message_history": []
        }
        
        handler = TrainerHandler(
            ai_agent=mock_ai_agent,
            state_manager=mock_state_manager
        )
        
        trainer_id = "trainer-123"
        user_data = {"phone_number": "+14155551234", "name": "John"}
        message_body = {"body": "Test message"}
        request_id = "test-123"
        
        # Act
        handler.handle_message(trainer_id, user_data, message_body, request_id)
        
        # Assert - state should be updated twice (user message + assistant response)
        assert mock_state_manager.update_state.call_count == 2
    
    def test_trainer_handler_handles_ai_agent_errors(self):
        """Test that AI agent errors are handled gracefully."""
        # Arrange
        mock_ai_agent = Mock()
        mock_ai_agent.process_message.return_value = {
            "success": False,
            "error": "Failed to process request"
        }
        
        handler = TrainerHandler(ai_agent=mock_ai_agent)
        handler.state_manager = Mock()
        handler.state_manager.get_state.return_value = None
        
        trainer_id = "trainer-123"
        user_data = {"phone_number": "+14155551234", "name": "John"}
        message_body = {"body": "Test message"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(trainer_id, user_data, message_body, request_id)
        
        # Assert
        assert "trouble" in response.lower() or "error" in response.lower()


class TestStudentHandler:
    """Test StudentHandler for session viewing."""
    
    def test_student_receives_menu_for_unknown_request(self):
        """Test that students receive menu for unrecognized messages."""
        # Arrange
        handler = StudentHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        
        student_id = "student-123"
        user_data = {"phone_number": "+14155551234", "name": "Sarah"}
        message_body = {"body": "Hello"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(student_id, user_data, message_body, request_id)
        
        # Assert
        assert "Sarah" in response
        assert "upcoming sessions" in response.lower()
        assert "confirm" in response.lower()
    
    def test_view_upcoming_sessions_shows_sessions(self):
        """Test that students can view their upcoming sessions."""
        # Arrange
        handler = StudentHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        
        # Mock session data
        now = datetime.utcnow()
        future_session = now + timedelta(days=2)
        
        handler.dynamodb.get_student_sessions.return_value = [
            {
                "session_id": "session-123",
                "session_datetime": future_session.isoformat(),
                "trainer_name": "John Doe",
                "duration_minutes": 60,
                "location": "Gym A",
                "status": "scheduled",
                "student_confirmed": False
            }
        ]
        
        student_id = "student-123"
        user_data = {"phone_number": "+14155551234", "name": "Sarah"}
        message_body = {"body": "Show my sessions"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(student_id, user_data, message_body, request_id)
        
        # Assert
        assert "upcoming sessions" in response.lower()
        assert "John Doe" in response
        assert "60 minutes" in response
        assert "Gym A" in response
        handler.dynamodb.get_student_sessions.assert_called_once()
    
    def test_no_upcoming_sessions_message(self):
        """Test message when student has no upcoming sessions."""
        # Arrange
        handler = StudentHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        handler.dynamodb.get_student_sessions.return_value = []
        
        student_id = "student-123"
        user_data = {"phone_number": "+14155551234", "name": "Sarah"}
        message_body = {"body": "Show my sessions"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(student_id, user_data, message_body, request_id)
        
        # Assert
        assert "don't have any" in response.lower()
        assert "upcoming sessions" in response.lower()
    
    def test_sessions_ordered_chronologically(self):
        """Test that sessions are displayed in chronological order."""
        # Arrange
        handler = StudentHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        
        # Mock multiple sessions
        now = datetime.utcnow()
        session1 = now + timedelta(days=1)
        session2 = now + timedelta(days=5)
        
        handler.dynamodb.get_student_sessions.return_value = [
            {
                "session_id": "session-1",
                "session_datetime": session1.isoformat(),
                "trainer_name": "John Doe",
                "duration_minutes": 60,
                "status": "scheduled",
                "student_confirmed": False
            },
            {
                "session_id": "session-2",
                "session_datetime": session2.isoformat(),
                "trainer_name": "Jane Smith",
                "duration_minutes": 45,
                "status": "scheduled",
                "student_confirmed": True
            }
        ]
        
        student_id = "student-123"
        user_data = {"phone_number": "+14155551234", "name": "Sarah"}
        message_body = {"body": "Show my sessions"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(student_id, user_data, message_body, request_id)
        
        # Assert
        assert "John Doe" in response
        assert "Jane Smith" in response
        # First session should appear before second
        assert response.index("John Doe") < response.index("Jane Smith")
        # Check confirmation status
        assert "Confirmed" in response  # session2 is confirmed
    
    def test_student_confirms_attendance(self):
        """Test that student can confirm attendance for upcoming session."""
        # Arrange
        handler = StudentHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        
        now = datetime.utcnow()
        future_session = now + timedelta(days=2)
        
        # Mock unconfirmed session
        session_data = {
            "session_id": "session-123",
            "trainer_id": "trainer-456",
            "session_datetime": future_session.isoformat(),
            "trainer_name": "John Doe",
            "duration_minutes": 60,
            "status": "scheduled",
            "student_confirmed": False
        }
        
        handler.dynamodb.get_student_sessions.return_value = [session_data]
        
        student_id = "student-123"
        user_data = {"phone_number": "+14155551234", "name": "Sarah"}
        message_body = {"body": "confirm"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(student_id, user_data, message_body, request_id)
        
        # Assert
        assert "confirmed" in response.lower()
        assert "John Doe" in response
        handler.dynamodb.put_session.assert_called_once()
        
        # Verify session was updated with confirmation
        updated_session = handler.dynamodb.put_session.call_args[0][0]
        assert updated_session["student_confirmed"] is True
        assert "student_confirmed_at" in updated_session
    
    def test_student_confirms_when_all_already_confirmed(self):
        """Test message when all sessions are already confirmed."""
        # Arrange
        handler = StudentHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        
        now = datetime.utcnow()
        future_session = now + timedelta(days=2)
        
        # Mock already confirmed session
        handler.dynamodb.get_student_sessions.return_value = [
            {
                "session_id": "session-123",
                "session_datetime": future_session.isoformat(),
                "trainer_name": "John Doe",
                "status": "scheduled",
                "student_confirmed": True
            }
        ]
        
        student_id = "student-123"
        user_data = {"phone_number": "+14155551234", "name": "Sarah"}
        message_body = {"body": "confirm"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(student_id, user_data, message_body, request_id)
        
        # Assert
        assert "already confirmed" in response.lower()
        handler.dynamodb.put_session.assert_not_called()
    
    def test_student_confirms_when_no_sessions(self):
        """Test message when student has no sessions to confirm."""
        # Arrange
        handler = StudentHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        handler.dynamodb.get_student_sessions.return_value = []
        
        student_id = "student-123"
        user_data = {"phone_number": "+14155551234", "name": "Sarah"}
        message_body = {"body": "confirm"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(student_id, user_data, message_body, request_id)
        
        # Assert
        assert "don't have any" in response.lower()
        handler.dynamodb.put_session.assert_not_called()
    
    def test_student_cancels_attendance(self):
        """Test that student can cancel attendance and trainer is notified."""
        # Arrange
        handler = StudentHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        
        now = datetime.utcnow()
        future_session = now + timedelta(days=2)
        
        # Mock session data
        session_data = {
            "session_id": "session-123",
            "trainer_id": "trainer-456",
            "student_name": "Sarah Smith",
            "session_datetime": future_session.isoformat(),
            "trainer_name": "John Doe",
            "duration_minutes": 60,
            "location": "Gym A",
            "status": "scheduled"
        }
        
        handler.dynamodb.get_student_sessions.return_value = [session_data]
        
        # Mock trainer data
        handler.dynamodb.get_trainer.return_value = {
            "trainer_id": "trainer-456",
            "name": "John Doe",
            "phone_number": "+14155559999"
        }
        
        student_id = "student-123"
        user_data = {"phone_number": "+14155551234", "name": "Sarah"}
        message_body = {"body": "cancel"}
        request_id = "test-123"
        
        # Act
        with patch('src.services.twilio_client.TwilioClient') as mock_twilio:
            mock_twilio_instance = Mock()
            mock_twilio.return_value = mock_twilio_instance
            
            response = handler.handle_message(student_id, user_data, message_body, request_id)
        
        # Assert
        assert "cancellation has been noted" in response.lower()
        assert "John Doe" in response
        
        # Verify trainer was notified
        mock_twilio_instance.send_message.assert_called_once()
        call_args = mock_twilio_instance.send_message.call_args
        assert call_args[1]["to"] == "+14155559999"
        assert "Sarah Smith" in call_args[1]["body"]
        assert "cancelled" in call_args[1]["body"].lower()
    
    def test_student_cancels_when_no_sessions(self):
        """Test message when student has no sessions to cancel."""
        # Arrange
        handler = StudentHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        handler.dynamodb.get_student_sessions.return_value = []
        
        student_id = "student-123"
        user_data = {"phone_number": "+14155551234", "name": "Sarah"}
        message_body = {"body": "cancel"}
        request_id = "test-123"
        
        # Act
        response = handler.handle_message(student_id, user_data, message_body, request_id)
        
        # Assert
        assert "don't have any" in response.lower()
    
    def test_student_cancels_continues_even_if_notification_fails(self):
        """Test that cancellation proceeds even if trainer notification fails."""
        # Arrange
        handler = StudentHandler()
        handler.dynamodb = Mock()
        handler.state_manager = Mock()
        
        now = datetime.utcnow()
        future_session = now + timedelta(days=2)
        
        session_data = {
            "session_id": "session-123",
            "trainer_id": "trainer-456",
            "student_name": "Sarah Smith",
            "session_datetime": future_session.isoformat(),
            "trainer_name": "John Doe",
            "duration_minutes": 60,
            "status": "scheduled"
        }
        
        handler.dynamodb.get_student_sessions.return_value = [session_data]
        handler.dynamodb.get_trainer.return_value = {
            "trainer_id": "trainer-456",
            "name": "John Doe",
            "phone_number": "+14155559999"
        }
        
        student_id = "student-123"
        user_data = {"phone_number": "+14155551234", "name": "Sarah"}
        message_body = {"body": "cancel"}
        request_id = "test-123"
        
        # Act
        with patch('src.services.twilio_client.TwilioClient') as mock_twilio:
            mock_twilio_instance = Mock()
            mock_twilio_instance.send_message.side_effect = Exception("Network error")
            mock_twilio.return_value = mock_twilio_instance
            
            response = handler.handle_message(student_id, user_data, message_body, request_id)
        
        # Assert - Student still gets confirmation even though notification failed
        assert "cancellation has been noted" in response.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
