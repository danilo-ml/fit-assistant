# Multi-Agent Architecture with AWS Strands

## Overview

FitAgent uses AWS Strands SDK to implement a swarm-based multi-agent architecture. This pattern enables specialized agents to handle different aspects of the conversation, improving accuracy and maintainability.

## Swarm Pattern

The swarm pattern allows agents to:
- **Hand off** conversations to specialized agents
- **Share context** across agent transitions
- **Maintain state** throughout the conversation
- **Collaborate** to solve complex tasks

## Agent Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│                   Coordinator Agent                      │
│              (Amazon Nova Micro)                         │
│  - Intent classification                                 │
│  - Route to specialized agents                           │
│  - Handle greetings and general queries                  │
└────────────┬────────────────────────────────────────────┘
             │
    ┌────────┴────────┬────────┬────────┬────────┬────────┐
    ▼                 ▼        ▼        ▼        ▼        ▼
┌─────────┐    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Student │    │ Session │ │ Payment │ │Calendar │ │Notific. │
│  Agent  │    │  Agent  │ │  Agent  │ │  Agent  │ │  Agent  │
│ (Nova   │    │ (Nova   │ │ (Nova   │ │(Claude  │ │ (Nova   │
│  Lite)  │    │  Pro)   │ │  Lite)  │ │  Haiku) │ │  Micro) │
└─────────┘    └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

## Agent Specifications

### 1. Coordinator Agent
**Model**: Amazon Nova Micro (cost-optimized for routing)

**Responsibilities**:
- Classify user intent from incoming messages
- Route to appropriate specialized agent
- Handle greetings, help requests, and general queries
- Maintain conversation flow

**Tools**: None (routing only)

**Example Handoffs**:
- "Add a new student" → Student Agent
- "Schedule a session" → Session Agent
- "Record payment" → Payment Agent
- "Connect my calendar" → Calendar Agent
- "Send a message to all students" → Notification Agent

### 2. Student Agent
**Model**: Amazon Nova Lite (simple CRUD operations)

**Responsibilities**:
- Register new students
- Update student information
- View student list
- Delete students

**Tools**:
- `register_student(name, phone_number, email, notes)`
- `update_student(student_id, **updates)`
- `view_students(trainer_id)`
- `delete_student(student_id)`

**Example Conversations**:
- "Add John Doe, phone +1234567890"
- "Show me all my students"
- "Update John's email to john@example.com"

### 3. Session Agent
**Model**: Amazon Nova Pro (complex scheduling logic)

**Responsibilities**:
- Schedule training sessions
- Detect scheduling conflicts
- Reschedule or cancel sessions
- View upcoming sessions
- Handle session confirmations

**Tools**:
- `schedule_session(trainer_id, student_id, datetime, duration, location, notes)`
- `reschedule_session(session_id, new_datetime)`
- `cancel_session(session_id, reason)`
- `view_sessions(trainer_id, start_date, end_date)`
- `confirm_session(session_id, confirmed)`

**Conflict Detection**:
- Checks for overlapping sessions
- Validates student availability
- Considers calendar sync conflicts

**Example Conversations**:
- "Schedule session with John tomorrow at 3pm"
- "Reschedule John's session to Friday at 4pm"
- "Cancel tomorrow's session with Sarah"

### 4. Payment Agent
**Model**: Amazon Nova Lite (simple CRUD operations)

**Responsibilities**:
- Register payment receipts
- View payment history
- Track payment status
- Handle payment confirmations

**Tools**:
- `register_payment(trainer_id, student_id, amount, currency, payment_date, receipt_url, notes)`
- `view_payments(trainer_id, student_id, status)`
- `update_payment_status(payment_id, status)`

**Receipt Handling**:
- Accepts image uploads via WhatsApp
- Stores in S3 with encryption
- Generates presigned URLs for viewing

**Example Conversations**:
- "Record payment from John, $100" (with image)
- "Show me all pending payments"
- "Mark payment #123 as confirmed"

### 5. Calendar Agent
**Model**: Claude 3 Haiku (OAuth complexity)

**Responsibilities**:
- Connect Google Calendar or Outlook
- Sync sessions to calendar
- Handle OAuth flow
- Disconnect calendar

**Tools**:
- `connect_calendar(trainer_id, provider)`
- `sync_calendar(trainer_id)`
- `disconnect_calendar(trainer_id)`
- `view_calendar_status(trainer_id)`

**OAuth Flow**:
1. Generate OAuth URL
2. Send to trainer via WhatsApp
3. Handle callback from OAuth provider
4. Store encrypted tokens in Secrets Manager
5. Sync existing sessions to calendar

**Example Conversations**:
- "Connect my Google Calendar"
- "Sync my calendar"
- "Disconnect my calendar"

### 6. Notification Agent
**Model**: Amazon Nova Micro (simple message queuing)

**Responsibilities**:
- Send broadcast messages to students
- Queue notifications to SQS
- Handle notification confirmations

**Tools**:
- `send_notification(trainer_id, student_ids, message)`
- `send_broadcast(trainer_id, message)`

**Rate Limiting**:
- Maximum 10 messages per minute
- Queued via SQS for async delivery

**Example Conversations**:
- "Send a message to all students: Class cancelled tomorrow"
- "Notify John and Sarah about the schedule change"

## Context Sharing

### Conversation State
Each agent has access to:
- **Trainer ID**: Current trainer context
- **Student ID**: Current student (if applicable)
- **Session ID**: Current session (if applicable)
- **Message History**: Last 10 messages
- **Conversation TTL**: 24 hours

### State Persistence
- Stored in DynamoDB with TTL
- Retrieved on each message
- Updated after agent response
- Cleared after 24 hours of inactivity

## Agent Handoff Protocol

### Handoff Triggers
1. **Intent Change**: User switches topics
2. **Task Completion**: Agent finishes its task
3. **Error Handling**: Agent cannot complete task

### Handoff Process
```python
# Coordinator identifies intent
intent = classify_intent(message)

# Hand off to specialized agent
if intent == "schedule_session":
    response = session_agent.run(
        context=conversation_state,
        message=message
    )
```

### Context Preservation
- Previous agent's context passed to new agent
- Conversation history maintained
- User doesn't need to repeat information

## Model Selection Rationale

| Agent | Model | Cost/1M Tokens | Rationale |
|-------|-------|----------------|-----------|
| Coordinator | Nova Micro | $0.035 | Simple routing, high volume |
| Student | Nova Lite | $0.06 | CRUD operations, moderate complexity |
| Session | Nova Pro | $0.80 | Complex scheduling logic, conflict detection |
| Payment | Nova Lite | $0.06 | CRUD operations, moderate complexity |
| Calendar | Claude Haiku | $0.25 | OAuth complexity, API integration |
| Notification | Nova Micro | $0.035 | Simple message queuing |

**Cost Optimization**: Using cheaper models for simple tasks reduces inference costs by ~70% compared to using Claude Sonnet for all agents.

## Error Handling

### Agent-Level Errors
- **Validation Errors**: Return user-friendly message
- **Tool Errors**: Retry with exponential backoff
- **Model Errors**: Fall back to simpler model

### System-Level Errors
- **SQS Dead-Letter Queue**: Failed messages after 3 retries
- **CloudWatch Alarms**: Alert on high error rates
- **Manual Intervention**: Review DLQ messages

## Testing Strategy

### Unit Tests
- Test each agent independently
- Mock tool functions
- Validate intent classification

### Integration Tests
- Test agent handoffs
- Validate context sharing
- Test end-to-end flows

### Property-Based Tests
- Test scheduling conflict detection
- Validate payment calculations
- Test notification rate limiting

## Performance Metrics

### Agent Metrics
- **Invocation Count**: Number of times agent is called
- **Average Duration**: Time to generate response
- **Error Rate**: Percentage of failed invocations
- **Handoff Rate**: Percentage of conversations handed off

### Model Metrics
- **Token Usage**: Input and output tokens per agent
- **Cost per Conversation**: Total inference cost
- **Latency**: Time to first token and total time

## Future Enhancements

- **Agent Learning**: Fine-tune models on conversation data
- **Dynamic Routing**: ML-based intent classification
- **Multi-Turn Planning**: Agents plan multi-step tasks
- **Human-in-the-Loop**: Escalate complex queries to human support
- **Agent Analytics**: Dashboard for agent performance
