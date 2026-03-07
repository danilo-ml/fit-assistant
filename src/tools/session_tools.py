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

from src.models.entities import Session
from src.models.dynamodb_client import DynamoDBClient
from src.services.session_conflict import SessionConflictDetector
from src.services.calendar_sync import CalendarSyncService
from src.utils.validation import InputSanitizer
from src.utils.logging import get_logger
from src.config import settings

# Initialize DynamoDB client, conflict detector, and calendar sync service
dynamodb_client = DynamoDBClient(
    table_name=settings.dynamodb_table, endpoint_url=settings.aws_endpoint_url
)
conflict_detector = SessionConflictDetector(dynamodb_client)
calendar_sync_service = CalendarSyncService(
    dynamodb_client=dynamodb_client, aws_endpoint_url=settings.aws_endpoint_url
)
logger = get_logger(__name__)


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

    This tool:
    1. Validates that the trainer exists
    2. Finds the student by name and verifies trainer-student link
    3. Parses and validates the date and time
    4. Checks for scheduling conflicts using SessionConflictDetector
    5. Creates a Session entity in DynamoDB with status="scheduled"
    6. Returns session_id and any conflicts detected

    Args:
        trainer_id: Trainer identifier (required)
        student_name: Student name (required)
        date: Session date in ISO format YYYY-MM-DD (required)
        time: Session time in HH:MM format (required)
        duration_minutes: Session duration in minutes, 15-480 (required)
        location: Session location (optional)

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


def reschedule_session(
    trainer_id: str,
    session_id: str,
    new_date: str,
    new_time: str,
) -> Dict[str, Any]:
    """
    Reschedule an existing training session to a new date and time.

    This tool:
    1. Validates that the session exists and belongs to the trainer
    2. Parses and validates the new date and time
    3. Checks for scheduling conflicts at the new time (excluding current session)
    4. Updates the session_datetime in DynamoDB
    5. Triggers calendar sync (placeholder for now)
    6. Returns updated session info and any conflicts detected

    Args:
        trainer_id: Trainer identifier (required)
        session_id: Session identifier to reschedule (required)
        new_date: New session date in ISO format YYYY-MM-DD (required)
        new_time: New session time in HH:MM format (required)

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


def cancel_session(
    trainer_id: str,
    session_id: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cancel an existing training session.

    This tool:
    1. Validates that the session exists and belongs to the trainer
    2. Updates the session status to "cancelled"
    3. Updates the updated_at timestamp
    4. Triggers calendar sync (placeholder for now)
    5. Returns success status and updated session info

    Args:
        trainer_id: Trainer identifier (required)
        session_id: Session identifier to cancel (required)
        reason: Optional cancellation reason

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



def view_calendar(
    trainer_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    View training sessions in the trainer's calendar within a date range.

    This tool:
    1. Validates the trainer exists
    2. Calculates date range based on filter (day/week/month) or explicit dates
    3. Queries sessions using session-date-index GSI
    4. Returns sessions in chronological order (earliest first)

    Args:
        trainer_id: Trainer identifier (required)
        start_date: Start date in ISO format YYYY-MM-DD (optional if filter provided)
        end_date: End date in ISO format YYYY-MM-DD (optional if filter provided)
        filter: Convenient date range filter: "day", "week", or "month" (optional)

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

        # Format sessions for response
        formatted_sessions = []
        for session in sessions:
            session_data = {
                "session_id": session["session_id"],
                "student_name": session["student_name"],
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

