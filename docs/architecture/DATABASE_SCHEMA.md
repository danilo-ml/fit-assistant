# DynamoDB Single-Table Design

## Overview

FitAgent uses a single DynamoDB table (`fitagent-main`) to store all entities. This design pattern optimizes for:
- **Cost efficiency**: One table instead of multiple
- **Query performance**: GSIs for common access patterns
- **Scalability**: On-demand capacity mode
- **Flexibility**: Easy to add new entity types

## Table Structure

### Primary Keys

| Attribute | Type | Description |
|-----------|------|-------------|
| `PK` | String (Partition Key) | Entity type + ID (e.g., `TRAINER#uuid`) |
| `SK` | String (Sort Key) | Related entity or metadata (e.g., `METADATA`, `SESSION#uuid`) |

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `entity_type` | String | Entity type (TRAINER, STUDENT, SESSION, PAYMENT, CONVERSATION) |
| `phone_number` | String | User's WhatsApp phone number |
| `created_at` | String (ISO 8601) | Creation timestamp |
| `updated_at` | String (ISO 8601) | Last update timestamp |
| `ttl` | Number (Unix timestamp) | Auto-deletion timestamp (conversations only) |
| `data` | Map | Entity-specific attributes |

## Entity Patterns

### 1. Trainer Entity

**PK**: `TRAINER#{trainer_id}`  
**SK**: `METADATA`

**Attributes**:
```json
{
  "PK": "TRAINER#550e8400-e29b-41d4-a716-446655440000",
  "SK": "METADATA",
  "entity_type": "TRAINER",
  "phone_number": "+1234567890",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "data": {
    "name": "John Smith",
    "email": "john@example.com",
    "business_name": "FitPro Training",
    "timezone": "America/New_York",
    "calendar_provider": "google",
    "calendar_connected": true,
    "feature_flags": {
      "session_confirmation": true,
      "payment_reminders": true
    }
  }
}
```

### 2. Student Entity

**PK**: `TRAINER#{trainer_id}`  
**SK**: `STUDENT#{student_id}`

**Attributes**:
```json
{
  "PK": "TRAINER#550e8400-e29b-41d4-a716-446655440000",
  "SK": "STUDENT#660e8400-e29b-41d4-a716-446655440001",
  "entity_type": "STUDENT",
  "phone_number": "+1987654321",
  "created_at": "2024-01-16T14:20:00Z",
  "updated_at": "2024-01-16T14:20:00Z",
  "data": {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "notes": "Prefers morning sessions",
    "active": true
  }
}
```

**Reverse Lookup** (for student-initiated messages):

**PK**: `STUDENT#{student_id}`  
**SK**: `TRAINER#{trainer_id}`

```json
{
  "PK": "STUDENT#660e8400-e29b-41d4-a716-446655440001",
  "SK": "TRAINER#550e8400-e29b-41d4-a716-446655440000",
  "entity_type": "STUDENT_TRAINER_LINK",
  "phone_number": "+1987654321",
  "created_at": "2024-01-16T14:20:00Z"
}
```

### 3. Session Entity

**PK**: `TRAINER#{trainer_id}`  
**SK**: `SESSION#{session_id}`

**Attributes**:
```json
{
  "PK": "TRAINER#550e8400-e29b-41d4-a716-446655440000",
  "SK": "SESSION#770e8400-e29b-41d4-a716-446655440002",
  "entity_type": "SESSION",
  "created_at": "2024-01-17T09:00:00Z",
  "updated_at": "2024-01-17T09:00:00Z",
  "data": {
    "student_id": "660e8400-e29b-41d4-a716-446655440001",
    "student_name": "Jane Doe",
    "session_datetime": "2024-01-20T10:00:00Z",
    "duration_minutes": 60,
    "location": "Main Gym",
    "status": "scheduled",
    "confirmed": false,
    "notes": "Focus on cardio",
    "calendar_event_id": "google_event_123"
  }
}
```

### 4. Payment Entity

**PK**: `TRAINER#{trainer_id}`  
**SK**: `PAYMENT#{payment_id}`

**Attributes**:
```json
{
  "PK": "TRAINER#550e8400-e29b-41d4-a716-446655440000",
  "SK": "PAYMENT#880e8400-e29b-41d4-a716-446655440003",
  "entity_type": "PAYMENT",
  "created_at": "2024-01-18T15:30:00Z",
  "updated_at": "2024-01-18T15:30:00Z",
  "data": {
    "student_id": "660e8400-e29b-41d4-a716-446655440001",
    "student_name": "Jane Doe",
    "amount": 100.00,
    "currency": "USD",
    "payment_date": "2024-01-18",
    "payment_status": "confirmed",
    "receipt_url": "https://s3.amazonaws.com/...",
    "notes": "January sessions"
  }
}
```

### 5. Conversation State Entity

**PK**: `CONVERSATION#{phone_number}`  
**SK**: `METADATA`

**Attributes**:
```json
{
  "PK": "CONVERSATION#+1234567890",
  "SK": "METADATA",
  "entity_type": "CONVERSATION",
  "phone_number": "+1234567890",
  "created_at": "2024-01-19T11:00:00Z",
  "updated_at": "2024-01-19T11:05:00Z",
  "ttl": 1705752300,
  "data": {
    "trainer_id": "550e8400-e29b-41d4-a716-446655440000",
    "current_agent": "session_agent",
    "context": {
      "student_id": "660e8400-e29b-41d4-a716-446655440001",
      "pending_action": "schedule_session"
    },
    "message_history": [
      {"role": "user", "content": "Schedule session with Jane"},
      {"role": "assistant", "content": "When would you like to schedule?"}
    ]
  }
}
```

## Global Secondary Indexes (GSIs)

### 1. Phone Number Index

**Purpose**: User identification and routing

**Keys**:
- **PK**: `phone_number`
- **SK**: `entity_type`

**Projection**: ALL

**Query Pattern**:
```python
# Find user by phone number
response = table.query(
    IndexName='phone-number-index',
    KeyConditionExpression='phone_number = :phone',
    ExpressionAttributeValues={':phone': '+1234567890'}
)
```

**Use Cases**:
- Identify if incoming message is from trainer or student
- Route message to correct handler
- Load user context

### 2. Session Date Index

**Purpose**: Calendar queries and reminders

**Keys**:
- **PK**: `trainer_id` (from data.trainer_id)
- **SK**: `session_datetime` (from data.session_datetime)

**Projection**: ALL

**Query Pattern**:
```python
# Get sessions for date range
response = table.query(
    IndexName='session-date-index',
    KeyConditionExpression='trainer_id = :trainer AND session_datetime BETWEEN :start AND :end',
    ExpressionAttributeValues={
        ':trainer': 'TRAINER#550e8400-e29b-41d4-a716-446655440000',
        ':start': '2024-01-20T00:00:00Z',
        ':end': '2024-01-20T23:59:59Z'
    }
)
```

**Use Cases**:
- Check for scheduling conflicts
- Query sessions for specific date range
- EventBridge reminder queries

### 3. Payment Status Index

**Purpose**: Payment tracking and reminders

**Keys**:
- **PK**: `trainer_id` (from data.trainer_id)
- **SK**: `payment_status#created_at` (composite)

**Projection**: ALL

**Query Pattern**:
```python
# Get pending payments
response = table.query(
    IndexName='payment-status-index',
    KeyConditionExpression='trainer_id = :trainer AND begins_with(payment_status_created, :status)',
    ExpressionAttributeValues={
        ':trainer': 'TRAINER#550e8400-e29b-41d4-a716-446655440000',
        ':status': 'pending#'
    }
)
```

**Use Cases**:
- Query payments by status
- Payment reminder queries
- Financial reporting

## Access Patterns

### 1. Get Trainer by Phone Number
```python
# Query phone-number-index
response = table.query(
    IndexName='phone-number-index',
    KeyConditionExpression='phone_number = :phone AND entity_type = :type',
    ExpressionAttributeValues={
        ':phone': '+1234567890',
        ':type': 'TRAINER'
    }
)
```

### 2. Get All Students for Trainer
```python
# Query main table
response = table.query(
    KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
    ExpressionAttributeValues={
        ':pk': 'TRAINER#550e8400-e29b-41d4-a716-446655440000',
        ':sk': 'STUDENT#'
    }
)
```

### 3. Get Sessions for Date Range
```python
# Query session-date-index
response = table.query(
    IndexName='session-date-index',
    KeyConditionExpression='trainer_id = :trainer AND session_datetime BETWEEN :start AND :end',
    ExpressionAttributeValues={
        ':trainer': 'TRAINER#550e8400-e29b-41d4-a716-446655440000',
        ':start': '2024-01-20T00:00:00Z',
        ':end': '2024-01-27T23:59:59Z'
    }
)
```

### 4. Check for Session Conflicts
```python
# Query session-date-index for overlapping time
response = table.query(
    IndexName='session-date-index',
    KeyConditionExpression='trainer_id = :trainer AND session_datetime BETWEEN :start AND :end',
    FilterExpression='#status = :status',
    ExpressionAttributeNames={'#status': 'data.status'},
    ExpressionAttributeValues={
        ':trainer': 'TRAINER#550e8400-e29b-41d4-a716-446655440000',
        ':start': '2024-01-20T10:00:00Z',
        ':end': '2024-01-20T11:00:00Z',
        ':status': 'scheduled'
    }
)
```

### 5. Get Conversation State
```python
# Get item directly
response = table.get_item(
    Key={
        'PK': 'CONVERSATION#+1234567890',
        'SK': 'METADATA'
    }
)
```

## Capacity Planning

### On-Demand Mode
- **Read**: $0.25 per million read request units
- **Write**: $1.25 per million write request units
- **Storage**: $0.25 per GB-month

### Estimated Usage (per trainer per month)
- **Reads**: ~10,000 (conversations, queries)
- **Writes**: ~1,000 (sessions, payments, conversations)
- **Storage**: ~10 MB

### Cost Estimate
- **Reads**: 10,000 × $0.25 / 1M = $0.0025
- **Writes**: 1,000 × $1.25 / 1M = $0.00125
- **Storage**: 0.01 GB × $0.25 = $0.0025
- **Total per trainer**: ~$0.01/month

## TTL Configuration

### Conversation State TTL
- **Attribute**: `ttl` (Unix timestamp)
- **Duration**: 24 hours after last update
- **Purpose**: Auto-delete inactive conversations
- **Benefit**: Reduce storage costs and maintain privacy

### Implementation
```python
# Set TTL when creating conversation
ttl = int(time.time()) + (24 * 60 * 60)  # 24 hours
item['ttl'] = ttl
```

## Backup & Recovery

### Point-in-Time Recovery (PITR)
- **Enabled**: Yes
- **Retention**: 35 days
- **RPO**: 5 minutes

### On-Demand Backups
- **Frequency**: Weekly
- **Retention**: 90 days
- **Purpose**: Long-term archival

## Best Practices

1. **Use Composite Sort Keys**: Combine attributes for efficient queries
2. **Minimize Item Size**: Keep items under 4 KB for best performance
3. **Use Sparse Indexes**: Only project necessary attributes to GSIs
4. **Batch Operations**: Use BatchGetItem and BatchWriteItem for bulk operations
5. **Conditional Writes**: Use ConditionExpression to prevent race conditions
6. **TTL for Ephemeral Data**: Auto-delete temporary data to reduce costs
7. **Monitor Throttling**: Set CloudWatch alarms for throttled requests
