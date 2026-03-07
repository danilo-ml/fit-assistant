"""
Unit tests for student management tool functions.

Tests the register_student, view_students, and update_student tools
with mocked DynamoDB operations.
"""

import pytest
from unittest.mock import patch

from src.tools.student_tools import register_student


class TestRegisterStudent:
    """Test cases for register_student tool function."""

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_new_student_success(self, mock_db):
        """Test successful registration of a new student."""
        # Setup mocks
        trainer_id = "trainer123"
        mock_db.get_trainer.return_value = {
            "trainer_id": trainer_id,
            "name": "Jane Trainer",
            "entity_type": "TRAINER",
        }
        mock_db.lookup_by_phone_number.return_value = None  # Student doesn't exist
        mock_db.put_student.return_value = {}
        mock_db.put_trainer_student_link.return_value = {}

        # Execute
        result = register_student(
            trainer_id=trainer_id,
            name="John Doe",
            phone_number="+14155552671",
            email="john@example.com",
            training_goal="Build muscle mass",
        )

        # Verify
        assert result["success"] is True
        assert "student_id" in result["data"]
        assert result["data"]["name"] == "John Doe"
        assert result["data"]["phone_number"] == "+14155552671"
        assert result["data"]["email"] == "john@example.com"
        assert result["data"]["training_goal"] == "Build muscle mass"

        # Verify DynamoDB calls
        mock_db.get_trainer.assert_called_once_with(trainer_id)
        mock_db.lookup_by_phone_number.assert_called_once_with("+14155552671")
        mock_db.put_student.assert_called_once()
        mock_db.put_trainer_student_link.assert_called_once()

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_student_invalid_phone_format(self, mock_db):
        """Test registration fails with invalid phone number format."""
        trainer_id = "trainer123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}

        # Execute with invalid phone
        result = register_student(
            trainer_id=trainer_id,
            name="John Doe",
            phone_number="invalid",
            email="john@example.com",
            training_goal="Build muscle",
        )

        # Verify
        assert result["success"] is False
        assert "Invalid phone number format" in result["error"]

        # Should not attempt to create student
        mock_db.put_student.assert_not_called()

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_student_normalizes_phone_number(self, mock_db):
        """Test that phone numbers are normalized to E.164 format."""
        trainer_id = "trainer123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.lookup_by_phone_number.return_value = None
        mock_db.put_student.return_value = {}
        mock_db.put_trainer_student_link.return_value = {}

        # Execute with US format phone
        result = register_student(
            trainer_id=trainer_id,
            name="John Doe",
            phone_number="(415) 555-2671",
            email="john@example.com",
            training_goal="Build muscle",
        )

        # Verify phone was normalized
        assert result["success"] is True
        assert result["data"]["phone_number"] == "+14155552671"

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_student_missing_name(self, mock_db):
        """Test registration fails when name is missing."""
        trainer_id = "trainer123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}

        result = register_student(
            trainer_id=trainer_id,
            name="",
            phone_number="+14155552671",
            email="john@example.com",
            training_goal="Build muscle",
        )

        assert result["success"] is False
        assert "name is required" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_student_missing_email(self, mock_db):
        """Test registration fails when email is missing."""
        trainer_id = "trainer123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}

        result = register_student(
            trainer_id=trainer_id,
            name="John Doe",
            phone_number="+14155552671",
            email="",
            training_goal="Build muscle",
        )

        assert result["success"] is False
        assert "email is required" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_student_missing_training_goal(self, mock_db):
        """Test registration fails when training goal is missing."""
        trainer_id = "trainer123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}

        result = register_student(
            trainer_id=trainer_id,
            name="John Doe",
            phone_number="+14155552671",
            email="john@example.com",
            training_goal="",
        )

        assert result["success"] is False
        assert "Training goal is required" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_student_trainer_not_found(self, mock_db):
        """Test registration fails when trainer doesn't exist."""
        trainer_id = "nonexistent"
        mock_db.get_trainer.return_value = None

        result = register_student(
            trainer_id=trainer_id,
            name="John Doe",
            phone_number="+14155552671",
            email="john@example.com",
            training_goal="Build muscle",
        )

        assert result["success"] is False
        assert "Trainer not found" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_existing_student_creates_link(self, mock_db):
        """Test linking existing student to new trainer (many-to-many)."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.lookup_by_phone_number.return_value = {
            "entity_type": "STUDENT",
            "student_id": student_id,
        }
        mock_db.get_trainer_student_link.return_value = None  # Link doesn't exist
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
        }
        mock_db.put_trainer_student_link.return_value = {}

        result = register_student(
            trainer_id=trainer_id,
            name="John Doe",
            phone_number="+14155552671",
            email="john@example.com",
            training_goal="Build muscle",
        )

        assert result["success"] is True
        assert result["data"]["student_id"] == student_id

        # Should create link but not create new student
        mock_db.put_trainer_student_link.assert_called_once()
        mock_db.put_student.assert_not_called()

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_student_already_linked(self, mock_db):
        """Test registration fails when student is already linked to trainer."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.lookup_by_phone_number.return_value = {
            "entity_type": "STUDENT",
            "student_id": student_id,
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }

        result = register_student(
            trainer_id=trainer_id,
            name="John Doe",
            phone_number="+14155552671",
            email="john@example.com",
            training_goal="Build muscle",
        )

        assert result["success"] is False
        assert "already registered" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_student_phone_is_trainer(self, mock_db):
        """Test registration fails when phone number belongs to a trainer."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.lookup_by_phone_number.return_value = {
            "entity_type": "TRAINER",
            "trainer_id": "trainer456",
        }

        result = register_student(
            trainer_id=trainer_id,
            name="John Doe",
            phone_number="+14155552671",
            email="john@example.com",
            training_goal="Build muscle",
        )

        assert result["success"] is False
        assert "already registered as a trainer" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_student_sanitizes_inputs(self, mock_db):
        """Test that HTML and script tags are sanitized from inputs."""
        trainer_id = "trainer123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.lookup_by_phone_number.return_value = None
        mock_db.put_student.return_value = {}
        mock_db.put_trainer_student_link.return_value = {}

        result = register_student(
            trainer_id=trainer_id,
            name='<script>alert("xss")</script>John Doe',
            phone_number="+14155552671",
            email="john@example.com",
            training_goal="<b>Build muscle</b>",
        )

        assert result["success"] is True
        # HTML tags should be stripped
        assert "<script>" not in result["data"]["name"]
        assert "<b>" not in result["data"]["training_goal"]
        assert "John Doe" in result["data"]["name"]
        assert "Build muscle" in result["data"]["training_goal"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_register_student_handles_exceptions(self, mock_db):
        """Test that unexpected exceptions are handled gracefully."""
        trainer_id = "trainer123"
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.lookup_by_phone_number.return_value = None
        mock_db.put_student.side_effect = Exception("Database error")

        result = register_student(
            trainer_id=trainer_id,
            name="John Doe",
            phone_number="+14155552671",
            email="john@example.com",
            training_goal="Build muscle",
        )

        assert result["success"] is False
        assert "Failed to register student" in result["error"]


class TestViewStudents:
    """Test cases for view_students tool function."""

    @patch("src.tools.student_tools.dynamodb_client")
    def test_view_students_success(self, mock_db):
        """Test successful retrieval of trainer's students."""
        trainer_id = "trainer123"

        # Setup mocks
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id, "name": "Jane Trainer"}

        mock_db.get_trainer_students.return_value = [
            {"trainer_id": trainer_id, "student_id": "student1", "status": "active"},
            {"trainer_id": trainer_id, "student_id": "student2", "status": "active"},
        ]

        mock_db.get_student.side_effect = [
            {
                "student_id": "student1",
                "name": "John Doe",
                "phone_number": "+14155552671",
                "email": "john@example.com",
                "training_goal": "Build muscle",
                "created_at": "2024-01-15T10:30:00Z",
            },
            {
                "student_id": "student2",
                "name": "Jane Smith",
                "phone_number": "+14155552672",
                "email": "jane@example.com",
                "training_goal": "Lose weight",
                "created_at": "2024-01-16T11:00:00Z",
            },
        ]

        # Execute
        from src.tools.student_tools import view_students

        result = view_students(trainer_id=trainer_id)

        # Verify
        assert result["success"] is True
        assert "students" in result["data"]
        assert len(result["data"]["students"]) == 2

        # Verify first student
        student1 = result["data"]["students"][0]
        assert student1["student_id"] == "student1"
        assert student1["name"] == "John Doe"
        assert student1["phone_number"] == "+14155552671"
        assert student1["email"] == "john@example.com"
        assert student1["training_goal"] == "Build muscle"
        assert student1["created_at"] == "2024-01-15T10:30:00Z"

        # Verify second student
        student2 = result["data"]["students"][1]
        assert student2["student_id"] == "student2"
        assert student2["name"] == "Jane Smith"

        # Verify DynamoDB calls
        mock_db.get_trainer.assert_called_once_with(trainer_id)
        mock_db.get_trainer_students.assert_called_once_with(trainer_id)
        assert mock_db.get_student.call_count == 2

    @patch("src.tools.student_tools.dynamodb_client")
    def test_view_students_empty_list(self, mock_db):
        """Test viewing students when trainer has no students."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = []

        from src.tools.student_tools import view_students

        result = view_students(trainer_id=trainer_id)

        assert result["success"] is True
        assert result["data"]["students"] == []

    @patch("src.tools.student_tools.dynamodb_client")
    def test_view_students_trainer_not_found(self, mock_db):
        """Test viewing students fails when trainer doesn't exist."""
        trainer_id = "nonexistent"
        mock_db.get_trainer.return_value = None

        from src.tools.student_tools import view_students

        result = view_students(trainer_id=trainer_id)

        assert result["success"] is False
        assert "Trainer not found" in result["error"]

        # Should not query students
        mock_db.get_trainer_students.assert_not_called()

    @patch("src.tools.student_tools.dynamodb_client")
    def test_view_students_filters_inactive_links(self, mock_db):
        """Test that inactive student links are filtered out."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"trainer_id": trainer_id, "student_id": "student1", "status": "active"},
            {"trainer_id": trainer_id, "student_id": "student2", "status": "inactive"},
        ]

        mock_db.get_student.return_value = {
            "student_id": "student1",
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }

        from src.tools.student_tools import view_students

        result = view_students(trainer_id=trainer_id)

        assert result["success"] is True
        assert len(result["data"]["students"]) == 1
        assert result["data"]["students"][0]["student_id"] == "student1"

        # Should only fetch active student
        mock_db.get_student.assert_called_once_with("student1")

    @patch("src.tools.student_tools.dynamodb_client")
    def test_view_students_handles_missing_student_data(self, mock_db):
        """Test that missing student records are skipped gracefully."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"trainer_id": trainer_id, "student_id": "student1", "status": "active"},
            {"trainer_id": trainer_id, "student_id": "student2", "status": "active"},
        ]

        # First student exists, second doesn't
        mock_db.get_student.side_effect = [
            {
                "student_id": "student1",
                "name": "John Doe",
                "phone_number": "+14155552671",
                "email": "john@example.com",
                "training_goal": "Build muscle",
                "created_at": "2024-01-15T10:30:00Z",
            },
            None,  # Student2 not found
        ]

        from src.tools.student_tools import view_students

        result = view_students(trainer_id=trainer_id)

        assert result["success"] is True
        assert len(result["data"]["students"]) == 1
        assert result["data"]["students"][0]["student_id"] == "student1"

    @patch("src.tools.student_tools.dynamodb_client")
    def test_view_students_handles_exceptions(self, mock_db):
        """Test that unexpected exceptions are handled gracefully."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.side_effect = Exception("Database error")

        from src.tools.student_tools import view_students

        result = view_students(trainer_id=trainer_id)

        assert result["success"] is False
        assert "Failed to retrieve students" in result["error"]


class TestUpdateStudent:
    """Test cases for update_student tool function."""

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_name_success(self, mock_db):
        """Test successful update of student name."""
        trainer_id = "trainer123"
        student_id = "student456"

        # Setup mocks
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id, "name": "Jane Trainer"}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }
        mock_db.put_student.return_value = {}

        # Execute
        from src.tools.student_tools import update_student

        result = update_student(
            trainer_id=trainer_id, student_id=student_id, name="John Smith"
        )

        # Verify
        assert result["success"] is True
        assert result["data"]["student_id"] == student_id
        assert result["data"]["name"] == "John Smith"
        assert result["data"]["phone_number"] == "+14155552671"
        assert result["data"]["email"] == "john@example.com"
        assert result["data"]["training_goal"] == "Build muscle"
        assert "updated_at" in result["data"]

        # Verify DynamoDB calls
        mock_db.get_trainer.assert_called_once_with(trainer_id)
        mock_db.get_student.assert_called_once_with(student_id)
        mock_db.get_trainer_student_link.assert_called_once_with(trainer_id, student_id)
        mock_db.put_student.assert_called_once()

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_multiple_fields(self, mock_db):
        """Test updating multiple fields at once."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }
        mock_db.put_student.return_value = {}

        from src.tools.student_tools import update_student

        result = update_student(
            trainer_id=trainer_id,
            student_id=student_id,
            name="John Smith",
            email="johnsmith@example.com",
            training_goal="Lose weight",
        )

        assert result["success"] is True
        assert result["data"]["name"] == "John Smith"
        assert result["data"]["email"] == "johnsmith@example.com"
        assert result["data"]["training_goal"] == "Lose weight"
        # Phone number should remain unchanged
        assert result["data"]["phone_number"] == "+14155552671"

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_phone_number(self, mock_db):
        """Test updating phone number with validation."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }
        mock_db.lookup_by_phone_number.return_value = None  # New phone not in use
        mock_db.put_student.return_value = {}

        from src.tools.student_tools import update_student

        result = update_student(
            trainer_id=trainer_id, student_id=student_id, phone_number="+14155552999"
        )

        assert result["success"] is True
        assert result["data"]["phone_number"] == "+14155552999"

        # Verify phone number lookup was called
        mock_db.lookup_by_phone_number.assert_called_once_with("+14155552999")

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_normalizes_phone(self, mock_db):
        """Test that phone numbers are normalized to E.164 format."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }
        mock_db.lookup_by_phone_number.return_value = None
        mock_db.put_student.return_value = {}

        from src.tools.student_tools import update_student

        result = update_student(
            trainer_id=trainer_id, student_id=student_id, phone_number="(415) 555-2999"
        )

        assert result["success"] is True
        assert result["data"]["phone_number"] == "+14155552999"

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_invalid_phone(self, mock_db):
        """Test update fails with invalid phone number."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }

        from src.tools.student_tools import update_student

        result = update_student(
            trainer_id=trainer_id, student_id=student_id, phone_number="invalid"
        )

        assert result["success"] is False
        assert "Invalid phone number format" in result["error"]

        # Should not attempt to update
        mock_db.put_student.assert_not_called()

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_phone_already_in_use(self, mock_db):
        """Test update fails when new phone number is already registered."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }
        mock_db.lookup_by_phone_number.return_value = {
            "entity_type": "STUDENT",
            "student_id": "different_student",
        }

        from src.tools.student_tools import update_student

        result = update_student(
            trainer_id=trainer_id, student_id=student_id, phone_number="+14155552999"
        )

        assert result["success"] is False
        assert "already registered to another user" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_trainer_not_found(self, mock_db):
        """Test update fails when trainer doesn't exist."""
        trainer_id = "nonexistent"
        student_id = "student456"

        mock_db.get_trainer.return_value = None

        from src.tools.student_tools import update_student

        result = update_student(trainer_id=trainer_id, student_id=student_id, name="John Smith")

        assert result["success"] is False
        assert "Trainer not found" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_student_not_found(self, mock_db):
        """Test update fails when student doesn't exist."""
        trainer_id = "trainer123"
        student_id = "nonexistent"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = None

        from src.tools.student_tools import update_student

        result = update_student(trainer_id=trainer_id, student_id=student_id, name="John Smith")

        assert result["success"] is False
        assert "Student not found" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_link_not_active(self, mock_db):
        """Test update fails when trainer-student link is not active."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "inactive",
        }

        from src.tools.student_tools import update_student

        result = update_student(trainer_id=trainer_id, student_id=student_id, name="John Smith")

        assert result["success"] is False
        assert "not linked to trainer" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_link_not_found(self, mock_db):
        """Test update fails when trainer-student link doesn't exist."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = None

        from src.tools.student_tools import update_student

        result = update_student(trainer_id=trainer_id, student_id=student_id, name="John Smith")

        assert result["success"] is False
        assert "not linked to trainer" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_no_fields_provided(self, mock_db):
        """Test update fails when no fields are provided."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }

        from src.tools.student_tools import update_student

        result = update_student(trainer_id=trainer_id, student_id=student_id)

        assert result["success"] is False
        assert "At least one field must be provided" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_sanitizes_inputs(self, mock_db):
        """Test that HTML and script tags are sanitized from inputs."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }
        mock_db.put_student.return_value = {}

        from src.tools.student_tools import update_student

        result = update_student(
            trainer_id=trainer_id,
            student_id=student_id,
            name='<script>alert("xss")</script>John Smith',
            training_goal="<b>Lose weight</b>",
        )

        assert result["success"] is True
        # HTML tags should be stripped
        assert "<script>" not in result["data"]["name"]
        assert "<b>" not in result["data"]["training_goal"]
        assert "John Smith" in result["data"]["name"]
        assert "Lose weight" in result["data"]["training_goal"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_handles_exceptions(self, mock_db):
        """Test that unexpected exceptions are handled gracefully."""
        trainer_id = "trainer123"
        student_id = "student456"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": "2024-01-15T10:30:00Z",
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }
        mock_db.put_student.side_effect = Exception("Database error")

        from src.tools.student_tools import update_student

        result = update_student(trainer_id=trainer_id, student_id=student_id, name="John Smith")

        assert result["success"] is False
        assert "Failed to update student" in result["error"]

    @patch("src.tools.student_tools.dynamodb_client")
    def test_update_student_preserves_created_at(self, mock_db):
        """Test that created_at timestamp is preserved during update."""
        from datetime import datetime

        trainer_id = "trainer123"
        student_id = "student456"
        original_created_at = "2024-01-15T10:30:00Z"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_student.return_value = {
            "student_id": student_id,
            "name": "John Doe",
            "phone_number": "+14155552671",
            "email": "john@example.com",
            "training_goal": "Build muscle",
            "created_at": original_created_at,
        }
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }

        # Capture the put_student call
        put_student_calls = []

        def capture_put_student(item):
            put_student_calls.append(item)
            return {}

        mock_db.put_student.side_effect = capture_put_student

        from src.tools.student_tools import update_student

        result = update_student(trainer_id=trainer_id, student_id=student_id, name="John Smith")

        assert result["success"] is True

        # Verify created_at was preserved in the DynamoDB call
        assert len(put_student_calls) == 1
        saved_item = put_student_calls[0]
        
        # Parse both timestamps and compare as datetime objects to handle format differences
        saved_created_at = datetime.fromisoformat(saved_item["created_at"].replace("Z", "+00:00"))
        original_created_at_dt = datetime.fromisoformat(original_created_at.replace("Z", "+00:00"))
        assert saved_created_at == original_created_at_dt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
