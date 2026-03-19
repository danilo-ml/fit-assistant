"""
Unit tests for session management tool functions.

Tests cover:
- schedule_session: Session scheduling with validation and conflict detection
- Input validation and sanitization
- Error handling for various edge cases
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.tools.session_tools import schedule_session


from src.tools.session_tools import schedule_session, reschedule_session, cancel_session, view_calendar
class TestScheduleSession:
    """Test suite for schedule_session tool function."""

    @pytest.fixture
    def future_date(self):
        """Get a future date for testing."""
        return (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Mock DynamoDB client."""
        with patch("src.tools.session_tools.dynamodb_client") as mock:
            yield mock

    @pytest.fixture
    def mock_conflict_detector(self):
        """Mock SessionConflictDetector."""
        with patch("src.tools.session_tools.conflict_detector") as mock:
            yield mock

    @pytest.fixture
    def mock_calendar_sync_service(self):
        """Mock CalendarSyncService."""
        with patch("src.tools.session_tools.calendar_sync_service") as mock:
            yield mock

    @pytest.fixture
    def trainer_data(self):
        """Sample trainer data."""
        return {
            "trainer_id": "trainer123",
            "name": "Jane Trainer",
            "email": "jane@example.com",
            "business_name": "Jane's Fitness",
            "phone_number": "+14155551234",
        }

    @pytest.fixture
    def student_data(self):
        """Sample student data."""
        return {
            "student_id": "student456",
            "name": "John Doe",
            "email": "john@example.com",
            "phone_number": "+14155555678",
            "training_goal": "Build muscle",
        }

    @pytest.fixture
    def trainer_student_link(self):
        """Sample trainer-student link."""
        return {
            "trainer_id": "trainer123",
            "student_id": "student456",
            "status": "active",
        }

    def test_schedule_session_success_no_conflicts(
        self, mock_dynamodb_client, mock_conflict_detector, mock_calendar_sync_service, trainer_data, student_data, trainer_student_link
    ):
        """Test successful session scheduling with no conflicts."""
        # Setup mocks
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}
        mock_calendar_sync_service.create_event.return_value = {
            "calendar_event_id": "cal_event_123",
            "calendar_provider": "google"
        }

        # Use a future date
        future_date = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

        # Call function
        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date=future_date,
            time="14:00",
            duration_minutes=60,
            location="Main Gym",
        )

        # Assertions
        if not result["success"]:
            print(f"Error: {result.get('error')}")
        assert result["success"] is True
        assert "session_id" in result["data"]
        assert result["data"]["student_name"] == "John Doe"
        assert result["data"]["session_datetime"] == f"{future_date}T14:00:00"
        assert result["data"]["duration_minutes"] == 60
        assert result["data"]["location"] == "Main Gym"
        assert result["data"]["status"] == "scheduled"
        assert "conflicts" not in result["data"]
        
        # Verify calendar sync was called
        assert result["data"]["calendar_event_id"] == "cal_event_123"
        assert result["data"]["calendar_provider"] == "google"

        # Verify DynamoDB calls
        mock_dynamodb_client.get_trainer.assert_called_once_with("trainer123")
        mock_dynamodb_client.get_trainer_students.assert_called_once_with("trainer123")
        # put_session should be called twice: once for initial save, once for calendar update
        assert mock_dynamodb_client.put_session.call_count == 2

    def test_schedule_session_success_with_conflicts(
        self, mock_dynamodb_client, mock_conflict_detector, mock_calendar_sync_service, trainer_data, student_data, trainer_student_link, future_date
    ):
        """Test session scheduling that detects conflicts but still creates session."""
        # Setup mocks with conflicting session
        conflicting_session = {
            "session_id": "session999",
            "student_name": "Jane Smith",
            "session_datetime": f"{future_date}T14:30:00",
            "duration_minutes": 60,
        }
        
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = [conflicting_session]
        mock_dynamodb_client.put_session.return_value = {}
        mock_calendar_sync_service.create_event.return_value = None  # Calendar sync fails

        # Call function
        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date=future_date,
            time="14:00",
            duration_minutes=60,
        )

        # Assertions
        assert result["success"] is True
        assert "conflicts" in result["data"]
        assert len(result["data"]["conflicts"]) == 1
        assert result["data"]["conflicts"][0]["session_id"] == "session999"
        assert result["data"]["conflicts"][0]["student_name"] == "Jane Smith"

    def test_schedule_session_without_location(
        self, mock_dynamodb_client, mock_conflict_detector, trainer_data, student_data, trainer_student_link, future_date
    ):
        """Test session scheduling without optional location."""
        # Setup mocks
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        # Call function without location
        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date=future_date,
            time="14:00",
            duration_minutes=60,
        )

        # Assertions
        assert result["success"] is True
        assert "location" not in result["data"]

    def test_schedule_session_trainer_not_found(self, mock_dynamodb_client):
        """Test error when trainer doesn't exist."""
        mock_dynamodb_client.get_trainer.return_value = None

        result = schedule_session(
            trainer_id="nonexistent",
            student_name="John Doe",
            date="2024-12-25",
            time="14:00",
            duration_minutes=60,
        )

        assert result["success"] is False
        assert "Trainer not found" in result["error"]

    def test_schedule_session_student_not_found(
        self, mock_dynamodb_client, trainer_data, trainer_student_link
    ):
        """Test error when student is not linked to trainer."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = []

        result = schedule_session(
            trainer_id="trainer123",
            student_name="Unknown Student",
            date="2024-12-25",
            time="14:00",
            duration_minutes=60,
        )

        assert result["success"] is False
        assert "not found or not linked" in result["error"]

    def test_schedule_session_student_inactive_link(
        self, mock_dynamodb_client, trainer_data, student_data
    ):
        """Test error when trainer-student link is inactive."""
        inactive_link = {
            "trainer_id": "trainer123",
            "student_id": "student456",
            "status": "inactive",
        }
        
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [inactive_link]

        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date="2024-12-25",
            time="14:00",
            duration_minutes=60,
        )

        assert result["success"] is False
        assert "not found or not linked" in result["error"]

    def test_schedule_session_missing_student_name(self, mock_dynamodb_client, trainer_data):
        """Test error when student name is missing."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data

        result = schedule_session(
            trainer_id="trainer123",
            student_name="",
            date="2024-12-25",
            time="14:00",
            duration_minutes=60,
        )

        assert result["success"] is False
        assert "Student name is required" in result["error"]

    def test_schedule_session_missing_date(self, mock_dynamodb_client, trainer_data):
        """Test error when date is missing."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data

        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date="",
            time="14:00",
            duration_minutes=60,
        )

        assert result["success"] is False
        assert "Session date is required" in result["error"]

    def test_schedule_session_missing_time(self, mock_dynamodb_client, trainer_data):
        """Test error when time is missing."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data

        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date="2024-12-25",
            time="",
            duration_minutes=60,
        )

        assert result["success"] is False
        assert "Session time is required" in result["error"]

    def test_schedule_session_invalid_duration_too_short(self, mock_dynamodb_client, trainer_data):
        """Test error when duration is too short."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data

        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date="2024-12-25",
            time="14:00",
            duration_minutes=10,
        )

        assert result["success"] is False
        assert "Duration must be between 15 and 480" in result["error"]

    def test_schedule_session_invalid_duration_too_long(self, mock_dynamodb_client, trainer_data):
        """Test error when duration is too long."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data

        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date="2024-12-25",
            time="14:00",
            duration_minutes=500,
        )

        assert result["success"] is False
        assert "Duration must be between 15 and 480" in result["error"]

    def test_schedule_session_invalid_date_format(
        self, mock_dynamodb_client, trainer_data, student_data, trainer_student_link
    ):
        """Test error when date format is invalid."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data

        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date="25-12-2024",  # Wrong format
            time="14:00",
            duration_minutes=60,
        )

        assert result["success"] is False
        assert "Invalid date or time format" in result["error"]

    def test_schedule_session_invalid_time_format(
        self, mock_dynamodb_client, trainer_data, student_data, trainer_student_link
    ):
        """Test error when time format is invalid."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data

        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date="2024-12-25",
            time="2:00 PM",  # Wrong format
            duration_minutes=60,
        )

        assert result["success"] is False
        assert "Invalid date or time format" in result["error"]

    def test_schedule_session_case_insensitive_student_name(
        self, mock_dynamodb_client, mock_conflict_detector, trainer_data, student_data, trainer_student_link, future_date
    ):
        """Test that student name matching is case-insensitive."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        # Call with different case
        result = schedule_session(
            trainer_id="trainer123",
            student_name="JOHN DOE",  # All caps
            date=future_date,
            time="14:00",
            duration_minutes=60,
        )

        # Should succeed and use the actual name from DB
        assert result["success"] is True
        assert result["data"]["student_name"] == "John Doe"  # Original case from DB

    def test_schedule_session_sanitizes_inputs(
        self, mock_dynamodb_client, mock_conflict_detector, trainer_data, student_data, trainer_student_link, future_date
    ):
        """Test that inputs are sanitized."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        # Call with potentially malicious input
        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date=future_date,
            time="14:00",
            duration_minutes=60,
            location="<script>alert('xss')</script>Main Gym",
        )

        # Should succeed with sanitized location
        assert result["success"] is True
        # Location should be sanitized (HTML tags removed)
        assert "<script>" not in result["data"]["location"]

    def test_schedule_session_conflict_detector_called_correctly(
        self, mock_dynamodb_client, mock_conflict_detector, trainer_data, student_data, trainer_student_link, future_date
    ):
        """Test that conflict detector is called with correct parameters."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date=future_date,
            time="14:00",
            duration_minutes=60,
        )

        # Verify conflict detector was called with correct parameters
        mock_conflict_detector.check_conflicts.assert_called_once()
        call_args = mock_conflict_detector.check_conflicts.call_args
        
        assert call_args.kwargs["trainer_id"] == "trainer123"
        assert call_args.kwargs["duration_minutes"] == 60
        assert isinstance(call_args.kwargs["session_datetime"], datetime)

    def test_schedule_session_minimum_duration(
        self, mock_dynamodb_client, mock_conflict_detector, trainer_data, student_data, trainer_student_link, future_date
    ):
        """Test scheduling with minimum allowed duration (15 minutes)."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date=future_date,
            time="14:00",
            duration_minutes=15,
        )

        assert result["success"] is True
        assert result["data"]["duration_minutes"] == 15

    def test_schedule_session_maximum_duration(
        self, mock_dynamodb_client, mock_conflict_detector, trainer_data, student_data, trainer_student_link, future_date
    ):
        """Test scheduling with maximum allowed duration (480 minutes)."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date=future_date,
            time="14:00",
            duration_minutes=480,
        )

        assert result["success"] is True
        assert result["data"]["duration_minutes"] == 480

    def test_schedule_session_iso_8601_datetime_format(
        self, mock_dynamodb_client, mock_conflict_detector, trainer_data, student_data, trainer_student_link, future_date
    ):
        """Test that session_datetime is returned in ISO 8601 format."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date=future_date,
            time="14:30",
            duration_minutes=60,
        )

        assert result["success"] is True
        # Verify ISO 8601 format
        session_datetime = result["data"]["session_datetime"]
        assert "T" in session_datetime
        # Should be parseable as ISO format
        datetime.fromisoformat(session_datetime)



class TestRescheduleSession:
    """Test suite for reschedule_session tool function."""

    @pytest.fixture
    def future_date(self):
        """Get a future date for testing."""
        return (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

    @pytest.fixture
    def new_future_date(self):
        """Get a different future date for rescheduling."""
        return (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%d")

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Mock DynamoDB client."""
        with patch("src.tools.session_tools.dynamodb_client") as mock:
            yield mock

    @pytest.fixture
    def mock_conflict_detector(self):
        """Mock SessionConflictDetector."""
        with patch("src.tools.session_tools.conflict_detector") as mock:
            yield mock

    @pytest.fixture
    def mock_calendar_sync_service(self):
        """Mock CalendarSyncService."""
        with patch("src.tools.session_tools.calendar_sync_service") as mock:
            yield mock

    @pytest.fixture
    def existing_session_data(self, future_date):
        """Sample existing session data."""
        return {
            "PK": "TRAINER#trainer123",
            "SK": "SESSION#session789",
            "session_id": "session789",
            "trainer_id": "trainer123",
            "student_id": "student456",
            "student_name": "John Doe",
            "session_datetime": f"{future_date}T14:00:00",
            "duration_minutes": 60,
            "location": "Main Gym",
            "status": "scheduled",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
        }

    def test_reschedule_session_success_no_conflicts(
        self, mock_dynamodb_client, mock_conflict_detector, existing_session_data, new_future_date
    ):
        """Test successful session rescheduling with no conflicts."""
        # Store the original datetime before mocking
        original_datetime = existing_session_data["session_datetime"]
        
        # Setup mocks
        mock_dynamodb_client.get_session.return_value = existing_session_data.copy()
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        # Call function
        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date=new_future_date,
            new_time="15:00",
        )

        # Assertions
        assert result["success"] is True
        assert result["data"]["session_id"] == "session789"
        assert result["data"]["student_name"] == "John Doe"
        assert result["data"]["old_datetime"] == original_datetime
        assert result["data"]["new_datetime"] == f"{new_future_date}T15:00:00"
        assert result["data"]["duration_minutes"] == 60
        assert result["data"]["status"] == "scheduled"
        assert result["data"]["location"] == "Main Gym"
        assert "conflicts" not in result["data"]

        # Verify conflict detector was called with exclude_session_id
        mock_conflict_detector.check_conflicts.assert_called_once()
        call_args = mock_conflict_detector.check_conflicts.call_args
        assert call_args.kwargs["exclude_session_id"] == "session789"

        # Verify session was updated
        mock_dynamodb_client.put_session.assert_called_once()

    def test_reschedule_session_success_with_conflicts(
        self, mock_dynamodb_client, mock_conflict_detector, existing_session_data, new_future_date
    ):
        """Test session rescheduling with conflicts detected."""
        # Setup mocks
        mock_dynamodb_client.get_session.return_value = existing_session_data
        mock_conflict_detector.check_conflicts.return_value = [
            {
                "session_id": "session999",
                "student_name": "Jane Smith",
                "session_datetime": f"{new_future_date}T15:30:00",
                "duration_minutes": 45,
            }
        ]
        mock_dynamodb_client.put_session.return_value = {}

        # Call function
        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date=new_future_date,
            new_time="15:00",
        )

        # Assertions
        assert result["success"] is True
        assert "conflicts" in result["data"]
        assert len(result["data"]["conflicts"]) == 1
        assert result["data"]["conflicts"][0]["session_id"] == "session999"
        assert result["data"]["conflicts"][0]["student_name"] == "Jane Smith"

    def test_reschedule_session_without_location(
        self, mock_dynamodb_client, mock_conflict_detector, existing_session_data, new_future_date
    ):
        """Test rescheduling session without location field."""
        # Remove location from existing session
        session_without_location = existing_session_data.copy()
        del session_without_location["location"]

        # Setup mocks
        mock_dynamodb_client.get_session.return_value = session_without_location
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        # Call function
        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date=new_future_date,
            new_time="15:00",
        )

        # Assertions
        assert result["success"] is True
        assert "location" not in result["data"]

    def test_reschedule_session_not_found(self, mock_dynamodb_client):
        """Test error when session doesn't exist."""
        mock_dynamodb_client.get_session.return_value = None

        result = reschedule_session(
            trainer_id="trainer123",
            session_id="nonexistent",
            new_date="2024-02-01",
            new_time="15:00",
        )

        assert result["success"] is False
        assert "Session not found" in result["error"]

    def test_reschedule_session_wrong_trainer(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test error when session belongs to different trainer."""
        mock_dynamodb_client.get_session.return_value = existing_session_data

        result = reschedule_session(
            trainer_id="different_trainer",
            session_id="session789",
            new_date="2024-02-01",
            new_time="15:00",
        )

        assert result["success"] is False
        assert "does not belong to trainer" in result["error"]

    def test_reschedule_cancelled_session(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test error when trying to reschedule a cancelled session."""
        cancelled_session = existing_session_data.copy()
        cancelled_session["status"] = "cancelled"

        mock_dynamodb_client.get_session.return_value = cancelled_session

        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date="2024-02-01",
            new_time="15:00",
        )

        assert result["success"] is False
        assert "Cannot reschedule a cancelled session" in result["error"]

    def test_reschedule_session_missing_session_id(self, mock_dynamodb_client):
        """Test error when session ID is missing."""
        result = reschedule_session(
            trainer_id="trainer123",
            session_id="",
            new_date="2024-02-01",
            new_time="15:00",
        )

        assert result["success"] is False
        assert "Session ID is required" in result["error"]

    def test_reschedule_session_missing_date(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test error when new date is missing."""
        mock_dynamodb_client.get_session.return_value = existing_session_data

        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date="",
            new_time="15:00",
        )

        assert result["success"] is False
        assert "New session date is required" in result["error"]

    def test_reschedule_session_missing_time(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test error when new time is missing."""
        mock_dynamodb_client.get_session.return_value = existing_session_data

        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date="2024-02-01",
            new_time="",
        )

        assert result["success"] is False
        assert "New session time is required" in result["error"]

    def test_reschedule_session_invalid_date_format(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test error when date format is invalid."""
        mock_dynamodb_client.get_session.return_value = existing_session_data

        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date="02/01/2024",  # Invalid format
            new_time="15:00",
        )

        assert result["success"] is False
        assert "Invalid date or time format" in result["error"]

    def test_reschedule_session_invalid_time_format(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test error when time format is invalid."""
        mock_dynamodb_client.get_session.return_value = existing_session_data

        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date="2024-02-01",
            new_time="3:00 PM",  # Invalid format
        )

        assert result["success"] is False
        assert "Invalid date or time format" in result["error"]

    def test_reschedule_session_to_past(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test error when trying to reschedule to the past."""
        mock_dynamodb_client.get_session.return_value = existing_session_data

        past_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date=past_date,
            new_time="15:00",
        )

        assert result["success"] is False
        assert "Cannot reschedule sessions to the past" in result["error"]

    def test_reschedule_session_sanitizes_inputs(
        self, mock_dynamodb_client, mock_conflict_detector, existing_session_data, new_future_date
    ):
        """Test that inputs are sanitized."""
        # Create a session with a clean ID
        clean_session_data = existing_session_data.copy()
        clean_session_data["session_id"] = "alertxsssession789"  # After sanitization
        
        mock_dynamodb_client.get_session.return_value = clean_session_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        # Pass malicious input that will be sanitized
        result = reschedule_session(
            trainer_id="trainer123",
            session_id="<script>alert('xss')</script>session789",
            new_date=new_future_date,
            new_time="15:00",
        )

        # After sanitization, the session_id becomes "alertxsssession789"
        # which matches our mock, so it should succeed
        assert result["success"] is True
        
        # Verify get_session was called with sanitized session_id
        mock_dynamodb_client.get_session.assert_called_once()
        call_args = mock_dynamodb_client.get_session.call_args
        # The sanitized session_id should not contain script tags
        assert "<script>" not in call_args[0][1]

    def test_reschedule_session_updates_timestamp(
        self, mock_dynamodb_client, mock_conflict_detector, existing_session_data, new_future_date
    ):
        """Test that updated_at timestamp is set."""
        mock_dynamodb_client.get_session.return_value = existing_session_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date=new_future_date,
            new_time="15:00",
        )

        assert result["success"] is True

        # Verify put_session was called with updated_at
        call_args = mock_dynamodb_client.put_session.call_args
        updated_session = call_args[0][0]
        assert "updated_at" in updated_session
        # Verify updated_at is recent (within last minute)
        updated_at = datetime.fromisoformat(updated_session["updated_at"].replace("Z", ""))
        assert (datetime.utcnow() - updated_at).total_seconds() < 60

    def test_reschedule_session_preserves_other_fields(
        self, mock_dynamodb_client, mock_conflict_detector, existing_session_data, new_future_date
    ):
        """Test that other session fields are preserved during reschedule."""
        mock_dynamodb_client.get_session.return_value = existing_session_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date=new_future_date,
            new_time="15:00",
        )

        assert result["success"] is True

        # Verify put_session was called with all original fields preserved
        call_args = mock_dynamodb_client.put_session.call_args
        updated_session = call_args[0][0]
        assert updated_session["student_id"] == "student456"
        assert updated_session["student_name"] == "John Doe"
        assert updated_session["duration_minutes"] == 60
        assert updated_session["location"] == "Main Gym"
        assert updated_session["status"] == "scheduled"
        assert updated_session["created_at"] == existing_session_data["created_at"]

    def test_reschedule_session_iso_8601_datetime_format(
        self, mock_dynamodb_client, mock_conflict_detector, existing_session_data, new_future_date
    ):
        """Test that new datetime is in ISO 8601 format."""
        mock_dynamodb_client.get_session.return_value = existing_session_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date=new_future_date,
            new_time="15:00",
        )

        assert result["success"] is True

        # Verify ISO 8601 format
        new_datetime = result["data"]["new_datetime"]
        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(new_datetime)
        assert isinstance(parsed, datetime)
        assert new_datetime == f"{new_future_date}T15:00:00"



class TestCancelSession:
    """Test suite for cancel_session tool function."""

    @pytest.fixture
    def future_date(self):
        """Get a future date for testing."""
        return (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Mock DynamoDB client."""
        with patch("src.tools.session_tools.dynamodb_client") as mock:
            yield mock

    @pytest.fixture
    def mock_calendar_sync_service(self):
        """Mock CalendarSyncService."""
        with patch("src.tools.session_tools.calendar_sync_service") as mock:
            yield mock

    @pytest.fixture
    def existing_session_data(self, future_date):
        """Sample existing session data."""
        return {
            "PK": "TRAINER#trainer123",
            "SK": "SESSION#session789",
            "session_id": "session789",
            "trainer_id": "trainer123",
            "student_id": "student456",
            "student_name": "John Doe",
            "session_datetime": f"{future_date}T14:00:00",
            "duration_minutes": 60,
            "location": "Main Gym",
            "status": "scheduled",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
        }

    def test_cancel_session_success_without_reason(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test successful session cancellation without reason."""
        # Setup mocks
        mock_dynamodb_client.get_session.return_value = existing_session_data.copy()
        mock_dynamodb_client.put_session.return_value = {}

        # Call function
        result = cancel_session(
            trainer_id="trainer123",
            session_id="session789",
        )

        # Assertions
        assert result["success"] is True
        assert result["data"]["session_id"] == "session789"
        assert result["data"]["student_name"] == "John Doe"
        assert result["data"]["session_datetime"] == existing_session_data["session_datetime"]
        assert result["data"]["duration_minutes"] == 60
        assert result["data"]["location"] == "Main Gym"
        assert result["data"]["status"] == "cancelled"
        assert "reason" not in result["data"]

        # Verify session was updated
        mock_dynamodb_client.put_session.assert_called_once()
        call_args = mock_dynamodb_client.put_session.call_args
        updated_session = call_args[0][0]
        assert updated_session["status"] == "cancelled"
        assert "updated_at" in updated_session

    def test_cancel_session_success_with_reason(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test successful session cancellation with reason."""
        # Setup mocks
        mock_dynamodb_client.get_session.return_value = existing_session_data.copy()
        mock_dynamodb_client.put_session.return_value = {}

        # Call function
        result = cancel_session(
            trainer_id="trainer123",
            session_id="session789",
            reason="Student requested cancellation",
        )

        # Assertions
        assert result["success"] is True
        assert result["data"]["status"] == "cancelled"
        assert result["data"]["reason"] == "Student requested cancellation"

        # Verify cancellation_reason was stored
        call_args = mock_dynamodb_client.put_session.call_args
        updated_session = call_args[0][0]
        assert updated_session["cancellation_reason"] == "Student requested cancellation"

    def test_cancel_session_without_location(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test cancelling session without location field."""
        # Remove location from existing session
        session_without_location = existing_session_data.copy()
        del session_without_location["location"]

        # Setup mocks
        mock_dynamodb_client.get_session.return_value = session_without_location
        mock_dynamodb_client.put_session.return_value = {}

        # Call function
        result = cancel_session(
            trainer_id="trainer123",
            session_id="session789",
        )

        # Assertions
        assert result["success"] is True
        assert "location" not in result["data"]

    def test_cancel_session_not_found(self, mock_dynamodb_client):
        """Test error when session doesn't exist."""
        mock_dynamodb_client.get_session.return_value = None

        result = cancel_session(
            trainer_id="trainer123",
            session_id="nonexistent",
        )

        assert result["success"] is False
        assert "Session not found" in result["error"]

    def test_cancel_session_wrong_trainer(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test error when session belongs to different trainer."""
        mock_dynamodb_client.get_session.return_value = existing_session_data

        result = cancel_session(
            trainer_id="different_trainer",
            session_id="session789",
        )

        assert result["success"] is False
        assert "does not belong to trainer" in result["error"]

    def test_cancel_already_cancelled_session(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test error when trying to cancel an already cancelled session."""
        cancelled_session = existing_session_data.copy()
        cancelled_session["status"] = "cancelled"

        mock_dynamodb_client.get_session.return_value = cancelled_session

        result = cancel_session(
            trainer_id="trainer123",
            session_id="session789",
        )

        assert result["success"] is False
        assert "already cancelled" in result["error"]

    def test_cancel_session_missing_session_id(self, mock_dynamodb_client):
        """Test error when session ID is missing."""
        result = cancel_session(
            trainer_id="trainer123",
            session_id="",
        )

        assert result["success"] is False
        assert "Session ID is required" in result["error"]

    def test_cancel_session_sanitizes_inputs(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test that inputs are sanitized."""
        # Create a session with a clean ID
        clean_session_data = existing_session_data.copy()
        clean_session_data["session_id"] = "alertxsssession789"  # After sanitization

        mock_dynamodb_client.get_session.return_value = clean_session_data
        mock_dynamodb_client.put_session.return_value = {}

        # Pass malicious input that will be sanitized
        result = cancel_session(
            trainer_id="trainer123",
            session_id="<script>alert('xss')</script>session789",
            reason="<script>alert('xss')</script>Cancellation",
        )

        # After sanitization, the session_id becomes "alertxsssession789"
        # which matches our mock, so it should succeed
        assert result["success"] is True

        # Verify get_session was called with sanitized session_id
        mock_dynamodb_client.get_session.assert_called_once()
        call_args = mock_dynamodb_client.get_session.call_args
        # The sanitized session_id should not contain script tags
        assert "<script>" not in call_args[0][1]

        # Verify reason was sanitized
        put_call_args = mock_dynamodb_client.put_session.call_args
        updated_session = put_call_args[0][0]
        assert "<script>" not in updated_session.get("cancellation_reason", "")

    def test_cancel_session_updates_timestamp(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test that updated_at timestamp is set."""
        mock_dynamodb_client.get_session.return_value = existing_session_data
        mock_dynamodb_client.put_session.return_value = {}

        result = cancel_session(
            trainer_id="trainer123",
            session_id="session789",
        )

        assert result["success"] is True

        # Verify put_session was called with updated_at
        call_args = mock_dynamodb_client.put_session.call_args
        updated_session = call_args[0][0]
        assert "updated_at" in updated_session
        # Verify updated_at is recent (within last minute)
        updated_at = datetime.fromisoformat(updated_session["updated_at"].replace("Z", ""))
        assert (datetime.utcnow() - updated_at).total_seconds() < 60

    def test_cancel_session_preserves_other_fields(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test that other session fields are preserved during cancellation."""
        mock_dynamodb_client.get_session.return_value = existing_session_data
        mock_dynamodb_client.put_session.return_value = {}

        result = cancel_session(
            trainer_id="trainer123",
            session_id="session789",
        )

        assert result["success"] is True

        # Verify put_session was called with all original fields preserved
        call_args = mock_dynamodb_client.put_session.call_args
        updated_session = call_args[0][0]
        assert updated_session["student_id"] == "student456"
        assert updated_session["student_name"] == "John Doe"
        assert updated_session["duration_minutes"] == 60
        assert updated_session["location"] == "Main Gym"
        assert updated_session["session_datetime"] == existing_session_data["session_datetime"]
        assert updated_session["created_at"] == existing_session_data["created_at"]

    def test_cancel_session_can_cancel_confirmed_session(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test that confirmed sessions can be cancelled."""
        confirmed_session = existing_session_data.copy()
        confirmed_session["status"] = "confirmed"

        mock_dynamodb_client.get_session.return_value = confirmed_session
        mock_dynamodb_client.put_session.return_value = {}

        result = cancel_session(
            trainer_id="trainer123",
            session_id="session789",
        )

        assert result["success"] is True
        assert result["data"]["status"] == "cancelled"

    def test_cancel_session_can_cancel_completed_session(
        self, mock_dynamodb_client, existing_session_data
    ):
        """Test that completed sessions can be cancelled (for record correction)."""
        completed_session = existing_session_data.copy()
        completed_session["status"] = "completed"

        mock_dynamodb_client.get_session.return_value = completed_session
        mock_dynamodb_client.put_session.return_value = {}

        result = cancel_session(
            trainer_id="trainer123",
            session_id="session789",
        )

        assert result["success"] is True
        assert result["data"]["status"] == "cancelled"



class TestViewCalendar:
    """Test suite for view_calendar tool function."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Mock DynamoDB client."""
        with patch("src.tools.session_tools.dynamodb_client") as mock:
            yield mock

    @pytest.fixture
    def trainer_data(self):
        """Sample trainer data."""
        return {
            "trainer_id": "trainer123",
            "name": "Jane Trainer",
            "email": "jane@example.com",
            "business_name": "Jane's Fitness",
            "phone_number": "+14155551234",
        }

    @pytest.fixture
    def sample_sessions(self):
        """Sample session data for testing."""
        base_time = datetime.utcnow() + timedelta(days=1)
        return [
            {
                "session_id": "session1",
                "trainer_id": "trainer123",
                "student_id": "student1",
                "student_name": "John Doe",
                "session_datetime": base_time.isoformat(),
                "duration_minutes": 60,
                "location": "Main Gym",
                "status": "scheduled",
            },
            {
                "session_id": "session2",
                "trainer_id": "trainer123",
                "student_id": "student2",
                "student_name": "Jane Smith",
                "session_datetime": (base_time + timedelta(hours=2)).isoformat(),
                "duration_minutes": 45,
                "status": "confirmed",
                "student_confirmed": True,
                "student_confirmed_at": base_time.isoformat(),
            },
            {
                "session_id": "session3",
                "trainer_id": "trainer123",
                "student_id": "student3",
                "student_name": "Bob Wilson",
                "session_datetime": (base_time + timedelta(days=1)).isoformat(),
                "duration_minutes": 90,
                "location": "Park",
                "status": "scheduled",
            },
        ]

    def test_view_calendar_with_week_filter(
        self, mock_dynamodb_client, trainer_data, sample_sessions
    ):
        """Test viewing calendar with week filter."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = sample_sessions

        result = view_calendar(trainer_id="trainer123", filter="week")

        if not result["success"]:
            print(f"Error: {result.get('error')}")
        assert result["success"] is True
        assert "sessions" in result["data"]
        assert result["data"]["total_count"] == 3
        assert len(result["data"]["sessions"]) == 3
        
        # Verify sessions are in chronological order
        sessions = result["data"]["sessions"]
        for i in range(len(sessions) - 1):
            assert sessions[i]["session_datetime"] <= sessions[i + 1]["session_datetime"]
        
        # Verify date range is included
        assert "start_date" in result["data"]
        assert "end_date" in result["data"]

    def test_view_calendar_with_day_filter(
        self, mock_dynamodb_client, trainer_data, sample_sessions
    ):
        """Test viewing calendar with day filter (today only)."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = sample_sessions[:2]

        result = view_calendar(trainer_id="trainer123", filter="day")

        assert result["success"] is True
        assert result["data"]["total_count"] == 2
        
        # Verify get_sessions_by_date_range was called
        mock_dynamodb_client.get_sessions_by_date_range.assert_called_once()

    def test_view_calendar_with_month_filter(
        self, mock_dynamodb_client, trainer_data, sample_sessions
    ):
        """Test viewing calendar with month filter (30 days)."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = sample_sessions

        result = view_calendar(trainer_id="trainer123", filter="month")

        assert result["success"] is True
        assert result["data"]["total_count"] == 3

    def test_view_calendar_with_explicit_date_range(
        self, mock_dynamodb_client, trainer_data, sample_sessions
    ):
        """Test viewing calendar with explicit start and end dates."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = sample_sessions

        result = view_calendar(
            trainer_id="trainer123",
            start_date="2024-01-20",
            end_date="2024-01-25",
        )

        assert result["success"] is True
        assert result["data"]["start_date"] == "2024-01-20"
        assert result["data"]["end_date"] == "2024-01-25"
        assert result["data"]["total_count"] == 3

    def test_view_calendar_default_to_week(
        self, mock_dynamodb_client, trainer_data, sample_sessions
    ):
        """Test that calendar defaults to 7 days if no filter or dates provided."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = sample_sessions

        result = view_calendar(trainer_id="trainer123")

        assert result["success"] is True
        assert result["data"]["total_count"] == 3

    def test_view_calendar_empty_results(
        self, mock_dynamodb_client, trainer_data
    ):
        """Test viewing calendar when no sessions exist."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = []

        result = view_calendar(trainer_id="trainer123", filter="week")

        assert result["success"] is True
        assert result["data"]["sessions"] == []
        assert result["data"]["total_count"] == 0

    def test_view_calendar_trainer_not_found(self, mock_dynamodb_client):
        """Test error when trainer doesn't exist."""
        mock_dynamodb_client.get_trainer.return_value = None

        result = view_calendar(trainer_id="nonexistent", filter="week")

        assert result["success"] is False
        assert "Trainer not found" in result["error"]

    def test_view_calendar_invalid_filter(
        self, mock_dynamodb_client, trainer_data
    ):
        """Test error with invalid filter value."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data

        result = view_calendar(trainer_id="trainer123", filter="invalid")

        assert result["success"] is False
        assert "Invalid filter value" in result["error"]

    def test_view_calendar_invalid_date_format(
        self, mock_dynamodb_client, trainer_data
    ):
        """Test error with invalid date format."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data

        result = view_calendar(
            trainer_id="trainer123",
            start_date="2024/01/20",  # Wrong format
            end_date="2024-01-25",
        )

        assert result["success"] is False
        assert "Invalid date format" in result["error"]

    def test_view_calendar_start_after_end(
        self, mock_dynamodb_client, trainer_data
    ):
        """Test error when start date is after end date."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data

        result = view_calendar(
            trainer_id="trainer123",
            start_date="2024-01-25",
            end_date="2024-01-20",
        )

        assert result["success"] is False
        assert "Start date must be before or equal to end date" in result["error"]

    def test_view_calendar_includes_optional_fields(
        self, mock_dynamodb_client, trainer_data
    ):
        """Test that optional fields are included when present."""
        session_with_optionals = {
            "session_id": "session1",
            "trainer_id": "trainer123",
            "student_id": "student1",
            "student_name": "John Doe",
            "session_datetime": datetime.utcnow().isoformat(),
            "duration_minutes": 60,
            "location": "Main Gym",
            "status": "confirmed",
            "student_confirmed": True,
            "student_confirmed_at": datetime.utcnow().isoformat(),
        }

        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [session_with_optionals]

        result = view_calendar(trainer_id="trainer123", filter="week")

        assert result["success"] is True
        session = result["data"]["sessions"][0]
        assert "location" in session
        assert session["location"] == "Main Gym"
        assert "student_confirmed" in session
        assert session["student_confirmed"] is True
        assert "student_confirmed_at" in session

    def test_view_calendar_excludes_missing_optional_fields(
        self, mock_dynamodb_client, trainer_data
    ):
        """Test that optional fields are excluded when not present."""
        session_without_optionals = {
            "session_id": "session1",
            "trainer_id": "trainer123",
            "student_id": "student1",
            "student_name": "John Doe",
            "session_datetime": datetime.utcnow().isoformat(),
            "duration_minutes": 60,
            "status": "scheduled",
        }

        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [session_without_optionals]

        result = view_calendar(trainer_id="trainer123", filter="week")

        assert result["success"] is True
        session = result["data"]["sessions"][0]
        assert "location" not in session
        assert "student_confirmed" not in session
        assert "student_confirmed_at" not in session

    def test_view_calendar_sorts_chronologically(
        self, mock_dynamodb_client, trainer_data
    ):
        """Test that sessions are sorted in chronological order (earliest first)."""
        base_time = datetime.utcnow()
        unsorted_sessions = [
            {
                "session_id": "session3",
                "student_name": "Charlie",
                "session_datetime": (base_time + timedelta(days=3)).isoformat(),
                "duration_minutes": 60,
                "status": "scheduled",
            },
            {
                "session_id": "session1",
                "student_name": "Alice",
                "session_datetime": (base_time + timedelta(days=1)).isoformat(),
                "duration_minutes": 60,
                "status": "scheduled",
            },
            {
                "session_id": "session2",
                "student_name": "Bob",
                "session_datetime": (base_time + timedelta(days=2)).isoformat(),
                "duration_minutes": 60,
                "status": "scheduled",
            },
        ]

        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = unsorted_sessions

        result = view_calendar(trainer_id="trainer123", filter="week")

        assert result["success"] is True
        sessions = result["data"]["sessions"]
        assert sessions[0]["student_name"] == "Alice"
        assert sessions[1]["student_name"] == "Bob"
        assert sessions[2]["student_name"] == "Charlie"

    def test_view_calendar_sanitizes_inputs(
        self, mock_dynamodb_client, trainer_data, sample_sessions
    ):
        """Test that inputs are sanitized properly."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = sample_sessions

        # Test with filter that needs sanitization
        result = view_calendar(trainer_id="trainer123", filter="  WEEK  ")

        assert result["success"] is True
        assert result["data"]["total_count"] == 3

    def test_view_calendar_student_name_filter_individual_session(
        self, mock_dynamodb_client, trainer_data, sample_sessions
    ):
        """Test filtering by student name returns matching individual sessions."""
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = sample_sessions

        result = view_calendar(
            trainer_id="trainer123", filter="week", student_name="Alice"
        )

        assert result["success"] is True
        for s in result["data"]["sessions"]:
            assert s["student_name"].lower() == "alice"

    def test_view_calendar_student_name_filter_includes_group_sessions(
        self, mock_dynamodb_client, trainer_data
    ):
        """Test that student_name filter includes group sessions where the student is enrolled."""
        individual_session = {
            "session_id": "sess1",
            "student_name": "Alice",
            "session_datetime": "2024-01-20T14:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
        }
        group_session = {
            "session_id": "sess2",
            "student_name": "",
            "session_datetime": "2024-01-21T10:00:00",
            "duration_minutes": 90,
            "status": "scheduled",
            "session_type": "group",
            "max_participants": 5,
            "enrolled_students": [
                {"student_id": "s1", "student_name": "Alice"},
                {"student_id": "s2", "student_name": "Bob"},
            ],
        }
        unrelated_session = {
            "session_id": "sess3",
            "student_name": "Charlie",
            "session_datetime": "2024-01-22T09:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
        }
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [
            individual_session, group_session, unrelated_session
        ]

        result = view_calendar(
            trainer_id="trainer123", filter="week", student_name="Alice"
        )

        assert result["success"] is True
        assert result["data"]["total_count"] == 2
        session_ids = [s["session_id"] for s in result["data"]["sessions"]]
        assert "sess1" in session_ids
        assert "sess2" in session_ids
        assert "sess3" not in session_ids

    def test_view_calendar_student_name_filter_case_insensitive(
        self, mock_dynamodb_client, trainer_data
    ):
        """Test that student_name filter is case-insensitive for group sessions."""
        group_session = {
            "session_id": "sess1",
            "student_name": "",
            "session_datetime": "2024-01-21T10:00:00",
            "duration_minutes": 90,
            "status": "scheduled",
            "session_type": "group",
            "max_participants": 5,
            "enrolled_students": [
                {"student_id": "s1", "student_name": "Alice Smith"},
            ],
        }
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [group_session]

        result = view_calendar(
            trainer_id="trainer123", filter="week", student_name="alice smith"
        )

        assert result["success"] is True
        assert result["data"]["total_count"] == 1

    def test_view_calendar_student_name_filter_no_match(
        self, mock_dynamodb_client, trainer_data
    ):
        """Test that student_name filter returns empty when no sessions match."""
        group_session = {
            "session_id": "sess1",
            "student_name": "",
            "session_datetime": "2024-01-21T10:00:00",
            "duration_minutes": 90,
            "status": "scheduled",
            "session_type": "group",
            "max_participants": 5,
            "enrolled_students": [
                {"student_id": "s1", "student_name": "Bob"},
            ],
        }
        individual_session = {
            "session_id": "sess2",
            "student_name": "Charlie",
            "session_datetime": "2024-01-22T09:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
        }
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [
            group_session, individual_session
        ]

        result = view_calendar(
            trainer_id="trainer123", filter="week", student_name="Nonexistent"
        )

        assert result["success"] is True
        assert result["data"]["total_count"] == 0
