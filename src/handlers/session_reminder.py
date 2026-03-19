"""
Session reminder Lambda function triggered by EventBridge.

This handler is triggered hourly by EventBridge and:
1. Queries sessions scheduled within the reminder window (1-48 hours ahead)
2. Gets trainer reminder configuration (default 24 hours)
3. Sends WhatsApp reminders to students with session details
4. For group sessions, sends individual reminders to each enrolled student
5. Excludes cancelled sessions
6. Records reminder delivery in DynamoDB

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List
import boto3

from models.dynamodb_client import DynamoDBClient
from services.twilio_client import TwilioClient
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)

# Initialize services
dynamodb_client = DynamoDBClient()
twilio_client = TwilioClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for sending session reminders.

    Triggered hourly by EventBridge. Queries sessions scheduled within
    the next 48 hours and sends reminders based on trainer configuration.

    Args:
        event: EventBridge event (scheduled rule)
        context: Lambda context object

    Returns:
        Dict with processing summary

    Example event structure:
        {
            "version": "0",
            "id": "event-id",
            "detail-type": "Scheduled Event",
            "source": "aws.events",
            "time": "2024-01-15T10:00:00Z",
            "region": "us-east-1",
            "resources": ["arn:aws:events:..."]
        }
    """
    logger.info(
        "Session reminder handler invoked",
        event_time=event.get("time"),
        function_name=context.function_name if context else "unknown",
    )

    current_time = datetime.utcnow()
    reminders_sent = 0
    reminders_failed = 0
    sessions_processed = 0

    try:
        # Get all trainers with active sessions in the reminder window
        # We'll query sessions for the next 48 hours (max reminder window)
        end_time = current_time + timedelta(hours=48)

        logger.info(
            "Querying sessions for reminder window",
            current_time=current_time.isoformat(),
            end_time=end_time.isoformat(),
        )

        # Get all trainers and check their sessions
        # Note: In production, consider maintaining a list of active trainers
        # For now, we'll query sessions and group by trainer
        sessions_to_remind = _get_sessions_needing_reminders(
            current_time, end_time
        )

        logger.info(
            "Found sessions needing reminders",
            session_count=len(sessions_to_remind),
        )

        # Process each session
        for session in sessions_to_remind:
            sessions_processed += 1

            try:
                # Send reminder(s) - group sessions return counts for multiple students
                result = _send_session_reminder(session, current_time)
                sent = result.get('sent', 1)
                failed = result.get('failed', 0)
                reminders_sent += sent
                reminders_failed += failed

                logger.info(
                    "Session reminder(s) sent successfully",
                    session_id=session.get("session_id"),
                    session_type=session.get("session_type", "individual"),
                    sent=sent,
                    failed=failed,
                    session_datetime=session.get("session_datetime"),
                )

            except Exception as e:
                reminders_failed += 1
                logger.error(
                    "Failed to send session reminder",
                    session_id=session.get("session_id"),
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Log summary
        logger.info(
            "Session reminder processing completed",
            sessions_processed=sessions_processed,
            reminders_sent=reminders_sent,
            reminders_failed=reminders_failed,
        )

        return {
            "statusCode": 200,
            "body": {
                "sessions_processed": sessions_processed,
                "reminders_sent": reminders_sent,
                "reminders_failed": reminders_failed,
            },
        }

    except Exception as e:
        logger.error(
            "Session reminder handler failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def _get_sessions_needing_reminders(
    current_time: datetime, end_time: datetime
) -> List[Dict[str, Any]]:
    """
    Get all sessions that need reminders sent.

    Queries sessions within the reminder window and filters based on:
    - Session status (exclude cancelled)
    - Trainer reminder configuration
    - Whether reminder was already sent

    Args:
        current_time: Current UTC time
        end_time: End of reminder window (48 hours ahead)

    Returns:
        List of sessions needing reminders
    """
    sessions_needing_reminders = []

    # Get all trainers (in production, maintain an active trainers list)
    # For now, we'll scan for sessions and group by trainer
    # This is not optimal but works for MVP
    
    # Query sessions using session-date-index
    # We need to get sessions for all trainers, so we'll need to scan
    # In production, consider a different approach or maintain trainer list
    
    # For MVP, let's get all active sessions by scanning
    # This should be optimized in production with a trainer list
    try:
        # Scan for sessions in the time window with non-cancelled status
        from boto3.dynamodb.conditions import Attr
        
        filter_expr = (
            Attr('entity_type').eq('SESSION') &
            Attr('session_datetime').between(
                current_time.isoformat(),
                end_time.isoformat()
            ) &
            Attr('status').is_in(['scheduled', 'confirmed'])
        )
        
        response = dynamodb_client.table.scan(FilterExpression=filter_expr)
        sessions = [dynamodb_client._deserialize_item(item) for item in response.get('Items', [])]
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = dynamodb_client.table.scan(
                FilterExpression=filter_expr,
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            sessions.extend([dynamodb_client._deserialize_item(item) for item in response.get('Items', [])])
        
        logger.info(
            "Found sessions in reminder window",
            session_count=len(sessions),
        )
        
        # Filter sessions based on trainer configuration
        for session in sessions:
            trainer_id = session.get('trainer_id')
            session_datetime = datetime.fromisoformat(session.get('session_datetime'))
            
            # Get trainer configuration
            trainer_config = dynamodb_client.get_trainer_config(trainer_id)
            
            # Check if session reminders are enabled
            if trainer_config and not trainer_config.get('session_reminders_enabled', True):
                continue
            
            # Get reminder hours (default 24)
            reminder_hours = (
                trainer_config.get('reminder_hours', settings.session_reminder_default_hours)
                if trainer_config
                else settings.session_reminder_default_hours
            )
            
            # Calculate time until session
            time_until_session = session_datetime - current_time
            hours_until_session = time_until_session.total_seconds() / 3600
            
            # Check if we should send reminder now
            # Send if within reminder window (with 1 hour tolerance)
            if reminder_hours - 1 <= hours_until_session <= reminder_hours + 1:
                # Check if reminder was already sent
                session_id = session.get('session_id')
                existing_reminders = dynamodb_client.get_session_reminders(session_id)
                
                session_type = session.get('session_type', 'individual')
                
                if session_type == 'group':
                    # For group sessions, check if all enrolled students already have reminders
                    enrolled_students = session.get('enrolled_students', [])
                    reminded_phones = {
                        r.get('recipient_phone')
                        for r in existing_reminders
                        if r.get('reminder_type') == 'session'
                    }
                    # Include session if any enrolled student still needs a reminder
                    has_unremindered = False
                    for enrolled in enrolled_students:
                        student = dynamodb_client.get_student(enrolled.get('student_id'))
                        if student and student.get('phone_number') not in reminded_phones:
                            has_unremindered = True
                            break
                    if has_unremindered:
                        sessions_needing_reminders.append(session)
                else:
                    # For individual sessions, check if any session reminder was sent
                    already_sent = any(
                        r.get('reminder_type') == 'session'
                        for r in existing_reminders
                    )
                    if not already_sent:
                        sessions_needing_reminders.append(session)
        
        return sessions_needing_reminders
        
    except Exception as e:
        logger.error(
            "Failed to query sessions for reminders",
            error=str(e),
            error_type=type(e).__name__,
        )
        return []


def _send_session_reminder(session: Dict[str, Any], current_time: datetime) -> Dict[str, int]:
    """
    Send session reminder(s) via WhatsApp.

    For individual sessions, sends one reminder to the student.
    For group sessions, iterates over enrolled_students and sends
    individual reminders to each student, recording a separate
    Reminder entity per student.

    Args:
        session: Session record from DynamoDB
        current_time: Current UTC time

    Returns:
        Dict with 'sent' and 'failed' counts

    Raises:
        Exception: If reminder sending fails for individual sessions
    """
    session_type = session.get('session_type', 'individual')

    if session_type == 'group':
        return _send_group_session_reminders(session, current_time)
    else:
        _send_individual_session_reminder(session, current_time)
        return {'sent': 1, 'failed': 0}


def _send_group_session_reminders(session: Dict[str, Any], current_time: datetime) -> Dict[str, int]:
    """
    Send individual WhatsApp reminders to each enrolled student in a group session.

    Args:
        session: Group session record from DynamoDB
        current_time: Current UTC time

    Returns:
        Dict with 'sent' and 'failed' counts
    """
    session_id = session.get('session_id')
    trainer_id = session.get('trainer_id')
    enrolled_students = session.get('enrolled_students', [])
    session_datetime = datetime.fromisoformat(session.get('session_datetime'))
    duration_minutes = session.get('duration_minutes', 60)
    location = session.get('location', '')

    # Get trainer info for message
    trainer = dynamodb_client.get_trainer(trainer_id)
    trainer_name = trainer.get('name', 'your trainer') if trainer else 'your trainer'

    # Get existing reminders to skip students who already received one
    existing_reminders = dynamodb_client.get_session_reminders(session_id)
    reminded_phones = {
        r.get('recipient_phone')
        for r in existing_reminders
        if r.get('reminder_type') == 'session'
    }

    # Format session datetime for display
    session_date = session_datetime.strftime('%A, %B %d, %Y')
    session_time = session_datetime.strftime('%I:%M %p')

    # Build reminder message
    message_parts = [
        "🔔 Session Reminder",
        "",
        f"You have a group training session with {trainer_name}:",
        f"📅 {session_date}",
        f"🕐 {session_time}",
        f"⏱️ Duration: {duration_minutes} minutes",
    ]

    if location:
        message_parts.append(f"📍 Location: {location}")

    message_parts.append("")
    message_parts.append("See you there! 💪")

    message_body = "\n".join(message_parts)

    sent = 0
    failed = 0

    for enrolled in enrolled_students:
        student_id = enrolled.get('student_id')

        try:
            # Look up student phone number
            student = dynamodb_client.get_student(student_id)
            if not student:
                logger.error(
                    "Enrolled student not found for group session reminder",
                    session_id=session_id,
                    student_id=student_id,
                )
                failed += 1
                continue

            student_phone = student.get('phone_number')
            if not student_phone:
                logger.error(
                    "Enrolled student phone number missing",
                    session_id=session_id,
                    student_id=student_id,
                )
                failed += 1
                continue

            # Skip if already reminded
            if student_phone in reminded_phones:
                logger.info(
                    "Skipping already-reminded student",
                    session_id=session_id,
                    student_id=student_id,
                )
                continue

            # Send WhatsApp message
            logger.info(
                "Sending group session reminder",
                session_id=session_id,
                student_id=student_id,
                student_phone=student_phone,
                session_datetime=session_datetime.isoformat(),
            )

            result = twilio_client.send_message(
                to=student_phone,
                body=message_body,
            )

            # Record reminder delivery in DynamoDB
            reminder_id = str(uuid.uuid4())
            reminder_record = {
                'PK': f'SESSION#{session_id}',
                'SK': f'REMINDER#{reminder_id}',
                'entity_type': 'REMINDER',
                'reminder_id': reminder_id,
                'session_id': session_id,
                'reminder_type': 'session',
                'recipient_phone': student_phone,
                'student_id': student_id,
                'status': 'sent',
                'sent_at': current_time.isoformat(),
                'message_sid': result.get('message_sid'),
                'created_at': current_time.isoformat(),
            }

            if result.get('status') in ['delivered', 'sent']:
                reminder_record['status'] = 'delivered'
                reminder_record['delivered_at'] = current_time.isoformat()

            dynamodb_client.put_reminder(reminder_record)

            logger.info(
                "Group session reminder recorded",
                reminder_id=reminder_id,
                session_id=session_id,
                student_id=student_id,
                message_sid=result.get('message_sid'),
                status=reminder_record['status'],
            )

            sent += 1

        except Exception as e:
            failed += 1
            logger.error(
                "Failed to send group session reminder to student",
                session_id=session_id,
                student_id=student_id,
                error=str(e),
                error_type=type(e).__name__,
            )

    return {'sent': sent, 'failed': failed}


def _send_individual_session_reminder(session: Dict[str, Any], current_time: datetime) -> None:
    """
    Send session reminder to a single student via WhatsApp (individual sessions).

    Args:
        session: Session record from DynamoDB
        current_time: Current UTC time

    Raises:
        Exception: If reminder sending fails
    """
    session_id = session.get('session_id')
    trainer_id = session.get('trainer_id')
    student_id = session.get('student_id')
    student_name = session.get('student_name')
    session_datetime = datetime.fromisoformat(session.get('session_datetime'))
    duration_minutes = session.get('duration_minutes', 60)
    location = session.get('location', '')

    # Get student phone number
    student = dynamodb_client.get_student(student_id)
    if not student:
        logger.error(
            "Student not found for session reminder",
            session_id=session_id,
            student_id=student_id,
        )
        raise ValueError(f"Student {student_id} not found")

    student_phone = student.get('phone_number')
    if not student_phone:
        logger.error(
            "Student phone number missing",
            session_id=session_id,
            student_id=student_id,
        )
        raise ValueError(f"Student {student_id} has no phone number")

    # Get trainer info for message
    trainer = dynamodb_client.get_trainer(trainer_id)
    trainer_name = trainer.get('name', 'your trainer') if trainer else 'your trainer'

    # Format session datetime for display
    session_date = session_datetime.strftime('%A, %B %d, %Y')
    session_time = session_datetime.strftime('%I:%M %p')

    # Build reminder message
    message_parts = [
        f"🔔 Session Reminder",
        f"",
        f"You have a training session with {trainer_name}:",
        f"📅 {session_date}",
        f"🕐 {session_time}",
        f"⏱️ Duration: {duration_minutes} minutes",
    ]

    if location:
        message_parts.append(f"📍 Location: {location}")

    message_parts.append("")
    message_parts.append("See you there! 💪")

    message_body = "\n".join(message_parts)

    # Send WhatsApp message
    logger.info(
        "Sending session reminder",
        session_id=session_id,
        student_phone=student_phone,
        session_datetime=session_datetime.isoformat(),
    )

    result = twilio_client.send_message(
        to=student_phone,
        body=message_body,
    )

    # Record reminder delivery in DynamoDB
    reminder_id = str(uuid.uuid4())
    reminder_record = {
        'PK': f'SESSION#{session_id}',
        'SK': f'REMINDER#{reminder_id}',
        'entity_type': 'REMINDER',
        'reminder_id': reminder_id,
        'session_id': session_id,
        'reminder_type': 'session',
        'recipient_phone': student_phone,
        'status': 'sent',
        'sent_at': current_time.isoformat(),
        'message_sid': result.get('message_sid'),
        'created_at': current_time.isoformat(),
    }

    # Update status to delivered if Twilio confirms delivery
    if result.get('status') in ['delivered', 'sent']:
        reminder_record['status'] = 'delivered'
        reminder_record['delivered_at'] = current_time.isoformat()

    dynamodb_client.put_reminder(reminder_record)

    logger.info(
        "Session reminder recorded",
        reminder_id=reminder_id,
        session_id=session_id,
        message_sid=result.get('message_sid'),
        status=reminder_record['status'],
    )
