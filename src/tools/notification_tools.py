"""
AI agent tool functions for notification management.

This module provides tool functions that the AI agent can call to:
- Send broadcast notifications to students

All functions follow the tool function pattern:
- Accept trainer_id as first parameter
- Return dict with 'success', 'data', and optional 'error' keys
- Validate inputs before processing
- Handle errors gracefully
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from models.dynamodb_client import DynamoDBClient
from utils.validation import InputSanitizer
from utils.logging import get_logger
from services.template_registry import TemplateRegistry
from config import settings
import boto3

logger = get_logger(__name__)

# Initialize DynamoDB client and SQS client
dynamodb_client = DynamoDBClient(
    table_name=settings.dynamodb_table, endpoint_url=settings.aws_endpoint_url
)

# Initialize SQS client
sqs_client = boto3.client(
    'sqs',
    region_name=settings.aws_region,
    endpoint_url=settings.aws_endpoint_url
)


def send_notification(
    trainer_id: str,
    message: str,
    recipients: str = "all",
    specific_student_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Send broadcast notification to students with rate limiting.

    This tool:
    1. Validates that the trainer exists
    2. Sanitizes the message content
    3. Selects recipients based on criteria:
       - "all": All active students linked to trainer
       - "specific": Specific students (requires specific_student_ids)
       - "upcoming_sessions": Students with sessions in next 7 days
    4. Queues individual messages to SQS notification queue with delays for rate limiting
    5. Records notification in DynamoDB with delivery tracking
    6. Returns queued count and success status

    Args:
        trainer_id: Trainer identifier (required)
        message: Notification message content (required)
        recipients: Recipient selection criteria (default: "all")
                   Options: "all", "specific", "upcoming_sessions"
        specific_student_ids: List of student IDs for "specific" recipients (optional)

    Returns:
        dict: {
            'success': bool,
            'data': {
                'notification_id': str,
                'message': str,
                'recipient_count': int,
                'queued_count': int,
                'recipients': [
                    {
                        'student_id': str,
                        'student_name': str,
                        'phone_number': str,
                        'status': str
                    },
                    ...
                ]
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> send_notification(
        ...     trainer_id='abc123',
        ...     message='Gym will be closed tomorrow for maintenance',
        ...     recipients='all'
        ... )
        {
            'success': True,
            'data': {
                'notification_id': 'notif123',
                'message': 'Gym will be closed tomorrow for maintenance',
                'recipient_count': 10,
                'queued_count': 10,
                'recipients': [...]
            }
        }

        >>> send_notification(
        ...     trainer_id='abc123',
        ...     message='Special session tomorrow at 6 AM',
        ...     recipients='upcoming_sessions'
        ... )
        {
            'success': True,
            'data': {
                'notification_id': 'notif456',
                'message': 'Special session tomorrow at 6 AM',
                'recipient_count': 3,
                'queued_count': 3,
                'recipients': [...]
            }
        }

    Validates: Requirements 10.1, 10.2, 10.3, 10.5
    """
    try:
        # Sanitize inputs
        sanitized_params = InputSanitizer.sanitize_tool_parameters(
            {
                "message": message,
                "recipients": recipients,
            }
        )

        message = sanitized_params["message"]
        recipients = sanitized_params["recipients"]

        # Validate required fields
        if not message:
            return {"success": False, "error": "Notification message is required"}

        if not recipients:
            return {"success": False, "error": "Recipients selection is required"}

        # Validate recipients option
        valid_recipients = ["all", "specific", "upcoming_sessions"]
        if recipients not in valid_recipients:
            return {
                "success": False,
                "error": f"Invalid recipients option. Must be one of: {', '.join(valid_recipients)}. Got: {recipients}",
            }

        # Validate specific_student_ids if recipients is "specific"
        if recipients == "specific" and not specific_student_ids:
            return {
                "success": False,
                "error": "specific_student_ids is required when recipients='specific'",
            }

        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Select recipients based on criteria
        selected_recipients = _select_recipients(
            trainer_id=trainer_id,
            recipients=recipients,
            specific_student_ids=specific_student_ids,
        )

        if not selected_recipients:
            return {
                "success": False,
                "error": f"No recipients found for selection criteria: {recipients}",
            }

        logger.info(
            "Selected notification recipients",
            trainer_id=trainer_id,
            recipients_criteria=recipients,
            recipient_count=len(selected_recipients),
        )

        # Generate notification ID
        import uuid
        notification_id = str(uuid.uuid4())

        # Queue individual messages to SQS with rate limiting
        # Target: 10 messages per second (Requirement 10.4)
        queued_count = _queue_notification_messages(
            notification_id=notification_id,
            trainer_id=trainer_id,
            message=message,
            recipients=selected_recipients,
            trainer_name=trainer.get("name", ""),
        )

        # Record notification in DynamoDB
        notification_record = _create_notification_record(
            notification_id=notification_id,
            trainer_id=trainer_id,
            message=message,
            recipients=selected_recipients,
        )

        logger.info(
            "Notification queued successfully",
            notification_id=notification_id,
            trainer_id=trainer_id,
            recipient_count=len(selected_recipients),
            queued_count=queued_count,
        )

        # Build response
        return {
            "success": True,
            "data": {
                "notification_id": notification_id,
                "message": message,
                "recipient_count": len(selected_recipients),
                "queued_count": queued_count,
                "recipients": [
                    {
                        "student_id": r["student_id"],
                        "student_name": r["student_name"],
                        "phone_number": r["phone_number"],
                        "status": "queued",
                    }
                    for r in selected_recipients
                ],
            },
        }

    except ValueError as e:
        # Validation errors
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        # Unexpected errors
        logger.error(
            "Failed to send notification",
            trainer_id=trainer_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {"success": False, "error": f"Failed to send notification: {str(e)}"}


def _select_recipients(
    trainer_id: str,
    recipients: str,
    specific_student_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Select notification recipients based on criteria.

    Args:
        trainer_id: Trainer identifier
        recipients: Selection criteria ("all", "specific", "upcoming_sessions")
        specific_student_ids: List of student IDs for "specific" selection

    Returns:
        List of recipient dictionaries with student_id, student_name, phone_number
    """
    selected = []

    if recipients == "all":
        # Get all active students linked to trainer
        trainer_students = dynamodb_client.get_trainer_students(trainer_id)

        for link in trainer_students:
            if link.get("status") != "active":
                continue

            student_id = link.get("student_id")
            if not student_id:
                continue

            # Get full student details
            student_data = dynamodb_client.get_student(student_id)
            if student_data:
                selected.append(
                    {
                        "student_id": student_data["student_id"],
                        "student_name": student_data["name"],
                        "phone_number": student_data["phone_number"],
                    }
                )

    elif recipients == "specific":
        # Get specific students by ID
        if not specific_student_ids:
            return []

        for student_id in specific_student_ids:
            # Verify trainer-student link exists and is active
            link = dynamodb_client.get_trainer_student_link(trainer_id, student_id)
            if not link or link.get("status") != "active":
                logger.warning(
                    "Student not linked to trainer or inactive",
                    trainer_id=trainer_id,
                    student_id=student_id,
                )
                continue

            # Get full student details
            student_data = dynamodb_client.get_student(student_id)
            if student_data:
                selected.append(
                    {
                        "student_id": student_data["student_id"],
                        "student_name": student_data["name"],
                        "phone_number": student_data["phone_number"],
                    }
                )

    elif recipients == "upcoming_sessions":
        # Get students with sessions in next 7 days
        current_time = datetime.utcnow()
        end_time = current_time + timedelta(days=7)

        sessions = dynamodb_client.get_sessions_by_date_range(
            trainer_id=trainer_id,
            start_datetime=current_time,
            end_datetime=end_time,
        )

        # Get unique student IDs from sessions
        student_ids = set()
        for session in sessions:
            # Only include scheduled or confirmed sessions
            if session.get("status") in ["scheduled", "confirmed"]:
                student_ids.add(session.get("student_id"))

        # Get student details for each unique student
        for student_id in student_ids:
            student_data = dynamodb_client.get_student(student_id)
            if student_data:
                selected.append(
                    {
                        "student_id": student_data["student_id"],
                        "student_name": student_data["name"],
                        "phone_number": student_data["phone_number"],
                    }
                )

    return selected


def _queue_notification_messages(
    notification_id: str,
    trainer_id: str,
    message: str,
    recipients: List[Dict[str, Any]],
    trainer_name: str = "",
) -> int:
    """
    Queue individual notification messages to SQS with rate limiting.

    Implements rate limiting by adding delays to messages:
    - Target: 10 messages per second (Requirement 10.4)
    - Delay calculation: message_index // 10 seconds

    When a broadcast template is configured in the TemplateRegistry,
    adds notification_type, content_sid, and template_variables to
    the SQS message body. Falls back to freeform when no template
    is configured.

    Args:
        notification_id: Notification identifier
        trainer_id: Trainer identifier
        message: Notification message content
        recipients: List of recipient dictionaries
        trainer_name: Trainer display name for template variables

    Returns:
        int: Number of messages successfully queued
    """
    queued_count = 0

    # Look up broadcast template
    registry = TemplateRegistry()
    broadcast_template = registry.get_template("broadcast")

    for i, recipient in enumerate(recipients):
        try:
            # Calculate delay for rate limiting (10 messages per second)
            delay_seconds = i // 10

            # Prepare message body
            message_body = {
                "notification_id": notification_id,
                "trainer_id": trainer_id,
                "recipient": recipient,
                "message": message,
                "attempt": 0,  # Track retry attempts
            }

            # Add template fields when broadcast template is configured
            if broadcast_template:
                message_body["notification_type"] = "broadcast"
                message_body["content_sid"] = broadcast_template.content_sid
                message_body["template_variables"] = {
                    "trainer_name": trainer_name,
                    "message_content": message,
                }

            # Send message to SQS notification queue
            response = sqs_client.send_message(
                QueueUrl=settings.notification_queue_url,
                MessageBody=json.dumps(message_body),
                DelaySeconds=min(delay_seconds, 900),  # Max delay is 900 seconds (15 minutes)
            )

            queued_count += 1

            logger.info(
                "Notification message queued",
                notification_id=notification_id,
                student_id=recipient["student_id"],
                delay_seconds=delay_seconds,
                message_id=response.get("MessageId"),
            )

        except Exception as e:
            logger.error(
                "Failed to queue notification message",
                notification_id=notification_id,
                student_id=recipient.get("student_id"),
                error=str(e),
                error_type=type(e).__name__,
            )

    return queued_count


def _create_notification_record(
    notification_id: str,
    trainer_id: str,
    message: str,
    recipients: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Create notification record in DynamoDB with delivery tracking.

    Args:
        notification_id: Notification identifier
        trainer_id: Trainer identifier
        message: Notification message content
        recipients: List of recipient dictionaries

    Returns:
        dict: Notification record
    """
    current_time = datetime.utcnow()

    notification_record = {
        "PK": f"TRAINER#{trainer_id}",
        "SK": f"NOTIFICATION#{notification_id}",
        "entity_type": "NOTIFICATION",
        "notification_id": notification_id,
        "trainer_id": trainer_id,
        "message": message,
        "recipient_count": len(recipients),
        "status": "queued",
        "recipients": [
            {
                "student_id": r["student_id"],
                "phone_number": r["phone_number"],
                "status": "queued",
            }
            for r in recipients
        ],
        "created_at": current_time.isoformat(),
        "updated_at": current_time.isoformat(),
    }

    # Save to DynamoDB
    dynamodb_client.table.put_item(Item=notification_record)

    logger.info(
        "Notification record created",
        notification_id=notification_id,
        trainer_id=trainer_id,
        recipient_count=len(recipients),
    )

    return notification_record
