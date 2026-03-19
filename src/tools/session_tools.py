"""
AI agent tool functions for session management.

This module provides tool functions that the AI agent can call to:
- Schedule training sessions
- Reschedule existing sessions
- Cancel sessions
- View calendar with sessions in date range

All functions follow the tool function pattern:
- Accept trainer_id as first parameter
- Return dict with 'success', 'data', and optional 'error' keys
- Validate inputs before processing
- Handle errors gracefully
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from strands import tool

from models.entities import Session
from models.dynamodb_client import DynamoDBClient
from services.session_conflict import SessionConflictDetector
from services.calendar_sync import CalendarSyncService
from utils.validation import InputSanitizer
from utils.logging import get_logger
from config import settings

# Initialize DynamoDB client, conflict detector, and calendar sync service
dynamodb_client = DynamoDBClient(
    table_name=settings.dynamodb_table, endpoint_url=settings.aws_endpoint_url
)
conflict_detector = SessionConflictDetector(dynamodb_client)
calendar_sync_service = CalendarSyncService(
    dynamodb_client=dynamodb_client, aws_endpoint_url=settings.aws_endpoint_url
)
logger = get_logger(__name__)


@tool
def schedule_session(
    trainer_id: str,
    student_name: str,
    date: str,
    time: str,
    duration_minutes: int,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Schedule a new training session with a student.
    
    Use this tool when the trainer wants to schedule a training session with one of their students.
    The tool validates the date/time, checks for scheduling conflicts, creates the session record,
    and syncs with the trainer's connected calendar if available.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        student_name: Student's name (e.g., "João Silva")
        date: Session date in ISO format YYYY-MM-DD (e.g., "2024-01-20")
        time: Session time in HH:MM format (e.g., "14:00")
        duration_minutes: Session duration in minutes, between 15 and 480 (e.g., 60)
        location: Session location (optional, e.g., "Main Gym")

    Returns:
        dict: {
            'success': bool,
            'data': {
                'session_id': str,
                'student_name': str,
                'session_datetime': str (ISO 8601 format),
                'duration_minutes': int,
                'location': str (optional),
                'status': str,
                'conflicts': [
                    {
                        'session_id': str,
                        'student_name': str,
                        'session_datetime': str,
                        'duration_minutes': int
                    },
                    ...
                ] (only if conflicts detected)
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> schedule_session(
        ...     trainer_id='abc123',
        ...     student_name='John Doe',
        ...     date='2024-01-20',
        ...     time='14:00',
        ...     duration_minutes=60,
        ...     location='Main Gym'
        ... )
        {
            'success': True,
            'data': {
                'session_id': 'xyz789',
                'student_name': 'John Doe',
                'session_datetime': '2024-01-20T14:00:00',
                'duration_minutes': 60,
                'location': 'Main Gym',
                'status': 'scheduled'
            }
        }

    Validates: Requirements 3.1, 3.2, 3.3, 3.4
    """
    try:
        # Sanitize string inputs
        sanitized_params = InputSanitizer.sanitize_tool_parameters(
            {
                "student_name": student_name,
                "date": date,
                "time": time,
                "location": location if location else "",
            }
        )

        student_name = sanitized_params["student_name"]
        date = sanitized_params["date"]
        time = sanitized_params["time"]
        location = sanitized_params["location"] if sanitized_params["location"] else None

        # Validate required fields
        if not student_name:
            return {"success": False, "error": "Student name is required"}

        if not date:
            return {"success": False, "error": "Session date is required"}

        if not time:
            return {"success": False, "error": "Session time is required"}

        if not duration_minutes:
            return {"success": False, "error": "Session duration is required"}

        # Validate duration range
        if duration_minutes < 15 or duration_minutes > 480:
            return {
                "success": False,
                "error": f"Duration must be between 15 and 480 minutes. Got: {duration_minutes}",
            }

        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Find student by name - get all trainer's students and match by name
        trainer_students = dynamodb_client.get_trainer_students(trainer_id)

        matching_student = None
        for link in trainer_students:
            if link.get("status") != "active":
                continue

            student_id = link.get("student_id")
            if not student_id:
                continue

            student_data = dynamodb_client.get_student(student_id)
            if student_data and student_data["name"].lower() == student_name.lower():
                matching_student = student_data
                break

        if not matching_student:
            return {
                "success": False,
                "error": f"Student '{student_name}' not found or not linked to this trainer. Please register the student first.",
            }

        student_id = matching_student["student_id"]

        # Parse date and time into datetime object
        try:
            # Combine date and time strings
            datetime_str = f"{date}T{time}:00"
            session_datetime = datetime.fromisoformat(datetime_str)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time. Error: {str(e)}",
            }

        # Check if session is in the past
        if session_datetime < datetime.utcnow():
            return {
                "success": False,
                "error": "Cannot schedule sessions in the past",
            }

        # Check for scheduling conflicts
        conflicts = conflict_detector.check_conflicts(
            trainer_id=trainer_id,
            session_datetime=session_datetime,
            duration_minutes=duration_minutes,
        )

        # Create session entity
        session = Session(
            trainer_id=trainer_id,
            student_id=student_id,
            student_name=matching_student["name"],  # Use the actual name from DB
            session_datetime=session_datetime,
            duration_minutes=duration_minutes,
            location=location,
            status="scheduled",
        )

        # Save session to DynamoDB
        dynamodb_client.put_session(session.to_dynamodb())

        # Sync with calendar (within 30 seconds requirement)
        # This implements graceful degradation - failures are logged but don't block session creation
        calendar_result = calendar_sync_service.create_event(
            trainer_id=trainer_id,
            session_id=session.session_id,
            student_name=session.student_name,
            session_datetime=session_datetime,
            duration_minutes=duration_minutes,
            location=location,
            student_email=matching_student.get("email"),
        )

        # If calendar sync succeeded, update session with calendar event info
        if calendar_result:
            session_data = dynamodb_client.get_session(trainer_id, session.session_id)
            if session_data:
                session_data["calendar_event_id"] = calendar_result["calendar_event_id"]
                session_data["calendar_provider"] = calendar_result["calendar_provider"]
                session_data["updated_at"] = datetime.utcnow().isoformat()
                dynamodb_client.put_session(session_data)
                
                logger.info(
                    "Session created with calendar sync",
                    trainer_id=trainer_id,
                    session_id=session.session_id,
                    calendar_provider=calendar_result["calendar_provider"],
                )
        else:
            logger.info(
                "Session created without calendar sync",
                trainer_id=trainer_id,
                session_id=session.session_id,
            )

        # Prepare response data
        response_data = {
            "session_id": session.session_id,
            "student_name": session.student_name,
            "session_datetime": session.session_datetime.isoformat(),
            "duration_minutes": session.duration_minutes,
            "status": session.status,
        }

        if location:
            response_data["location"] = location

        # Include calendar sync info if available
        if calendar_result:
            response_data["calendar_event_id"] = calendar_result["calendar_event_id"]
            response_data["calendar_provider"] = calendar_result["calendar_provider"]

        # Include conflicts if any were detected
        if conflicts:
            response_data["conflicts"] = [
                {
                    "session_id": c["session_id"],
                    "student_name": c["student_name"],
                    "session_datetime": c["session_datetime"],
                    "duration_minutes": c["duration_minutes"],
                }
                for c in conflicts
            ]

        return {"success": True, "data": response_data}

    except ValueError as e:
        # Pydantic validation errors
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        # Unexpected errors
        return {"success": False, "error": f"Failed to schedule session: {str(e)}"}


@tool
def reschedule_session(
    trainer_id: str,
    session_id: str,
    new_date: str,
    new_time: str,
) -> Dict[str, Any]:
    """
    Reschedule an existing training session to a new date and time.
    
    Use this tool when the trainer wants to move an existing session to a different date/time.
    The tool validates the new date/time, checks for scheduling conflicts, updates the session,
    and syncs with the trainer's connected calendar if available.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        session_id: Session identifier to reschedule (e.g., "xyz789")
        new_date: New session date in ISO format YYYY-MM-DD (e.g., "2024-01-21")
        new_time: New session time in HH:MM format (e.g., "15:00")

    Returns:
        dict: {
            'success': bool,
            'data': {
                'session_id': str,
                'student_name': str,
                'old_datetime': str (ISO 8601 format),
                'new_datetime': str (ISO 8601 format),
                'duration_minutes': int,
                'location': str (optional),
                'status': str,
                'conflicts': [
                    {
                        'session_id': str,
                        'student_name': str,
                        'session_datetime': str,
                        'duration_minutes': int
                    },
                    ...
                ] (only if conflicts detected)
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> reschedule_session(
        ...     trainer_id='abc123',
        ...     session_id='xyz789',
        ...     new_date='2024-01-21',
        ...     new_time='15:00'
        ... )
        {
            'success': True,
            'data': {
                'session_id': 'xyz789',
                'student_name': 'John Doe',
                'old_datetime': '2024-01-20T14:00:00',
                'new_datetime': '2024-01-21T15:00:00',
                'duration_minutes': 60,
                'status': 'scheduled'
            }
        }

    Validates: Requirements 3.5
    """
    try:
        # Sanitize string inputs
        sanitized_params = InputSanitizer.sanitize_tool_parameters(
            {
                "session_id": session_id,
                "new_date": new_date,
                "new_time": new_time,
            }
        )

        session_id = sanitized_params["session_id"]
        new_date = sanitized_params["new_date"]
        new_time = sanitized_params["new_time"]

        # Validate required fields
        if not session_id:
            return {"success": False, "error": "Session ID is required"}

        if not new_date:
            return {"success": False, "error": "New session date is required"}

        if not new_time:
            return {"success": False, "error": "New session time is required"}

        # Retrieve existing session
        session_data = dynamodb_client.get_session(trainer_id, session_id)
        if not session_data:
            return {
                "success": False,
                "error": f"Session not found: {session_id}",
            }

        # Verify session belongs to trainer
        if session_data.get("trainer_id") != trainer_id:
            return {
                "success": False,
                "error": f"Session {session_id} does not belong to trainer {trainer_id}",
            }

        # Check if session is already cancelled
        if session_data.get("status") == "cancelled":
            return {
                "success": False,
                "error": "Cannot reschedule a cancelled session",
            }

        # Parse new date and time into datetime object
        try:
            # Combine date and time strings
            datetime_str = f"{new_date}T{new_time}:00"
            new_session_datetime = datetime.fromisoformat(datetime_str)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid date or time format. Use YYYY-MM-DD for date and HH:MM for time. Error: {str(e)}",
            }

        # Check if new session time is in the past
        if new_session_datetime < datetime.utcnow():
            return {
                "success": False,
                "error": "Cannot reschedule sessions to the past",
            }

        # Check for scheduling conflicts (excluding current session)
        conflicts = conflict_detector.check_conflicts(
            trainer_id=trainer_id,
            session_datetime=new_session_datetime,
            duration_minutes=session_data["duration_minutes"],
            exclude_session_id=session_id,
        )

        # Store old datetime for response
        old_datetime = session_data["session_datetime"]

        # Update session with new datetime
        session_data["session_datetime"] = new_session_datetime.isoformat()
        session_data["updated_at"] = datetime.utcnow().isoformat()

        # Save updated session to DynamoDB
        dynamodb_client.put_session(session_data)

        # Sync with calendar if event exists (within 30 seconds requirement)
        # This implements graceful degradation - failures are logged but don't block session update
        calendar_synced = False
        if session_data.get("calendar_event_id") and session_data.get("calendar_provider"):
            calendar_synced = calendar_sync_service.update_event(
                trainer_id=trainer_id,
                session_id=session_id,
                calendar_event_id=session_data["calendar_event_id"],
                calendar_provider=session_data["calendar_provider"],
                student_name=session_data["student_name"],
                session_datetime=new_session_datetime,
                duration_minutes=session_data["duration_minutes"],
                location=session_data.get("location"),
            )
            
            if calendar_synced:
                logger.info(
                    "Session rescheduled with calendar sync",
                    trainer_id=trainer_id,
                    session_id=session_id,
                    calendar_provider=session_data["calendar_provider"],
                )
            else:
                logger.warning(
                    "Session rescheduled but calendar sync failed",
                    trainer_id=trainer_id,
                    session_id=session_id,
                )
        else:
            logger.info(
                "Session rescheduled without calendar sync (no calendar connected)",
                trainer_id=trainer_id,
                session_id=session_id,
            )

        # Prepare response data
        response_data = {
            "session_id": session_data["session_id"],
            "student_name": session_data["student_name"],
            "old_datetime": old_datetime,
            "new_datetime": new_session_datetime.isoformat(),
            "duration_minutes": session_data["duration_minutes"],
            "status": session_data["status"],
        }

        if session_data.get("location"):
            response_data["location"] = session_data["location"]

        # Include calendar sync status
        if session_data.get("calendar_event_id"):
            response_data["calendar_synced"] = calendar_synced

        # Include conflicts if any were detected
        if conflicts:
            response_data["conflicts"] = [
                {
                    "session_id": c["session_id"],
                    "student_name": c["student_name"],
                    "session_datetime": c["session_datetime"],
                    "duration_minutes": c["duration_minutes"],
                }
                for c in conflicts
            ]

        return {"success": True, "data": response_data}

    except ValueError as e:
        # Validation errors
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        # Unexpected errors
        return {"success": False, "error": f"Failed to reschedule session: {str(e)}"}


@tool
def cancel_session(
    trainer_id: str,
    session_id: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cancel an existing training session.
    
    Use this tool when the trainer wants to cancel a scheduled session.
    The tool updates the session status to cancelled, records the cancellation reason if provided,
    and syncs with the trainer's connected calendar if available.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        session_id: Session identifier to cancel (e.g., "xyz789")
        reason: Optional cancellation reason (e.g., "Student requested cancellation")

    Returns:
        dict: {
            'success': bool,
            'data': {
                'session_id': str,
                'student_name': str,
                'session_datetime': str (ISO 8601 format),
                'duration_minutes': int,
                'location': str (optional),
                'status': str,
                'reason': str (optional)
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> cancel_session(
        ...     trainer_id='abc123',
        ...     session_id='xyz789',
        ...     reason='Student requested cancellation'
        ... )
        {
            'success': True,
            'data': {
                'session_id': 'xyz789',
                'student_name': 'John Doe',
                'session_datetime': '2024-01-20T14:00:00',
                'duration_minutes': 60,
                'status': 'cancelled',
                'reason': 'Student requested cancellation'
            }
        }

    Validates: Requirements 3.6
    """
    try:
        # Sanitize string inputs
        sanitized_params = InputSanitizer.sanitize_tool_parameters(
            {
                "session_id": session_id,
                "reason": reason if reason else "",
            }
        )

        session_id = sanitized_params["session_id"]
        reason = sanitized_params["reason"] if sanitized_params["reason"] else None

        # Validate required fields
        if not session_id:
            return {"success": False, "error": "Session ID is required"}

        # Retrieve existing session
        session_data = dynamodb_client.get_session(trainer_id, session_id)
        if not session_data:
            return {
                "success": False,
                "error": f"Session not found: {session_id}",
            }

        # Verify session belongs to trainer
        if session_data.get("trainer_id") != trainer_id:
            return {
                "success": False,
                "error": f"Session {session_id} does not belong to trainer {trainer_id}",
            }

        # Check if session is already cancelled
        if session_data.get("status") == "cancelled":
            return {
                "success": False,
                "error": "Session is already cancelled",
            }

        # Update session status to cancelled
        session_data["status"] = "cancelled"
        session_data["updated_at"] = datetime.utcnow().isoformat()

        # Add cancellation reason if provided
        if reason:
            session_data["cancellation_reason"] = reason

        # Save updated session to DynamoDB
        dynamodb_client.put_session(session_data)

        # Sync with calendar if event exists (within 30 seconds requirement)
        # This implements graceful degradation - failures are logged but don't block session cancellation
        calendar_synced = False
        if session_data.get("calendar_event_id") and session_data.get("calendar_provider"):
            calendar_synced = calendar_sync_service.delete_event(
                trainer_id=trainer_id,
                session_id=session_id,
                calendar_event_id=session_data["calendar_event_id"],
                calendar_provider=session_data["calendar_provider"],
            )
            
            if calendar_synced:
                logger.info(
                    "Session cancelled with calendar sync",
                    trainer_id=trainer_id,
                    session_id=session_id,
                    calendar_provider=session_data["calendar_provider"],
                )
            else:
                logger.warning(
                    "Session cancelled but calendar sync failed",
                    trainer_id=trainer_id,
                    session_id=session_id,
                )
        else:
            logger.info(
                "Session cancelled without calendar sync (no calendar connected)",
                trainer_id=trainer_id,
                session_id=session_id,
            )

        # Prepare response data
        response_data = {
            "session_id": session_data["session_id"],
            "student_name": session_data["student_name"],
            "session_datetime": session_data["session_datetime"],
            "duration_minutes": session_data["duration_minutes"],
            "status": session_data["status"],
        }

        if session_data.get("location"):
            response_data["location"] = session_data["location"]

        if reason:
            response_data["reason"] = reason

        # Include calendar sync status
        if session_data.get("calendar_event_id"):
            response_data["calendar_synced"] = calendar_synced

        return {"success": True, "data": response_data}

    except ValueError as e:
        # Validation errors
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        # Unexpected errors
        return {"success": False, "error": f"Failed to cancel session: {str(e)}"}



@tool
def view_calendar(
    trainer_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    filter: Optional[str] = None,
    student_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    View training sessions in the trainer's calendar within a date range.
    
    Use this tool when the trainer wants to see their scheduled sessions.
    The tool can show sessions for today, this week, this month, or a custom date range.
    Sessions are returned in chronological order (earliest first).
    Optionally filter by student name to see only sessions involving a specific student,
    including group sessions where that student is enrolled.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        start_date: Start date in ISO format YYYY-MM-DD (optional if filter provided, e.g., "2024-01-20")
        end_date: End date in ISO format YYYY-MM-DD (optional if filter provided, e.g., "2024-01-25")
        filter: Convenient date range filter: "day" (today), "week" (next 7 days), or "month" (next 30 days) (optional)
        student_name: Filter sessions by student name (optional). For individual sessions, matches the session's student_name. For group sessions, matches any enrolled student's name. Case-insensitive.

    Returns:
        dict: {
            'success': bool,
            'data': {
                'sessions': [
                    {
                        'session_id': str,
                        'student_name': str,
                        'session_datetime': str (ISO 8601 format),
                        'duration_minutes': int,
                        'location': str (optional),
                        'status': str,
                        'student_confirmed': bool (optional),
                        'student_confirmed_at': str (optional)
                    },
                    ...
                ],
                'start_date': str,
                'end_date': str,
                'total_count': int
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> view_calendar(trainer_id='abc123', filter='week')
        {
            'success': True,
            'data': {
                'sessions': [
                    {
                        'session_id': 'xyz789',
                        'student_name': 'John Doe',
                        'session_datetime': '2024-01-20T14:00:00',
                        'duration_minutes': 60,
                        'location': 'Main Gym',
                        'status': 'scheduled'
                    }
                ],
                'start_date': '2024-01-15',
                'end_date': '2024-01-22',
                'total_count': 1
            }
        }

        >>> view_calendar(
        ...     trainer_id='abc123',
        ...     start_date='2024-01-20',
        ...     end_date='2024-01-25'
        ... )
        {
            'success': True,
            'data': {
                'sessions': [...],
                'start_date': '2024-01-20',
                'end_date': '2024-01-25',
                'total_count': 3
            }
        }

    Validates: Requirements 3.7, 7.5
    """
    try:
        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Calculate date range
        now = datetime.utcnow()

        if filter:
            # Sanitize filter input
            sanitized_filter = InputSanitizer.sanitize_tool_parameters(
                {"filter": filter}
            )["filter"]

            filter_lower = sanitized_filter.lower()

            if filter_lower == "day":
                # Today only
                start_datetime = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_datetime = start_datetime + timedelta(days=1)
            elif filter_lower == "week":
                # Next 7 days from now
                start_datetime = now
                end_datetime = now + timedelta(days=7)
            elif filter_lower == "month":
                # Next 30 days from now
                start_datetime = now
                end_datetime = now + timedelta(days=30)
            else:
                return {
                    "success": False,
                    "error": f"Invalid filter value. Use 'day', 'week', or 'month'. Got: {filter}",
                }
        elif start_date and end_date:
            # Use explicit date range
            sanitized_params = InputSanitizer.sanitize_tool_parameters(
                {
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

            start_date = sanitized_params["start_date"]
            end_date = sanitized_params["end_date"]

            try:
                # Parse dates - assume start of day for start_date and end of day for end_date
                start_datetime = datetime.fromisoformat(f"{start_date}T00:00:00")
                end_datetime = datetime.fromisoformat(f"{end_date}T23:59:59")
            except ValueError as e:
                return {
                    "success": False,
                    "error": f"Invalid date format. Use YYYY-MM-DD. Error: {str(e)}",
                }

            # Validate date range
            if start_datetime > end_datetime:
                return {
                    "success": False,
                    "error": "Start date must be before or equal to end date",
                }
        else:
            # Default to next 7 days if no filter or dates provided
            start_datetime = now
            end_datetime = now + timedelta(days=7)

        # Query sessions using session-date-index GSI
        sessions = dynamodb_client.get_sessions_by_date_range(
            trainer_id=trainer_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )

        # Sort sessions by datetime (chronological order - earliest first)
        sessions.sort(key=lambda s: s.get("session_datetime", ""))

        # Filter by student name if provided
        if student_name:
            sanitized_student_name = InputSanitizer.sanitize_tool_parameters(
                {"student_name": student_name}
            )["student_name"]
            student_name_lower = sanitized_student_name.lower()

            filtered_sessions = []
            for session in sessions:
                # Individual sessions: match the session's student_name
                if session.get("student_name", "").lower() == student_name_lower:
                    filtered_sessions.append(session)
                # Group sessions: match any enrolled student's name
                elif session.get("session_type") == "group":
                    enrolled = session.get("enrolled_students", [])
                    if any(
                        s.get("student_name", "").lower() == student_name_lower
                        for s in enrolled
                    ):
                        filtered_sessions.append(session)
            sessions = filtered_sessions

        # Format sessions for response
        formatted_sessions = []
        for session in sessions:
            session_data = {
                "session_id": session["session_id"],
                "student_name": session.get("student_name", ""),
                "session_datetime": session["session_datetime"],
                "duration_minutes": session["duration_minutes"],
                "status": session["status"],
            }

            # Add optional fields if present
            if session.get("location"):
                session_data["location"] = session["location"]

            if session.get("student_confirmed") is not None:
                session_data["student_confirmed"] = session["student_confirmed"]

            if session.get("student_confirmed_at"):
                session_data["student_confirmed_at"] = session["student_confirmed_at"]

            # Include group session metadata
            if session.get("session_type") == "group":
                session_data["session_type"] = "group"
                session_data["enrolled_student_count"] = len(session.get("enrolled_students", []))
                session_data["max_participants"] = session.get("max_participants")

            formatted_sessions.append(session_data)

        # Prepare response
        response_data = {
            "sessions": formatted_sessions,
            "start_date": start_datetime.strftime("%Y-%m-%d"),
            "end_date": end_datetime.strftime("%Y-%m-%d"),
            "total_count": len(formatted_sessions),
        }

        return {"success": True, "data": response_data}

    except ValueError as e:
        # Validation errors
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        # Unexpected errors
        return {"success": False, "error": f"Failed to view calendar: {str(e)}"}



@tool
def schedule_recurring_session(
    trainer_id: str,
    student_name: str,
    day_of_week: str,
    time: str,
    duration_minutes: int,
    number_of_weeks: int = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Schedule recurring training sessions on the same day(s) and time each week.
    
    Use this tool when the trainer wants to schedule multiple sessions that repeat weekly
    on the same day(s) and time. Supports multiple days of the week separated by commas
    (e.g., "terça-feira, quinta-feira"). If number_of_weeks is not provided, defaults to
    12 weeks (3 months).

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        student_name: Student's name (e.g., "Juliana Nano")
        day_of_week: Day(s) of the week in Portuguese, comma-separated for multiple days (e.g., "terça-feira", "terça-feira, quinta-feira")
        time: Session time in HH:MM format (e.g., "18:00")
        duration_minutes: Session duration in minutes, between 15 and 480 (e.g., 60)
        number_of_weeks: Number of weeks to schedule. Optional - defaults to 12 (3 months). Max 52.
        location: Session location (optional, e.g., "Bluefit")

    Returns:
        dict: {
            'success': bool,
            'data': {
                'sessions_created': int,
                'sessions': [...],
                'conflicts': [...] (only if conflicts detected)
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> schedule_recurring_session(
        ...     trainer_id='abc123',
        ...     student_name='Juliana Nano',
        ...     day_of_week='terça-feira, quinta-feira',
        ...     time='17:00',
        ...     duration_minutes=60,
        ... )
    """
    try:
        # Sanitize string inputs
        sanitized_params = InputSanitizer.sanitize_tool_parameters(
            {
                "student_name": student_name,
                "day_of_week": day_of_week,
                "time": time,
                "location": location if location else "",
            }
        )

        student_name = sanitized_params["student_name"]
        day_of_week = sanitized_params["day_of_week"].lower()
        time = sanitized_params["time"]
        location = sanitized_params["location"] if sanitized_params["location"] else None

        # Validate required fields
        if not student_name:
            return {"success": False, "error": "Student name is required"}

        if not day_of_week:
            return {"success": False, "error": "Day of week is required"}

        if not time:
            return {"success": False, "error": "Session time is required"}

        if not duration_minutes:
            return {"success": False, "error": "Session duration is required"}

        # Default number_of_weeks to 12 (3 months) if not provided
        if not number_of_weeks:
            number_of_weeks = 12

        # Validate duration range
        if duration_minutes < 15 or duration_minutes > 480:
            return {
                "success": False,
                "error": f"Duration must be between 15 and 480 minutes. Got: {duration_minutes}",
            }

        # Validate number of weeks
        if number_of_weeks < 1 or number_of_weeks > 52:
            return {
                "success": False,
                "error": f"Number of weeks must be between 1 and 52. Got: {number_of_weeks}",
            }
        
        # Limit to 12 weeks (3 months) to avoid timeouts
        if number_of_weeks > 12:
            logger.warning(
                "Limiting recurring sessions to 12 weeks to avoid timeout",
                trainer_id=trainer_id,
                requested_weeks=number_of_weeks
            )
            number_of_weeks = 12

        # Map Portuguese day names to weekday numbers (0=Monday, 6=Sunday)
        day_mapping = {
            "segunda-feira": 0,
            "segunda": 0,
            "terça-feira": 1,
            "terça": 1,
            "terca-feira": 1,
            "terca": 1,
            "quarta-feira": 2,
            "quarta": 2,
            "quinta-feira": 3,
            "quinta": 3,
            "sexta-feira": 4,
            "sexta": 4,
            "sábado": 5,
            "sabado": 5,
            "domingo": 6,
        }

        # Parse multiple days of week (comma-separated)
        day_parts = [d.strip().lower() for d in day_of_week.split(",") if d.strip()]
        target_weekdays = []
        for day_part in day_parts:
            weekday_num = day_mapping.get(day_part)
            if weekday_num is None:
                return {
                    "success": False,
                    "error": f"Invalid day of week: '{day_part}'. Use: segunda-feira, terça-feira, quarta-feira, quinta-feira, sexta-feira, sábado, domingo.",
                }
            if weekday_num not in target_weekdays:
                target_weekdays.append(weekday_num)
        
        if not target_weekdays:
            return {
                "success": False,
                "error": f"No valid days of week provided. Got: {day_of_week}",
            }

        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Find student by name
        trainer_students = dynamodb_client.get_trainer_students(trainer_id)

        matching_student = None
        for link in trainer_students:
            if link.get("status") != "active":
                continue

            student_id = link.get("student_id")
            if not student_id:
                continue

            student_data = dynamodb_client.get_student(student_id)
            if student_data and student_data["name"].lower() == student_name.lower():
                matching_student = student_data
                break

        if not matching_student:
            return {
                "success": False,
                "error": f"Student '{student_name}' not found or not linked to this trainer. Please register the student first.",
            }

        student_id = matching_student["student_id"]

        # Calculate the first occurrence of each target weekday
        now = datetime.utcnow()
        current_weekday = now.weekday()

        # Parse time
        try:
            hour, minute = map(int, time.split(':'))
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("Invalid time")
        except (ValueError, AttributeError):
            return {
                "success": False,
                "error": f"Invalid time format. Use HH:MM (e.g., 18:00). Got: {time}",
            }

        # Build list of all session dates across all target weekdays
        all_session_dates = []
        for target_weekday in sorted(target_weekdays):
            days_ahead = target_weekday - current_weekday
            if days_ahead <= 0:
                days_ahead += 7
            first_date = now + timedelta(days=days_ahead)
            for week in range(number_of_weeks):
                session_date = first_date + timedelta(weeks=week)
                all_session_dates.append(session_date)

        # Sort all dates chronologically
        all_session_dates.sort()

        # Query all potential conflicts at once
        first_dt = all_session_dates[0].replace(hour=hour, minute=minute, second=0, microsecond=0) - timedelta(minutes=30)
        last_dt = all_session_dates[-1].replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(minutes=duration_minutes + 30)

        existing_sessions = dynamodb_client.get_sessions_by_date_range(
            trainer_id=trainer_id,
            start_datetime=first_dt,
            end_datetime=last_dt,
            status_filter=['scheduled', 'confirmed']
        )
        
        # Build a set of existing session time windows for fast lookup
        existing_windows = []
        for session in existing_sessions:
            session_start = datetime.fromisoformat(session['session_datetime'])
            session_end = session_start + timedelta(minutes=session['duration_minutes'])
            existing_windows.append({
                'start': session_start,
                'end': session_end,
                'session': session
            })

        created_sessions = []
        conflicts_found = []

        for session_date in all_session_dates:
            session_datetime = session_date.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0
            )
            
            session_end_time = session_datetime + timedelta(minutes=duration_minutes)

            # Check for conflicts using pre-fetched data
            conflict_found = None
            for window in existing_windows:
                # Check for overlap: (start1 < end2) AND (end1 > start2)
                if session_datetime < window['end'] and session_end_time > window['start']:
                    conflict_found = window['session']
                    break
            
            if conflict_found:
                # Record conflict but continue creating other sessions
                conflicts_found.append({
                    "date": session_datetime.strftime("%Y-%m-%d"),
                    "conflicting_session": {
                        "session_id": conflict_found["session_id"],
                        "student_name": conflict_found["student_name"],
                        "session_datetime": conflict_found["session_datetime"],
                    }
                })
                continue  # Skip this week due to conflict

            # Create session entity
            session = Session(
                trainer_id=trainer_id,
                student_id=student_id,
                student_name=matching_student["name"],
                session_datetime=session_datetime,
                duration_minutes=duration_minutes,
                location=location,
                status="scheduled",
            )

            # Save session to DynamoDB
            dynamodb_client.put_session(session.to_dynamodb())

            # Add to created sessions list
            session_info = {
                "session_id": session.session_id,
                "student_name": session.student_name,
                "session_datetime": session.session_datetime.isoformat(),
                "duration_minutes": session.duration_minutes,
                "status": session.status,
            }

            if location:
                session_info["location"] = location

            created_sessions.append(session_info)

        # Sync with calendar as a single recurring event
        if created_sessions:
            # Map weekday numbers to RRULE day codes
            rrule_day_map = {0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU"}
            weekday_codes = [rrule_day_map[wd] for wd in sorted(target_weekdays)]

            calendar_result = calendar_sync_service.create_recurring_event(
                trainer_id=trainer_id,
                student_name=matching_student["name"],
                session_datetime=datetime.fromisoformat(created_sessions[0]["session_datetime"]),
                duration_minutes=duration_minutes,
                weekday_codes=weekday_codes,
                count=len(created_sessions),
                location=location,
                student_email=matching_student.get("email"),
            )

            if calendar_result:
                # Store the recurring event ID on all sessions
                for session_info in created_sessions:
                    try:
                        session_data = dynamodb_client.get_session(trainer_id, session_info["session_id"])
                        if session_data:
                            session_data["calendar_event_id"] = calendar_result["calendar_event_id"]
                            session_data["calendar_provider"] = calendar_result["calendar_provider"]
                            session_data["updated_at"] = datetime.utcnow().isoformat()
                            dynamodb_client.put_session(session_data)
                        session_info["calendar_event_id"] = calendar_result["calendar_event_id"]
                        session_info["calendar_provider"] = calendar_result["calendar_provider"]
                    except Exception as e:
                        logger.warning(
                            "Failed to update session with calendar info",
                            session_id=session_info["session_id"],
                            error=str(e),
                        )

                logger.info(
                    "Recurring calendar event created for all sessions",
                    trainer_id=trainer_id,
                    calendar_event_id=calendar_result["calendar_event_id"],
                    sessions_count=len(created_sessions),
                )

        # Prepare response
        if not created_sessions:
            return {
                "success": False,
                "error": f"Could not create any sessions. All {number_of_weeks} weeks had conflicts.",
                "data": {
                    "sessions_created": 0,
                    "conflicts": conflicts_found
                }
            }

        response_data = {
            "sessions_created": len(created_sessions),
            "sessions": created_sessions,
        }

        if conflicts_found:
            response_data["conflicts"] = conflicts_found
            response_data["message"] = f"Created {len(created_sessions)} sessions. {len(conflicts_found)} weeks skipped due to conflicts."

        logger.info(
            "Recurring sessions created",
            trainer_id=trainer_id,
            student_name=student_name,
            sessions_created=len(created_sessions),
            conflicts=len(conflicts_found),
        )

        return {"success": True, "data": response_data}

    except ValueError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        logger.error(
            "Failed to schedule recurring sessions",
            trainer_id=trainer_id,
            error=str(e),
            exc_info=True
        )
        return {"success": False, "error": f"Failed to schedule recurring sessions: {str(e)}"}


@tool
def cancel_student_sessions(
    trainer_id: str,
    student_name: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cancel all scheduled sessions with a specific student.

    Use this tool when the trainer wants to cancel all upcoming sessions
    with a student at once (e.g., student is leaving, schedule change).
    Cancels all sessions with status 'scheduled' and syncs with calendar.

    Args:
        trainer_id: Trainer identifier (injected automatically)
        student_name: Student's name (e.g., "Juliana Nano")
        reason: Optional cancellation reason

    Returns:
        dict: {
            'success': bool,
            'data': {
                'cancelled_count': int,
                'sessions': [...],
                'calendar_synced': bool
            },
            'error': str (optional)
        }

    Examples:
        When trainer says: "Cancelar todas as sessões com Juliana Nano"
        When trainer says: "Cancelar sessões da Maria"
    """
    try:
        # Sanitize inputs
        student_name = InputSanitizer.sanitize_string(student_name)
        if reason:
            reason = InputSanitizer.sanitize_string(reason)

        if not student_name:
            return {"success": False, "error": "Student name is required"}

        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Find student by name
        trainer_students = dynamodb_client.get_trainer_students(trainer_id)
        matching_student = None
        for link in trainer_students:
            if link.get("status") != "active":
                continue
            student_id = link.get("student_id")
            if not student_id:
                continue
            student_data = dynamodb_client.get_student(student_id)
            if student_data and student_data["name"].lower() == student_name.lower():
                matching_student = student_data
                break

        if not matching_student:
            return {
                "success": False,
                "error": f"Student '{student_name}' not found or not linked to this trainer.",
            }

        student_id = matching_student["student_id"]

        # Get all scheduled sessions for this student
        now = datetime.utcnow()
        sessions = dynamodb_client.get_sessions_by_date_range(
            trainer_id=trainer_id,
            start_datetime=now,
            end_datetime=now + timedelta(days=365),
            status_filter=["scheduled"],
        )

        # Filter to only this student's sessions
        student_sessions = [s for s in sessions if s.get("student_id") == student_id]

        if not student_sessions:
            return {
                "success": False,
                "error": f"No scheduled sessions found with {student_name}.",
            }

        # Cancel each session
        cancelled = []
        calendar_event_ids = set()

        for session in student_sessions:
            session_id = session["session_id"]
            session["status"] = "cancelled"
            session["cancelled_at"] = now.isoformat()
            session["updated_at"] = now.isoformat()
            if reason:
                session["cancellation_reason"] = reason

            dynamodb_client.put_session(session)

            cancelled.append({
                "session_id": session_id,
                "session_datetime": session["session_datetime"],
                "duration_minutes": session["duration_minutes"],
            })

            # Collect unique calendar event IDs
            if session.get("calendar_event_id"):
                calendar_event_ids.add(
                    (session["calendar_event_id"], session.get("calendar_provider"))
                )

        # Delete calendar events (recurring event = 1 deletion for all)
        calendar_synced = False
        for event_id, provider in calendar_event_ids:
            try:
                result = calendar_sync_service.delete_event(
                    trainer_id=trainer_id,
                    session_id=cancelled[0]["session_id"],  # Any session ID for logging
                    calendar_event_id=event_id,
                    calendar_provider=provider,
                )
                if result:
                    calendar_synced = True
            except Exception as e:
                logger.warning(
                    "Failed to delete calendar event",
                    event_id=event_id,
                    error=str(e),
                )

        logger.info(
            "Cancelled all sessions with student",
            trainer_id=trainer_id,
            student_name=student_name,
            cancelled_count=len(cancelled),
            calendar_synced=calendar_synced,
        )

        return {
            "success": True,
            "data": {
                "cancelled_count": len(cancelled),
                "sessions": cancelled,
                "calendar_synced": calendar_synced,
            },
        }

    except Exception as e:
        logger.error(
            "Failed to cancel student sessions",
            trainer_id=trainer_id,
            student_name=student_name,
            error=str(e),
        )
        return {"success": False, "error": f"Failed to cancel sessions: {str(e)}"}
