# API Endpoints Reference

FitAgent API endpoints for webhook handling and OAuth callbacks.

## Base URL

- **Local**: `http://localhost:8000`
- **Staging**: `https://api-staging.fitagent.com`
- **Production**: `https://api.fitagent.com`

## Authentication

### Webhook Endpoints
- **Method**: Twilio signature verification
- **Header**: `X-Twilio-Signature`
- **Validation**: HMAC-SHA1 signature

### OAuth Endpoints
- **Method**: OAuth 2.0 authorization code flow
- **State Parameter**: CSRF protection

## Endpoints

### POST /webhook

Receive incoming WhatsApp messages from Twilio.

**Request**:
```http
POST /webhook HTTP/1.1
Host: api.fitagent.com
Content-Type: application/x-www-form-urlencoded
X-Twilio-Signature: abc123...

From=whatsapp:+1234567890&
To=whatsapp:+15551234567&
Body=Hello&
MessageSid=SM123456789&
NumMedia=0
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| From | string | Yes | Sender's WhatsApp number (E.164 format) |
| To | string | Yes | Recipient's WhatsApp number |
| Body | string | Yes | Message text content |
| MessageSid | string | Yes | Unique message identifier |
| NumMedia | integer | No | Number of media attachments |
| MediaUrl0 | string | No | URL of first media attachment |
| MediaContentType0 | string | No | MIME type of first media |

**Response**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "queued",
  "message_id": "msg_123456789"
}
```

**Error Responses**:
```http
HTTP/1.1 403 Forbidden
{
  "error": "Invalid signature"
}

HTTP/1.1 400 Bad Request
{
  "error": "Missing required parameter: From"
}

HTTP/1.1 500 Internal Server Error
{
  "error": "Failed to queue message"
}
```

---

### GET /oauth/callback

Handle OAuth callback from calendar providers.

**Request**:
```http
GET /oauth/callback?code=abc123&state=trainer_id:provider HTTP/1.1
Host: api.fitagent.com
```

**Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| code | string | Yes | OAuth authorization code |
| state | string | Yes | State parameter (format: `trainer_id:provider`) |
| error | string | No | Error code if authorization failed |

**Response (Success)**:
```http
HTTP/1.1 200 OK
Content-Type: text/html

<html>
  <body>
    <h1>Calendar Connected!</h1>
    <p>You can close this window and return to WhatsApp.</p>
  </body>
</html>
```

**Response (Error)**:
```http
HTTP/1.1 400 Bad Request
Content-Type: text/html

<html>
  <body>
    <h1>Connection Failed</h1>
    <p>Error: Invalid authorization code</p>
  </body>
</html>
```

---

### GET /health

Health check endpoint for monitoring.

**Request**:
```http
GET /health HTTP/1.1
Host: api.fitagent.com
```

**Response**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "healthy",
  "timestamp": "2024-01-20T10:00:00Z",
  "version": "1.0.0",
  "services": {
    "dynamodb": "healthy",
    "s3": "healthy",
    "sqs": "healthy",
    "bedrock": "healthy"
  }
}
```

---

## Internal Endpoints (Lambda-to-Lambda)

These endpoints are not publicly accessible.

### Message Processor

**Trigger**: SQS message from webhook handler

**Event**:
```json
{
  "Records": [
    {
      "messageId": "msg_123",
      "body": "{\"from\": \"+1234567890\", \"body\": \"Hello\"}",
      "attributes": {
        "ApproximateReceiveCount": "1"
      }
    }
  ]
}
```

### Session Reminder

**Trigger**: EventBridge scheduled rule

**Event**:
```json
{
  "version": "0",
  "id": "event_123",
  "detail-type": "Scheduled Event",
  "source": "aws.events",
  "time": "2024-01-20T10:00:00Z",
  "detail": {}
}
```

### Payment Reminder

**Trigger**: EventBridge scheduled rule (monthly)

**Event**:
```json
{
  "version": "0",
  "id": "event_456",
  "detail-type": "Scheduled Event",
  "source": "aws.events",
  "time": "2024-01-01T09:00:00Z",
  "detail": {}
}
```

### Notification Sender

**Trigger**: SQS message from notification queue

**Event**:
```json
{
  "Records": [
    {
      "messageId": "notif_123",
      "body": "{\"trainer_id\": \"uuid\", \"student_ids\": [\"uuid1\"], \"message\": \"Hello\"}",
      "attributes": {
        "ApproximateReceiveCount": "1"
      }
    }
  ]
}
```

---

## Rate Limiting

### Webhook Endpoint
- **Limit**: 100 requests per minute per IP
- **Burst**: 200 requests
- **Response**: `429 Too Many Requests`

### OAuth Endpoint
- **Limit**: 10 requests per minute per IP
- **Burst**: 20 requests
- **Response**: `429 Too Many Requests`

---

## Error Codes

| Code | Description | Action |
|------|-------------|--------|
| 400 | Bad Request | Check request parameters |
| 403 | Forbidden | Verify signature or authentication |
| 404 | Not Found | Check endpoint URL |
| 429 | Too Many Requests | Implement backoff and retry |
| 500 | Internal Server Error | Contact support |
| 503 | Service Unavailable | Retry after delay |

---

## Webhook Signature Verification

### Algorithm
1. Concatenate URL + POST parameters (sorted)
2. Compute HMAC-SHA1 with auth token
3. Base64 encode result
4. Compare with `X-Twilio-Signature` header

### Example (Python)
```python
import hmac
import hashlib
import base64

def verify_signature(url, params, signature, auth_token):
    # Sort parameters
    sorted_params = sorted(params.items())
    
    # Concatenate URL + parameters
    data = url + ''.join(f'{k}{v}' for k, v in sorted_params)
    
    # Compute HMAC-SHA1
    mac = hmac.new(
        auth_token.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha1
    )
    
    # Base64 encode
    expected = base64.b64encode(mac.digest()).decode('utf-8')
    
    # Compare
    return hmac.compare_digest(expected, signature)
```

---

## Testing

### Local Testing
```bash
# Start server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Test webhook
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp:+1234567890&To=whatsapp:+15551234567&Body=test"

# Test health
curl http://localhost:8000/health
```

### Staging Testing
```bash
# Test webhook (requires valid signature)
curl -X POST https://api-staging.fitagent.com/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "X-Twilio-Signature: <signature>" \
  -d "From=whatsapp:+1234567890&Body=test"
```

---

## Monitoring

### CloudWatch Metrics
- `WebhookRequests`: Total webhook requests
- `WebhookErrors`: Failed webhook requests
- `OAuthCallbacks`: OAuth callback requests
- `MessageProcessingTime`: Average processing time

### CloudWatch Alarms
- High error rate (> 5%)
- High latency (> 3 seconds)
- Low throughput (< 10 req/min)

### Logs
- CloudWatch Logs: `/aws/lambda/fitagent-webhook-handler`
- Log format: JSON structured logging
- Retention: 30 days
