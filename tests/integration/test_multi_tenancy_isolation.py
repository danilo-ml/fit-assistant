"""
Integration tests for multi-tenancy data isolation.

These tests verify that trainers cannot access each other's data
through the tool functions, ensuring proper multi-tenancy security.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.tools.student_tools import register_student, view_students, update_student
from src.tools.session_tools import schedule_session, reschedule_session, cancel_session
from src.tools.payment_tools import register_payment, view_payments


class TestMultiTenancyIsolation:
    """Test that trainers cannot access each other's data."""

    @patch("src.tools.student_tools.dynamodb_client")
    def test_trainer_cannot_view_other_trainer_students(self, mock_db):
        """Test that trainer A cannot see trainer B's students."""
        trainer_a_id = "trainer_a"
        trainer_b_id = "trainer_b"

        # Setup: Trainer A exists and has students
        mock_db.get_trainer.return_value = {"trainer_id": trainer_a_id}
        mock_db.get_trainer_students.return_value = [
            {"trainer_id": trainer_a_id, "student_id": "student_a1", "status": "active"}
        ]
        mock_db.get_student.return_value = {
            "student_id": "student_a1",
            "name": "Student A1",
            "phone_number": "+14155551111",
            "email": "student_a1@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:00:00Z",
        }

        # Trainer A views their students
        result_a = view_students(trainer_id=trainer_a_id)
        assert result_a["success"] is True
        assert len(result_a["data"]["students"]) == 1
        assert result_a["data"]["students"][0]["student_id"] == "student_a1"

        # Setup: Trainer B exists and has different students
        mock_db.get_trainer.return_value = {"trainer_id": trainer_b_id}
        mock_db.get_trainer_students.return_value = [
            {"trainer_id": trainer_b_id, "student_id": "student_b1", "status": "active"}
        ]
        mock_db.get_student.return_value = {
            "student_id": "student_b1",
            "name": "Student B1",
            "phone_number": "+14155552222",
            "email": "student_b1@example.com",
            "training_goal": "Lose weight",
            "created_at": "2024-01-15T11:00:00Z",
        }

        # Trainer B views their students
        result_b = view_students(trainer_id=trainer_b_id)
        assert result_b["success"] is True
        assert len(result_b["data"]["students"]) == 1
        assert result_b["data"]["students"][0]["student_id"] == "student_b1"

        # Verify: Student IDs are different
        assert result_a["data"]["students"][0]["student_id"] != result_b["data"]["students"][0]["student_id"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_trainer_cannot_update_other_trainer_student(self, mock_db):
        """Test that trainer A cannot update trainer B's student."""
        trainer_a_id = "trainer_a"
        trainer_b_id = "trainer_b"
        student_b_id = "student_b1"

        # Setup: Trainer A exists
        mock_db.get_trainer.return_value = {"trainer_id": trainer_a_id}
        
        # Setup: Student belongs to trainer B
        mock_db.get_student.return_value = {
            "student_id": student_b_id,
            "name": "Student B1",
            "phone_number": "+14155552222",
            "email": "student_b1@example.com",
            "training_goal": "Lose weight",
            "created_at": "2024-01-15T11:00:00Z",
        }
        
        # Setup: No link exists between trainer A and student B
        mock_db.get_trainer_student_link.return_value = None

        # Trainer A tries to update trainer B's student
        result = update_student(
            trainer_id=trainer_a_id,
            student_id=student_b_id,
            name="Hacked Name"
        )

        # Should fail - no link between trainer A and student B
        assert result["success"] is False
        assert "not linked to trainer" in result["error"]

        # Verify: Student was not updated
        mock_db.put_student.assert_not_called()

    @patch("src.tools.session_tools.dynamodb_client")
    @patch("src.tools.session_tools.conflict_detector")
    def test_trainer_cannot_reschedule_other_trainer_session(self, mock_conflict, mock_db):
        """Test that trainer A cannot reschedule trainer B's session."""
        trainer_a_id = "trainer_a"
        trainer_b_id = "trainer_b"
        session_b_id = "session_b1"
        
        future_date = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

        # Setup: Session belongs to trainer B
        mock_db.get_session.return_value = {
            "session_id": session_b_id,
            "trainer_id": trainer_b_id,  # Belongs to trainer B
            "student_id": "student_b1",
            "student_name": "Student B1",
            "session_datetime": f"{future_date}T14:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
        }

        # Trainer A tries to reschedule trainer B's session
        result = reschedule_session(
            trainer_id=trainer_a_id,
            session_id=session_b_id,
            new_date=future_date,
            new_time="15:00"
        )

        # Should fail - session belongs to trainer B
        assert result["success"] is False
        assert "does not belong to trainer" in result["error"]

        # Verify: Session was not updated
        mock_db.put_session.assert_not_called()

    @patch("src.tools.session_tools.dynamodb_client")
    def test_trainer_cannot_cancel_other_trainer_session(self, mock_db):
        """Test that trainer A cannot cancel trainer B's session."""
        trainer_a_id = "trainer_a"
        trainer_b_id = "trainer_b"
        session_b_id = "session_b1"
        
        future_date = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

        # Setup: Session belongs to trainer B
        mock_db.get_session.return_value = {
            "session_id": session_b_id,
            "trainer_id": trainer_b_id,  # Belongs to trainer B
            "student_id": "student_b1",
            "student_name": "Student B1",
            "session_datetime": f"{future_date}T14:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
        }

        # Trainer A tries to cancel trainer B's session
        result = cancel_session(
            trainer_id=trainer_a_id,
            session_id=session_b_id,
            reason="Trying to cancel other trainer's session"
        )

        # Should fail - session belongs to trainer B
        assert result["success"] is False
        assert "does not belong to trainer" in result["error"]

        # Verify: Session was not updated
        mock_db.put_session.assert_not_called()

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_trainer_cannot_view_other_trainer_payments(self, mock_db):
        """Test that trainer A cannot see trainer B's payments."""
        trainer_a_id = "trainer_a"
        trainer_b_id = "trainer_b"

        # Setup: Trainer A exists and has payments
        mock_db.get_trainer.return_value = {"trainer_id": trainer_a_id}
        mock_db.get_trainer_payments.return_value = [
            {
                "payment_id": "payment_a1",
                "trainer_id": trainer_a_id,
                "student_id": "student_a1",
                "student_name": "Student A1",
                "amount": 100.00,
                "currency": "USD",
                "payment_date": "2024-01-15",
                "payment_status": "pending",
                "created_at": "2024-01-15T10:00:00Z",
            }
        ]

        # Trainer A views their payments
        result_a = view_payments(trainer_id=trainer_a_id)
        assert result_a["success"] is True
        assert len(result_a["data"]["payments"]) == 1
        assert result_a["data"]["payments"][0]["payment_id"] == "payment_a1"

        # Setup: Trainer B exists and has different payments
        mock_db.get_trainer.return_value = {"trainer_id": trainer_b_id}
        mock_db.get_trainer_payments.return_value = [
            {
                "payment_id": "payment_b1",
                "trainer_id": trainer_b_id,
                "student_id": "student_b1",
                "student_name": "Student B1",
                "amount": 150.00,
                "currency": "USD",
                "payment_date": "2024-01-16",
                "payment_status": "confirmed",
                "created_at": "2024-01-16T10:00:00Z",
            }
        ]

        # Trainer B views their payments
        result_b = view_payments(trainer_id=trainer_b_id)
        assert result_b["success"] is True
        assert len(result_b["data"]["payments"]) == 1
        assert result_b["data"]["payments"][0]["payment_id"] == "payment_b1"

        # Verify: Payment IDs are different
        assert result_a["data"]["payments"][0]["payment_id"] != result_b["data"]["payments"][0]["payment_id"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_trainer_cannot_confirm_other_trainer_payment(self, mock_db):
        """Test that trainer A cannot confirm trainer B's payment."""
        from src.tools.payment_tools import confirm_payment

        trainer_a_id = "trainer_a"
        trainer_b_id = "trainer_b"
        payment_b_id = "payment_b1"

        # Setup: Payment belongs to trainer B
        mock_db.get_payment.return_value = {
            "payment_id": payment_b_id,
            "trainer_id": trainer_b_id,  # Belongs to trainer B
            "student_id": "student_b1",
            "student_name": "Student B1",
            "amount": 150.00,
            "currency": "USD",
            "payment_date": "2024-01-16",
            "payment_status": "pending",
            "created_at": "2024-01-16T10:00:00Z",
        }

        # Trainer A tries to confirm trainer B's payment
        result = confirm_payment(
            trainer_id=trainer_a_id,
            payment_id=payment_b_id
        )

        # Should fail - payment belongs to trainer B
        assert result["success"] is False
        assert "does not belong to trainer" in result["error"]

        # Verify: Payment was not updated
        mock_db.put_payment.assert_not_called()

    @patch("src.tools.student_tools.dynamodb_client")
    def test_database_queries_scoped_by_trainer_id(self, mock_db):
        """Test that database queries include trainer_id in partition key."""
        trainer_id = "trainer_123"

        # Setup
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = []

        # Execute
        view_students(trainer_id=trainer_id)

        # Verify: Query was scoped to trainer_id
        mock_db.get_trainer_students.assert_called_once_with(trainer_id)
        
        # The actual DynamoDB query would use PK=TRAINER#{trainer_id}
        # This ensures data isolation at the database level
