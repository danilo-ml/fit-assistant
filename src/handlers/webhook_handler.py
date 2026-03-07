"""
Webhook handler Lambda function for receiving Twilio WhatsApp messages.

This handler receives POST requests from Twilio's WhatsApp API, validates
the signature for security, and enqueues messages to SQS for async processing.

Requirements: 13.1, 13.2, 13.3
"""

import json
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError
from src.services.twilio_client import TwilioClient
from src.utils.logging import get_logger
from src.config import settings

logger = get_logger(__name__)

# Initialize SQS client
sqs_client = boto3.client(
    "sqs", endpoint_url=settings.aws_endpoint_url, region_name=settings.aws_region
)

# Initialize Twilio client for signature validation
twilio_client = TwilioClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for Twilio WhatsApp webhook.

    Validates Twilio signature, enqueues message to SQS, and returns TwiML response.
    Target: Complete within 100ms to meet Twilio's timeout requirements.

    Args:
        event: API Gateway event containing webhook payload
        context: Lambda context object

    Returns:
        API Gateway response with status code and TwiML body

    Example event structure:
        {
            "body": "MessageSid=SM123&From=whatsapp:+1234567890&Body=Hello",
            "headers": {
                "X-Twilio-Signature": "signature_value",
                "Host": "example.com"
            },
            "requestContext": {
                "requestId": "abc-123",
                "domainName": "example.com",
                "path": "/webhook"
            }
        }
    """
    request_id = event.get("requestContext", {}).get("requestId", "unknown")

    logger.info(
        "Webhook request received", request_id=request_id, method=event.get("httpMethod", "POST")
    )

    try:
        # Extract request components
        headers = event.get("headers", {})
        body = event.get("body", "")

        # Parse form-encoded body
        params = _parse_form_body(body)

        # Extract phone number for logging
        from_number = params.get("From", "").replace("whatsapp:", "")
        message_sid = params.get("MessageSid", "unknown")

        logger.info(
            "Processing webhook",
            request_id=request_id,
            message_sid=message_sid,
            phone_number=from_number,
            has_media=int(params.get("NumMedia", 0)) > 0,
        )

        # Validate Twilio signature
        signature = headers.get("X-Twilio-Signature") or headers.get("x-twilio-signature")
        if not signature:
            logger.warning(
                "Missing Twilio signature", request_id=request_id, message_sid=message_sid
            )
            return _error_response(400, "Missing X-Twilio-Signature header")

        # Reconstruct full URL for signature validation
        url = _reconstruct_url(event)

        # Validate signature
        is_valid = twilio_client.validate_signature(url, params, signature)

        if not is_valid:
            logger.error(
                "Invalid Twilio signature", request_id=request_id, message_sid=message_sid, url=url
            )
            return _error_response(403, "Invalid Twilio signature")

        logger.info(
            "Twilio signature validated successfully",
            request_id=request_id,
            message_sid=message_sid,
        )

        # Enqueue message to SQS
        message_body = {
            "message_sid": message_sid,
            "from": from_number,
            "to": params.get("To", "").replace("whatsapp:", ""),
            "body": params.get("Body", ""),
            "num_media": int(params.get("NumMedia", 0)),
            "media_urls": _extract_media_urls(params),
            "timestamp": params.get("Timestamp", ""),
            "request_id": request_id,
        }

        _enqueue_to_sqs(message_body, request_id)

        logger.info(
            "Message enqueued successfully",
            request_id=request_id,
            message_sid=message_sid,
            phone_number=from_number,
        )

        # Return 200 OK with empty TwiML response
        return _success_response()

    except Exception as e:
        logger.error(
            "Webhook processing failed",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        # Return 200 to prevent Twilio retries for application errors
        # The message will be in DLQ if SQS enqueue failed
        return _success_response()


def _parse_form_body(body: str) -> Dict[str, str]:
    """
    Parse form-encoded body into dictionary.

    Args:
        body: Form-encoded string (e.g., "key1=value1&key2=value2")

    Returns:
        Dictionary of parsed parameters
    """
    from urllib.parse import parse_qs, unquote

    if not body:
        return {}

    # Parse query string format
    parsed = parse_qs(body, keep_blank_values=True)

    # Convert lists to single values (Twilio sends single values)
    params = {}
    for key, value in parsed.items():
        params[key] = unquote(value[0]) if value else ""

    return params


def _reconstruct_url(event: Dict[str, Any]) -> str:
    """
    Reconstruct full URL from API Gateway event for signature validation.

    Args:
        event: API Gateway event

    Returns:
        Full URL including protocol, domain, and path
    """
    headers = event.get("headers", {})
    request_context = event.get("requestContext", {})

    # Get protocol (default to https)
    protocol = headers.get("X-Forwarded-Proto", "https")

    # Get domain
    domain = request_context.get("domainName") or headers.get("Host", "")

    # Get path
    path = request_context.get("path", "/webhook")

    # Construct full URL
    url = f"{protocol}://{domain}{path}"

    return url


def _extract_media_urls(params: Dict[str, str]) -> list:
    """
    Extract media URLs from webhook parameters.

    Twilio sends media as MediaUrl0, MediaUrl1, etc.

    Args:
        params: Parsed webhook parameters

    Returns:
        List of media URL dictionaries with url and content_type
    """
    media_urls = []
    num_media = int(params.get("NumMedia", 0))

    for i in range(num_media):
        media_url = params.get(f"MediaUrl{i}")
        media_content_type = params.get(f"MediaContentType{i}")

        if media_url:
            media_urls.append(
                {"url": media_url, "content_type": media_content_type or "application/octet-stream"}
            )

    return media_urls


def _enqueue_to_sqs(message_body: Dict[str, Any], request_id: str) -> None:
    """
    Enqueue message to SQS for async processing.

    Args:
        message_body: Message payload to enqueue
        request_id: Request ID for tracing

    Raises:
        ClientError: If SQS enqueue fails
    """
    try:
        response = sqs_client.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=json.dumps(message_body),
            MessageAttributes={
                "request_id": {"StringValue": request_id, "DataType": "String"},
                "message_sid": {
                    "StringValue": message_body.get("message_sid", "unknown"),
                    "DataType": "String",
                },
            },
        )

        logger.info(
            "Message sent to SQS",
            request_id=request_id,
            message_id=response.get("MessageId"),
            queue_url=settings.sqs_queue_url,
        )

    except ClientError as e:
        logger.error(
            "Failed to enqueue message to SQS",
            request_id=request_id,
            error=str(e),
            error_code=e.response["Error"]["Code"],
            queue_url=settings.sqs_queue_url,
        )
        raise


def _success_response() -> Dict[str, Any]:
    """
    Generate successful API Gateway response with TwiML.

    Returns:
        API Gateway response dict with 200 status and TwiML body
    """
    twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'

    return {"statusCode": 200, "headers": {"Content-Type": "text/xml"}, "body": twiml_response}


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Generate error API Gateway response.

    Args:
        status_code: HTTP status code
        message: Error message

    Returns:
        API Gateway response dict with error status and message
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }
