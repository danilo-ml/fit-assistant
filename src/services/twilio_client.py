"""
Twilio WhatsApp API client wrapper.
Provides methods for sending WhatsApp messages and validating webhook signatures.
"""

from typing import Optional
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class TwilioClient:
    """
    Wrapper for Twilio WhatsApp API operations.
    
    Provides:
    - send_message(): Send outbound WhatsApp messages
    - validate_signature(): Validate incoming webhook signatures
    """
    
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        whatsapp_number: Optional[str] = None
    ):
        """
        Initialize Twilio client.
        
        Args:
            account_sid: Twilio account SID (defaults to settings)
            auth_token: Twilio auth token (defaults to settings)
            whatsapp_number: Twilio WhatsApp number (defaults to settings)
        """
        # Get credentials from Secrets Manager or environment variables
        if account_sid is None or auth_token is None or whatsapp_number is None:
            creds = settings.get_twilio_credentials()
            self.account_sid = account_sid or creds['account_sid']
            self.auth_token = auth_token or creds['auth_token']
            self.whatsapp_number = whatsapp_number or creds['whatsapp_number']
        else:
            self.account_sid = account_sid
            self.auth_token = auth_token
            self.whatsapp_number = whatsapp_number
        
        # Initialize Twilio client
        self.client = Client(self.account_sid, self.auth_token)
        
        # Initialize request validator for signature verification
        self.validator = RequestValidator(self.auth_token)
        
        logger.info(
            "TwilioClient initialized",
            account_sid=self.account_sid[:8] + "..." if self.account_sid else None,
            whatsapp_number=self.whatsapp_number
        )
    
    def send_message(
        self,
        to: str,
        body: str,
        media_url: Optional[str] = None
    ) -> dict:
        """
        Send a WhatsApp message to a recipient.
        
        Args:
            to: Recipient phone number in E.164 format (e.g., +1234567890)
            body: Message text content
            media_url: Optional URL for media attachment
        
        Returns:
            dict: Message details including message_sid, status, and timestamps
            
        Raises:
            TwilioException: If message sending fails
        
        Example:
            >>> client = TwilioClient()
            >>> result = client.send_message(
            ...     to="+1234567890",
            ...     body="Your session is scheduled for tomorrow at 2 PM"
            ... )
            >>> print(result['message_sid'])
        """
        # Ensure phone numbers have whatsapp: prefix
        from_number = self._format_whatsapp_number(self.whatsapp_number)
        to_number = self._format_whatsapp_number(to)
        
        logger.info(
            "Sending WhatsApp message",
            to=to_number,
            body_length=len(body),
            has_media=media_url is not None
        )
        
        try:
            # Prepare message parameters
            message_params = {
                'from_': from_number,
                'to': to_number,
                'body': body
            }
            
            # Add media URL if provided
            if media_url:
                message_params['media_url'] = [media_url]
            
            # Send message via Twilio
            message = self.client.messages.create(**message_params)
            
            result = {
                'message_sid': message.sid,
                'status': message.status,
                'to': to,
                'from': self.whatsapp_number,
                'body': body,
                'date_created': message.date_created.isoformat() if message.date_created else None,
                'date_sent': message.date_sent.isoformat() if message.date_sent else None,
                'error_code': message.error_code,
                'error_message': message.error_message
            }
            
            logger.info(
                "WhatsApp message sent successfully",
                message_sid=message.sid,
                status=message.status,
                to=to_number
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Failed to send WhatsApp message",
                to=to_number,
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    def send_template_message(
        self,
        to: str,
        content_sid: str,
        content_variables: str,
    ) -> dict:
        """
        Send a WhatsApp template message using Twilio Content API.

        Uses content_sid and content_variables instead of body, enabling
        delivery of business-initiated messages outside the 24-hour
        customer service window.

        Args:
            to: Recipient phone number in E.164 format (e.g., +1234567890)
            content_sid: Twilio Content SID (HX + 32 hex chars)
            content_variables: JSON string of placeholder values,
                e.g. '{"1":"John","2":"Monday"}'

        Returns:
            dict with keys: message_sid, status, error_code, error_message

        Raises:
            TwilioException: If message sending fails due to network/timeout

        Example:
            >>> client = TwilioClient()
            >>> result = client.send_template_message(
            ...     to="+1234567890",
            ...     content_sid="HXb5b62575e6e4ff6129ad7c8efe1f983e",
            ...     content_variables='{"1":"John","2":"Monday 10 AM"}'
            ... )
            >>> print(result['message_sid'])
        """
        from twilio.base.exceptions import TwilioRestException

        from_number = self._format_whatsapp_number(self.whatsapp_number)
        to_number = self._format_whatsapp_number(to)

        logger.info(
            "Sending WhatsApp template message",
            to=to_number,
            content_sid=content_sid,
        )

        try:
            message = self.client.messages.create(
                from_=from_number,
                to=to_number,
                content_sid=content_sid,
                content_variables=content_variables,
            )

            result = {
                'message_sid': message.sid,
                'status': message.status,
                'error_code': message.error_code,
                'error_message': message.error_message,
            }

            logger.info(
                "WhatsApp template message sent successfully",
                message_sid=message.sid,
                status=message.status,
                to=to_number,
                content_sid=content_sid,
            )

            return result

        except TwilioRestException as e:
            if e.code == 63016:
                logger.error(
                    "Freeform message blocked outside customer service window. "
                    "Use a pre-approved template message instead.",
                    to=to_number,
                    error_code=e.code,
                    error=str(e),
                )
            elif 'content_sid' in str(e).lower() or 'content sid' in str(e).lower():
                logger.error(
                    "Invalid Content SID",
                    to=to_number,
                    content_sid=content_sid,
                    error_code=e.code,
                    error=str(e),
                )
            elif 'content_variables' in str(e).lower() or 'content variables' in str(e).lower():
                logger.error(
                    "Invalid Content Variables",
                    to=to_number,
                    content_sid=content_sid,
                    content_variables=content_variables,
                    error_code=e.code,
                    error=str(e),
                )
            else:
                logger.error(
                    "Failed to send WhatsApp template message",
                    to=to_number,
                    content_sid=content_sid,
                    error=str(e),
                    error_type=type(e).__name__,
                )

            return {
                'message_sid': None,
                'status': 'failed',
                'error_code': e.code,
                'error_message': str(e),
            }

        except Exception as e:
            logger.error(
                "Failed to send WhatsApp template message",
                to=to_number,
                content_sid=content_sid,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def validate_signature(
        self,
        url: str,
        params: dict,
        signature: str
    ) -> bool:
        """
        Validate Twilio webhook signature.
        
        Verifies that the webhook request came from Twilio by validating
        the X-Twilio-Signature header against the request URL and parameters.
        
        Args:
            url: Full URL of the webhook endpoint (including protocol and domain)
            params: Dictionary of POST parameters from the webhook
            signature: X-Twilio-Signature header value from the request
        
        Returns:
            bool: True if signature is valid, False otherwise
        
        Example:
            >>> client = TwilioClient()
            >>> is_valid = client.validate_signature(
            ...     url="https://example.com/webhook",
            ...     params={"From": "whatsapp:+1234567890", "Body": "Hello"},
            ...     signature="abc123..."
            ... )
            >>> if not is_valid:
            ...     raise ValueError("Invalid Twilio signature")
        """
        logger.info(
            "Validating Twilio webhook signature",
            url=url,
            has_signature=bool(signature)
        )
        
        try:
            is_valid = self.validator.validate(url, params, signature)
            
            if is_valid:
                logger.info("Twilio signature validation successful", url=url)
            else:
                logger.warning(
                    "Twilio signature validation failed",
                    url=url,
                    signature_prefix=signature[:10] + "..." if signature else None
                )
            
            return is_valid
            
        except Exception as e:
            logger.error(
                "Error during signature validation",
                url=url,
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    @staticmethod
    def _format_whatsapp_number(phone_number: str) -> str:
        """
        Format phone number with whatsapp: prefix if not already present.
        
        Args:
            phone_number: Phone number in E.164 format
        
        Returns:
            str: Phone number with whatsapp: prefix
        """
        if not phone_number:
            return phone_number
        
        if phone_number.startswith('whatsapp:'):
            return phone_number
        
        return f'whatsapp:{phone_number}'
