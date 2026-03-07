"""
Payment reminder Lambda function triggered by EventBridge.

This handler is triggered monthly by EventBridge and:
1. Queries unpaid sessions from the previous month
2. Gets trainer payment reminder configuration (default day 1)
3. Groups unpaid sessions by student
4. Calculates total amount due and session count per student
5. Sends WhatsApp reminders only to students with unpaid sessions

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict
import boto3

from src.models.dynamodb_client import DynamoDBClient
from src.services.twilio_client import TwilioClient
from src.utils.logging import get_logger
from src.config import settings

logger = get_logger(__name__)

# Initialize services
dynamodb_client = DynamoDBClient()
twilio_client = TwilioClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for sending payment reminders.

    Triggered monthly by EventBridge on configured day of month.
    Queries unpaid sessions from previous month and sends reminders
    to students with outstanding payments.

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
            "time": "2024-01-01T10:00:00Z",
            "region": "us-east-1",
            "resources": ["arn:aws:events:..."]
        }
    """
    logger.info(
        "Payment reminder handler invoked",
        event_time=event.get("time"),
        function_name=context.function_name if context else "unknown",
    )

    current_date = datetime.utcnow().date()
    reminders_sent = 0
    reminders_failed = 0
    trainers_processed = 0

    try:
        # Calculate previous month date range
        first_day_current_month = current_date.replace(day=1)
        last_day_previous_month = first_day_current_month - timedelta(days=1)
        first_day_previous_month = last_day_previous_month.replace(day=1)

        logger.info(
            "Processing payment reminders for previous month",
            previous_month_start=first_day_previous_month.isoformat(),
            previous_month_end=last_day_previous_month.isoformat(),
        )

        # Get all trainers with payment reminders enabled
        # Note: In production, maintain a list of active trainers
        # For MVP, we'll scan for unpaid payments and group by trainer
        unpaid_payments = _get_unpaid_payments_previous_month(
            first_day_previous_month, last_day_previous_month
        )

        logger.info(
            "Found unpaid payments from previous month",
            payment_count=len(unpaid_payments),
        )

        # Group payments by trainer and student
        trainer_student_payments = _group_payments_by_trainer_and_student(
            unpaid_payments
        )

        logger.info(
            "Grouped payments by trainer and student",
            trainer_count=len(trainer_student_payments),
        )

        # Process each trainer
        for trainer_id, student_payments in trainer_student_payments.items():
            trainers_processed += 1

            # Check if payment reminders are enabled for this trainer
            trainer_config = dynamodb_client.get_trainer_config(trainer_id)
            if trainer_config and not trainer_config.get('payment_reminders_enabled', True):
                logger.info(
                    "Payment reminders disabled for trainer",
                    trainer_id=trainer_id,
                )
                continue

            # Send reminders to each student with unpaid sessions
            for student_id, payments in student_payments.items():
                try:
                    _send_payment_reminder(
                        trainer_id=trainer_id,
                        student_id=student_id,
                        payments=payments,
                        current_date=current_date,
                    )
                    reminders_sent += 1

                    logger.info(
                        "Payment reminder sent successfully",
                        trainer_id=trainer_id,
                        student_id=student_id,
                        unpaid_count=len(payments),
                    )

                except Exception as e:
                    reminders_failed += 1
                    logger.error(
                        "Failed to send payment reminder",
                        trainer_id=trainer_id,
                        student_id=student_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )

        # Log summary
        logger.info(
            "Payment reminder processing completed",
            trainers_processed=trainers_processed,
            reminders_sent=reminders_sent,
            reminders_failed=reminders_failed,
        )

        return {
            "statusCode": 200,
            "body": {
                "trainers_processed": trainers_processed,
                "reminders_sent": reminders_sent,
                "reminders_failed": reminders_failed,
            },
        }

    except Exception as e:
        logger.error(
            "Payment reminder handler failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def _get_unpaid_payments_previous_month(
    start_date: datetime.date, end_date: datetime.date
) -> List[Dict[str, Any]]:
    """
    Get all unpaid payments from the previous month.

    Scans for payment records with status='pending' and payment_date
    within the previous month.

    Args:
        start_date: First day of previous month
        end_date: Last day of previous month

    Returns:
        List of unpaid payment records
    """
    try:
        from boto3.dynamodb.conditions import Attr

        # Scan for unpaid payments in the date range
        filter_expr = (
            Attr('entity_type').eq('PAYMENT') &
            Attr('payment_status').eq('pending') &
            Attr('payment_date').between(
                start_date.isoformat(),
                end_date.isoformat()
            )
        )

        response = dynamodb_client.table.scan(FilterExpression=filter_expr)
        payments = [dynamodb_client._deserialize_item(item) for item in response.get('Items', [])]

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = dynamodb_client.table.scan(
                FilterExpression=filter_expr,
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            payments.extend([dynamodb_client._deserialize_item(item) for item in response.get('Items', [])])

        logger.info(
            "Found unpaid payments",
            payment_count=len(payments),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        return payments

    except Exception as e:
        logger.error(
            "Failed to query unpaid payments",
            error=str(e),
            error_type=type(e).__name__,
        )
        return []


def _group_payments_by_trainer_and_student(
    payments: List[Dict[str, Any]]
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Group payments by trainer and then by student.

    Args:
        payments: List of payment records

    Returns:
        Dict mapping trainer_id -> student_id -> list of payments
    """
    grouped = defaultdict(lambda: defaultdict(list))

    for payment in payments:
        trainer_id = payment.get('trainer_id')
        student_id = payment.get('student_id')

        if trainer_id and student_id:
            grouped[trainer_id][student_id].append(payment)

    return dict(grouped)


def _send_payment_reminder(
    trainer_id: str,
    student_id: str,
    payments: List[Dict[str, Any]],
    current_date: datetime.date,
) -> None:
    """
    Send payment reminder to student via WhatsApp.

    Calculates total amount due and session count, then sends
    a consolidated reminder message.

    Args:
        trainer_id: Trainer ID
        student_id: Student ID
        payments: List of unpaid payment records for this student
        current_date: Current date

    Raises:
        Exception: If reminder sending fails
    """
    # Get student info
    student = dynamodb_client.get_student(student_id)
    if not student:
        logger.error(
            "Student not found for payment reminder",
            trainer_id=trainer_id,
            student_id=student_id,
        )
        raise ValueError(f"Student {student_id} not found")

    student_phone = student.get('phone_number')
    student_name = student.get('name', 'there')

    if not student_phone:
        logger.error(
            "Student phone number missing",
            trainer_id=trainer_id,
            student_id=student_id,
        )
        raise ValueError(f"Student {student_id} has no phone number")

    # Get trainer info
    trainer = dynamodb_client.get_trainer(trainer_id)
    trainer_name = trainer.get('name', 'your trainer') if trainer else 'your trainer'
    business_name = trainer.get('business_name', '') if trainer else ''

    # Calculate total amount due and session count
    total_amount = sum(payment.get('amount', 0) for payment in payments)
    session_count = len(payments)
    currency = payments[0].get('currency', 'USD') if payments else 'USD'

    # Build reminder message
    message_parts = [
        f"💰 Payment Reminder",
        f"",
        f"Hi {student_name}!",
        f"",
        f"This is a friendly reminder from {trainer_name}",
    ]

    if business_name:
        message_parts.append(f"({business_name})")

    message_parts.extend([
        f"",
        f"You have {session_count} unpaid session{'s' if session_count > 1 else ''} from last month:",
        f"",
        f"💵 Total Amount Due: {currency} {total_amount:.2f}",
        f"📊 Number of Sessions: {session_count}",
        f"",
        f"Please send your payment at your earliest convenience.",
        f"",
        f"Thank you! 🙏",
    ])

    message_body = "\n".join(message_parts)

    # Send WhatsApp message
    logger.info(
        "Sending payment reminder",
        trainer_id=trainer_id,
        student_id=student_id,
        student_phone=student_phone,
        total_amount=total_amount,
        session_count=session_count,
    )

    result = twilio_client.send_message(
        to=student_phone,
        body=message_body,
    )

    # Record reminder delivery in DynamoDB
    # We'll create a reminder record for the first payment in the list
    # and reference all payment IDs
    reminder_id = str(uuid.uuid4())
    current_time = datetime.utcnow()

    # Store reminder as a notification record under the trainer
    notification_record = {
        'PK': f'TRAINER#{trainer_id}',
        'SK': f'NOTIFICATION#{reminder_id}',
        'entity_type': 'NOTIFICATION',
        'notification_id': reminder_id,
        'trainer_id': trainer_id,
        'message': message_body,
        'recipient_count': 1,
        'status': 'sent',
        'recipients': [
            {
                'student_id': student_id,
                'phone_number': student_phone,
                'status': 'sent',
                'sent_at': current_time.isoformat(),
                'message_sid': result.get('message_sid'),
            }
        ],
        'notification_type': 'payment_reminder',
        'payment_ids': [p.get('payment_id') for p in payments],
        'total_amount': total_amount,
        'session_count': session_count,
        'created_at': current_time.isoformat(),
        'updated_at': current_time.isoformat(),
    }

    # Update status to delivered if Twilio confirms delivery
    if result.get('status') in ['delivered', 'sent']:
        notification_record['status'] = 'delivered'
        notification_record['recipients'][0]['status'] = 'delivered'
        notification_record['recipients'][0]['delivered_at'] = current_time.isoformat()

    dynamodb_client.put_notification(notification_record)

    logger.info(
        "Payment reminder recorded",
        notification_id=reminder_id,
        trainer_id=trainer_id,
        student_id=student_id,
        message_sid=result.get('message_sid'),
        status=notification_record['status'],
    )
