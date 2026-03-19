"""
AI agent tool functions for group session management.

This module provides tool functions that the AI agent can call to:
- Configure group size limits for trainers
- Schedule group training sessions
- Enroll and remove students from group sessions
- Cancel and reschedule group sessions

All functions follow the tool function pattern:
- Accept trainer_id as first parameter
- Return dict with 'success', 'data', and optional 'error' keys
- Validate inputs before processing
- Handle errors gracefully
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from strands import tool

from models.entities import TrainerConfig, GroupSession
from models.dynamodb_client import DynamoDBClient
from services.session_conflict import SessionConflictDetector
from services.calendar_sync import CalendarSyncService
from utils.validation import InputSanitizer
from utils.logging import get_logger
from config import settings

# Initialize DynamoDB client
dynamodb_client = DynamoDBClient(
    table_name=settings.dynamodb_table, endpoint_url=settings.aws_endpoint_url
)
conflict_detector = SessionConflictDetector(dynamodb_client)
calendar_sync_service = CalendarSyncService(
    dynamodb_client=dynamodb_client, aws_endpoint_url=settings.aws_endpoint_url
)
logger = get_logger(__name__)


@tool
def configure_group_size_limit(
    trainer_id: str,
    limit: int,
) -> Dict[str, Any]:
    """
    Configure the maximum number of students allowed in a group session.

    Use this tool when the trainer wants to set or update their group size limit.
    The limit controls the maximum number of students that can be enrolled in any
    single group training session.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        limit: Maximum number of students per group session, between 2 and 50

    Returns:
        dict: {
            'success': bool,
            'data': {'group_size_limit': int},
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> configure_group_size_limit(trainer_id='abc123', limit=15)
        {'success': True, 'data': {'group_size_limit': 15}}

    Validates: Requirements 1.2, 1.3, 1.4
    """
    try:
        # Validate limit range
        if limit < 2 or limit > 50:
            return {
                "success": False,
                "error": "Group size limit must be between 2 and 50",
            }

        # Read existing TrainerConfig or create a new one
        config_data = dynamodb_client.get_trainer_config(trainer_id)

        if config_data:
            config = TrainerConfig.from_dynamodb(config_data)
            config.group_size_limit = limit
            config.updated_at = datetime.utcnow()
        else:
            config = TrainerConfig(
                trainer_id=trainer_id,
                group_size_limit=limit,
            )

        # Save to DynamoDB
        dynamodb_client.put_trainer_config(config.to_dynamodb())

        logger.info(
            "Group size limit configured",
            trainer_id=trainer_id,
            group_size_limit=limit,
        )

        return {"success": True, "data": {"group_size_limit": limit}}

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to configure group size limit: {str(e)}",
        }


@tool
def schedule_group_session(
    trainer_id: str,
    date: str,
    time: str,
    duration_minutes: int,
    location: Optional[str] = None,
    max_participants: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Schedule a new group training session.

    Use this tool when the trainer wants to schedule a group training session
    for multiple students. The tool validates the date/time, checks for scheduling
    conflicts, creates the group session record, and syncs with the trainer's
    connected calendar if available.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        date: Session date in ISO format YYYY-MM-DD (e.g., "2024-01-20")
        time: Session time in HH:MM format (e.g., "14:00")
        duration_minutes: Session duration in minutes, between 15 and 480 (e.g., 60)
        location: Session location (optional, e.g., "Main Gym")
        max_participants: Maximum number of students (optional, defaults to trainer's group_size_limit)

    Returns:
        dict: {
            'success': bool,
            'data': {
                'session_id': str,
                'session_type': 'group',
                'session_datetime': str (ISO 8601 format),
                'duration_minutes': int,
                'location': str (optional),
                'max_participants': int,
                'enrolled_students': [],
                'status': str,
                'conflicts': [...] (only if conflicts detected)
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> schedule_group_session(
        ...     trainer_id='abc123',
        ...     date='2024-01-20',
        ...     time='14:00',
        ...     duration_minutes=60,
        ...     location='Main Gym'
        ... )
        {
            'success': True,
            'data': {
                'session_id': 'xyz789',
                'session_type': 'group',
                'session_datetime': '2024-01-20T14:00:00',
                'duration_minutes': 60,
                'location': 'Main Gym',
                'max_participants': 10,
                'enrolled_students': [],
                'status': 'scheduled'
            }
        }

    Validates: Requirements 2.1, 2.2, 2.4, 2.5
    """
    try:
        # Sanitize string inputs
        sanitized_params = InputSanitizer.sanitize_tool_parameters(
            {
                "date": date,
                "time": time,
                "location": location if location else "",
            }
        )

        date = sanitized_params["date"]
        time = sanitized_params["time"]
        location = sanitized_params["location"] if sanitized_params["location"] else None

        # Validate required fields
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

        # Get trainer's config for group_size_limit default
        config_data = dynamodb_client.get_trainer_config(trainer_id)
        if config_data:
            trainer_config = TrainerConfig.from_dynamodb(config_data)
        else:
            trainer_config = TrainerConfig(trainer_id=trainer_id)

        group_size_limit = trainer_config.group_size_limit

        # Determine effective max_participants
        if max_participants is not None:
            # Validate custom max_participants does not exceed trainer's group_size_limit
            if max_participants > group_size_limit:
                return {
                    "success": False,
                    "error": f"Max participants ({max_participants}) exceeds your group size limit ({group_size_limit})",
                }
            effective_max = max_participants
        else:
            # Default to trainer's group_size_limit
            effective_max = group_size_limit

        # Parse date and time into datetime object
        try:
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

        # Create GroupSession entity
        group_session = GroupSession(
            trainer_id=trainer_id,
            session_datetime=session_datetime,
            duration_minutes=duration_minutes,
            location=location,
            status="scheduled",
            max_participants=effective_max,
            enrolled_students=[],
        )

        # Save session to DynamoDB
        dynamodb_client.put_session(group_session.to_dynamodb())

        # Sync with calendar (graceful degradation)
        calendar_result = calendar_sync_service.create_event(
            trainer_id=trainer_id,
            session_id=group_session.session_id,
            student_name="Group Session",
            session_datetime=session_datetime,
            duration_minutes=duration_minutes,
            location=location,
        )

        # If calendar sync succeeded, update session with calendar event info
        if calendar_result:
            session_data = dynamodb_client.get_session(trainer_id, group_session.session_id)
            if session_data:
                session_data["calendar_event_id"] = calendar_result["calendar_event_id"]
                session_data["calendar_provider"] = calendar_result["calendar_provider"]
                session_data["updated_at"] = datetime.utcnow().isoformat()
                dynamodb_client.put_session(session_data)

                logger.info(
                    "Group session created with calendar sync",
                    trainer_id=trainer_id,
                    session_id=group_session.session_id,
                    calendar_provider=calendar_result["calendar_provider"],
                )
        else:
            logger.info(
                "Group session created without calendar sync",
                trainer_id=trainer_id,
                session_id=group_session.session_id,
            )

        # Prepare response data
        response_data = {
            "session_id": group_session.session_id,
            "session_type": "group",
            "session_datetime": group_session.session_datetime.isoformat(),
            "duration_minutes": group_session.duration_minutes,
            "max_participants": group_session.max_participants,
            "enrolled_students": group_session.enrolled_students,
            "status": group_session.status,
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
                    "student_name": c.get("student_name", "Group Session"),
                    "session_datetime": c["session_datetime"],
                    "duration_minutes": c["duration_minutes"],
                }
                for c in conflicts
            ]

        return {"success": True, "data": response_data}

    except ValueError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        return {"success": False, "error": f"Failed to schedule group session: {str(e)}"}


@tool
def enroll_student(
    trainer_id: str,
    session_id: str,
    student_names: List[str],
) -> Dict[str, Any]:
    """
    Enroll one or more students in a group training session.

    Use this tool when the trainer wants to add students to an existing group session.
    The tool validates each student individually: checks they are linked to the trainer,
    not already enrolled, and the session is not full. Returns per-student results.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        session_id: Group session identifier to enroll students in
        student_names: List of student names to enroll (e.g., ["João Silva", "Maria Santos"])

    Returns:
        dict: {
            'success': bool,
            'data': {
                'session_id': str,
                'results': [
                    {'student_name': str, 'success': bool, 'error': str (optional)},
                    ...
                ],
                'enrolled_count': int,
                'max_participants': int
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> enroll_student(
        ...     trainer_id='abc123',
        ...     session_id='xyz789',
        ...     student_names=['João Silva', 'Maria Santos']
        ... )
        {
            'success': True,
            'data': {
                'session_id': 'xyz789',
                'results': [
                    {'student_name': 'João Silva', 'success': True},
                    {'student_name': 'Maria Santos', 'success': True}
                ],
                'enrolled_count': 2,
                'max_participants': 10
            }
        }

    Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
    """
    try:
        # Validate required fields
        if not session_id:
            return {"success": False, "error": "Session ID is required"}

        if not student_names:
            return {"success": False, "error": "At least one student name is required"}

        # Retrieve the session
        session_data = dynamodb_client.get_session(trainer_id, session_id)
        if not session_data:
            return {
                "success": False,
                "error": f"Session not found: {session_id}",
            }

        # Verify it's a group session
        if session_data.get("session_type") != "group":
            return {
                "success": False,
                "error": "This is not a group session. Use schedule_session for individual sessions.",
            }

        # Get current enrolled students and max_participants
        enrolled_students = session_data.get("enrolled_students", [])
        max_participants = session_data.get("max_participants", 10)

        # Get all trainer's students for name lookup
        trainer_students = dynamodb_client.get_trainer_students(trainer_id)

        # Build a lookup of active students by lowercase name
        student_lookup = {}
        for link in trainer_students:
            if link.get("status") != "active":
                continue
            student_id = link.get("student_id")
            if not student_id:
                continue
            student_data = dynamodb_client.get_student(student_id)
            if student_data:
                student_lookup[student_data["name"].lower()] = student_data

        # Process each student name
        results = []
        for name in student_names:
            sanitized_name = InputSanitizer.sanitize_tool_parameters({"name": name})["name"]

            # Look up student by name
            student_data = student_lookup.get(sanitized_name.lower())
            if not student_data:
                results.append({
                    "student_name": sanitized_name,
                    "success": False,
                    "error": f"Student '{sanitized_name}' not found or not linked to this trainer",
                })
                continue

            student_id = student_data["student_id"]
            student_name_actual = student_data["name"]

            # Check if already enrolled
            already_enrolled = any(
                e.get("student_id") == student_id for e in enrolled_students
            )
            if already_enrolled:
                results.append({
                    "student_name": student_name_actual,
                    "success": False,
                    "error": f"Student '{student_name_actual}' is already enrolled in this session",
                })
                continue

            # Check if session is full
            if len(enrolled_students) >= max_participants:
                results.append({
                    "student_name": student_name_actual,
                    "success": False,
                    "error": f"Session is full ({len(enrolled_students)}/{max_participants} enrolled)",
                })
                continue

            # All checks passed — enroll the student
            enrolled_students.append({
                "student_id": student_id,
                "student_name": student_name_actual,
            })
            results.append({
                "student_name": student_name_actual,
                "success": True,
            })

        # Update session in DynamoDB if any students were enrolled
        any_enrolled = any(r["success"] for r in results)
        if any_enrolled:
            session_data["enrolled_students"] = enrolled_students
            session_data["updated_at"] = datetime.utcnow().isoformat()
            dynamodb_client.put_session(session_data)

            logger.info(
                "Students enrolled in group session",
                trainer_id=trainer_id,
                session_id=session_id,
                enrolled_count=len(enrolled_students),
            )

            # Update calendar event with all enrolled student emails
            if session_data.get("calendar_event_id") and session_data.get("calendar_provider"):
                all_emails = []
                for enrolled in enrolled_students:
                    sid = enrolled.get("student_id")
                    if sid:
                        sdata = dynamodb_client.get_student(sid)
                        if sdata and sdata.get("email"):
                            all_emails.append(sdata["email"])

                if all_emails:
                    session_dt = datetime.fromisoformat(session_data["session_datetime"])
                    calendar_sync_service.update_event(
                        trainer_id=trainer_id,
                        session_id=session_id,
                        calendar_event_id=session_data["calendar_event_id"],
                        calendar_provider=session_data["calendar_provider"],
                        student_name="Group Session",
                        session_datetime=session_dt,
                        duration_minutes=session_data["duration_minutes"],
                        location=session_data.get("location"),
                        attendee_emails=all_emails,
                    )

        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "results": results,
                "enrolled_count": len(enrolled_students),
                "max_participants": max_participants,
            },
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to enroll students: {str(e)}",
        }


@tool
def remove_student(
    trainer_id: str,
    session_id: str,
    student_name: str,
) -> Dict[str, Any]:
    """
    Remove a student from a group training session.

    Use this tool when the trainer wants to remove a student from an existing
    group session. The tool verifies the student is currently enrolled and
    removes them from the enrolled students list.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        session_id: Group session identifier to remove the student from
        student_name: Name of the student to remove (case-insensitive match)

    Returns:
        dict: {
            'success': bool,
            'data': {
                'session_id': str,
                'removed_student': str,
                'enrolled_count': int,
                'max_participants': int
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> remove_student(
        ...     trainer_id='abc123',
        ...     session_id='xyz789',
        ...     student_name='João Silva'
        ... )
        {
            'success': True,
            'data': {
                'session_id': 'xyz789',
                'removed_student': 'João Silva',
                'enrolled_count': 1,
                'max_participants': 10
            }
        }

    Validates: Requirements 4.1, 4.2, 4.3
    """
    try:
        # Validate required fields
        if not session_id:
            return {"success": False, "error": "Session ID is required"}

        if not student_name:
            return {"success": False, "error": "Student name is required"}

        # Sanitize input
        sanitized = InputSanitizer.sanitize_tool_parameters({"name": student_name})
        student_name = sanitized["name"]

        # Retrieve the session
        session_data = dynamodb_client.get_session(trainer_id, session_id)
        if not session_data:
            return {
                "success": False,
                "error": f"Session not found: {session_id}",
            }

        # Verify it's a group session
        if session_data.get("session_type") != "group":
            return {
                "success": False,
                "error": "This is not a group session.",
            }

        # Get current enrolled students
        enrolled_students = session_data.get("enrolled_students", [])

        # Find the student by name (case-insensitive)
        student_index = None
        matched_name = None
        for i, enrolled in enumerate(enrolled_students):
            if enrolled.get("student_name", "").lower() == student_name.lower():
                student_index = i
                matched_name = enrolled.get("student_name")
                break

        if student_index is None:
            return {
                "success": False,
                "error": f"Student '{student_name}' is not enrolled in this session",
            }

        # Remove the student
        enrolled_students.pop(student_index)

        # Update session in DynamoDB
        session_data["enrolled_students"] = enrolled_students
        session_data["updated_at"] = datetime.utcnow().isoformat()
        dynamodb_client.put_session(session_data)

        # Update calendar event to remove the student's email
        if session_data.get("calendar_event_id") and session_data.get("calendar_provider"):
            remaining_emails = []
            for enrolled in enrolled_students:
                sid = enrolled.get("student_id")
                if sid:
                    sdata = dynamodb_client.get_student(sid)
                    if sdata and sdata.get("email"):
                        remaining_emails.append(sdata["email"])

            session_dt = datetime.fromisoformat(session_data["session_datetime"])
            calendar_sync_service.update_event(
                trainer_id=trainer_id,
                session_id=session_id,
                calendar_event_id=session_data["calendar_event_id"],
                calendar_provider=session_data["calendar_provider"],
                student_name="Group Session",
                session_datetime=session_dt,
                duration_minutes=session_data["duration_minutes"],
                location=session_data.get("location"),
                attendee_emails=remaining_emails,
            )

        logger.info(
            "Student removed from group session",
            trainer_id=trainer_id,
            session_id=session_id,
            student_name=matched_name,
            enrolled_count=len(enrolled_students),
        )

        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "removed_student": matched_name,
                "enrolled_count": len(enrolled_students),
                "max_participants": session_data.get("max_participants", 10),
            },
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to remove student: {str(e)}",
        }

@tool
def cancel_group_session(
    trainer_id: str,
    session_id: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cancel an existing group training session.

    Use this tool when the trainer wants to cancel a scheduled group session.
    The tool updates the session status to cancelled, records the cancellation reason
    if provided, returns the list of enrolled student names so the trainer knows who
    was affected, and syncs with the trainer's connected calendar if available.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        session_id: Group session identifier to cancel (e.g., "xyz789")
        reason: Optional cancellation reason (e.g., "Weather conditions")

    Returns:
        dict: {
            'success': bool,
            'data': {
                'session_id': str,
                'session_datetime': str (ISO 8601 format),
                'duration_minutes': int,
                'location': str (optional),
                'status': str,
                'reason': str (optional),
                'enrolled_students': list of student name strings
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> cancel_group_session(
        ...     trainer_id='abc123',
        ...     session_id='xyz789',
        ...     reason='Weather conditions'
        ... )
        {
            'success': True,
            'data': {
                'session_id': 'xyz789',
                'session_datetime': '2024-01-20T14:00:00',
                'duration_minutes': 60,
                'status': 'cancelled',
                'reason': 'Weather conditions',
                'enrolled_students': ['João Silva', 'Maria Santos']
            }
        }

    Validates: Requirements 5.1, 5.2, 5.3, 5.4
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

        # Verify it's a group session
        if session_data.get("session_type") != "group":
            return {
                "success": False,
                "error": "This is not a group session. Use cancel_session for individual sessions.",
            }

        # Check if session is already cancelled
        if session_data.get("status") == "cancelled":
            return {
                "success": False,
                "error": "Session is already cancelled",
            }

        # Extract enrolled student names before cancellation
        enrolled_students = session_data.get("enrolled_students", [])
        enrolled_student_names = [
            s.get("student_name", "") for s in enrolled_students
        ]

        # Update session status to cancelled
        session_data["status"] = "cancelled"
        session_data["updated_at"] = datetime.utcnow().isoformat()

        # Add cancellation reason if provided
        if reason:
            session_data["cancellation_reason"] = reason

        # Save updated session to DynamoDB
        dynamodb_client.put_session(session_data)

        # Sync with calendar if event exists
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
                    "Group session cancelled with calendar sync",
                    trainer_id=trainer_id,
                    session_id=session_id,
                    calendar_provider=session_data["calendar_provider"],
                )
            else:
                logger.warning(
                    "Group session cancelled but calendar sync failed",
                    trainer_id=trainer_id,
                    session_id=session_id,
                )
        else:
            logger.info(
                "Group session cancelled without calendar sync (no calendar connected)",
                trainer_id=trainer_id,
                session_id=session_id,
            )

        # Prepare response data
        response_data = {
            "session_id": session_data["session_id"],
            "session_datetime": session_data["session_datetime"],
            "duration_minutes": session_data["duration_minutes"],
            "status": session_data["status"],
            "enrolled_students": enrolled_student_names,
        }

        if session_data.get("location"):
            response_data["location"] = session_data["location"]

        if reason:
            response_data["reason"] = reason

        # Include calendar sync status
        if session_data.get("calendar_event_id"):
            response_data["calendar_synced"] = calendar_synced

        logger.info(
            "Group session cancelled",
            trainer_id=trainer_id,
            session_id=session_id,
            enrolled_count=len(enrolled_student_names),
        )

        return {"success": True, "data": response_data}

    except ValueError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to cancel group session: {str(e)}",
        }



@tool
def reschedule_group_session(
    trainer_id: str,
    session_id: str,
    new_date: str,
    new_time: str,
) -> Dict[str, Any]:
    """
    Reschedule an existing group training session to a new date and time.

    Use this tool when the trainer wants to move an existing group session to a
    different date/time. The tool validates the new date/time, checks for scheduling
    conflicts, updates the session datetime while preserving all enrolled students,
    and syncs with the trainer's connected calendar if available.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        session_id: Group session identifier to reschedule (e.g., "xyz789")
        new_date: New session date in ISO format YYYY-MM-DD (e.g., "2024-01-21")
        new_time: New session time in HH:MM format (e.g., "15:00")

    Returns:
        dict: {
            'success': bool,
            'data': {
                'session_id': str,
                'session_type': 'group',
                'old_datetime': str (ISO 8601 format),
                'new_datetime': str (ISO 8601 format),
                'duration_minutes': int,
                'location': str (optional),
                'status': str,
                'enrolled_students': list,
                'max_participants': int,
                'conflicts': [...] (only if conflicts detected)
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> reschedule_group_session(
        ...     trainer_id='abc123',
        ...     session_id='xyz789',
        ...     new_date='2024-01-21',
        ...     new_time='15:00'
        ... )
        {
            'success': True,
            'data': {
                'session_id': 'xyz789',
                'session_type': 'group',
                'old_datetime': '2024-01-20T14:00:00',
                'new_datetime': '2024-01-21T15:00:00',
                'duration_minutes': 60,
                'enrolled_students': [
                    {'student_id': 'stu1', 'student_name': 'João Silva'}
                ],
                'max_participants': 10,
                'status': 'scheduled'
            }
        }

    Validates: Requirements 6.1, 6.2, 6.3, 6.4
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

        # Verify it's a group session
        if session_data.get("session_type") != "group":
            return {
                "success": False,
                "error": "This is not a group session. Use reschedule_session for individual sessions.",
            }

        # Check if session is cancelled
        if session_data.get("status") == "cancelled":
            return {
                "success": False,
                "error": "Cannot reschedule a cancelled session",
            }

        # Parse new date and time into datetime object
        try:
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

        # Preserve enrolled_students (do not modify)
        enrolled_students = session_data.get("enrolled_students", [])

        # Update session with new datetime
        session_data["session_datetime"] = new_session_datetime.isoformat()
        session_data["updated_at"] = datetime.utcnow().isoformat()

        # Save updated session to DynamoDB
        dynamodb_client.put_session(session_data)

        # Sync with calendar if event exists (graceful degradation)
        calendar_synced = False
        if session_data.get("calendar_event_id") and session_data.get("calendar_provider"):
            calendar_synced = calendar_sync_service.update_event(
                trainer_id=trainer_id,
                session_id=session_id,
                calendar_event_id=session_data["calendar_event_id"],
                calendar_provider=session_data["calendar_provider"],
                student_name="Group Session",
                session_datetime=new_session_datetime,
                duration_minutes=session_data["duration_minutes"],
                location=session_data.get("location"),
            )

            if calendar_synced:
                logger.info(
                    "Group session rescheduled with calendar sync",
                    trainer_id=trainer_id,
                    session_id=session_id,
                    calendar_provider=session_data["calendar_provider"],
                )
            else:
                logger.warning(
                    "Group session rescheduled but calendar sync failed",
                    trainer_id=trainer_id,
                    session_id=session_id,
                )
        else:
            logger.info(
                "Group session rescheduled without calendar sync (no calendar connected)",
                trainer_id=trainer_id,
                session_id=session_id,
            )

        # Prepare response data
        response_data = {
            "session_id": session_data["session_id"],
            "session_type": "group",
            "old_datetime": old_datetime,
            "new_datetime": new_session_datetime.isoformat(),
            "duration_minutes": session_data["duration_minutes"],
            "status": session_data["status"],
            "enrolled_students": enrolled_students,
            "max_participants": session_data.get("max_participants", 10),
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
                    "student_name": c.get("student_name", "Group Session"),
                    "session_datetime": c["session_datetime"],
                    "duration_minutes": c["duration_minutes"],
                }
                for c in conflicts
            ]

        logger.info(
            "Group session rescheduled",
            trainer_id=trainer_id,
            session_id=session_id,
            old_datetime=old_datetime,
            new_datetime=new_session_datetime.isoformat(),
            enrolled_count=len(enrolled_students),
        )

        return {"success": True, "data": response_data}

    except ValueError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to reschedule group session: {str(e)}",
        }
