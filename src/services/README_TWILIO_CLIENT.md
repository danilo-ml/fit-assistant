# TwilioClient Wrapper

## Overview

The `TwilioClient` class provides a wrapper around the Twilio WhatsApp API, offering methods for sending WhatsApp messages and validating webhook signatures. This implementation follows the project's architectural patterns and includes comprehensive error handling and logging.

## Features

- **Send WhatsApp Messages**: Send text messages with optional media attachments
- **Signature Validation**: Verify incoming webhook requests are from Twilio
- **Automatic Formatting**: Handles `whatsapp:` prefix formatting automatically
- **Structured Logging**: All operations are logged with context
- **Error Handling**: Graceful handling of Twilio API exceptions

## Usage

### Initialization

```python
from src.services.twilio_client import TwilioClient

# Using default settings from config
client = TwilioClient()

# Using custom credentials
client = TwilioClient(
    account_sid="AC123456789",
    auth_token="your_auth_token",
    whatsapp_number="+14155238886"
)
```

### Sending Messages

```python
# Send a simple text message
result = client.send_message(
    to="+1234567890",
    body="Your session is scheduled for tomorrow at 2 PM"
)

print(f"Message SID: {result['message_sid']}")
print(f"Status: {result['status']}")

# Send a message with media attachment
result = client.send_message(
    to="+1234567890",
    body="Here is your receipt",
    media_url="https://example.com/receipt.jpg"
)
```

### Validating Webhook Signatures

```python
# In your webhook handler
def webhook_handler(request):
    client = TwilioClient()
    
    # Extract signature and parameters
    signature = request.headers.get('X-Twilio-Signature')
    url = request.url  # Full URL including protocol and domain
    params = request.form.to_dict()
    
    # Validate signature
    if not client.validate_signature(url, params, signature):
        return {'statusCode': 403, 'body': 'Invalid signature'}
    
    # Process webhook...
```

## API Reference

### `__init__(account_sid, auth_token, whatsapp_number)`

Initialize the TwilioClient.

**Parameters:**
- `account_sid` (str, optional): Twilio account SID. Defaults to `settings.twilio_account_sid`
- `auth_token` (str, optional): Twilio auth token. Defaults to `settings.twilio_auth_token`
- `whatsapp_number` (str, optional): Twilio WhatsApp number. Defaults to `settings.twilio_whatsapp_number`

### `send_message(to, body, media_url=None)`

Send a WhatsApp message to a recipient.

**Parameters:**
- `to` (str): Recipient phone number in E.164 format (e.g., `+1234567890`)
- `body` (str): Message text content
- `media_url` (str, optional): URL for media attachment

**Returns:**
- `dict`: Message details including:
  - `message_sid`: Twilio message identifier
  - `status`: Message status (queued, sent, delivered, etc.)
  - `to`: Recipient phone number
  - `from`: Sender phone number
  - `body`: Message text
  - `date_created`: Creation timestamp (ISO 8601)
  - `date_sent`: Sent timestamp (ISO 8601)
  - `error_code`: Error code if failed
  - `error_message`: Error message if failed

**Raises:**
- `TwilioRestException`: If message sending fails

**Example:**
```python
result = client.send_message(
    to="+1234567890",
    body="Your session is scheduled for tomorrow at 2 PM"
)
```

### `validate_signature(url, params, signature)`

Validate Twilio webhook signature.

**Parameters:**
- `url` (str): Full URL of the webhook endpoint (including protocol and domain)
- `params` (dict): Dictionary of POST parameters from the webhook
- `signature` (str): X-Twilio-Signature header value from the request

**Returns:**
- `bool`: True if signature is valid, False otherwise

**Example:**
```python
is_valid = client.validate_signature(
    url="https://example.com/webhook",
    params={"From": "whatsapp:+1234567890", "Body": "Hello"},
    signature="abc123..."
)
```

### `_format_whatsapp_number(phone_number)` (static)

Format phone number with `whatsapp:` prefix if not already present.

**Parameters:**
- `phone_number` (str): Phone number in E.164 format

**Returns:**
- `str`: Phone number with `whatsapp:` prefix

## Error Handling

The TwilioClient handles errors gracefully:

1. **Twilio API Errors**: `TwilioRestException` is raised with details about the failure
2. **Network Errors**: Generic exceptions are logged and re-raised
3. **Signature Validation Errors**: Returns `False` instead of raising exceptions

All errors are logged with structured logging including:
- Error type
- Error message
- Request context (phone number, URL, etc.)

## Integration with Other Components

### Webhook Handler

```python
# src/handlers/webhook_handler.py
from src.services.twilio_client import TwilioClient

def lambda_handler(event, context):
    client = TwilioClient()
    
    # Validate signature
    signature = event['headers'].get('X-Twilio-Signature')
    url = event['requestContext']['domainName'] + event['path']
    params = parse_form_data(event['body'])
    
    if not client.validate_signature(url, params, signature):
        return {'statusCode': 403, 'body': 'Invalid signature'}
    
    # Process message...
```

### Notification Sender

```python
# src/handlers/notification_sender.py
from src.services.twilio_client import TwilioClient

def lambda_handler(event, context):
    client = TwilioClient()
    
    for record in event['Records']:
        message_data = json.loads(record['body'])
        
        try:
            result = client.send_message(
                to=message_data['recipient'],
                body=message_data['message']
            )
            logger.info(f"Notification sent: {result['message_sid']}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            raise  # Let SQS retry
```

### Message Router

```python
# src/services/message_router.py
from src.services.twilio_client import TwilioClient

def send_response(phone_number: str, message: str):
    client = TwilioClient()
    
    result = client.send_message(
        to=phone_number,
        body=message
    )
    
    return result['message_sid']
```

## Testing

The TwilioClient includes comprehensive unit tests covering:

- Initialization with default and custom settings
- Successful message sending
- Message sending with media attachments
- WhatsApp prefix formatting
- Error handling (Twilio exceptions, network errors)
- Signature validation (success, failure, edge cases)
- Integration workflows

Run tests:
```bash
pytest tests/unit/test_twilio_client.py -v
```

## Configuration

Required environment variables (set in `.env` or environment):

```bash
TWILIO_ACCOUNT_SID=AC123456789
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=+14155238886
```

## Security Considerations

1. **Signature Validation**: Always validate webhook signatures to prevent unauthorized message injection
2. **HTTPS Only**: Twilio requires HTTPS for webhook endpoints
3. **Token Security**: Never log or expose the auth token in plaintext
4. **Rate Limiting**: Respect Twilio's rate limits (handled at the application level)

## Requirements Validation

This implementation validates the following requirements:

- **Requirement 13.2**: Validates Twilio webhook signature to ensure message authenticity
- **Requirement 20.7**: Verifies Twilio webhook signatures to prevent unauthorized message injection

## Related Components

- `src/handlers/webhook_handler.py`: Receives incoming WhatsApp messages
- `src/handlers/notification_sender.py`: Sends broadcast notifications
- `src/services/message_router.py`: Routes messages and sends responses
- `src/utils/logging.py`: Structured logging utilities
- `src/config.py`: Environment configuration
