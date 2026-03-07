"""
Integration tests for session tools with calendar sync.

Tests verify that session operations correctly integrate with the calendar sync service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.tools.session_tools import schedule_session, reschedule_session, cancel_session


class TestSessionCalendarIntegration:
    """Integration tests for session tools with calendar sync."""

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

    def test_schedule_session_with_calendar_sync(
        self,
        mock_dynamodb_client,
        mock_conflict_detector,
        mock_calendar_sync_service,
        trainer_data,
        student_data,
        trainer_student_link,
        future_date,
    ):
        """Test that schedule_session calls calendar sync and stores event info."""
        # Setup mocks
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = []
        
        # Mock get_session to return the session with calendar info
        def mock_get_session(trainer_id, session_id):
            return {
                "session_id": session_id,
                "trainer_id": trainer_id,
                "student_id": "student456",
                "student_name": "John Doe",
                "session_datetime": f"{future_date}T14:00:00",
                "duration_minutes": 60,
                "status": "scheduled",
            }
        
        mock_dynamodb_client.get_session.side_effect = mock_get_session
        mock_dynamodb_client.put_session.return_value = {}
        
        # Mock calendar sync to return event info
        mock_calendar_sync_service.create_event.return_value = {
            "calendar_event_id": "google_event_123",
            "calendar_provider": "google",
        }

        # Call schedule_session
        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date=future_date,
            time="14:00",
            duration_minutes=60,
            location="Main Gym",
        )

        # Verify success
        assert result["success"] is True
        assert result["data"]["calendar_event_id"] == "google_event_123"
        assert result["data"]["calendar_provider"] == "google"

        # Verify calendar sync was called with correct parameters
        mock_calendar_sync_service.create_event.assert_called_once()
        call_args = mock_calendar_sync_service.create_event.call_args
        assert call_args.kwargs["trainer_id"] == "trainer123"
        assert call_args.kwargs["student_name"] == "John Doe"
        assert call_args.kwargs["duration_minutes"] == 60
        assert call_args.kwargs["location"] == "Main Gym"

        # Verify session was updated with calendar info
        assert mock_dynamodb_client.put_session.call_count == 2  # Initial + calendar update

    def test_schedule_session_without_calendar_sync(
        self,
        mock_dynamodb_client,
        mock_conflict_detector,
        mock_calendar_sync_service,
        trainer_data,
        student_data,
        trainer_student_link,
        future_date,
    ):
        """Test that schedule_session succeeds even when calendar sync fails."""
        # Setup mocks
        mock_dynamodb_client.get_trainer.return_value = trainer_data
        mock_dynamodb_client.get_trainer_students.return_value = [trainer_student_link]
        mock_dynamodb_client.get_student.return_value = student_data
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}
        
        # Mock calendar sync to return None (failure)
        mock_calendar_sync_service.create_event.return_value = None

        # Call schedule_session
        result = schedule_session(
            trainer_id="trainer123",
            student_name="John Doe",
            date=future_date,
            time="14:00",
            duration_minutes=60,
        )

        # Verify success (graceful degradation)
        assert result["success"] is True
        assert "calendar_event_id" not in result["data"]
        assert "calendar_provider" not in result["data"]

        # Verify session was still created
        assert mock_dynamodb_client.put_session.call_count == 1

    def test_reschedule_session_with_calendar_sync(
        self,
        mock_dynamodb_client,
        mock_conflict_detector,
        mock_calendar_sync_service,
        future_date,
    ):
        """Test that reschedule_session calls calendar sync update."""
        new_date = (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%d")
        
        # Setup existing session with calendar info
        existing_session = {
            "session_id": "session789",
            "trainer_id": "trainer123",
            "student_id": "student456",
            "student_name": "John Doe",
            "session_datetime": f"{future_date}T14:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
            "calendar_event_id": "google_event_123",
            "calendar_provider": "google",
        }
        
        mock_dynamodb_client.get_session.return_value = existing_session
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}
        
        # Mock calendar sync to succeed
        mock_calendar_sync_service.update_event.return_value = True

        # Call reschedule_session
        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date=new_date,
            new_time="15:00",
        )

        # Verify success
        assert result["success"] is True
        assert result["data"]["calendar_synced"] is True

        # Verify calendar sync was called
        mock_calendar_sync_service.update_event.assert_called_once()
        call_args = mock_calendar_sync_service.update_event.call_args
        assert call_args.kwargs["trainer_id"] == "trainer123"
        assert call_args.kwargs["session_id"] == "session789"
        assert call_args.kwargs["calendar_event_id"] == "google_event_123"
        assert call_args.kwargs["calendar_provider"] == "google"

    def test_reschedule_session_without_calendar(
        self,
        mock_dynamodb_client,
        mock_conflict_detector,
        mock_calendar_sync_service,
        future_date,
    ):
        """Test that reschedule_session works without calendar connection."""
        new_date = (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%d")
        
        # Setup existing session WITHOUT calendar info
        existing_session = {
            "session_id": "session789",
            "trainer_id": "trainer123",
            "student_id": "student456",
            "student_name": "John Doe",
            "session_datetime": f"{future_date}T14:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
        }
        
        mock_dynamodb_client.get_session.return_value = existing_session
        mock_conflict_detector.check_conflicts.return_value = []
        mock_dynamodb_client.put_session.return_value = {}

        # Call reschedule_session
        result = reschedule_session(
            trainer_id="trainer123",
            session_id="session789",
            new_date=new_date,
            new_time="15:00",
        )

        # Verify success
        assert result["success"] is True
        assert "calendar_synced" not in result["data"]

        # Verify calendar sync was NOT called
        mock_calendar_sync_service.update_event.assert_not_called()

    def test_cancel_session_with_calendar_sync(
        self,
        mock_dynamodb_client,
        mock_calendar_sync_service,
        future_date,
    ):
        """Test that cancel_session calls calendar sync delete."""
        # Setup existing session with calendar info
        existing_session = {
            "session_id": "session789",
            "trainer_id": "trainer123",
            "student_id": "student456",
            "student_name": "John Doe",
            "session_datetime": f"{future_date}T14:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
            "calendar_event_id": "google_event_123",
            "calendar_provider": "google",
        }
        
        mock_dynamodb_client.get_session.return_value = existing_session
        mock_dynamodb_client.put_session.return_value = {}
        
        # Mock calendar sync to succeed
        mock_calendar_sync_service.delete_event.return_value = True

        # Call cancel_session
        result = cancel_session(
            trainer_id="trainer123",
            session_id="session789",
            reason="Student requested cancellation",
        )

        # Verify success
        assert result["success"] is True
        assert result["data"]["status"] == "cancelled"
        assert result["data"]["calendar_synced"] is True

        # Verify calendar sync was called
        mock_calendar_sync_service.delete_event.assert_called_once()
        call_args = mock_calendar_sync_service.delete_event.call_args
        assert call_args.kwargs["trainer_id"] == "trainer123"
        assert call_args.kwargs["session_id"] == "session789"
        assert call_args.kwargs["calendar_event_id"] == "google_event_123"
        assert call_args.kwargs["calendar_provider"] == "google"

    def test_cancel_session_calendar_sync_failure(
        self,
        mock_dynamodb_client,
        mock_calendar_sync_service,
        future_date,
    ):
        """Test that cancel_session succeeds even when calendar sync fails."""
        # Setup existing session with calendar info
        existing_session = {
            "session_id": "session789",
            "trainer_id": "trainer123",
            "student_id": "student456",
            "student_name": "John Doe",
            "session_datetime": f"{future_date}T14:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
            "calendar_event_id": "google_event_123",
            "calendar_provider": "google",
        }
        
        mock_dynamodb_client.get_session.return_value = existing_session
        mock_dynamodb_client.put_session.return_value = {}
        
        # Mock calendar sync to fail
        mock_calendar_sync_service.delete_event.return_value = False

        # Call cancel_session
        result = cancel_session(
            trainer_id="trainer123",
            session_id="session789",
        )

        # Verify success (graceful degradation)
        assert result["success"] is True
        assert result["data"]["status"] == "cancelled"
        assert result["data"]["calendar_synced"] is False

        # Verify session was still cancelled
        mock_dynamodb_client.put_session.assert_called_once()
