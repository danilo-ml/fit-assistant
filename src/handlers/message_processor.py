"""
Message processor Lambda function for processing WhatsApp messages from SQS FIFO queue.

This handler is triggered by SQS FIFO queue and processes messages by:
1. Extracting message from SQS event records (batch size 1 for FIFO)
2. Using MessageRouter to identify user and get handler type
3. Routing to appropriate handler (OnboardingHandler, TrainerHandler, StudentHandler)
4. Sending response via TwilioClient within 10 seconds
5. Handling failures with SQS retry mechanism (3 attempts with exponential backoff)

Messages from the same phone number (MessageGroupId) are processed sequentially in arrival
order to maintain conversational context. Messages from different phone numbers can still
be processed in parallel.

Requirements: 13.4, 13.5, 13.6, 13.7
"""

# CRITICAL: Import patch first to fix OpenTelemetry issues
import lambda_patch  # noqa: F401

import json
import time
from datetime import datetime
from typing import Dict, Any, List
import boto3
from botocore.exceptions import ClientError
from pydantic import ValidationError

from services.message_router import MessageRouter, HandlerType
from services.twilio_client import TwilioClient
from services.conversation_handlers import (
    OnboardingHandler,
    TrainerHandler,
    StudentHandler,
)
from services.strands_agent_service import get_strands_agent_service
from models.dynamodb_client import DynamoDBClient
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)

# Initialize services
message_router = MessageRouter()
twilio_client = TwilioClient()
db_client = DynamoDBClient()

# Initialize conversation handlers
onboarding_handler = OnboardingHandler()
trainer_handler = TrainerHandler()
student_handler = StudentHandler()

# Initialize SQS client for DLQ operations if needed
sqs_client = boto3.client(
    "sqs", endpoint_url=settings.aws_endpoint_url, region_name=settings.aws_region
)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for processing WhatsApp messages from SQS FIFO queue.

    Processes messages sequentially per phone number (MessageGroupId) from SQS FIFO queue,
    routes to appropriate handlers, and sends responses via Twilio. Messages from the same
    phone number are processed in strict order to maintain conversational context. Messages
    from different phone numbers can still be processed in parallel.

    Failed messages are automatically retried by SQS (3 attempts with exponential backoff)
    and moved to DLQ after retries.

    Args:
        event: SQS event containing message records
        context: Lambda context object

    Returns:
        Dict with batchItemFailures for partial batch failure handling

    Example event structure:
        {
            "Records": [
                {
                    "messageId": "msg-123",
                    "receiptHandle": "receipt-handle",
                    "body": "{\"message_sid\": \"SM123\", \"from\": \"+1234567890\", ...}",
                    "attributes": {
                        "ApproximateReceiveCount": "1",
                        "MessageGroupId": "+1234567890"
                    },
                    "messageAttributes": {
                        "request_id": {"stringValue": "abc-123"},
                        "phone_number": {"stringValue": "+1234567890"}
                    }
                }
            ]
        }
    """
    logger.info(
        "Message processor invoked",
        record_count=len(event.get("Records", [])),
        function_name=context.function_name if context else "unknown",
    )

    # Track failed messages for partial batch failure
    batch_item_failures = []

    # Process each SQS record
    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")
        receipt_handle = record.get("receiptHandle", "")
        
        # Extract request_id and phone_number from message attributes
        message_attributes = record.get("messageAttributes", {})
        request_id = (
            message_attributes.get("request_id", {}).get("stringValue", "unknown")
        )
        phone_number_attr = (
            message_attributes.get("phone_number", {}).get("stringValue", "")
        )
        
        # Get retry count
        receive_count = int(record.get("attributes", {}).get("ApproximateReceiveCount", 1))

        logger.info(
            "Processing SQS record from FIFO queue",
            message_id=message_id,
            request_id=request_id,
            message_group_id=phone_number_attr,
            receive_count=receive_count,
        )

        try:
            # Parse message body
            message_body = json.loads(record.get("body", "{}"))
            
            # Extract message details
            phone_number = message_body.get("from", "")
            message_sid = message_body.get("message_sid", "unknown")
            body_text = message_body.get("body", "")
            
            logger.info(
                "Processing message",
                message_sid=message_sid,
                phone_number=phone_number,
                request_id=request_id,
                has_media=message_body.get("num_media", 0) > 0,
            )

            # Process the message with timeout tracking
            start_time = time.time()
            
            # Route and process message
            response_text = _process_message(
                phone_number=phone_number,
                message_body=message_body,
                request_id=request_id,
            )
            
            # Send response via Twilio
            _send_response(
                to=phone_number,
                body=response_text,
                request_id=request_id,
                message_sid=message_sid,
            )
            
            # Check processing time
            elapsed_time = time.time() - start_time
            
            logger.info(
                "Message processed successfully",
                message_sid=message_sid,
                phone_number=phone_number,
                request_id=request_id,
                elapsed_seconds=round(elapsed_time, 2),
            )
            
            # Warn if processing took too long
            if elapsed_time > 10:
                logger.warning(
                    "Message processing exceeded 10 second target",
                    message_sid=message_sid,
                    elapsed_seconds=round(elapsed_time, 2),
                )

        except json.JSONDecodeError as e:
            # JSON parsing errors - invalid message format, don't retry
            logger.error(
                "Invalid JSON in message body, skipping retry",
                message_id=message_id,
                request_id=request_id,
                phone_number=phone_number_attr,
                error=str(e),
                error_type="JSONDecodeError",
            )
            # Don't add to batch_item_failures - message will be deleted
            
        except ValidationError as e:
            # Pydantic validation errors - invalid user input, don't retry
            logger.error(
                "Pydantic validation error in message processing, skipping retry",
                message_id=message_id,
                request_id=request_id,
                phone_number=phone_number_attr,
                receive_count=receive_count,
                error=str(e),
                error_type="ValidationError",
                validation_errors=e.errors() if hasattr(e, 'errors') else None,
            )
            # Don't add to batch_item_failures - message will be deleted
            
        except ValueError as e:
            # Standard validation errors - invalid user input, don't retry
            logger.error(
                "Validation error in message processing, skipping retry",
                message_id=message_id,
                request_id=request_id,
                phone_number=phone_number_attr,
                receive_count=receive_count,
                error=str(e),
                error_type="ValueError",
            )
            # Don't add to batch_item_failures - message will be deleted
            
        except ClientError as e:
            # AWS service errors - may be transient, allow retry
            logger.error(
                "AWS service error, will retry",
                message_id=message_id,
                request_id=request_id,
                receive_count=receive_count,
                error=str(e),
                error_type="ClientError",
                error_code=e.response.get('Error', {}).get('Code', 'Unknown'),
            )
            
            # Add to batch item failures for SQS retry
            batch_item_failures.append({"itemIdentifier": message_id})
            
            # Log if this is the final retry attempt
            if receive_count >= 3:
                logger.error(
                    "AWS service error persisted after maximum retries, moving to DLQ",
                    message_id=message_id,
                    request_id=request_id,
                    receive_count=receive_count,
                )
                
        except Exception as e:
            # Unexpected errors - log and allow retry
            logger.error(
                "Unexpected error in message processing, will retry",
                message_id=message_id,
                request_id=request_id,
                receive_count=receive_count,
                error=str(e),
                error_type=type(e).__name__,
            )
            
            # Add to batch item failures for SQS retry
            batch_item_failures.append({"itemIdentifier": message_id})
            
            # Log if this is the final retry attempt
            if receive_count >= 3:
                logger.error(
                    "Message failed after maximum retries, moving to DLQ",
                    message_id=message_id,
                    request_id=request_id,
                    receive_count=receive_count,
                )

    # Return batch item failures for partial batch failure handling
    result = {"batchItemFailures": batch_item_failures}
    
    logger.info(
        "Message processor completed",
        total_records=len(event.get("Records", [])),
        failed_records=len(batch_item_failures),
    )
    
    return result


def process_confirmation_response(
    phone_number: str,
    message: str,
) -> bool:
    """
    Detect and process session confirmation responses.
    
    Args:
        phone_number: Student's phone number
        message: User's message
    
    Returns:
        True if message was a confirmation response, False otherwise
    """
    # Normalize message
    normalized = message.strip().upper()
    
    # Check if it's a YES/NO response
    if normalized not in ['YES', 'NO']:
        return False
    
    # Lookup student by phone number
    try:
        response = db_client.table.query(
            IndexName='phone-number-index',
            KeyConditionExpression='phone_number = :phone',
            ExpressionAttributeValues={':phone': phone_number}
        )
        
        items = response.get('Items', [])
        if not items:
            return False
        
        # Find student entity
        student_item = None
        for item in items:
            if item.get('entity_type') == 'STUDENT':
                student_item = item
                break
        
        if not student_item:
            return False
        
        student_id = student_item.get('student_id')
        trainer_id = student_item.get('trainer_id')
        
        # Find pending confirmation session for this student
        pending_session = find_pending_confirmation_session(
            student_id=student_id,
            trainer_id=trainer_id,
        )
        
        if not pending_session:
            return False
        
        # Update session based on response
        now = datetime.utcnow()
        confirmation_status = 'completed' if normalized == 'YES' else 'missed'
        
        db_client.update_item(
            pk=f"TRAINER#{trainer_id}",
            sk=f"SESSION#{pending_session['session_id']}",
            updates={
                'confirmation_status': confirmation_status,
                'status': confirmation_status,  # Also update main status
                'confirmed_at': now.isoformat(),
                'confirmation_response': message,
                'updated_at': now.isoformat(),
                'confirmation_status_datetime': f'{confirmation_status}#{pending_session["session_datetime"]}',
            }
        )
        
        logger.info(
            "Session confirmation processed",
            session_id=pending_session['session_id'],
            confirmation_status=confirmation_status,
            student_id=student_id,
        )
        
        # Send acknowledgment
        ack_message = (
            "Thanks for confirming! " +
            ("Session marked as completed." if normalized == 'YES' 
             else "Session marked as missed.")
        )
        
        twilio_client.send_message(
            to=phone_number,
            body=ack_message,
        )
        
        return True
    
    except Exception as e:
        logger.error(
            "Error processing confirmation response",
            phone_number=phone_number,
            error=str(e),
        )
        return False


def find_pending_confirmation_session(
    student_id: str,
    trainer_id: str,
) -> Dict[str, Any]:
    """
    Find pending confirmation session for a student.
    
    Args:
        student_id: Student identifier
        trainer_id: Trainer identifier
    
    Returns:
        Session item dict or None
    """
    try:
        # Query sessions for this trainer and student
        response = db_client.table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk_prefix)',
            FilterExpression='student_id = :student_id AND confirmation_status = :status',
            ExpressionAttributeValues={
                ':pk': f'TRAINER#{trainer_id}',
                ':sk_prefix': 'SESSION#',
                ':student_id': student_id,
                ':status': 'pending_confirmation',
            }
        )
        
        items = response.get('Items', [])
        
        # Return the most recent pending confirmation session
        if items:
            # Sort by session_datetime descending
            items.sort(key=lambda x: x.get('session_datetime', ''), reverse=True)
            return items[0]
        
        return None
    
    except Exception as e:
        logger.error(
            "Error finding pending confirmation session",
            student_id=student_id,
            trainer_id=trainer_id,
            error=str(e),
        )
        return None


def _process_message(
    phone_number: str, message_body: Dict[str, Any], request_id: str
) -> str:
    """
    Process message by routing to appropriate handler.

    Args:
        phone_number: Sender's phone number in E.164 format
        message_body: Message payload from SQS
        request_id: Request ID for tracing

    Returns:
        Response text to send back to user

    Raises:
        Exception: If message processing fails
    """
    body_text = message_body.get("body", "")
    
    # Check if this is a session confirmation response (YES/NO)
    if process_confirmation_response(phone_number, body_text):
        # Confirmation was handled, return empty (already sent acknowledgment)
        return ""
    
    logger.info(
        "Routing message",
        phone_number=phone_number,
        request_id=request_id,
    )

    # Route message to appropriate handler
    routing_result = message_router.route_message(phone_number, message_body)
    
    handler_type = routing_result["handler_type"]
    user_id = routing_result.get("user_id")
    user_data = routing_result.get("user_data")

    logger.info(
        "Message routed",
        phone_number=phone_number,
        handler_type=handler_type,
        user_id=user_id,
        request_id=request_id,
    )

    # Process based on handler type
    if handler_type == HandlerType.ONBOARDING:
        response_text = _handle_onboarding(phone_number, message_body, request_id)
    elif handler_type == HandlerType.TRAINER:
        response_text = _handle_trainer(user_id, user_data, message_body, request_id, phone_number)
    elif handler_type == HandlerType.STUDENT:
        response_text = _handle_student(user_id, user_data, message_body, request_id)
    else:
        logger.error(
            "Unknown handler type",
            handler_type=handler_type,
            phone_number=phone_number,
            request_id=request_id,
        )
        response_text = "Sorry, we encountered an error processing your message. Please try again."

    return response_text


def _handle_onboarding(
    phone_number: str, message_body: Dict[str, Any], request_id: str
) -> str:
    """
    Handle onboarding flow for unregistered users.

    Uses OnboardingHandler to manage trainer registration flow.

    Args:
        phone_number: User's phone number
        message_body: Message payload
        request_id: Request ID for tracing

    Returns:
        Response text for onboarding flow
    """
    logger.info(
        "Processing onboarding message",
        phone_number=phone_number,
        request_id=request_id,
    )

    return onboarding_handler.handle_message(
        phone_number=phone_number,
        message_body=message_body,
        request_id=request_id,
    )


def _handle_trainer(
    trainer_id: str,
    user_data: Dict[str, Any],
    message_body: Dict[str, Any],
    request_id: str,
    phone_number: str = None,
) -> str:
    """
    Handle trainer messages with Strands Agent Service.

    Uses StrandsAgentService to process trainer messages with a single agent
    that has all FitAgent tools (student, session, payment management).

    Args:
        trainer_id: Trainer's unique identifier
        user_data: Trainer's user record from DynamoDB
        message_body: Message payload
        request_id: Request ID for tracing
        phone_number: Phone number for logging

    Returns:
        Response text from AI agent in PT-BR
    """
    logger.info(
        "Processing trainer message with Strands Agent",
        trainer_id=trainer_id,
        request_id=request_id,
        phone_number=phone_number,
    )
    
    # Get Strands Agent Service
    agent_service = get_strands_agent_service()
    
    # Process message through agent
    result = agent_service.process_message(
        trainer_id=trainer_id,
        message=message_body.get("body", ""),
        phone_number=phone_number
    )
    
    # Handle result
    if result.get('success'):
        logger.info(
            "Trainer message processed successfully",
            trainer_id=trainer_id,
            request_id=request_id,
        )
        return result.get('response', 'Mensagem processada com sucesso.')
    else:
        error_msg = result.get('error', 'Erro desconhecido')
        logger.error(
            "Trainer message processing failed",
            trainer_id=trainer_id,
            request_id=request_id,
            error=error_msg,
        )
        return result.get('error', 'Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.')


def _handle_student(
    student_id: str,
    user_data: Dict[str, Any],
    message_body: Dict[str, Any],
    request_id: str,
) -> str:
    """
    Handle student messages with AI agent.

    Uses StudentHandler for session viewing and confirmation.

    Args:
        student_id: Student's unique identifier
        user_data: Student's user record from DynamoDB
        message_body: Message payload
        request_id: Request ID for tracing

    Returns:
        Response text from AI agent
    """
    logger.info(
        "Processing student message",
        student_id=student_id,
        request_id=request_id,
    )

    return student_handler.handle_message(
        student_id=student_id,
        user_data=user_data,
        message_body=message_body,
        request_id=request_id,
    )


def _send_response(
    to: str, body: str, request_id: str, message_sid: str
) -> None:
    """
    Send response message via Twilio.

    Args:
        to: Recipient phone number in E.164 format
        body: Response text to send
        request_id: Request ID for tracing
        message_sid: Original message SID for correlation

    Raises:
        Exception: If message sending fails
    """
    # Skip sending if body is empty (e.g., confirmation already sent)
    if not body or not body.strip():
        logger.info(
            "Skipping response send (empty body)",
            to=to,
            request_id=request_id,
        )
        return
    
    logger.info(
        "Sending response",
        to=to,
        request_id=request_id,
        original_message_sid=message_sid,
        body_length=len(body),
    )

    try:
        result = twilio_client.send_message(to=to, body=body)

        logger.info(
            "Response sent successfully",
            to=to,
            request_id=request_id,
            response_message_sid=result.get("message_sid"),
            status=result.get("status"),
        )

    except Exception as e:
        logger.error(
            "Failed to send response",
            to=to,
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
