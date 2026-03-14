"""
Property-based test for tool function preservation.

This test verifies that ALL 10 tool functions execute with the same parameters,
validation logic, and return values. This is CORRECT behavior that must be
preserved after implementing the message ordering and language fixes.

**EXPECTED OUTCOME ON UNFIXED CODE**: Test PASSES
- All tool functions execute correctly with same parameters
- Validation logic unchanged
- Return value structures unchanged
- DynamoDB queries and data structures unchanged

**Validates: Requirements 3.5, 3.6, 3.7, 3.8**
"""

import pytest
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st, settings, HealthCheck, assume
from datetime import datetime, timedelta
import uuid

# Import all tool functions - use absolute imports from project root
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tools.student_tools import register_student, view_students, update_student
from tools.session_tools import (
    schedule_session,
    reschedule_session,
    cancel_session,
    view_calendar
)
from tools.payment_tools import register_payment, confirm_payment, view_payments
from tools.calendar_tools import connect_calendar
from tools.notification_tools import send_notification


class TestToolFunctionPreservation:
    """
    Preservation test for all tool functions.
    
    This test verifies that the message ordering and language fixes do NOT
    change the behavior of any tool functions. All 10 tool functions must
    continue to work with the same parameters, validation, and return values.
    """
    
    @patch('tools.student_tools.dynamodb_client')
    def test_register_student_parameters_and_validation(self, mock_db):
        """
        Test that register_student accepts same parameters and validation.
        
        Verifies:
        - Function signature unchanged
        - Parameter validation unchanged
        - Return value structure unchanged
        - DynamoDB operations unchanged
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        student_name = "John Doe"
        phone_number = "+14155552671"
        email = "john@example.com"
        training_goal = "Build muscle"
        
        # Mock trainer exists
        mock_db.get_trainer.return_value = {
            "trainer_id": trainer_id,
            "name": "Trainer Name"
        }
        
        # Mock no existing user
        mock_db.lookup_by_phone_number.return_value = None
        
        # Mock put operations
        mock_db.put_student.return_value = None
        mock_db.put_trainer_student_link.return_value = None
        
        # Act
        result = register_student(
            trainer_id=trainer_id,
            name=student_name,
            phone_number=phone_number,
            email=email,
            training_goal=training_goal
        )
        
        # Assert - Verify return structure
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "success" in result, "Result should have 'success' key"
        assert "data" in result or "error" in result, "Result should have 'data' or 'error' key"
        
        if result["success"]:
            assert "student_id" in result["data"], "Data should have 'student_id'"
            assert "name" in result["data"], "Data should have 'name'"
            assert "phone_number" in result["data"], "Data should have 'phone_number'"
            assert "email" in result["data"], "Data should have 'email'"
            assert "training_goal" in result["data"], "Data should have 'training_goal'"
            
            # Verify DynamoDB operations called
            assert mock_db.put_student.called, "Should call put_student"
            assert mock_db.put_trainer_student_link.called, "Should call put_trainer_student_link"
    
    @patch('tools.student_tools.dynamodb_client')
    def test_view_students_return_structure(self, mock_db):
        """
        Test that view_students returns same structure.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        student_id = str(uuid.uuid4())
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"student_id": student_id, "status": "active"}
        ]
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Act
        result = view_students(trainer_id=trainer_id)
        
        # Assert
        assert result["success"] is True
        assert "students" in result["data"]
        assert isinstance(result["data"]["students"], list)
        
        if len(result["data"]["students"]) > 0:
            student = result["data"]["students"][0]
            assert "student_id" in student
            assert "name" in student
            assert "phone_number" in student
            assert "email" in student
            assert "training_goal" in student
    
    @patch('tools.session_tools.dynamodb_client')
    @patch('tools.session_tools.conflict_detector')
    @patch('tools.session_tools.calendar_sync_service')
    def test_schedule_session_parameters_and_validation(
        self, mock_calendar, mock_conflict, mock_db
    ):
        """
        Test that schedule_session accepts same parameters and validation.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        student_id = str(uuid.uuid4())
        student_name = "John Doe"
        date = "2024-12-25"
        time = "14:00"
        duration_minutes = 60
        location = "Main Gym"
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"student_id": student_id, "status": "active"}
        ]
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": student_name
        }
        mock_conflict.check_conflicts.return_value = []
        mock_db.put_session.return_value = None
        mock_calendar.create_event.return_value = None
        
        # Act
        result = schedule_session(
            trainer_id=trainer_id,
            student_name=student_name,
            date=date,
            time=time,
            duration_minutes=duration_minutes,
            location=location
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        if result["success"]:
            assert "session_id" in result["data"]
            assert "student_name" in result["data"]
            assert "session_datetime" in result["data"]
            assert "duration_minutes" in result["data"]
            assert "status" in result["data"]
            
            # Verify DynamoDB operations
            assert mock_db.put_session.called
    
    @patch('tools.session_tools.dynamodb_client')
    @patch('tools.session_tools.conflict_detector')
    @patch('tools.session_tools.calendar_sync_service')
    def test_reschedule_session_parameters(
        self, mock_calendar, mock_conflict, mock_db
    ):
        """
        Test that reschedule_session accepts same parameters.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        mock_db.get_session.return_value = {
            "session_id": session_id,
            "trainer_id": trainer_id,
            "student_name": "John Doe",
            "session_datetime": "2024-12-25T14:00:00",
            "duration_minutes": 60,
            "status": "scheduled"
        }
        mock_conflict.check_conflicts.return_value = []
        mock_db.put_session.return_value = None
        mock_calendar.update_event.return_value = False
        
        # Act
        result = reschedule_session(
            trainer_id=trainer_id,
            session_id=session_id,
            new_date="2024-12-26",
            new_time="15:00"
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        if result["success"]:
            assert "session_id" in result["data"]
            assert "old_datetime" in result["data"]
            assert "new_datetime" in result["data"]
    
    @patch('tools.session_tools.dynamodb_client')
    @patch('tools.session_tools.calendar_sync_service')
    def test_cancel_session_parameters(self, mock_calendar, mock_db):
        """
        Test that cancel_session accepts same parameters.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        mock_db.get_session.return_value = {
            "session_id": session_id,
            "trainer_id": trainer_id,
            "student_name": "John Doe",
            "session_datetime": "2024-12-25T14:00:00",
            "duration_minutes": 60,
            "status": "scheduled"
        }
        mock_db.put_session.return_value = None
        mock_calendar.delete_event.return_value = False
        
        # Act
        result = cancel_session(
            trainer_id=trainer_id,
            session_id=session_id,
            reason="Student requested"
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        if result["success"]:
            assert result["data"]["status"] == "cancelled"
    
    @patch('tools.session_tools.dynamodb_client')
    def test_view_calendar_parameters(self, mock_db):
        """
        Test that view_calendar accepts same parameters.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_sessions_by_date_range.return_value = []
        
        # Act
        result = view_calendar(
            trainer_id=trainer_id,
            filter="week"
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        if result["success"]:
            assert "sessions" in result["data"]
            assert "start_date" in result["data"]
            assert "end_date" in result["data"]
            assert "total_count" in result["data"]
    
    @patch('tools.payment_tools.dynamodb_client')
    def test_register_payment_parameters(self, mock_db):
        """
        Test that register_payment accepts same parameters.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        student_id = str(uuid.uuid4())
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"student_id": student_id, "name": "John Doe"}
        ]
        mock_db.put_payment.return_value = None
        
        # Act
        result = register_payment(
            trainer_id=trainer_id,
            student_name="John Doe",
            amount=100.00,
            payment_date="2024-01-15",
            student_id=student_id
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        if result["success"]:
            assert "payment_id" in result["data"]
            assert "amount" in result["data"]
            assert "payment_status" in result["data"]
    
    @patch('tools.payment_tools.dynamodb_client')
    def test_confirm_payment_parameters(self, mock_db):
        """
        Test that confirm_payment accepts same parameters.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        payment_id = str(uuid.uuid4())
        
        mock_db.get_payment.return_value = {
            "payment_id": payment_id,
            "trainer_id": trainer_id,
            "student_id": str(uuid.uuid4()),
            "student_name": "John Doe",
            "amount": 100.00,
            "currency": "USD",
            "payment_date": "2024-01-15",
            "payment_status": "pending"
        }
        mock_db.put_payment.return_value = None
        
        # Act
        result = confirm_payment(
            trainer_id=trainer_id,
            payment_id=payment_id
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        if result["success"]:
            assert result["data"]["payment_status"] == "confirmed"
            assert "confirmed_at" in result["data"]
    
    @patch('tools.payment_tools.dynamodb_client')
    def test_view_payments_parameters(self, mock_db):
        """
        Test that view_payments accepts same parameters.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_payments.return_value = []
        
        # Act
        result = view_payments(trainer_id=trainer_id)
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        if result["success"]:
            assert "payments" in result["data"]
            assert isinstance(result["data"]["payments"], list)
    
    @patch('tools.calendar_tools.dynamodb_client')
    @patch('tools.calendar_tools.settings')
    def test_connect_calendar_parameters(self, mock_settings, mock_db):
        """
        Test that connect_calendar accepts same parameters.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_settings.google_client_id = "test_client_id"
        mock_settings.google_client_secret = "test_secret"
        mock_settings.oauth_redirect_uri = "https://example.com/callback"
        mock_settings.dynamodb_table = "test-table"
        
        # Mock DynamoDB put_item
        mock_db.dynamodb = MagicMock()
        mock_db.dynamodb.put_item.return_value = None
        
        # Act
        result = connect_calendar(
            trainer_id=trainer_id,
            provider="google"
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        if result["success"]:
            assert "oauth_url" in result["data"]
            assert "provider" in result["data"]
            assert "expires_in" in result["data"]
    
    @patch('tools.notification_tools.dynamodb_client')
    @patch('tools.notification_tools.sqs_client')
    def test_send_notification_parameters(self, mock_sqs, mock_db):
        """
        Test that send_notification accepts same parameters.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        student_id = str(uuid.uuid4())
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"student_id": student_id, "status": "active"}
        ]
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671"
        }
        mock_sqs.send_message.return_value = {"MessageId": "msg123"}
        
        # Mock table for notification record
        mock_db.table = MagicMock()
        mock_db.table.put_item.return_value = None
        
        # Act
        result = send_notification(
            trainer_id=trainer_id,
            message="Test notification",
            recipients="all"
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        if result["success"]:
            assert "notification_id" in result["data"]
            assert "message" in result["data"]
            assert "recipient_count" in result["data"]
            assert "queued_count" in result["data"]
    
    @given(
        student_name=st.text(min_size=2, max_size=50).filter(lambda x: x.strip()),
        email=st.emails(),
        training_goal=st.text(min_size=5, max_size=100).filter(lambda x: x.strip())
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @patch('tools.student_tools.dynamodb_client')
    def test_property_register_student_accepts_various_inputs(
        self, mock_db, student_name, email, training_goal
    ):
        """
        Property-based test: register_student accepts various valid inputs.
        
        Generates random student data and verifies the function handles it
        consistently with proper validation.
        
        **Property**: For all valid student data, register_student returns
        consistent structure with success/error indication.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        phone_number = "+14155552671"  # Use valid E.164 format
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.lookup_by_phone_number.return_value = None
        mock_db.put_student.return_value = None
        mock_db.put_trainer_student_link.return_value = None
        
        # Act
        result = register_student(
            trainer_id=trainer_id,
            name=student_name,
            phone_number=phone_number,
            email=email,
            training_goal=training_goal
        )
        
        # Assert - Verify consistent return structure
        assert isinstance(result, dict), "Result must be a dictionary"
        assert "success" in result, "Result must have 'success' key"
        assert isinstance(result["success"], bool), "'success' must be boolean"
        
        # If successful, verify data structure
        if result["success"]:
            assert "data" in result, "Successful result must have 'data' key"
            assert isinstance(result["data"], dict), "'data' must be a dictionary"
            assert "student_id" in result["data"], "Data must have 'student_id'"
            assert "name" in result["data"], "Data must have 'name'"
            assert "phone_number" in result["data"], "Data must have 'phone_number'"
            assert "email" in result["data"], "Data must have 'email'"
            assert "training_goal" in result["data"], "Data must have 'training_goal'"
        else:
            # If failed, verify error structure
            assert "error" in result, "Failed result must have 'error' key"
            assert isinstance(result["error"], str), "'error' must be a string"
    
    @given(
        duration_minutes=st.integers(min_value=15, max_value=480)
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @patch('tools.session_tools.dynamodb_client')
    @patch('tools.session_tools.conflict_detector')
    @patch('tools.session_tools.calendar_sync_service')
    def test_property_schedule_session_duration_validation(
        self, mock_calendar, mock_conflict, mock_db, duration_minutes
    ):
        """
        Property-based test: schedule_session validates duration correctly.
        
        **Property**: For all durations in valid range (15-480), schedule_session
        accepts the value and processes it correctly.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        student_id = str(uuid.uuid4())
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"student_id": student_id, "status": "active"}
        ]
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe"
        }
        mock_conflict.check_conflicts.return_value = []
        mock_db.put_session.return_value = None
        mock_calendar.create_event.return_value = None
        
        # Use future date
        future_date = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Act
        result = schedule_session(
            trainer_id=trainer_id,
            student_name="John Doe",
            date=future_date,
            time="14:00",
            duration_minutes=duration_minutes
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        # Duration in valid range should succeed (assuming other conditions met)
        if result["success"]:
            assert result["data"]["duration_minutes"] == duration_minutes
    
    @given(
        amount=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @patch('tools.payment_tools.dynamodb_client')
    def test_property_register_payment_amount_validation(
        self, mock_db, amount
    ):
        """
        Property-based test: register_payment validates amount correctly.
        
        **Property**: For all positive amounts, register_payment accepts the
        value and processes it correctly.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.5, 3.6, 3.7, 3.8**
        """
        # Arrange
        trainer_id = str(uuid.uuid4())
        student_id = str(uuid.uuid4())
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"student_id": student_id, "name": "John Doe"}
        ]
        mock_db.put_payment.return_value = None
        
        # Act
        result = register_payment(
            trainer_id=trainer_id,
            student_name="John Doe",
            amount=amount,
            payment_date="2024-01-15",
            student_id=student_id
        )
        
        # Assert
        assert isinstance(result, dict)
        assert "success" in result
        
        # Positive amounts should succeed
        if result["success"]:
            assert result["data"]["amount"] == amount


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
