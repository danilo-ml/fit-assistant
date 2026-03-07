"""
Message routing service for identifying users and routing to appropriate handlers.

This module implements phone number-based user identification using DynamoDB GSI
and routes messages to the appropriate handler (Onboarding, Trainer, or Student).
"""

from typing import Dict, Any, Optional
from enum import Enum

from src.models.dynamodb_client import DynamoDBClient
from src.utils.logging import StructuredLogger
from src.config import settings

logger = StructuredLogger(__name__)


class HandlerType(str, Enum):
    """Handler types for message routing."""

    ONBOARDING = "onboarding"
    TRAINER = "trainer"
    STUDENT = "student"


class MessageRouter:
    """
    Routes WhatsApp messages to appropriate handlers based on phone number lookup.

    The router queries the phone-number-index GSI to identify if the sender is
    a registered trainer, student, or unknown user, then returns the appropriate
    handler type for processing.

    Performance target: Complete routing within 200ms.
    """

    def __init__(self, dynamodb_client: Optional[DynamoDBClient] = None):
        """
        Initialize MessageRouter with DynamoDB client.

        Args:
            dynamodb_client: Optional DynamoDB client instance. If not provided,
                           creates a new client with default settings.
        """
        self.dynamodb = dynamodb_client or DynamoDBClient(
            table_name=settings.dynamodb_table, endpoint_url=settings.aws_endpoint_url
        )

    def route_message(self, phone_number: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route message to appropriate handler based on phone number lookup.

        This method:
        1. Extracts phone number from message
        2. Queries phone-number-index GSI to identify user type
        3. Returns handler type and user context

        Args:
            phone_number: Sender's phone number in E.164 format
            message: Message payload from WhatsApp webhook

        Returns:
            Dict containing:
                - handler_type: HandlerType enum (onboarding, trainer, or student)
                - user_id: User identifier if found (trainer_id or student_id)
                - entity_type: Entity type if found (TRAINER or STUDENT)
                - user_data: Full user record if found

        Example:
            >>> router = MessageRouter()
            >>> result = router.route_message("+1234567890", message_data)
            >>> print(result['handler_type'])
            HandlerType.TRAINER
        """
        logger.info(
            "Routing message", phone_number=phone_number, message_sid=message.get("MessageSid")
        )

        # Query phone-number-index GSI for user lookup
        user_record = self.dynamodb.lookup_by_phone_number(phone_number)

        if not user_record:
            # Unknown phone number - route to onboarding
            logger.info("Unknown phone number, routing to onboarding", phone_number=phone_number)
            return {
                "handler_type": HandlerType.ONBOARDING,
                "user_id": None,
                "entity_type": None,
                "user_data": None,
            }

        entity_type = user_record.get("entity_type")

        if entity_type == "TRAINER":
            # Registered trainer - route to trainer handler
            trainer_id = user_record.get("trainer_id")
            logger.info(
                "Trainer identified, routing to trainer handler",
                phone_number=phone_number,
                trainer_id=trainer_id,
            )
            return {
                "handler_type": HandlerType.TRAINER,
                "user_id": trainer_id,
                "entity_type": entity_type,
                "user_data": user_record,
            }

        elif entity_type == "STUDENT":
            # Registered student - route to student handler
            student_id = user_record.get("student_id")
            logger.info(
                "Student identified, routing to student handler",
                phone_number=phone_number,
                student_id=student_id,
            )
            return {
                "handler_type": HandlerType.STUDENT,
                "user_id": student_id,
                "entity_type": entity_type,
                "user_data": user_record,
            }

        else:
            # Unknown entity type - route to onboarding as fallback
            logger.warning(
                "Unknown entity type, routing to onboarding",
                phone_number=phone_number,
                entity_type=entity_type,
            )
            return {
                "handler_type": HandlerType.ONBOARDING,
                "user_id": None,
                "entity_type": entity_type,
                "user_data": user_record,
            }

    def extract_phone_number(self, webhook_payload: Dict[str, Any]) -> str:
        """
        Extract phone number from Twilio webhook payload.

        Args:
            webhook_payload: Twilio webhook POST data

        Returns:
            Phone number in E.164 format (without 'whatsapp:' prefix)

        Raises:
            ValueError: If phone number cannot be extracted

        Example:
            >>> router = MessageRouter()
            >>> phone = router.extract_phone_number({'From': 'whatsapp:+1234567890'})
            >>> print(phone)
            +1234567890
        """
        from_field = webhook_payload.get("From", "")

        if not from_field:
            raise ValueError("Missing 'From' field in webhook payload")

        # Remove 'whatsapp:' prefix if present
        phone_number = from_field.replace("whatsapp:", "")

        if not phone_number:
            raise ValueError("Empty phone number after removing prefix")

        logger.info(
            "Extracted phone number from webhook", from_field=from_field, phone_number=phone_number
        )

        return phone_number
