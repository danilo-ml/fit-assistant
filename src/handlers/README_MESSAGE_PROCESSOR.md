# Message Processor Lambda Function

## Overview

The message processor is a Lambda function triggered by SQS that processes WhatsApp messages asynchronously. It routes messages to appropriate handlers based on user identification and sends responses via Twilio.

**Requirements**: 13.4, 13.5, 13.6, 13.7

## Architecture

```
SQS Queue → Message Processor Lambda → Message Router → Handler (Onboarding/Trainer/Student) → Twilio Response
                                                                                              ↓
                                                                                         Dead Letter Queue (after 3 retries)
```

## Key Features

- **Asynchronous Processing**: Triggered by SQS for reliable message handling
- **User Identification**: Uses MessageRouter to identify users by phone number
- **Handler Routing**: Routes to OnboardingHandler, TrainerHandler, or StudentHandler
- **Response Delivery**: Sends responses via TwilioClient within 10 seconds
- **Retry Logic**: Automatic retry with exponential backoff (3 attempts via SQS)
- **Partial Batch Failure**: Returns failed message IDs for SQS retry
- **Dead Letter Queue**: Failed messages after max retries move to DLQ

## Message Flow

1. **SQS Trigger**: Lambda receives batch of messages from SQS queue
2. **Extract Message**: Parse message body containing WhatsApp message data
3. **Route Message**: Use MessageRouter to identify user type (trainer/student/unknown)
4. **Process Message**: Route to appropriate handler based on user type
5. **Send Response**: Send response text via TwilioClient
6. **Handle Failures**: Return failed message IDs for SQS retry

## SQS Event Structure

```json
{
  "Records": [
    {
      "messageId": "msg-123",
      "receiptHandle": "receipt-handle-123",
      "body": "{\"message_sid\": \"SM123\", \"from\": \"+1234567890\", \"body\": \"Hello\"}",
      "attributes": {
        "ApproximateReceiveCount": "1"
      },
      "messageAttributes": {
        "request_id": {"stringValue": "req-123"}
      }
    }
  ]
}
```

## Message Body Format

The message body (from webhook_handler) contains:

```json
{
  "message_sid": "SM123456",
  "from": "+1234567890",
  "to": "+0987654321",
  "body": "Hello, I want to schedule a session",
  "num_media": 0,
  "media_urls": [],
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req-123"
}
```

## Handler Types

### 1. Onboarding Handler
- **Trigger**: Unknown phone number (not in DynamoDB)
- **Purpose**: Welcome new users and initiate registration
- **Response**: Welcome message with options to register as trainer or student
- **Status**: Placeholder implementation (TODO: AI agent integration)

### 2. Trainer Handler
- **Trigger**: Phone number identified as registered trainer
- **Purpose**: Process trainer requests (schedule sessions, manage students, etc.)
- **Response**: AI-powered responses with tool execution
- **Status**: Placeholder implementation (TODO: AWS Strands integration)

### 3. Student Handler
- **Trigger**: Phone number identified as registered student
- **Purpose**: Process student requests (view sessions, confirm attendance, etc.)
- **Response**: AI-powered responses for student queries
- **Status**: Placeholder implementation (TODO: AWS Strands integration)

## Error Handling

### Retry Logic
- **Mechanism**: SQS automatic retry with exponential backoff
- **Max Attempts**: 3 retries
- **Backoff**: Exponential (e.g., 1s, 2s, 4s)
- **DLQ**: Messages move to dead-letter queue after max retries

### Partial Batch Failure
The function returns failed message IDs to SQS:

```python
{
  "batchItemFailures": [
    {"itemIdentifier": "msg-123"}
  ]
}
```

This allows SQS to retry only failed messages, not the entire batch.

### Error Scenarios

1. **Invalid JSON**: Message body cannot be parsed → Retry
2. **Routing Failure**: MessageRouter throws exception → Retry
3. **Twilio Failure**: Response sending fails → Retry
4. **Timeout**: Processing exceeds 10 seconds → Warning logged, continues
5. **Max Retries**: After 3 attempts → Move to DLQ

## Performance Targets

- **Processing Time**: < 10 seconds per message (Requirement 13.7)
- **Routing Time**: < 200ms for phone lookup (via MessageRouter)
- **Response Time**: < 5 seconds for Twilio API call
- **Batch Size**: Configurable (default: 10 messages per batch)

## Configuration

Environment variables (from `src/config.py`):

```python
sqs_queue_url: str              # SQS queue URL for incoming messages
dlq_url: str                    # Dead letter queue URL
twilio_account_sid: str         # Twilio account SID
twilio_auth_token: str          # Twilio auth token
twilio_whatsapp_number: str     # Twilio WhatsApp number
dynamodb_table: str             # DynamoDB table name
aws_endpoint_url: str           # LocalStack endpoint (local dev)
```

## Lambda Configuration

Recommended Lambda settings:

```yaml
FunctionName: fitagent-message-processor
Runtime: python3.12
Handler: src.handlers.message_processor.lambda_handler
Timeout: 30  # seconds
MemorySize: 512  # MB
ReservedConcurrentExecutions: 10  # Limit concurrency

Environment:
  Variables:
    SQS_QUEUE_URL: !Ref MessageQueue
    DLQ_URL: !Ref DeadLetterQueue
    DYNAMODB_TABLE: !Ref MainTable
    # ... other config

EventSourceMapping:
  Type: AWS::Lambda::EventSourceMapping
  Properties:
    EventSourceArn: !GetAtt MessageQueue.Arn
    FunctionName: !Ref MessageProcessorFunction
    BatchSize: 10
    MaximumBatchingWindowInSeconds: 5
    FunctionResponseTypes:
      - ReportBatchItemFailures
```

## Monitoring and Logging

### CloudWatch Logs

All logs are JSON-formatted for CloudWatch Insights:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Message processed successfully",
  "service": "fitagent",
  "request_id": "req-123",
  "phone_number": "***7890",
  "message_sid": "SM123456",
  "elapsed_seconds": 2.34
}
```

### CloudWatch Metrics

Key metrics to monitor:

- **ProcessedMessages**: Count of successfully processed messages
- **FailedMessages**: Count of failed messages
- **ProcessingTime**: Duration of message processing
- **DLQMessages**: Count of messages in dead letter queue
- **ThrottledMessages**: Count of throttled Lambda invocations

### CloudWatch Alarms

Recommended alarms:

1. **High DLQ Count**: Alert when DLQ has > 10 messages
2. **High Error Rate**: Alert when error rate > 5%
3. **Slow Processing**: Alert when p99 latency > 10 seconds
4. **Lambda Throttling**: Alert when throttled invocations > 0

## Testing

### Unit Tests

Run unit tests:

```bash
pytest tests/unit/test_message_processor.py -v
```

Test coverage:
- Lambda handler with single/multiple records
- Partial batch failure handling
- Routing to different handler types
- Error handling and retries
- Response sending

### Integration Tests

Test with LocalStack:

```bash
# Start LocalStack
docker-compose up -d

# Send test message to SQS
aws --endpoint-url=http://localhost:4566 sqs send-message \
  --queue-url http://localhost:4566/000000000000/fitagent-messages.fifo \
  --message-group-id "test-group" \
  --message-body '{"message_sid":"SM123","from":"+1234567890","body":"Hello"}'

# Check Lambda logs
aws --endpoint-url=http://localhost:4566 logs tail /aws/lambda/message-processor
```

### Manual Testing

Test with real Twilio webhook:

1. Configure Twilio webhook to point to API Gateway
2. Send WhatsApp message to Twilio number
3. Check CloudWatch logs for processing
4. Verify response received in WhatsApp

## Future Enhancements

### Phase 1: AI Agent Integration
- Replace placeholder handlers with AWS Strands integration
- Implement tool-calling architecture
- Add conversation state management

### Phase 2: Advanced Features
- Media handling (images, PDFs for receipts)
- Multi-language support
- Rich message formatting (buttons, lists)

### Phase 3: Optimization
- Batch processing optimization
- Caching for frequent queries
- Connection pooling for DynamoDB/Twilio

## Troubleshooting

### Messages Not Processing

1. Check SQS queue has messages: `aws sqs get-queue-attributes`
2. Check Lambda has event source mapping: `aws lambda list-event-source-mappings`
3. Check Lambda execution role has SQS permissions
4. Check CloudWatch logs for errors

### High DLQ Count

1. Check DLQ messages: `aws sqs receive-message --queue-url <dlq-url>`
2. Analyze error patterns in CloudWatch logs
3. Fix root cause and replay messages from DLQ

### Slow Processing

1. Check CloudWatch metrics for processing time
2. Analyze logs for bottlenecks (routing, Twilio API, etc.)
3. Increase Lambda memory if needed
4. Optimize DynamoDB queries

### Twilio Failures

1. Check Twilio account status and balance
2. Verify Twilio credentials in environment variables
3. Check Twilio API logs for errors
4. Verify phone numbers are in E.164 format

## Related Components

- **webhook_handler.py**: Receives webhooks and enqueues to SQS
- **message_router.py**: Routes messages based on phone number lookup
- **twilio_client.py**: Sends WhatsApp messages via Twilio API
- **dynamodb_client.py**: Queries user data from DynamoDB

## References

- [AWS Lambda SQS Event Source](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [SQS Partial Batch Failure](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#services-sqs-batchfailurereporting)
- [Twilio WhatsApp API](https://www.twilio.com/docs/whatsapp/api)
- [Requirements Document](../../.kiro/specs/fitagent-whatsapp-assistant/requirements.md)
- [Design Document](../../.kiro/specs/fitagent-whatsapp-assistant/design.md)
