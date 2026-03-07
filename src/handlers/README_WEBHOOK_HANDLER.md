# Webhook Handler

Lambda function that receives Twilio WhatsApp webhook POST requests, validates signatures, and enqueues messages to SQS for async processing.

## Requirements

Validates: Requirements 13.1, 13.2, 13.3

## Functionality

1. **Receives Twilio Webhooks**: Accepts POST requests from Twilio's WhatsApp API via API Gateway
2. **Signature Validation**: Validates X-Twilio-Signature header to ensure request authenticity
3. **Message Enqueueing**: Sends validated messages to SQS queue for async processing
4. **TwiML Response**: Returns empty TwiML response to acknowledge receipt

## Performance Target

- Complete processing within 100ms to meet Twilio's timeout requirements
- Signature validation and SQS enqueueing are optimized for speed

## API Gateway Event Structure

```python
{
    "httpMethod": "POST",
    "headers": {
        "X-Twilio-Signature": "signature_value",
        "Host": "api.example.com",
        "X-Forwarded-Proto": "https"
    },
    "body": "MessageSid=SM123&From=whatsapp:+1234567890&Body=Hello",
    "requestContext": {
        "requestId": "abc-123",
        "domainName": "api.example.com",
        "path": "/webhook"
    }
}
```

## SQS Message Format

```python
{
    "message_sid": "SM123456",
    "from": "+1234567890",
    "to": "+0987654321",
    "body": "Hello World",
    "num_media": 0,
    "media_urls": [],
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "abc-123"
}
```

## Response Format

### Success (200 OK)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response></Response>
```

### Missing Signature (400 Bad Request)
```json
{
    "error": "Missing X-Twilio-Signature header"
}
```

### Invalid Signature (403 Forbidden)
```json
{
    "error": "Invalid Twilio signature"
}
```

## Error Handling

- **Missing Signature**: Returns 400 error, message not enqueued
- **Invalid Signature**: Returns 403 error, message not enqueued
- **SQS Failure**: Returns 200 to prevent Twilio retries (message will be in DLQ)
- **Other Errors**: Returns 200 to prevent Twilio retries, logs error for investigation

## Configuration

Required environment variables (from `src/config.py`):
- `sqs_queue_url`: SQS queue URL for message enqueueing
- `twilio_account_sid`: Twilio account SID
- `twilio_auth_token`: Twilio auth token for signature validation
- `aws_region`: AWS region
- `aws_endpoint_url`: AWS endpoint (for LocalStack)

## Usage

### Deploy as Lambda Function

```bash
# Package handler
zip -r webhook_handler.zip src/

# Deploy via CloudFormation or AWS CLI
aws lambda create-function \
  --function-name webhook-handler \
  --runtime python3.12 \
  --handler src.handlers.webhook_handler.lambda_handler \
  --zip-file fileb://webhook_handler.zip \
  --role arn:aws:iam::ACCOUNT:role/lambda-execution-role
```

### Configure API Gateway

```yaml
# CloudFormation snippet
WebhookApi:
  Type: AWS::ApiGateway::RestApi
  Properties:
    Name: FitAgent-Webhook
    
WebhookResource:
  Type: AWS::ApiGateway::Resource
  Properties:
    RestApiId: !Ref WebhookApi
    ParentId: !GetAtt WebhookApi.RootResourceId
    PathPart: webhook
    
WebhookMethod:
  Type: AWS::ApiGateway::Method
  Properties:
    RestApiId: !Ref WebhookApi
    ResourceId: !Ref WebhookResource
    HttpMethod: POST
    AuthorizationType: NONE
    Integration:
      Type: AWS_PROXY
      IntegrationHttpMethod: POST
      Uri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${WebhookHandler.Arn}/invocations
```

### Configure Twilio Webhook

In Twilio Console:
1. Go to WhatsApp Sandbox or Phone Number settings
2. Set "When a message comes in" webhook URL to: `https://your-api-gateway-url/webhook`
3. Set HTTP method to POST

## Testing

Run unit tests:
```bash
pytest tests/unit/test_webhook_handler.py -v
```

Test coverage includes:
- Form body parsing (URL-encoded, special characters)
- URL reconstruction for signature validation
- Media URL extraction (single and multiple attachments)
- Signature validation (valid, invalid, missing)
- SQS enqueueing (success and failure)
- Error handling (malformed body, empty body)
- Request ID propagation
- Phone number extraction

## Security

- **Signature Validation**: All requests must have valid Twilio signature
- **HTTPS Only**: API Gateway should enforce HTTPS
- **Rate Limiting**: API Gateway rate limiting configured (100 req/min per IP)
- **No Sensitive Data Logging**: Phone numbers are masked in logs

## Monitoring

Key CloudWatch metrics to monitor:
- Lambda invocation count
- Lambda duration (should be < 100ms)
- Lambda errors
- SQS messages sent
- 403 errors (invalid signatures - potential attack)

## Related Components

- `src/services/twilio_client.py`: Twilio signature validation
- `src/handlers/message_processor.py`: Processes messages from SQS
- `src/utils/logging.py`: Structured logging with phone number masking
