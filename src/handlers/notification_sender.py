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

from models.dynamodb_client import DynamoDBClient
from services.twilio_client import TwilioClient
from services.template_registry import TemplateRegistry, TemplateConfig, build_content_variables
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)

# Initialize services
dynamodb_client = DynamoDBClient()
twilio_client = TwilioClient()
template_registry = TemplateRegistry()
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
                content_sid = message_body.get("content_sid")
                template_variables = message_body.get("template_variables")
                notification_type = message_body.get("notification_type")

                logger.info(
                    "Processing notification message",
                    notification_id=notification_id,
                    student_id=recipient.get("student_id"),
                    attempt=attempt,
                    notification_type=notification_type,
                    has_content_sid=bool(content_sid),
                )

                # Send WhatsApp message
                result = _send_notification_message(
                    trainer_id=trainer_id,
                    recipient=recipient,
                    message=message_text,
                    content_sid=content_sid,
                    template_variables=template_variables,
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
                        sending_method=result.get("sending_method"),
                    )

                    logger.info(
                        "Notification sent successfully",
                        notification_id=notification_id,
                        student_id=recipient.get("student_id"),
                        message_sid=result.get("message_sid"),
                        sending_method=result.get("sending_method"),
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
                            sending_method=result.get("sending_method"),
                            error_code=result.get("error_code"),
                            error_message=result.get("error_message"),
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
    content_sid: str = None,
    template_variables: Dict[str, str] = None,
) -> Dict[str, Any]:
    """
    Send notification message to recipient via WhatsApp.

    Attempts template sending when content_sid is present. Falls back to
    freeform if template variables are missing or incomplete.

    Args:
        trainer_id: Trainer identifier
        recipient: Recipient dictionary with student_id, student_name, phone_number
        message: Notification message content (used for freeform fallback)
        content_sid: Optional Twilio Content SID for template messages
        template_variables: Optional dict of template placeholder values

    Returns:
        dict: {
            'success': bool,
            'message_sid': str (optional),
            'sending_method': 'template' or 'freeform',
            'error': str (optional),
            'error_code': int (optional),
            'error_message': str (optional),
        }
    """
    try:
        student_id = recipient.get("student_id")
        student_name = recipient.get("student_name")
        phone_number = recipient.get("phone_number")

        if not phone_number:
            return {
                "success": False,
                "sending_method": "freeform",
                "error": f"Student {student_id} has no phone number",
            }

        # Attempt template message if content_sid is provided
        if content_sid and template_variables is not None:
            # Build a TemplateConfig from the content_sid and variable keys
            template_config = TemplateConfig(
                content_sid=content_sid,
                variables=list(template_variables.keys()),
            )
            variables_json = build_content_variables(template_config, template_variables)

            if variables_json:
                logger.info(
                    "Sending template notification message",
                    student_id=student_id,
                    phone_number=phone_number,
                    content_sid=content_sid,
                )

                result = twilio_client.send_template_message(
                    to=phone_number,
                    content_sid=content_sid,
                    content_variables=variables_json,
                )

                return {
                    "success": result.get("status") != "failed",
                    "message_sid": result.get("message_sid"),
                    "sending_method": "template",
                    "error_code": result.get("error_code"),
                    "error_message": result.get("error_message"),
                    "error": result.get("error_message") if result.get("status") == "failed" else None,
                }
            else:
                logger.warning(
                    "Missing template variables, falling back to freeform",
                    student_id=student_id,
                    content_sid=content_sid,
                )

        # Fallback to freeform message
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
            "Sending freeform notification message",
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
            "sending_method": "freeform",
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
            "sending_method": "freeform",
            "error": str(e),
        }


def _update_notification_status(
    trainer_id: str,
    notification_id: str,
    recipient: Dict[str, Any],
    status: str,
    message_sid: str = None,
    error: str = None,
    sending_method: str = None,
    error_code: int = None,
    error_message: str = None,
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
        sending_method: "template" or "freeform" (optional)
        error_code: Twilio error code on failure (optional)
        error_message: Twilio error message on failure (optional)
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
                if sending_method:
                    r["sending_method"] = sending_method
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
                    if error_code is not None:
                        r["error_code"] = error_code
                    if error_message:
                        r["error_message"] = error_message
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
