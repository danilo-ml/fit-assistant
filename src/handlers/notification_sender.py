"""
Notification sender Lambda function triggered by SQS.

This handler is triggered by SQS notification queue and:
1. Processes individual notification messages
2. Sends WhatsApp messages via TwilioClient
3. Implements rate limiting (10 messages/second via SQS delays)
4. Implements retry logic (2 retries with 5-minute delays)
5. Updates delivery status in DynamoDB

Requirements: 10.4, 10.6
"""

import json
from datetime import datetime
from typing import Dict, Any
import boto3

from src.models.dynamodb_client import DynamoDBClient
from src.services.twilio_client import TwilioClient
from src.utils.logging import get_logger
from src.config import settings

logger = get_logger(__name__)

# Initialize services
dynamodb_client = DynamoDBClient()
twilio_client = TwilioClient()
sqs_client = boto3.client(
    'sqs',
    region_name=settings.aws_region,
    endpoint_url=settings.aws_endpoint_url
)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for sending notification messages.

    Triggered by SQS notification queue. Processes individual messages
    and sends them via WhatsApp with retry logic.

    Args:
        event: SQS event containing notification messages
        context: Lambda context object

    Returns:
        Dict with processing summary

    Example event structure:
        {
            "Records": [
                {
                    "messageId": "msg-id",
                    "receiptHandle": "receipt-handle",
                    "body": "{...}",
                    "attributes": {
                        "ApproximateReceiveCount": "1",
                        "SentTimestamp": "1234567890"
                    }
                }
            ]
        }
    """
    logger.info(
        "Notification sender handler invoked",
        record_count=len(event.get("Records", [])),
        function_name=context.function_name if context else "unknown",
    )

    messages_processed = 0
    messages_sent = 0
    messages_failed = 0
    messages_retried = 0

    try:
        # Process each SQS record
        for record in event.get("Records", []):
            messages_processed += 1

            try:
                # Parse message body
                message_body = json.loads(record["body"])
                notification_id = message_body.get("notification_id")
                trainer_id = message_body.get("trainer_id")
                recipient = message_body.get("recipient")
                message_text = message_body.get("message")
                attempt = message_body.get("attempt", 0)

                logger.info(
                    "Processing notification message",
                    notification_id=notification_id,
                    student_id=recipient.get("student_id"),
                    attempt=attempt,
                )

                # Send WhatsApp message
                result = _send_notification_message(
                    trainer_id=trainer_id,
                    recipient=recipient,
                    message=message_text,
                )

                if result["success"]:
                    messages_sent += 1

                    # Update delivery status in DynamoDB
                    _update_notification_status(
                        trainer_id=trainer_id,
                        notification_id=notification_id,
                        recipient=recipient,
                        status="sent",
                        message_sid=result.get("message_sid"),
                    )

                    logger.info(
                        "Notification sent successfully",
                        notification_id=notification_id,
                        student_id=recipient.get("student_id"),
                        message_sid=result.get("message_sid"),
                    )

                else:
                    # Message failed, check if we should retry
                    if attempt < 2:  # Max 2 retries (Requirement 10.6)
                        messages_retried += 1

                        # Requeue message with 5-minute delay (300 seconds)
                        _requeue_message(
                            message_body=message_body,
                            attempt=attempt + 1,
                            delay_seconds=300,  # 5 minutes
                        )

                        logger.warning(
                            "Notification failed, requeuing for retry",
                            notification_id=notification_id,
                            student_id=recipient.get("student_id"),
                            attempt=attempt + 1,
                            error=result.get("error"),
                        )

                    else:
                        # Max retries exceeded, mark as failed
                        messages_failed += 1

                        _update_notification_status(
                            trainer_id=trainer_id,
                            notification_id=notification_id,
                            recipient=recipient,
                            status="failed",
                            error=result.get("error"),
                        )

                        logger.error(
                            "Notification failed after max retries",
                            notification_id=notification_id,
                            student_id=recipient.get("student_id"),
                            attempts=attempt + 1,
                            error=result.get("error"),
                        )

            except Exception as e:
                messages_failed += 1
                logger.error(
                    "Failed to process notification message",
                    record_id=record.get("messageId"),
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Log summary
        logger.info(
            "Notification sender processing completed",
            messages_processed=messages_processed,
            messages_sent=messages_sent,
            messages_failed=messages_failed,
            messages_retried=messages_retried,
        )

        return {
            "statusCode": 200,
            "body": {
                "messages_processed": messages_processed,
                "messages_sent": messages_sent,
                "messages_failed": messages_failed,
                "messages_retried": messages_retried,
            },
        }

    except Exception as e:
        logger.error(
            "Notification sender handler failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def _send_notification_message(
    trainer_id: str,
    recipient: Dict[str, Any],
    message: str,
) -> Dict[str, Any]:
    """
    Send notification message to recipient via WhatsApp.

    Args:
        trainer_id: Trainer identifier
        recipient: Recipient dictionary with student_id, student_name, phone_number
        message: Notification message content

    Returns:
        dict: {
            'success': bool,
            'message_sid': str (optional),
            'error': str (optional)
        }
    """
    try:
        student_id = recipient.get("student_id")
        student_name = recipient.get("student_name")
        phone_number = recipient.get("phone_number")

        if not phone_number:
            return {
                "success": False,
                "error": f"Student {student_id} has no phone number",
            }

        # Get trainer info for message context
        trainer = dynamodb_client.get_trainer(trainer_id)
        trainer_name = trainer.get("name", "your trainer") if trainer else "your trainer"

        # Build notification message with trainer context
        message_parts = [
            f"📢 Message from {trainer_name}",
            "",
            message,
        ]

        message_body = "\n".join(message_parts)

        # Send WhatsApp message
        logger.info(
            "Sending notification message",
            student_id=student_id,
            phone_number=phone_number,
        )

        result = twilio_client.send_message(
            to=phone_number,
            body=message_body,
        )

        return {
            "success": True,
            "message_sid": result.get("message_sid"),
        }

    except Exception as e:
        logger.error(
            "Failed to send notification message",
            student_id=recipient.get("student_id"),
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "success": False,
            "error": str(e),
        }


def _update_notification_status(
    trainer_id: str,
    notification_id: str,
    recipient: Dict[str, Any],
    status: str,
    message_sid: str = None,
    error: str = None,
) -> None:
    """
    Update notification delivery status in DynamoDB.

    Args:
        trainer_id: Trainer identifier
        notification_id: Notification identifier
        recipient: Recipient dictionary
        status: Delivery status ("sent", "delivered", "failed")
        message_sid: Twilio message SID (optional)
        error: Error message if failed (optional)
    """
    try:
        current_time = datetime.utcnow()

        # Get notification record
        notification = dynamodb_client.table.get_item(
            Key={
                "PK": f"TRAINER#{trainer_id}",
                "SK": f"NOTIFICATION#{notification_id}",
            }
        ).get("Item")

        if not notification:
            logger.warning(
                "Notification record not found",
                trainer_id=trainer_id,
                notification_id=notification_id,
            )
            return

        # Update recipient status in the recipients list
        recipients = notification.get("recipients", [])
        student_id = recipient.get("student_id")

        for r in recipients:
            if r.get("student_id") == student_id:
                r["status"] = status
                if status == "sent":
                    r["sent_at"] = current_time.isoformat()
                    if message_sid:
                        r["message_sid"] = message_sid
                elif status == "delivered":
                    r["delivered_at"] = current_time.isoformat()
                elif status == "failed":
                    r["failed_at"] = current_time.isoformat()
                    if error:
                        r["error"] = error
                break

        # Update overall notification status
        # Check if all recipients have been processed
        all_sent = all(r.get("status") in ["sent", "delivered", "failed"] for r in recipients)
        if all_sent:
            # Count statuses
            sent_count = sum(1 for r in recipients if r.get("status") in ["sent", "delivered"])
            failed_count = sum(1 for r in recipients if r.get("status") == "failed")

            if failed_count == 0:
                notification["status"] = "completed"
            elif sent_count == 0:
                notification["status"] = "failed"
            else:
                notification["status"] = "partial"

        # Update notification record
        notification["recipients"] = recipients
        notification["updated_at"] = current_time.isoformat()

        dynamodb_client.table.put_item(Item=notification)

        logger.info(
            "Notification status updated",
            notification_id=notification_id,
            student_id=student_id,
            status=status,
        )

    except Exception as e:
        logger.error(
            "Failed to update notification status",
            notification_id=notification_id,
            student_id=recipient.get("student_id"),
            error=str(e),
            error_type=type(e).__name__,
        )


def _requeue_message(
    message_body: Dict[str, Any],
    attempt: int,
    delay_seconds: int,
) -> None:
    """
    Requeue failed message for retry.

    Args:
        message_body: Original message body
        attempt: Current attempt number
        delay_seconds: Delay before retry (5 minutes = 300 seconds)
    """
    try:
        # Update attempt counter
        message_body["attempt"] = attempt

        # Send message back to queue with delay
        response = sqs_client.send_message(
            QueueUrl=settings.notification_queue_url,
            MessageBody=json.dumps(message_body),
            DelaySeconds=delay_seconds,
        )

        logger.info(
            "Message requeued for retry",
            notification_id=message_body.get("notification_id"),
            student_id=message_body.get("recipient", {}).get("student_id"),
            attempt=attempt,
            delay_seconds=delay_seconds,
            message_id=response.get("MessageId"),
        )

    except Exception as e:
        logger.error(
            "Failed to requeue message",
            notification_id=message_body.get("notification_id"),
            error=str(e),
            error_type=type(e).__name__,
        )
