"""
Session conflict detection service for FitAgent.

This module provides conflict detection for session scheduling by checking
for time overlaps with existing sessions using the session-date-index GSI.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from src.models.dynamodb_client import DynamoDBClient


class SessionConflictDetector:
    """
    Detects scheduling conflicts for training sessions.
    
    Checks for time overlaps between a proposed session and existing sessions
    for a trainer, using a 30-minute buffer before and after each session.
    """
    
    def __init__(self, dynamodb_client: Optional[DynamoDBClient] = None):
        """
        Initialize the conflict detector.
        
        Args:
            dynamodb_client: DynamoDB client instance (creates new one if not provided)
        """
        self.dynamodb = dynamodb_client or DynamoDBClient()
    
    def check_conflicts(
        self,
        trainer_id: str,
        session_datetime: datetime,
        duration_minutes: int,
        exclude_session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Check for scheduling conflicts with existing sessions.
        
        Queries sessions using the session-date-index GSI with a 30-minute buffer
        before and after the proposed session time. Detects overlaps by comparing
        start and end times.
        
        Args:
            trainer_id: Trainer ID to check conflicts for
            session_datetime: Proposed session start datetime
            duration_minutes: Proposed session duration in minutes
            exclude_session_id: Optional session ID to exclude from conflict check
                               (useful when rescheduling an existing session)
        
        Returns:
            List of conflicting session dicts. Empty list if no conflicts.
            Each dict contains full session details including session_id, student_name,
            session_datetime, duration_minutes, and status.
        
        Example:
            >>> detector = SessionConflictDetector()
            >>> conflicts = detector.check_conflicts(
            ...     trainer_id='abc123',
            ...     session_datetime=datetime(2024, 1, 20, 14, 0),
            ...     duration_minutes=60
            ... )
            >>> if conflicts:
            ...     print(f"Found {len(conflicts)} conflicting sessions")
        """
        # Calculate proposed session time window
        session_start = session_datetime
        session_end = session_datetime + timedelta(minutes=duration_minutes)
        
        # Add 30-minute buffer for query window
        query_start = session_start - timedelta(minutes=30)
        query_end = session_end + timedelta(minutes=30)
        
        # Query sessions in the time window using session-date-index GSI
        # Only consider scheduled and confirmed sessions (not cancelled or completed)
        sessions = self.dynamodb.get_sessions_by_date_range(
            trainer_id=trainer_id,
            start_datetime=query_start,
            end_datetime=query_end,
            status_filter=['scheduled', 'confirmed']
        )
        
        # Check each session for time overlap
        conflicts = []
        for session in sessions:
            # Skip the session being rescheduled
            if exclude_session_id and session.get('session_id') == exclude_session_id:
                continue
            
            # Parse existing session times
            existing_start = datetime.fromisoformat(session['session_datetime'])
            existing_end = existing_start + timedelta(minutes=session['duration_minutes'])
            
            # Check for overlap: sessions overlap if one starts before the other ends
            # Overlap condition: (start1 < end2) AND (end1 > start2)
            if session_start < existing_end and session_end > existing_start:
                conflicts.append(session)
        
        return conflicts
