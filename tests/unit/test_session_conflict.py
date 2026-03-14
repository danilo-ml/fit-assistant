"""
Unit tests for SessionConflictDetector.

Tests conflict detection logic including:
- No conflicts when sessions don't overlap
- Conflicts detected when sessions overlap
- 30-minute buffer handling
- Exclusion of specific sessions (for rescheduling)
- Edge cases (adjacent sessions, same start time, etc.)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from src.services.session_conflict import SessionConflictDetector
from src.models.dynamodb_client import DynamoDBClient


@pytest.fixture
def mock_dynamodb_client():
    """Create a mock DynamoDB client."""
    return Mock()


@pytest.fixture
def detector(mock_dynamodb_client):
    """Create a SessionConflictDetector with mocked DynamoDB client."""
    return SessionConflictDetector(dynamodb_client=mock_dynamodb_client)


def create_session(
    session_id: str,
    trainer_id: str,
    session_datetime: datetime,
    duration_minutes: int,
    status: str = 'scheduled'
) -> dict:
    """Helper to create a session dict."""
    return {
        'session_id': session_id,
        'trainer_id': trainer_id,
        'student_id': 'student123',
        'student_name': 'John Doe',
        'session_datetime': session_datetime.isoformat(),
        'duration_minutes': duration_minutes,
        'status': status
    }


class TestSessionConflictDetector:
    """Test suite for SessionConflictDetector."""
    
    def test_no_conflicts_when_no_existing_sessions(self, detector, mock_dynamodb_client):
        """Test that no conflicts are found when there are no existing sessions."""
        # Arrange
        mock_dynamodb_client.get_sessions_by_date_range.return_value = []
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 14, 0),
            duration_minutes=60
        )
        
        # Assert
        assert conflicts == []
        mock_dynamodb_client.get_sessions_by_date_range.assert_called_once()
    
    def test_no_conflicts_when_sessions_dont_overlap(self, detector, mock_dynamodb_client):
        """Test that no conflicts are found when sessions don't overlap."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)
        existing_session = create_session(
            session_id='session1',
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 10, 0),  # 4 hours earlier
            duration_minutes=60
        )
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=60
        )
        
        # Assert
        assert conflicts == []
    
    def test_conflict_detected_when_sessions_overlap(self, detector, mock_dynamodb_client):
        """Test that conflict is detected when sessions overlap."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)  # 2:00 PM - 3:00 PM
        existing_session = create_session(
            session_id='session1',
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 14, 30),  # 2:30 PM - 3:30 PM (overlaps)
            duration_minutes=60
        )
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=60
        )
        
        # Assert
        assert len(conflicts) == 1
        assert conflicts[0]['session_id'] == 'session1'
    
    def test_conflict_detected_when_proposed_session_starts_during_existing(self, detector, mock_dynamodb_client):
        """Test conflict when proposed session starts during an existing session."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 30)  # 2:30 PM - 3:30 PM
        existing_session = create_session(
            session_id='session1',
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 14, 0),  # 2:00 PM - 3:00 PM
            duration_minutes=60
        )
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=60
        )
        
        # Assert
        assert len(conflicts) == 1
        assert conflicts[0]['session_id'] == 'session1'
    
    def test_conflict_detected_when_existing_session_starts_during_proposed(self, detector, mock_dynamodb_client):
        """Test conflict when existing session starts during proposed session."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)  # 2:00 PM - 4:00 PM (2 hours)
        existing_session = create_session(
            session_id='session1',
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 15, 0),  # 3:00 PM - 4:00 PM
            duration_minutes=60
        )
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=120
        )
        
        # Assert
        assert len(conflicts) == 1
        assert conflicts[0]['session_id'] == 'session1'
    
    def test_conflict_detected_when_sessions_have_same_start_time(self, detector, mock_dynamodb_client):
        """Test conflict when sessions have the same start time."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)
        existing_session = create_session(
            session_id='session1',
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 14, 0),  # Same start time
            duration_minutes=60
        )
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=60
        )
        
        # Assert
        assert len(conflicts) == 1
        assert conflicts[0]['session_id'] == 'session1'
    
    def test_no_conflict_when_sessions_are_adjacent(self, detector, mock_dynamodb_client):
        """Test that adjacent sessions (end-to-start) don't conflict."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 15, 0)  # 3:00 PM - 4:00 PM
        existing_session = create_session(
            session_id='session1',
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 14, 0),  # 2:00 PM - 3:00 PM (ends when proposed starts)
            duration_minutes=60
        )
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=60
        )
        
        # Assert
        assert conflicts == []
    
    def test_multiple_conflicts_detected(self, detector, mock_dynamodb_client):
        """Test that multiple conflicting sessions are all detected."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)  # 2:00 PM - 4:00 PM (2 hours)
        existing_sessions = [
            create_session('session1', 'trainer123', datetime(2024, 1, 20, 13, 30), 60),  # Overlaps at start
            create_session('session2', 'trainer123', datetime(2024, 1, 20, 15, 0), 60),   # Overlaps in middle
            create_session('session3', 'trainer123', datetime(2024, 1, 20, 15, 30), 60),  # Overlaps at end
        ]
        mock_dynamodb_client.get_sessions_by_date_range.return_value = existing_sessions
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=120
        )
        
        # Assert
        assert len(conflicts) == 3
        assert {c['session_id'] for c in conflicts} == {'session1', 'session2', 'session3'}
    
    def test_exclude_session_id_filters_out_specified_session(self, detector, mock_dynamodb_client):
        """Test that exclude_session_id parameter filters out the specified session."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)
        existing_sessions = [
            create_session('session1', 'trainer123', datetime(2024, 1, 20, 14, 0), 60),  # Would conflict
            create_session('session2', 'trainer123', datetime(2024, 1, 20, 14, 30), 60),  # Would conflict
        ]
        mock_dynamodb_client.get_sessions_by_date_range.return_value = existing_sessions
        
        # Act - exclude session1 (useful when rescheduling)
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=60,
            exclude_session_id='session1'
        )
        
        # Assert
        assert len(conflicts) == 1
        assert conflicts[0]['session_id'] == 'session2'
    
    def test_cancelled_sessions_not_included_in_conflicts(self, detector, mock_dynamodb_client):
        """Test that cancelled sessions are not considered conflicts."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)
        # Mock returns only scheduled/confirmed sessions (cancelled filtered by DynamoDB query)
        existing_session = create_session(
            session_id='session1',
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 14, 0),
            duration_minutes=60,
            status='scheduled'
        )
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=60
        )
        
        # Assert
        assert len(conflicts) == 1
        # Verify that status_filter was passed to exclude cancelled sessions
        call_args = mock_dynamodb_client.get_sessions_by_date_range.call_args
        assert call_args[1]['status_filter'] == ['scheduled', 'confirmed']
    
    def test_query_uses_30_minute_buffer(self, detector, mock_dynamodb_client):
        """Test that the query includes a 30-minute buffer before and after."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)  # 2:00 PM
        duration = 60  # 1 hour
        mock_dynamodb_client.get_sessions_by_date_range.return_value = []
        
        # Act
        detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=duration
        )
        
        # Assert
        call_args = mock_dynamodb_client.get_sessions_by_date_range.call_args
        start_datetime = call_args[1]['start_datetime']
        end_datetime = call_args[1]['end_datetime']
        
        # Query should start 30 minutes before proposed start
        expected_start = proposed_time - timedelta(minutes=30)
        # Query should end 30 minutes after proposed end
        expected_end = proposed_time + timedelta(minutes=duration) + timedelta(minutes=30)
        
        assert start_datetime == expected_start
        assert end_datetime == expected_end
    
    def test_short_duration_sessions(self, detector, mock_dynamodb_client):
        """Test conflict detection with short duration sessions (15 minutes)."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)  # 2:00 PM - 2:15 PM
        existing_session = create_session(
            session_id='session1',
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 14, 10),  # 2:10 PM - 2:25 PM (overlaps)
            duration_minutes=15
        )
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=15
        )
        
        # Assert
        assert len(conflicts) == 1
        assert conflicts[0]['session_id'] == 'session1'
    
    def test_long_duration_sessions(self, detector, mock_dynamodb_client):
        """Test conflict detection with long duration sessions (4 hours)."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 10, 0)  # 10:00 AM - 2:00 PM (4 hours)
        existing_session = create_session(
            session_id='session1',
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 12, 0),  # 12:00 PM - 1:00 PM (in middle)
            duration_minutes=60
        )
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=240
        )
        
        # Assert
        assert len(conflicts) == 1
        assert conflicts[0]['session_id'] == 'session1'
    
    def test_conflict_detection_with_different_trainers(self, detector, mock_dynamodb_client):
        """Test that sessions from different trainers don't conflict."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)
        # Mock returns empty list (different trainer's sessions not returned)
        mock_dynamodb_client.get_sessions_by_date_range.return_value = []
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=60
        )
        
        # Assert
        assert conflicts == []
        # Verify correct trainer_id was queried
        call_args = mock_dynamodb_client.get_sessions_by_date_range.call_args
        assert call_args[1]['trainer_id'] == 'trainer123'
    
    def test_creates_dynamodb_client_if_not_provided(self):
        """Test that SessionConflictDetector creates its own DynamoDB client if not provided."""
        # Act
        detector = SessionConflictDetector()
        
        # Assert
        assert detector.dynamodb is not None
        assert isinstance(detector.dynamodb, DynamoDBClient)
    
    def test_edge_case_one_minute_overlap(self, detector, mock_dynamodb_client):
        """Test that even a 1-minute overlap is detected as a conflict."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)  # 2:00 PM - 3:00 PM
        existing_session = create_session(
            session_id='session1',
            trainer_id='trainer123',
            session_datetime=datetime(2024, 1, 20, 14, 59),  # 2:59 PM - 3:59 PM (1 min overlap)
            duration_minutes=60
        )
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=60
        )
        
        # Assert
        assert len(conflicts) == 1
        assert conflicts[0]['session_id'] == 'session1'
    
    def test_returns_full_session_details_in_conflicts(self, detector, mock_dynamodb_client):
        """Test that conflict results include all session details."""
        # Arrange
        proposed_time = datetime(2024, 1, 20, 14, 0)
        existing_session = {
            'session_id': 'session1',
            'trainer_id': 'trainer123',
            'student_id': 'student456',
            'student_name': 'Jane Smith',
            'session_datetime': datetime(2024, 1, 20, 14, 30).isoformat(),
            'duration_minutes': 60,
            'status': 'scheduled',
            'location': 'Gym A'
        }
        mock_dynamodb_client.get_sessions_by_date_range.return_value = [existing_session]
        
        # Act
        conflicts = detector.check_conflicts(
            trainer_id='trainer123',
            session_datetime=proposed_time,
            duration_minutes=60
        )
        
        # Assert
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict['session_id'] == 'session1'
        assert conflict['student_name'] == 'Jane Smith'
        assert conflict['location'] == 'Gym A'
        assert conflict['duration_minutes'] == 60


# Import DynamoDBClient for the test that checks instance type
from src.models.dynamodb_client import DynamoDBClient
