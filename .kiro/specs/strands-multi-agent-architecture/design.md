# Design Document: Strands Multi-Agent Architecture

## Overview

This design document specifies the migration of FitAgent from a single-agent architecture to a Swarm-based multi-agent architecture using AWS Bedrock Agents (Strands Agents SDK). The migration transforms the current monolithic AIAgent class into a coordinated team of 6 specialized agents that autonomously collaborate through handoffs to handle student management, session scheduling, payment tracking, calendar integration, and notifications.

### Current Architecture

The existing system uses a single AIAgent class (`src/services/ai_agent.py`) that:
- Processes all WhatsApp messages through one Claude model instance
- Maintains a flat tool registry with 11 tool functions
- Executes tools sequentially based on Bedrock's tool-calling API
- Manages conversation context through message history
- Operates within a 5-second response time budget

### Target Architecture

The new Swarm-based architecture will:
- Deploy 6 specialized agents (Coordinator, Student, Session, Payment, Calendar, Notification)
- Use autonomous agent handoffs via `handoff_to_agent` tool
- Maintain Shared_Context for conversation continuity across agents
- Use Invocation_State for multi-tenancy isolation (trainer_id)
- Operate within a 10-second response time budget (120s execution timeout)
- Support gradual migration via feature flag

### Key Benefits

1. **Specialization**: Each agent focuses on a specific domain with tailored prompts and tools
2. **Scalability**: Agents can be optimized independently (different models, caching strategies)
3. **Maintainability**: Clear separation of concerns makes debugging and updates easier
4. **Extensibility**: New agents can be added without modifying existing ones
5. **Cost Efficiency**: Use Amazon Nova models for routine tasks, Claude for complex reasoning

### Migration Strategy

The migration will be phased using a feature flag (`ENABLE_MULTI_AGENT`) to toggle between architectures:
- Phase 1: Implement Swarm infrastructure and Coordinator agent
- Phase 2: Migrate specialized agents one at a time
- Phase 3: Add session confirmation feature
- Phase 4: Full rollout with monitoring



## Architecture

### Swarm Pattern Overview

The Swarm pattern is a multi-agent orchestration approach where specialized agents autonomously hand off tasks to each other based on conversation context. Unlike the Graph pattern (pre-defined paths) or Workflow pattern (rigid sequences), the Swarm pattern allows emergent collaboration through the `handoff_to_agent` tool.

```
┌─────────────────────────────────────────────────────────────────┐
│                        WhatsApp Message                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Webhook Handler (Lambda)                      │
│                  Routes to Message Processor                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Message Processor (Lambda)                     │
│              Identifies trainer_id via phone lookup              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Swarm Orchestrator                          │
│                  (Entry_Agent: Coordinator)                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
              ┌──────────────┴──────────────┐
              │   Autonomous Handoffs via   │
              │    handoff_to_agent tool    │
              └──────────────┬──────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Student    │    │   Session    │    │   Payment    │
│    Agent     │    │    Agent     │    │    Agent     │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                    │
       │                   ▼                    │
       │           ┌──────────────┐            │
       │           │   Calendar   │            │
       │           │    Agent     │            │
       │           └──────────────┘            │
       │                                       │
       └───────────────────┬───────────────────┘
                           │
                           ▼
                  ┌──────────────┐
                  │ Notification │
                  │    Agent     │
                  └──────────────┘
```

### Agent Topology



| Agent | Role | Tools | Handoff Targets |
|-------|------|-------|-----------------|
| Coordinator | Entry point, intent analysis, entity extraction | None (orchestration only) | All agents |
| Student | Student registration, updates, queries | register_student, view_students, update_student | Session, Payment |
| Session | Session scheduling, rescheduling, cancellation | schedule_session, reschedule_session, cancel_session, view_calendar, view_session_history | Calendar, Payment |
| Payment | Payment registration, confirmation, tracking | register_payment, confirm_payment, view_payments | None (terminal) |
| Calendar | Calendar integration (Google, Outlook) | connect_calendar, sync_calendar_event | None (terminal) |
| Notification | Broadcast messages to students | send_notification | None (terminal) |

### Handoff Flow Examples

**Example 1: Schedule Session**
```
User: "Schedule a session with John tomorrow at 2pm for 60 minutes"
  ↓
Coordinator: Extracts entities (student_name="John", date="tomorrow", time="2pm", duration=60)
  ↓ handoff_to_agent(Session_Agent)
Session_Agent: Validates student exists, checks conflicts, creates session
  ↓ handoff_to_agent(Calendar_Agent)
Calendar_Agent: Syncs event to Google Calendar
  ↓ Response
User: "Session scheduled and synced to your calendar"
```

**Example 2: Register Student then Schedule**
```
User: "Add a new student Sarah, phone +14155551234, email sarah@example.com, goal is weight loss"
  ↓
Coordinator: Identifies student registration intent
  ↓ handoff_to_agent(Student_Agent)
Student_Agent: Registers student, stores in DynamoDB
  ↓ Response with follow-up
User: "Sarah registered! Would you like to schedule a session?"
User: "Yes, tomorrow at 3pm"
  ↓
Coordinator: Retrieves previous context (student_name="Sarah")
  ↓ handoff_to_agent(Session_Agent)
Session_Agent: Schedules session using student from Shared_Context
```

### Shared_Context Structure

Shared_Context is the working memory available to all agents, containing:

```python
{
    "original_request": "Schedule a session with John tomorrow at 2pm",
    "extracted_entities": {
        "student_name": "John",
        "date": "2024-01-15",
        "time": "14:00",
        "duration_minutes": 60
    },
    "handoff_history": [
        {
            "from_agent": "Coordinator_Agent",
            "to_agent": "Session_Agent",
            "reason": "User wants to schedule a session",
            "timestamp": "2024-01-14T10:30:00Z"
        }
    ],
    "agent_contributions": {
        "Session_Agent": {
            "session_id": "abc123",
            "session_datetime": "2024-01-15T14:00:00Z",
            "conflict_check": "passed"
        }
    },
    "handoff_count": 2,
    "conversation_id": "conv_xyz789"
}
```

### Invocation_State Structure

Invocation_State contains configuration and objects passed via kwargs, NOT visible in LLM prompts:

```python
{
    "trainer_id": "trainer_abc123",
    "phone_number": "+14155559999",
    "db_client": <DynamoDBClient instance>,
    "s3_client": <S3Client instance>,
    "feature_flags": {
        "enable_calendar_sync": True,
        "enable_session_confirmation": True
    }
}
```

### Timeout Configuration



| Configuration | Value | Rationale |
|---------------|-------|-----------|
| max_handoffs | 5-7 | Prevents infinite loops while allowing complex workflows |
| node_timeout | 30s | Individual agent execution limit |
| execution_timeout | 120s | Total swarm execution limit (well within 10s response budget for most cases) |
| response_time_budget | 10s | WhatsApp user experience requirement |

The execution_timeout is set to 120s to handle edge cases (calendar API delays, retries), but typical conversations complete in 3-5 seconds.

## Components and Interfaces

### Coordinator Agent

**Responsibilities:**
- Entry point for all WhatsApp messages
- Intent analysis and entity extraction
- Handoff decision-making
- General conversation handling (greetings, help)

**System Prompt:**
```
You are the Coordinator Agent for FitAgent, an AI assistant helping personal trainers manage their business.

Your role is to:
1. Analyze user intent from WhatsApp messages
2. Extract key entities (student names, dates, times, amounts)
3. Hand off to the appropriate specialized agent using handoff_to_agent tool
4. Handle general conversation (greetings, help requests) directly

Available specialized agents:
- Student_Agent: Student registration, updates, queries
- Session_Agent: Session scheduling, rescheduling, cancellation
- Payment_Agent: Payment registration, confirmation, tracking
- Calendar_Agent: Calendar integration (Google, Outlook)
- Notification_Agent: Broadcast messages to students

Guidelines:
- If intent is ambiguous, ask clarifying questions before handing off
- Include extracted entities in handoff reason
- For multi-step workflows, hand off to the first agent in the sequence
- Handle greetings and help requests without handoff
- Be concise and friendly

Example handoffs:
- "Schedule a session with John" → handoff_to_agent(Session_Agent, reason="User wants to schedule session with student John")
- "Add new student Sarah" → handoff_to_agent(Student_Agent, reason="User wants to register new student Sarah")
- "Show my payments" → handoff_to_agent(Payment_Agent, reason="User wants to view payment history")
```

**Tools:**
- `handoff_to_agent(agent_name: str, reason: str)` - Transfer control to specialized agent

**Handoff Logic:**
- Student keywords (register, add, new student) → Student_Agent
- Session keywords (schedule, book, reschedule, cancel) → Session_Agent
- Payment keywords (payment, paid, receipt) → Payment_Agent
- Calendar keywords (connect, sync, calendar) → Calendar_Agent
- Notification keywords (send message, notify, broadcast) → Notification_Agent

### Student Agent

**Responsibilities:**
- Student registration with validation
- Student information updates
- Student queries and listing

**System Prompt:**
```
You are the Student Agent for FitAgent. Your role is to manage student records for personal trainers.

Your capabilities:
- Register new students with phone number validation
- Update student information (name, email, phone, training goal)
- View student lists and details

Guidelines:
- Validate phone numbers are in E.164 format (+14155551234)
- Check for duplicate phone numbers before registration
- Confirm all required fields before registering (name, phone, email, training_goal)
- After successful registration, offer to schedule a session (handoff to Session_Agent)
- Include student_id and student_name in Shared_Context for downstream agents

When to hand off:
- If user wants to schedule a session after registration → handoff_to_agent(Session_Agent)
- If user wants to record a payment → handoff_to_agent(Payment_Agent)
```

**Tools:**
- `register_student(name, phone_number, email, training_goal)` - Register new student
- `view_students()` - List all students for trainer
- `update_student(student_id, **updates)` - Update student information
- `handoff_to_agent(agent_name, reason)` - Transfer to another agent

**Handoff Triggers:**
- After registration, if user mentions scheduling → Session_Agent
- If user mentions payment → Payment_Agent

### Session Agent

**Responsibilities:**
- Session scheduling with conflict detection
- Session rescheduling and cancellation
- Calendar view and session history
- Session confirmation status tracking

**System Prompt:**
```
You are the Session Agent for FitAgent. Your role is to manage training session scheduling.

Your capabilities:
- Schedule new sessions with conflict detection
- Reschedule existing sessions
- Cancel sessions
- View calendar and session history with confirmation status

Guidelines:
- Always check for time conflicts before scheduling
- Validate student exists (check Shared_Context or query)
- Confirm date, time, duration, and student name before scheduling
- Default duration is 60 minutes if not specified
- After successful scheduling, offer calendar sync (handoff to Calendar_Agent)
- Include session_id, session_datetime, student_name in Shared_Context

Session confirmation statuses:
- scheduled: Session is booked but not yet occurred
- completed: Student confirmed session happened
- missed: Student confirmed session was missed
- pending_confirmation: Session occurred but no response from student
- cancelled: Session was cancelled

When to hand off:
- After scheduling, if trainer has calendar connected → handoff_to_agent(Calendar_Agent)
- If user wants to record payment for session → handoff_to_agent(Payment_Agent)
```

**Tools:**
- `schedule_session(student_name, date, time, duration_minutes, location?)` - Schedule new session
- `reschedule_session(session_id, new_date, new_time)` - Reschedule existing session
- `cancel_session(session_id, reason?)` - Cancel session
- `view_calendar(start_date?, end_date?, filter?)` - View sessions in date range
- `view_session_history(confirmation_status?, start_date?, end_date?)` - View sessions with confirmation status
- `handoff_to_agent(agent_name, reason)` - Transfer to another agent

**Handoff Triggers:**
- After scheduling → Calendar_Agent (if calendar connected)
- If payment mentioned → Payment_Agent

### Payment Agent

**Responsibilities:**
- Payment registration with receipt storage
- Payment confirmation
- Payment history and statistics

**System Prompt:**
```
You are the Payment Agent for FitAgent. Your role is to track payments and receipts.

Your capabilities:
- Register payments with optional receipt images
- Confirm payments
- View payment history with filtering
- Calculate payment statistics

Guidelines:
- Confirm amount, student name, and payment date before registering
- Ask if payment should be marked as confirmed or pending
- Support filtering by student name or status (pending/confirmed)
- Calculate total revenue and outstanding amounts
- Include payment_id, amount, payment_status in Shared_Context

This is typically a terminal agent - conclude conversation after payment operations unless user has follow-up requests.
```

**Tools:**
- `register_payment(student_name, amount, payment_date, currency?, session_id?)` - Register payment
- `confirm_payment(payment_id)` - Confirm payment
- `view_payments(student_name?, status?)` - View payment history

**Handoff Triggers:**
- None (terminal agent - concludes conversation)

### Calendar Agent

**Responsibilities:**
- OAuth2 calendar connection (Google, Outlook)
- Calendar event synchronization
- Token refresh and error handling

**System Prompt:**
```
You are the Calendar Agent for FitAgent. Your role is to integrate with external calendar services.

Your capabilities:
- Generate OAuth2 authorization URLs for Google Calendar and Outlook
- Sync session events to connected calendars
- Handle token refresh and API errors gracefully

Guidelines:
- When connecting calendar, provide clear OAuth instructions
- When syncing events, use session data from Shared_Context
- If calendar sync fails, inform user but don't block session creation
- Handle rate limits with exponential backoff

This is typically a terminal agent - conclude conversation after calendar operations.
```

**Tools:**
- `connect_calendar(provider)` - Generate OAuth URL for Google or Outlook
- `sync_calendar_event(session_id)` - Sync session to calendar (uses Shared_Context)

**Handoff Triggers:**
- None (terminal agent - concludes conversation)

### Notification Agent

**Responsibilities:**
- Broadcast message composition
- Recipient validation and queuing
- Rate limit enforcement

**System Prompt:**
```
You are the Notification Agent for FitAgent. Your role is to send broadcast messages to students.

Your capabilities:
- Send broadcast messages to multiple students
- Support message templates with variable substitution
- Validate recipients belong to trainer
- Queue messages for asynchronous delivery

Guidelines:
- Confirm message content and recipients before sending
- Enforce Twilio rate limits (10 messages/second)
- Report partial success if some recipients fail
- Include notification_id and recipient_count in Shared_Context

This is typically a terminal agent - conclude conversation after queuing notifications.
```

**Tools:**
- `send_notification(message, student_ids?, student_names?)` - Send broadcast message

**Handoff Triggers:**
- None (terminal agent - concludes conversation)



## Data Models

### Session Entity Extensions

The Session entity will be extended to support session confirmation tracking:

```python
class Session(BaseModel):
    """Training session entity model with confirmation tracking."""
    
    session_id: str
    entity_type: Literal["SESSION"] = "SESSION"
    trainer_id: str
    student_id: str
    student_name: str
    session_datetime: datetime
    duration_minutes: int
    location: Optional[str] = None
    
    # Existing status field - extended with new values
    status: Literal[
        "scheduled",           # Session is booked but not yet occurred
        "completed",           # Student confirmed session happened
        "missed",              # Student confirmed session was missed
        "pending_confirmation", # Session occurred but no response from student
        "cancelled"            # Session was cancelled
    ] = "scheduled"
    
    # New confirmation fields
    confirmation_status: Literal[
        "scheduled",           # Not yet time to confirm
        "completed",           # Confirmed as completed
        "missed",              # Confirmed as missed
        "pending_confirmation", # Awaiting student response
        "cancelled"            # Session was cancelled
    ] = "scheduled"
    confirmation_requested_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    confirmation_response: Optional[str] = None  # Student's exact response
    
    # Existing calendar fields
    calendar_event_id: Optional[str] = None
    calendar_provider: Optional[Literal["google", "outlook"]] = None
    
    # Existing confirmation fields (deprecated in favor of confirmation_status)
    student_confirmed: bool = False
    student_confirmed_at: Optional[datetime] = None
    
    created_at: datetime
    updated_at: datetime
```

### New GSI: session-confirmation-index

For efficient querying of sessions by confirmation status:

```
GSI Name: session-confirmation-index
Partition Key: trainer_id (String)
Sort Key: confirmation_status#session_datetime (String)
Projection: ALL

Example items:
PK: trainer_abc123
SK: completed#2024-01-15T14:00:00Z

PK: trainer_abc123
SK: missed#2024-01-14T10:00:00Z

PK: trainer_abc123
SK: pending_confirmation#2024-01-13T16:00:00Z
```

This GSI enables queries like:
- "Show all completed sessions this month"
- "Show all missed sessions"
- "Show sessions pending confirmation"
- Calculate attendance rate (completed / (completed + missed))

### Shared_Context Schema

```python
class SharedContext(BaseModel):
    """Shared context passed between agents in the swarm."""
    
    conversation_id: str
    original_request: str
    extracted_entities: Dict[str, Any] = {}
    handoff_history: List[HandoffRecord] = []
    agent_contributions: Dict[str, Dict[str, Any]] = {}
    handoff_count: int = 0
    created_at: datetime
    updated_at: datetime

class HandoffRecord(BaseModel):
    """Record of an agent handoff."""
    
    from_agent: str
    to_agent: str
    reason: str
    timestamp: datetime
```

### Invocation_State Schema

```python
class InvocationState(BaseModel):
    """State passed via kwargs, not visible in LLM prompts."""
    
    trainer_id: str
    phone_number: str
    db_client: Any  # DynamoDBClient instance
    s3_client: Any  # S3 client instance
    twilio_client: Any  # Twilio client instance
    feature_flags: Dict[str, bool] = {}
```

### Session Confirmation Record

Session confirmation data is stored within the Session entity (not a separate entity):

```python
# Stored in Session entity
{
    "PK": "TRAINER#trainer_abc123",
    "SK": "SESSION#session_xyz789",
    "entity_type": "SESSION",
    "session_id": "session_xyz789",
    "trainer_id": "trainer_abc123",
    "student_id": "student_123",
    "student_name": "John Doe",
    "session_datetime": "2024-01-15T14:00:00Z",
    "duration_minutes": 60,
    "status": "completed",
    "confirmation_status": "completed",
    "confirmation_requested_at": "2024-01-15T15:00:00Z",  # 1 hour after session
    "confirmed_at": "2024-01-15T15:05:00Z",
    "confirmation_response": "YES",
    "created_at": "2024-01-14T10:00:00Z",
    "updated_at": "2024-01-15T15:05:00Z"
}
```

## Integration Points

### Strands SDK Integration

The Strands Agents SDK will be integrated into the existing Lambda architecture:

```python
# src/services/swarm_orchestrator.py

from strands_agents import Agent, Swarm, tool
from typing import Dict, Any, List

class SwarmOrchestrator:
    """
    Orchestrates multi-agent collaboration using Strands SDK.
    
    This class replaces the single AIAgent for trainers with the
    multi-agent feature flag enabled.
    """
    
    def __init__(
        self,
        model_id: str = "amazon.nova-micro-v1:0",
        region: str = "us-east-1",
    ):
        self.model_id = model_id
        self.region = region
        
        # Initialize specialized agents
        self.coordinator_agent = self._create_coordinator_agent()
        self.student_agent = self._create_student_agent()
        self.session_agent = self._create_session_agent()
        self.payment_agent = self._create_payment_agent()
        self.calendar_agent = self._create_calendar_agent()
        self.notification_agent = self._create_notification_agent()
        
        # Create swarm with coordinator as entry agent
        self.swarm = Swarm(
            entry_agent=self.coordinator_agent,
            max_handoffs=7,
            node_timeout=30,
            execution_timeout=120,
        )
    
    def process_message(
        self,
        trainer_id: str,
        message: str,
        conversation_history: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process message through the swarm.
        
        Args:
            trainer_id: Trainer identifier
            message: User's WhatsApp message
            conversation_history: Previous conversation context
        
        Returns:
            dict: {
                'success': bool,
                'response': str,
                'handoff_path': List[str],
                'tool_calls': List[Dict],
                'error': str (optional)
            }
        """
        # Prepare invocation state (not visible to LLM)
        invocation_state = {
            "trainer_id": trainer_id,
            "db_client": get_db_client(),
            "s3_client": get_s3_client(),
            "twilio_client": get_twilio_client(),
        }
        
        # Prepare shared context (visible to LLM)
        shared_context = {
            "original_request": message,
            "extracted_entities": {},
            "handoff_history": [],
            "agent_contributions": {},
            "handoff_count": 0,
        }
        
        # Execute swarm
        result = self.swarm.run(
            message=message,
            shared_context=shared_context,
            invocation_state=invocation_state,
            conversation_history=conversation_history,
        )
        
        return result
```

### Message Processor Integration

The existing `message_processor.py` Lambda handler will be updated to support both architectures:

```python
# src/handlers/message_processor.py

from src.services.ai_agent import AIAgent
from src.services.swarm_orchestrator import SwarmOrchestrator
from src.config import settings

def lambda_handler(event, context):
    """Process WhatsApp message with single or multi-agent architecture."""
    
    # Extract message and trainer_id from event
    message = event['message']
    phone_number = event['phone_number']
    
    # Lookup trainer by phone number
    trainer_id = lookup_trainer_by_phone(phone_number)
    
    # Check feature flag
    if settings.enable_multi_agent:
        # Use Swarm orchestrator
        orchestrator = SwarmOrchestrator()
        result = orchestrator.process_message(
            trainer_id=trainer_id,
            message=message,
        )
    else:
        # Use existing single agent
        agent = AIAgent()
        result = agent.process_message(
            trainer_id=trainer_id,
            message=message,
        )
    
    # Send response via Twilio
    send_whatsapp_message(phone_number, result['response'])
    
    return {'statusCode': 200}
```

### Tool Function Integration

Existing tool functions in `src/tools/` will be wrapped with Strands SDK decorators:

```python
# src/tools/session_tools.py

from strands_agents import tool, ToolContext

@tool(context=True)
def schedule_session(
    ctx: ToolContext,
    student_name: str,
    date: str,
    time: str,
    duration_minutes: int,
    location: str = None,
) -> dict:
    """
    Schedule a new training session with conflict detection.
    
    Args:
        ctx: Tool context containing invocation_state
        student_name: Name of the student
        date: Session date in YYYY-MM-DD format
        time: Session time in HH:MM format
        duration_minutes: Duration in minutes (15-480)
        location: Optional session location
    
    Returns:
        dict: {'success': bool, 'data': dict, 'error': str (optional)}
    """
    # Extract trainer_id from invocation_state
    trainer_id = ctx.invocation_state['trainer_id']
    db_client = ctx.invocation_state['db_client']
    
    # Existing implementation...
    # (validation, conflict check, DynamoDB write)
    
    return {
        'success': True,
        'data': {
            'session_id': session.session_id,
            'session_datetime': session.session_datetime.isoformat(),
            'student_name': student_name,
        }
    }
```

### DynamoDB Integration

No schema changes required for existing entities. New GSI will be added:

```yaml
# infrastructure/template.yml

Resources:
  FitAgentTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: fitagent-main
      # ... existing configuration ...
      
      GlobalSecondaryIndexes:
        # Existing GSIs
        - IndexName: phone-number-index
          # ... existing config ...
        
        - IndexName: session-date-index
          # ... existing config ...
        
        - IndexName: payment-status-index
          # ... existing config ...
        
        # New GSI for session confirmation
        - IndexName: session-confirmation-index
          KeySchema:
            - AttributeName: trainer_id
              KeyType: HASH
            - AttributeName: confirmation_status_datetime
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
          ProvisionedThroughput:
            ReadCapacityUnits: 5
            WriteCapacityUnits: 5
```



## Session Confirmation Feature Design

### Overview

The session confirmation feature automatically verifies session attendance by sending confirmation requests to students 1 hour after scheduled sessions. Students reply YES (completed) or NO (missed), and the system updates the session status accordingly.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EventBridge Scheduled Rule                    │
│              Triggers every 5 minutes to check for               │
│              sessions that ended 1 hour ago                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│          Session Confirmation Handler (Lambda)                   │
│  1. Query sessions where:                                        │
│     - session_datetime + duration + 1 hour <= now                │
│     - confirmation_status = "scheduled"                          │
│  2. For each session:                                            │
│     - Send confirmation message to student                       │
│     - Update confirmation_status = "pending_confirmation"        │
│     - Set confirmation_requested_at = now                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Twilio WhatsApp API                           │
│         Sends: "Did your session with [Trainer] on              │
│         [Date] at [Time] happen? Reply YES or NO"                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Student Replies via WhatsApp                  │
│                    "YES" or "NO"                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Webhook Handler → Message Processor                 │
│  1. Detect confirmation response (YES/NO)                        │
│  2. Lookup pending confirmation session                          │
│  3. Update session:                                              │
│     - confirmation_status = "completed" or "missed"              │
│     - confirmed_at = now                                         │
│     - confirmation_response = user's message                     │
└─────────────────────────────────────────────────────────────────┘
```

### Lambda Handler: session_confirmation.py

```python
# src/handlers/session_confirmation.py

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

import boto3
from boto3.dynamodb.conditions import Key, Attr

from src.models.dynamodb_client import DynamoDBClient
from src.models.entities import Session
from src.services.twilio_client import TwilioClient
from src.utils.logging import get_logger
from src.config import settings

logger = get_logger(__name__)


def lambda_handler(event, context):
    """
    EventBridge scheduled handler for session confirmation requests.
    
    Triggered every 5 minutes to check for sessions that ended 1 hour ago
    and send confirmation requests to students.
    
    Event: EventBridge scheduled event (cron: */5 * * * ? *)
    """
    try:
        logger.info("Session confirmation handler started")
        
        # Initialize clients
        db_client = DynamoDBClient()
        twilio_client = TwilioClient()
        
        # Calculate time window: sessions that ended 1 hour ago
        now = datetime.utcnow()
        check_time_start = now - timedelta(hours=1, minutes=5)  # 1h5m ago
        check_time_end = now - timedelta(hours=1)  # 1h ago
        
        # Query sessions needing confirmation
        sessions = query_sessions_for_confirmation(
            db_client=db_client,
            start_time=check_time_start,
            end_time=check_time_end,
        )
        
        logger.info(
            "Found sessions for confirmation",
            count=len(sessions),
            time_window=f"{check_time_start} to {check_time_end}",
        )
        
        # Send confirmation requests
        sent_count = 0
        failed_count = 0
        
        for session in sessions:
            try:
                send_confirmation_request(
                    session=session,
                    twilio_client=twilio_client,
                    db_client=db_client,
                )
                sent_count += 1
            except Exception as e:
                logger.error(
                    "Failed to send confirmation request",
                    session_id=session.session_id,
                    error=str(e),
                )
                failed_count += 1
        
        logger.info(
            "Session confirmation handler completed",
            sent=sent_count,
            failed=failed_count,
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'sent': sent_count,
                'failed': failed_count,
            })
        }
    
    except Exception as e:
        logger.error(
            "Session confirmation handler error",
            error=str(e),
        )
        raise


def query_sessions_for_confirmation(
    db_client: DynamoDBClient,
    start_time: datetime,
    end_time: datetime,
) -> List[Session]:
    """
    Query sessions that need confirmation requests.
    
    Finds sessions where:
    - session_datetime + duration is between start_time and end_time
    - confirmation_status = "scheduled"
    - status != "cancelled"
    
    Args:
        db_client: DynamoDB client
        start_time: Start of time window
        end_time: End of time window
    
    Returns:
        List of Session objects needing confirmation
    """
    # Scan table for sessions (in production, use GSI for efficiency)
    # Filter: confirmation_status = "scheduled" AND status != "cancelled"
    # AND session_datetime + duration between start_time and end_time
    
    sessions = []
    
    # Query all trainers' sessions (this is inefficient - see optimization below)
    response = db_client.table.scan(
        FilterExpression=Attr('entity_type').eq('SESSION') &
                        Attr('confirmation_status').eq('scheduled') &
                        Attr('status').ne('cancelled')
    )
    
    for item in response.get('Items', []):
        session = Session.from_dynamodb(item)
        
        # Calculate session end time
        session_end = session.session_datetime + timedelta(
            minutes=session.duration_minutes
        )
        
        # Check if session ended in the time window
        if start_time <= session_end <= end_time:
            sessions.append(session)
    
    return sessions


def send_confirmation_request(
    session: Session,
    twilio_client: TwilioClient,
    db_client: DynamoDBClient,
) -> None:
    """
    Send confirmation request to student and update session status.
    
    Args:
        session: Session object
        twilio_client: Twilio client
        db_client: DynamoDB client
    """
    # Get student phone number
    student = db_client.get_item(
        pk=f"STUDENT#{session.student_id}",
        sk="METADATA",
    )
    student_phone = student['phone_number']
    
    # Get trainer name
    trainer = db_client.get_item(
        pk=f"TRAINER#{session.trainer_id}",
        sk="METADATA",
    )
    trainer_name = trainer['name']
    
    # Format confirmation message
    message = format_confirmation_message(
        trainer_name=trainer_name,
        session_datetime=session.session_datetime,
        duration_minutes=session.duration_minutes,
    )
    
    # Send via Twilio
    twilio_client.send_message(
        to=student_phone,
        body=message,
    )
    
    # Update session status
    now = datetime.utcnow()
    db_client.update_item(
        pk=f"TRAINER#{session.trainer_id}",
        sk=f"SESSION#{session.session_id}",
        updates={
            'confirmation_status': 'pending_confirmation',
            'confirmation_requested_at': now.isoformat(),
            'updated_at': now.isoformat(),
        }
    )
    
    logger.info(
        "Confirmation request sent",
        session_id=session.session_id,
        student_phone=student_phone,
    )


def format_confirmation_message(
    trainer_name: str,
    session_datetime: datetime,
    duration_minutes: int,
) -> str:
    """
    Format confirmation request message.
    
    Args:
        trainer_name: Trainer's name
        session_datetime: Session date and time
        duration_minutes: Session duration
    
    Returns:
        Formatted message string
    """
    date_str = session_datetime.strftime("%A, %B %d")
    time_str = session_datetime.strftime("%I:%M %p")
    
    return (
        f"Hi! Did your {duration_minutes}-minute training session with "
        f"{trainer_name} on {date_str} at {time_str} happen?\n\n"
        f"Reply YES if it happened, or NO if it was missed."
    )
```

### Message Processor Updates

The `message_processor.py` handler will be updated to detect and process confirmation responses:

```python
# src/handlers/message_processor.py (additions)

def process_confirmation_response(
    phone_number: str,
    message: str,
    db_client: DynamoDBClient,
) -> bool:
    """
    Detect and process session confirmation responses.
    
    Args:
        phone_number: Student's phone number
        message: User's message
        db_client: DynamoDB client
    
    Returns:
        True if message was a confirmation response, False otherwise
    """
    # Normalize message
    normalized = message.strip().upper()
    
    # Check if it's a YES/NO response
    if normalized not in ['YES', 'NO']:
        return False
    
    # Lookup student by phone number
    student = lookup_student_by_phone(phone_number, db_client)
    if not student:
        return False
    
    # Find pending confirmation session for this student
    pending_session = find_pending_confirmation_session(
        student_id=student['student_id'],
        db_client=db_client,
    )
    
    if not pending_session:
        return False
    
    # Update session based on response
    now = datetime.utcnow()
    confirmation_status = 'completed' if normalized == 'YES' else 'missed'
    
    db_client.update_item(
        pk=f"TRAINER#{pending_session['trainer_id']}",
        sk=f"SESSION#{pending_session['session_id']}",
        updates={
            'confirmation_status': confirmation_status,
            'status': confirmation_status,  # Also update main status
            'confirmed_at': now.isoformat(),
            'confirmation_response': message,
            'updated_at': now.isoformat(),
        }
    )
    
    logger.info(
        "Session confirmation processed",
        session_id=pending_session['session_id'],
        confirmation_status=confirmation_status,
    )
    
    # Send acknowledgment
    ack_message = (
        "Thanks for confirming! " +
        ("Session marked as completed." if normalized == 'YES' 
         else "Session marked as missed.")
    )
    
    return True  # Indicates message was handled
```

### EventBridge Rule Configuration

```yaml
# infrastructure/template.yml

Resources:
  SessionConfirmationRule:
    Type: AWS::Events::Rule
    Properties:
      Name: session-confirmation-trigger
      Description: Triggers session confirmation handler every 5 minutes
      ScheduleExpression: "cron(*/5 * * * ? *)"  # Every 5 minutes
      State: ENABLED
      Targets:
        - Arn: !GetAtt SessionConfirmationFunction.Arn
          Id: SessionConfirmationTarget

  SessionConfirmationFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: fitagent-session-confirmation
      Runtime: python3.12
      Handler: src.handlers.session_confirmation.lambda_handler
      Code:
        S3Bucket: !Ref DeploymentBucket
        S3Key: lambda.zip
      Environment:
        Variables:
          DYNAMODB_TABLE: !Ref FitAgentTable
          TWILIO_ACCOUNT_SID: !Ref TwilioAccountSid
          TWILIO_AUTH_TOKEN: !Ref TwilioAuthToken
          TWILIO_WHATSAPP_NUMBER: !Ref TwilioWhatsAppNumber
      Timeout: 60
      MemorySize: 512

  SessionConfirmationPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref SessionConfirmationFunction
      Action: lambda:InvokeFunction
      Principal: events.amazonaws.com
      SourceArn: !GetAtt SessionConfirmationRule.Arn
```

### Session History Tool

New tool function for viewing sessions with confirmation status:

```python
# src/tools/session_tools.py (addition)

@tool(context=True)
def view_session_history(
    ctx: ToolContext,
    confirmation_status: str = None,
    start_date: str = None,
    end_date: str = None,
) -> dict:
    """
    View session history with confirmation status filtering.
    
    Args:
        ctx: Tool context
        confirmation_status: Filter by status (completed, missed, pending_confirmation, scheduled, cancelled)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    
    Returns:
        dict: {
            'success': bool,
            'data': {
                'sessions': List[dict],
                'statistics': {
                    'total_sessions': int,
                    'completed_sessions': int,
                    'missed_sessions': int,
                    'pending_confirmations': int,
                    'attendance_rate': float
                }
            }
        }
    """
    trainer_id = ctx.invocation_state['trainer_id']
    db_client = ctx.invocation_state['db_client']
    
    # Query sessions using session-confirmation-index if filtering by status
    if confirmation_status:
        sessions = query_sessions_by_confirmation_status(
            trainer_id=trainer_id,
            confirmation_status=confirmation_status,
            start_date=start_date,
            end_date=end_date,
            db_client=db_client,
        )
    else:
        sessions = query_all_sessions(
            trainer_id=trainer_id,
            start_date=start_date,
            end_date=end_date,
            db_client=db_client,
        )
    
    # Calculate statistics
    stats = calculate_session_statistics(sessions)
    
    return {
        'success': True,
        'data': {
            'sessions': [s.dict() for s in sessions],
            'statistics': stats,
        }
    }


def calculate_session_statistics(sessions: List[Session]) -> dict:
    """Calculate session statistics including attendance rate."""
    
    total = len(sessions)
    completed = sum(1 for s in sessions if s.confirmation_status == 'completed')
    missed = sum(1 for s in sessions if s.confirmation_status == 'missed')
    pending = sum(1 for s in sessions if s.confirmation_status == 'pending_confirmation')
    
    # Attendance rate = completed / (completed + missed)
    attendance_rate = (
        completed / (completed + missed) if (completed + missed) > 0 else 0.0
    )
    
    return {
        'total_sessions': total,
        'completed_sessions': completed,
        'missed_sessions': missed,
        'pending_confirmations': pending,
        'attendance_rate': round(attendance_rate, 2),
    }
```



## Migration Strategy and Feature Flag

### Feature Flag Implementation

```python
# src/config.py (addition)

class Settings(BaseSettings):
    # ... existing settings ...
    
    # Multi-agent feature flag
    enable_multi_agent: bool = False
    
    # Per-trainer feature flags (stored in DynamoDB)
    trainer_feature_flags_table: str = "fitagent-feature-flags"
```

### Gradual Rollout Strategy

**Phase 1: Infrastructure Setup (Week 1-2)**
- Install Strands SDK dependency
- Create SwarmOrchestrator class
- Implement Coordinator agent
- Add feature flag to config
- Deploy to staging environment

**Phase 2: Agent Migration (Week 3-5)**
- Week 3: Migrate Student_Agent and Session_Agent
- Week 4: Migrate Payment_Agent and Calendar_Agent
- Week 5: Migrate Notification_Agent
- Each week: Deploy to staging, run integration tests

**Phase 3: Session Confirmation Feature (Week 6)**
- Implement session_confirmation.py Lambda handler
- Add session-confirmation-index GSI
- Update Session entity with confirmation fields
- Deploy EventBridge rule
- Test confirmation flow end-to-end

**Phase 4: Production Rollout (Week 7-8)**
- Week 7: Enable for 10% of trainers (canary deployment)
- Monitor metrics: response time, error rate, handoff count
- Week 8: Gradual rollout to 50%, then 100%
- Keep feature flag for emergency rollback

### Rollback Procedure

If issues are detected:
1. Set `enable_multi_agent=False` in environment variables
2. Redeploy Lambda functions
3. System automatically falls back to single AIAgent
4. No data migration required (both architectures use same DynamoDB schema)

### Per-Trainer Feature Flags

For granular control, feature flags can be stored per trainer:

```python
# src/services/feature_flags.py

def is_multi_agent_enabled(trainer_id: str) -> bool:
    """Check if multi-agent is enabled for specific trainer."""
    
    # Check global flag first
    if not settings.enable_multi_agent:
        return False
    
    # Check per-trainer override
    db_client = DynamoDBClient()
    flags = db_client.get_item(
        pk=f"TRAINER#{trainer_id}",
        sk="FEATURE_FLAGS",
    )
    
    if flags:
        return flags.get('enable_multi_agent', True)
    
    return True  # Default to enabled if global flag is on
```



## Performance Design

### Response Time Optimization

**Target: 10-second response time for WhatsApp messages**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Response Time Budget (10s)                    │
├─────────────────────────────────────────────────────────────────┤
│ Webhook Handler:           100ms                                 │
│ Message Processor Setup:   200ms                                 │
│ Swarm Execution:          8000ms (typical: 3-5s)                 │
│ Twilio Response:           200ms                                 │
│ Buffer:                   1500ms                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Timeout Configuration Strategy

| Timeout | Value | Purpose |
|---------|-------|---------|
| node_timeout | 30s | Prevents individual agent from hanging |
| execution_timeout | 120s | Allows complex workflows with retries |
| Lambda timeout | 180s | Provides buffer for execution_timeout |
| response_time_budget | 10s | User experience requirement |

The execution_timeout (120s) is set high to handle edge cases (calendar API delays, DynamoDB throttling retries), but typical conversations complete in 3-5 seconds with 2-3 handoffs.

### Agent Instance Caching

```python
# src/services/swarm_orchestrator.py

# Module-level cache for Lambda warm starts
_agent_cache = {}

def get_swarm_orchestrator(model_id: str = None) -> SwarmOrchestrator:
    """
    Get cached SwarmOrchestrator instance for Lambda warm starts.
    
    This reduces cold start overhead by reusing agent instances
    across Lambda invocations within the same execution context.
    """
    cache_key = model_id or settings.bedrock_model_id
    
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = SwarmOrchestrator(model_id=cache_key)
    
    return _agent_cache[cache_key]
```

### DynamoDB Query Optimization

**Use GSIs for efficient queries:**

```python
# Efficient: Use session-date-index GSI
sessions = db_client.query(
    IndexName='session-date-index',
    KeyConditionExpression=Key('trainer_id').eq(trainer_id) &
                          Key('session_datetime').between(start, end)
)

# Efficient: Use session-confirmation-index GSI
completed_sessions = db_client.query(
    IndexName='session-confirmation-index',
    KeyConditionExpression=Key('trainer_id').eq(trainer_id) &
                          Key('confirmation_status_datetime').begins_with('completed#')
)

# Inefficient: Scan entire table (avoid)
sessions = db_client.scan(
    FilterExpression=Attr('trainer_id').eq(trainer_id)
)
```

### Shared_Context Size Management

```python
# src/services/swarm_orchestrator.py

MAX_CONTEXT_SIZE = 50_000  # 50KB limit

def compress_shared_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compress Shared_Context when it exceeds size limit.
    
    Strategy:
    1. Keep original_request and extracted_entities (always needed)
    2. Summarize handoff_history (keep last 3 handoffs)
    3. Summarize agent_contributions (keep only essential data)
    """
    context_size = len(json.dumps(context))
    
    if context_size < MAX_CONTEXT_SIZE:
        return context
    
    # Keep recent handoffs
    if len(context['handoff_history']) > 3:
        context['handoff_history'] = context['handoff_history'][-3:]
    
    # Summarize agent contributions
    for agent_name, contribution in context['agent_contributions'].items():
        # Keep only IDs and essential fields
        if 'session_id' in contribution:
            context['agent_contributions'][agent_name] = {
                'session_id': contribution['session_id'],
                'session_datetime': contribution.get('session_datetime'),
            }
    
    return context
```

### Token Usage Optimization

**Use Amazon Nova models for cost efficiency:**

```python
# Agent model configuration
AGENT_MODELS = {
    'coordinator': 'amazon.nova-micro-v1:0',      # Lightweight routing
    'student': 'amazon.nova-lite-v1:0',           # Simple CRUD operations
    'session': 'amazon.nova-pro-v1:0',            # Complex scheduling logic
    'payment': 'amazon.nova-lite-v1:0',           # Simple CRUD operations
    'calendar': 'anthropic.claude-3-haiku-v1:0',  # OAuth complexity
    'notification': 'amazon.nova-micro-v1:0',     # Simple message queuing
}
```

**Prompt compression techniques:**

```python
# Concise system prompts (avoid verbose instructions)
# Use few-shot examples sparingly (2-3 examples max)
# Remove redundant context from Shared_Context
# Use structured data instead of natural language where possible
```

### Caching Strategy

```python
# Cache agent responses for identical queries (5-minute TTL)
from functools import lru_cache
from datetime import datetime, timedelta

_response_cache = {}

def get_cached_response(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached response if available and not expired."""
    if cache_key in _response_cache:
        cached_data, timestamp = _response_cache[cache_key]
        if datetime.utcnow() - timestamp < timedelta(minutes=5):
            return cached_data
    return None

def cache_response(cache_key: str, response: Dict[str, Any]) -> None:
    """Cache response with timestamp."""
    _response_cache[cache_key] = (response, datetime.utcnow())
```

## Security Design

### Multi-Tenancy Isolation

**Invocation_State enforces trainer_id isolation:**

```python
# CORRECT: trainer_id from Invocation_State
@tool(context=True)
def view_students(ctx: ToolContext) -> dict:
    trainer_id = ctx.invocation_state['trainer_id']  # Secure
    
    # Query scoped to trainer
    students = db_client.query(
        KeyConditionExpression=Key('PK').eq(f'TRAINER#{trainer_id}') &
                              Key('SK').begins_with('STUDENT#')
    )
    return {'success': True, 'data': students}

# INCORRECT: trainer_id from Shared_Context (LLM can manipulate)
@tool(context=True)
def view_students_insecure(ctx: ToolContext) -> dict:
    # NEVER DO THIS - LLM could inject different trainer_id
    trainer_id = ctx.shared_context.get('trainer_id')  # INSECURE
    # ...
```

**Validation in all tool functions:**

```python
@tool(context=True)
def schedule_session(
    ctx: ToolContext,
    student_name: str,
    date: str,
    time: str,
    duration_minutes: int,
) -> dict:
    trainer_id = ctx.invocation_state['trainer_id']
    
    # Validate student belongs to trainer
    student = lookup_student_by_name(student_name, trainer_id)
    if not student:
        return {
            'success': False,
            'error': f'Student {student_name} not found in your roster'
        }
    
    # Validate student's trainer_id matches
    if student['trainer_id'] != trainer_id:
        logger.error(
            "Cross-tenant access attempt",
            trainer_id=trainer_id,
            student_trainer_id=student['trainer_id'],
        )
        return {
            'success': False,
            'error': 'Authorization error'
        }
    
    # Proceed with scheduling...
```

### OAuth Token Encryption

```python
# src/services/calendar_sync.py

import boto3
from src.utils.encryption import encrypt_token, decrypt_token

def store_oauth_tokens(
    trainer_id: str,
    provider: str,
    access_token: str,
    refresh_token: str,
) -> None:
    """Store OAuth tokens with KMS encryption."""
    
    kms_client = boto3.client('kms')
    
    # Encrypt refresh token (long-lived)
    encrypted_refresh_token = encrypt_token(
        token=refresh_token,
        kms_client=kms_client,
        key_alias=settings.kms_key_alias,
    )
    
    # Store in DynamoDB
    db_client.put_item({
        'PK': f'TRAINER#{trainer_id}',
        'SK': 'CALENDAR_CONFIG',
        'provider': provider,
        'encrypted_refresh_token': encrypted_refresh_token,
        'scope': 'calendar.events',
        'connected_at': datetime.utcnow().isoformat(),
    })
    
    # Access tokens stored in memory only (short-lived)
    # Never log tokens
```

### PII Sanitization

```python
# src/utils/logging.py

import re

def sanitize_phone_number(phone: str) -> str:
    """Sanitize phone number for logging."""
    # +14155551234 -> +1415***1234
    if len(phone) > 8:
        return phone[:5] + '***' + phone[-4:]
    return '***'

def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove PII from log data."""
    sanitized = data.copy()
    
    # Sanitize phone numbers
    if 'phone_number' in sanitized:
        sanitized['phone_number'] = sanitize_phone_number(sanitized['phone_number'])
    
    # Remove email addresses
    if 'email' in sanitized:
        sanitized['email'] = '***@***.com'
    
    # Remove OAuth tokens
    for key in ['access_token', 'refresh_token', 'encrypted_refresh_token']:
        if key in sanitized:
            sanitized[key] = '***'
    
    return sanitized
```

### Invocation_State Security

```python
# CRITICAL: Invocation_State must NEVER appear in LLM prompts

# CORRECT: Strands SDK handles this automatically
swarm.run(
    message=message,
    shared_context=shared_context,      # Visible to LLM
    invocation_state=invocation_state,  # NOT visible to LLM
)

# Verification test
def test_invocation_state_not_in_prompts():
    """Verify Invocation_State never appears in LLM prompts."""
    
    # Mock Bedrock client to capture prompts
    with patch('boto3.client') as mock_client:
        mock_bedrock = MagicMock()
        mock_client.return_value = mock_bedrock
        
        # Execute swarm
        orchestrator = SwarmOrchestrator()
        orchestrator.process_message(
            trainer_id='test_trainer',
            message='Schedule a session',
        )
        
        # Check all Bedrock calls
        for call in mock_bedrock.converse.call_args_list:
            prompt_text = json.dumps(call)
            
            # Invocation_State data should NOT appear
            assert 'test_trainer' not in prompt_text
            assert 'trainer_id' not in prompt_text
            assert 'db_client' not in prompt_text
```

### Input Validation

```python
# src/utils/validation.py

from pydantic import BaseModel, validator, Field

class ScheduleSessionInput(BaseModel):
    """Validated input for schedule_session tool."""
    
    student_name: str = Field(min_length=1, max_length=100)
    date: str  # YYYY-MM-DD format
    time: str  # HH:MM format
    duration_minutes: int = Field(ge=15, le=480)
    location: Optional[str] = Field(max_length=200)
    
    @validator('date')
    def validate_date_format(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')
        return v
    
    @validator('time')
    def validate_time_format(cls, v):
        try:
            datetime.strptime(v, '%H:%M')
        except ValueError:
            raise ValueError('Time must be in HH:MM format')
        return v

# Use in tool function
@tool(context=True)
def schedule_session(ctx: ToolContext, **kwargs) -> dict:
    try:
        # Validate inputs
        validated = ScheduleSessionInput(**kwargs)
    except ValidationError as e:
        return {
            'success': False,
            'error': f'Invalid input: {e}'
        }
    
    # Proceed with validated data...
```

## Error Handling

### Agent Failure Handling

```python
# src/services/swarm_orchestrator.py

def process_message(self, trainer_id: str, message: str) -> Dict[str, Any]:
    """Process message with comprehensive error handling."""
    
    try:
        result = self.swarm.run(
            message=message,
            shared_context=self._build_shared_context(message),
            invocation_state=self._build_invocation_state(trainer_id),
        )
        
        return {
            'success': True,
            'response': result['response'],
            'handoff_path': result['handoff_path'],
        }
    
    except MaxHandoffsExceeded as e:
        # Handoff limit reached
        logger.warning(
            "Max handoffs exceeded",
            trainer_id=trainer_id,
            handoff_count=e.handoff_count,
        )
        return {
            'success': False,
            'response': (
                "I'm having trouble completing your request. "
                "It seems more complex than expected. "
                "Could you try breaking it into smaller steps?"
            ),
            'error': 'max_handoffs_exceeded',
        }
    
    except NodeTimeoutError as e:
        # Individual agent timeout
        logger.error(
            "Agent timeout",
            trainer_id=trainer_id,
            agent_name=e.agent_name,
            timeout=e.timeout,
        )
        return {
            'success': False,
            'response': (
                "I'm taking longer than expected to process your request. "
                "Please try again in a moment."
            ),
            'error': 'agent_timeout',
        }
    
    except ExecutionTimeoutError as e:
        # Total swarm timeout
        logger.error(
            "Swarm execution timeout",
            trainer_id=trainer_id,
            execution_time=e.execution_time,
        )
        return {
            'success': False,
            'response': (
                "Your request is taking too long to process. "
                "Please try again or simplify your request."
            ),
            'error': 'execution_timeout',
        }
    
    except DynamoDBThrottlingError as e:
        # DynamoDB rate limiting
        logger.error(
            "DynamoDB throttling",
            trainer_id=trainer_id,
            operation=e.operation,
        )
        return {
            'success': False,
            'response': (
                "We're experiencing high load right now. "
                "Please try again in a few seconds."
            ),
            'error': 'throttling',
        }
    
    except Exception as e:
        # Unexpected errors
        logger.error(
            "Unexpected swarm error",
            trainer_id=trainer_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            'success': False,
            'response': (
                "Something went wrong while processing your request. "
                "Our team has been notified. Please try again later."
            ),
            'error': 'internal_error',
        }
```

### Graceful Degradation

```python
# Calendar sync failure doesn't block session creation

@tool(context=True)
def schedule_session(ctx: ToolContext, **kwargs) -> dict:
    trainer_id = ctx.invocation_state['trainer_id']
    
    # Create session in DynamoDB (critical path)
    session = create_session_in_db(trainer_id, **kwargs)
    
    # Attempt calendar sync (non-critical)
    calendar_synced = False
    try:
        if has_calendar_connected(trainer_id):
            sync_to_calendar(session)
            calendar_synced = True
    except CalendarAPIError as e:
        # Log error but don't fail the operation
        logger.warning(
            "Calendar sync failed",
            session_id=session.session_id,
            error=str(e),
        )
    
    return {
        'success': True,
        'data': {
            'session_id': session.session_id,
            'session_datetime': session.session_datetime.isoformat(),
            'calendar_synced': calendar_synced,
        },
        'message': (
            f'Session scheduled for {session.session_datetime}. ' +
            ('Synced to your calendar.' if calendar_synced 
             else 'Note: Calendar sync failed, but session was created.')
        )
    }
```

### Retry Logic with Exponential Backoff

```python
# src/utils/retry.py

import time
import random
from functools import wraps

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exceptions: tuple = (Exception,),
):
    """Decorator for exponential backoff retry logic."""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    
                    # Calculate delay with jitter
                    delay = min(
                        base_delay * (2 ** attempt) + random.uniform(0, 1),
                        max_delay
                    )
                    
                    logger.warning(
                        "Retry attempt",
                        function=func.__name__,
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e),
                    )
                    
                    time.sleep(delay)
            
        return wrapper
    return decorator

# Usage
@retry_with_backoff(
    max_retries=3,
    base_delay=1.0,
    exceptions=(ClientError, ThrottlingException),
)
def query_dynamodb(table, key):
    """Query DynamoDB with automatic retry on throttling."""
    return table.get_item(Key=key)
```

### Dead Letter Queue for Failed Messages

```python
# src/handlers/message_processor.py

def lambda_handler(event, context):
    """Process message with DLQ fallback."""
    
    try:
        # Process message
        result = process_whatsapp_message(event)
        
        # Send response
        send_response(result)
        
        return {'statusCode': 200}
    
    except Exception as e:
        logger.error(
            "Message processing failed",
            error=str(e),
            event=event,
        )
        
        # Send to DLQ for manual review
        sqs_client = boto3.client('sqs')
        sqs_client.send_message(
            QueueUrl=settings.dlq_url,
            MessageBody=json.dumps({
                'original_event': event,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat(),
            })
        )
        
        # Send user-friendly error
        send_error_response(
            phone_number=event['phone_number'],
            message="Sorry, I couldn't process your message. Our team will review it shortly."
        )
        
        # Don't raise - message is in DLQ
        return {'statusCode': 500}
```



## Testing Strategy

### Dual Testing Approach

The testing strategy combines unit tests and property-based tests for comprehensive coverage:

**Unit Tests:**
- Specific examples and edge cases
- Integration points between components
- Error conditions and validation
- Configuration verification

**Property-Based Tests:**
- Universal properties across all inputs
- Comprehensive input coverage through randomization
- Invariant verification
- Security and isolation guarantees

Both approaches are complementary and necessary. Unit tests catch concrete bugs with specific examples, while property tests verify general correctness across the input space.

### Property-Based Testing Configuration

**Library:** Hypothesis (Python property-based testing library)

**Configuration:**
```python
# pytest.ini

[pytest]
# Property test settings
hypothesis_profile = default

[tool:hypothesis]
max_examples = 100  # Minimum 100 iterations per property test
deadline = 5000     # 5 second timeout per test case
```

**Test Tagging Format:**

Each property test must reference its design document property:

```python
from hypothesis import given, strategies as st

@given(
    student_name=st.text(min_size=1, max_size=100),
    phone_number=st.from_regex(r'^\+[1-9]\d{10,14}$'),
)
def test_student_registration_validation(student_name, phone_number):
    """
    Feature: strands-multi-agent-architecture, Property 1:
    For any student registration attempt, phone number validation
    should reject invalid formats and accept valid E.164 formats.
    """
    # Test implementation...
```

### Unit Test Structure

```
tests/
├── unit/
│   ├── test_coordinator_agent.py      # Coordinator agent tests
│   ├── test_student_agent.py          # Student agent tests
│   ├── test_session_agent.py          # Session agent tests
│   ├── test_payment_agent.py          # Payment agent tests
│   ├── test_calendar_agent.py         # Calendar agent tests
│   ├── test_notification_agent.py     # Notification agent tests
│   ├── test_swarm_orchestrator.py     # Swarm coordination tests
│   ├── test_shared_context.py         # Context management tests
│   ├── test_invocation_state.py       # Invocation state tests
│   ├── test_session_confirmation.py   # Session confirmation tests
│   └── test_feature_flags.py          # Feature flag tests
│
├── integration/
│   ├── test_handoff_flows.py          # End-to-end handoff scenarios
│   ├── test_session_confirmation_flow.py  # Confirmation workflow
│   ├── test_multi_tenant_isolation.py # Cross-tenant security
│   └── test_backward_compatibility.py # Single vs multi-agent
│
└── property/
    ├── test_swarm_properties.py       # Swarm coordination properties
    ├── test_context_properties.py     # Context management properties
    ├── test_isolation_properties.py   # Multi-tenancy properties
    └── test_confirmation_properties.py # Session confirmation properties
```

### Example Unit Tests

```python
# tests/unit/test_coordinator_agent.py

def test_coordinator_routes_student_intent_to_student_agent():
    """Coordinator should route student registration to Student_Agent."""
    
    coordinator = create_coordinator_agent()
    message = "Add a new student named John"
    
    result = coordinator.process(message)
    
    assert result['handoff_to'] == 'Student_Agent'
    assert 'John' in result['extracted_entities']['student_name']

def test_coordinator_routes_session_intent_to_session_agent():
    """Coordinator should route scheduling to Session_Agent."""
    
    coordinator = create_coordinator_agent()
    message = "Schedule a session with Sarah tomorrow at 2pm"
    
    result = coordinator.process(message)
    
    assert result['handoff_to'] == 'Session_Agent'
    assert result['extracted_entities']['student_name'] == 'Sarah'

def test_coordinator_handles_greetings_without_handoff():
    """Coordinator should handle greetings directly."""
    
    coordinator = create_coordinator_agent()
    message = "Hello"
    
    result = coordinator.process(message)
    
    assert result['handoff_to'] is None
    assert 'hello' in result['response'].lower()
```

```python
# tests/unit/test_session_confirmation.py

def test_confirmation_sent_one_hour_after_session():
    """Confirmation should be sent 1 hour after session end."""
    
    # Create session ending 1 hour ago
    session_end = datetime.utcnow() - timedelta(hours=1, minutes=2)
    session = create_test_session(
        session_datetime=session_end - timedelta(minutes=60),
        duration_minutes=60,
        confirmation_status='scheduled',
    )
    
    # Run confirmation handler
    result = session_confirmation_handler({}, {})
    
    # Verify confirmation was sent
    assert result['sent'] == 1
    
    # Verify session updated
    updated_session = get_session(session.session_id)
    assert updated_session['confirmation_status'] == 'pending_confirmation'
    assert updated_session['confirmation_requested_at'] is not None

def test_yes_response_marks_session_completed():
    """YES response should mark session as completed."""
    
    session = create_test_session(
        confirmation_status='pending_confirmation'
    )
    
    # Simulate student response
    process_confirmation_response(
        phone_number=session.student_phone,
        message='YES',
    )
    
    # Verify session updated
    updated_session = get_session(session.session_id)
    assert updated_session['confirmation_status'] == 'completed'
    assert updated_session['confirmed_at'] is not None
    assert updated_session['confirmation_response'] == 'YES'

def test_no_response_marks_session_missed():
    """NO response should mark session as missed."""
    
    session = create_test_session(
        confirmation_status='pending_confirmation'
    )
    
    # Simulate student response
    process_confirmation_response(
        phone_number=session.student_phone,
        message='NO',
    )
    
    # Verify session updated
    updated_session = get_session(session.session_id)
    assert updated_session['confirmation_status'] == 'missed'
```

### Example Integration Tests

```python
# tests/integration/test_handoff_flows.py

def test_register_student_then_schedule_session_flow():
    """Test complete flow: register student → schedule session → sync calendar."""
    
    orchestrator = SwarmOrchestrator()
    trainer_id = 'test_trainer'
    
    # Step 1: Register student
    result1 = orchestrator.process_message(
        trainer_id=trainer_id,
        message='Add student John, phone +14155551234, email john@example.com, goal weight loss',
    )
    
    assert result1['success'] is True
    assert 'Student_Agent' in result1['handoff_path']
    student_id = result1['agent_contributions']['Student_Agent']['student_id']
    
    # Step 2: Schedule session
    result2 = orchestrator.process_message(
        trainer_id=trainer_id,
        message='Schedule a session with John tomorrow at 2pm for 60 minutes',
    )
    
    assert result2['success'] is True
    assert 'Session_Agent' in result2['handoff_path']
    assert 'Calendar_Agent' in result2['handoff_path']
    
    # Verify session created
    session_id = result2['agent_contributions']['Session_Agent']['session_id']
    session = get_session(session_id)
    assert session['student_id'] == student_id
    assert session['trainer_id'] == trainer_id

def test_session_confirmation_end_to_end():
    """Test complete confirmation flow from trigger to response."""
    
    # Create session that ended 1 hour ago
    session = create_test_session(
        session_datetime=datetime.utcnow() - timedelta(hours=2),
        duration_minutes=60,
    )
    
    # Trigger confirmation handler
    session_confirmation_handler({}, {})
    
    # Verify message sent to student
    messages = get_twilio_messages(to=session.student_phone)
    assert len(messages) == 1
    assert 'Did your session' in messages[0]['body']
    
    # Simulate student response
    webhook_handler({
        'From': session.student_phone,
        'Body': 'YES',
    }, {})
    
    # Verify session updated
    updated_session = get_session(session.session_id)
    assert updated_session['confirmation_status'] == 'completed'
```

### Example Property-Based Tests

```python
# tests/property/test_swarm_properties.py

from hypothesis import given, strategies as st

@given(
    message=st.text(min_size=1, max_size=500),
    trainer_id=st.text(min_size=1, max_size=50),
)
def test_shared_context_always_contains_original_request(message, trainer_id):
    """
    Feature: strands-multi-agent-architecture, Property 2:
    For any message and trainer_id, Shared_Context should always
    contain the original_request field after swarm execution.
    """
    orchestrator = SwarmOrchestrator()
    
    result = orchestrator.process_message(
        trainer_id=trainer_id,
        message=message,
    )
    
    assert 'shared_context' in result
    assert 'original_request' in result['shared_context']
    assert result['shared_context']['original_request'] == message

@given(
    handoff_count=st.integers(min_value=1, max_value=10),
)
def test_max_handoffs_prevents_infinite_loops(handoff_count):
    """
    Feature: strands-multi-agent-architecture, Property 3:
    For any handoff count exceeding max_handoffs, the swarm
    should terminate and return an error.
    """
    orchestrator = SwarmOrchestrator(max_handoffs=5)
    
    # Create scenario that would cause many handoffs
    # (mock agents to always hand off to next agent)
    with patch_agents_to_always_handoff():
        result = orchestrator.process_message(
            trainer_id='test',
            message='test',
        )
    
    if handoff_count > 5:
        assert result['success'] is False
        assert 'max_handoffs' in result['error']
    else:
        # Should complete normally
        assert result['handoff_count'] <= 5
```

```python
# tests/property/test_isolation_properties.py

@given(
    trainer1_id=st.text(min_size=1, max_size=50),
    trainer2_id=st.text(min_size=1, max_size=50),
    student_name=st.text(min_size=1, max_size=100),
)
def test_trainer_workspace_isolation(trainer1_id, trainer2_id, student_name):
    """
    Feature: strands-multi-agent-architecture, Property 4:
    For any two different trainers, students registered by one trainer
    should not be visible to the other trainer.
    """
    assume(trainer1_id != trainer2_id)
    
    # Trainer 1 registers student
    orchestrator = SwarmOrchestrator()
    orchestrator.process_message(
        trainer_id=trainer1_id,
        message=f'Add student {student_name}, phone +14155551234, email test@example.com, goal fitness',
    )
    
    # Trainer 2 tries to view students
    result = orchestrator.process_message(
        trainer_id=trainer2_id,
        message='Show me my students',
    )
    
    # Trainer 2 should not see Trainer 1's student
    students = result['agent_contributions']['Student_Agent']['students']
    student_names = [s['name'] for s in students]
    assert student_name not in student_names

@given(
    trainer_id=st.text(min_size=1, max_size=50),
)
def test_invocation_state_not_in_llm_prompts(trainer_id):
    """
    Feature: strands-multi-agent-architecture, Property 5:
    For any trainer_id, Invocation_State data should never appear
    in LLM prompts (security requirement).
    """
    with patch('boto3.client') as mock_client:
        mock_bedrock = MagicMock()
        mock_client.return_value = mock_bedrock
        
        orchestrator = SwarmOrchestrator()
        orchestrator.process_message(
            trainer_id=trainer_id,
            message='Show my students',
        )
        
        # Check all Bedrock API calls
        for call in mock_bedrock.converse.call_args_list:
            prompt_data = json.dumps(call)
            
            # Invocation_State fields should NOT appear
            assert trainer_id not in prompt_data
            assert 'trainer_id' not in prompt_data
            assert 'db_client' not in prompt_data
            assert 'invocation_state' not in prompt_data.lower()
```

```python
# tests/property/test_confirmation_properties.py

@given(
    session_datetime=st.datetimes(
        min_value=datetime(2024, 1, 1),
        max_value=datetime(2025, 12, 31),
    ),
    duration_minutes=st.integers(min_value=15, max_value=480),
)
def test_confirmation_sent_one_hour_after_session_end(session_datetime, duration_minutes):
    """
    Feature: strands-multi-agent-architecture, Property 6:
    For any session, confirmation request should be sent exactly
    1 hour after session_datetime + duration_minutes.
    """
    session = create_test_session(
        session_datetime=session_datetime,
        duration_minutes=duration_minutes,
        confirmation_status='scheduled',
    )
    
    # Calculate expected confirmation time
    expected_confirmation_time = session_datetime + timedelta(
        minutes=duration_minutes + 60
    )
    
    # Mock current time to be at confirmation time
    with freeze_time(expected_confirmation_time):
        session_confirmation_handler({}, {})
    
    # Verify confirmation was sent
    updated_session = get_session(session.session_id)
    assert updated_session['confirmation_status'] == 'pending_confirmation'
    assert updated_session['confirmation_requested_at'] is not None

@given(
    response=st.sampled_from(['YES', 'yes', 'Yes', 'NO', 'no', 'No']),
)
def test_confirmation_response_case_insensitive(response):
    """
    Feature: strands-multi-agent-architecture, Property 7:
    For any case variation of YES/NO, the system should correctly
    update confirmation_status.
    """
    session = create_test_session(
        confirmation_status='pending_confirmation'
    )
    
    process_confirmation_response(
        phone_number=session.student_phone,
        message=response,
    )
    
    updated_session = get_session(session.session_id)
    
    if response.upper() == 'YES':
        assert updated_session['confirmation_status'] == 'completed'
    else:
        assert updated_session['confirmation_status'] == 'missed'
```

### Test Coverage Requirements

- Minimum 70% code coverage for all agent-related code
- 100% coverage for security-critical functions (multi-tenancy, OAuth)
- All correctness properties must have corresponding property tests
- All edge cases identified in requirements must have unit tests

### Continuous Integration

```yaml
# .github/workflows/test.yml

name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run unit tests
        run: pytest tests/unit/ -v
      
      - name: Run property tests
        run: pytest tests/property/ -v --hypothesis-show-statistics
      
      - name: Run integration tests
        run: pytest tests/integration/ -v
      
      - name: Check coverage
        run: |
          pytest --cov=src --cov-report=html --cov-report=term
          coverage report --fail-under=70
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```



## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property Reflection

After analyzing all acceptance criteria, I identified properties that could be combined or were redundant:

**Redundancies Eliminated:**
- Requirements 1.3 and 2.1 both specify Coordinator as Entry_Agent → Combined into Property 1
- Requirements 1.5 and 8.1 both specify Shared_Context maintenance → Combined into Property 2
- Requirements 1.6, 13.2 specify max_handoffs configuration → Combined into example test
- Requirements 1.7, 13.3 specify node_timeout configuration → Combined into example test
- Requirements 1.8, 13.4 specify execution_timeout configuration → Combined into example test
- Requirements 4.9 and 7.1.9 both specify view_session_history tool → Combined into example test

**Properties Combined:**
- Student validation (3.2) and session student validation (4.4) → Combined into Property 8 (validation across all operations)
- Data propagation requirements (2.7, 3.7, 4.8, 5.7, 7.7) → Combined into Property 3 (context propagation)
- Terminal agent behavior (5.8, 6.8, 7.8) → Combined into Property 11 (terminal agents don't handoff)

### Property 1: Coordinator Entry Point

*For any* WhatsApp message received by the system, the Coordinator_Agent should be the first agent to process it (Entry_Agent configuration).

**Validates: Requirements 1.3, 2.1**

### Property 2: Shared_Context Persistence

*For any* agent handoff in the swarm, the Shared_Context should be propagated to the receiving agent and should always contain the original_request, handoff_history, and agent_contributions fields.

**Validates: Requirements 1.5, 8.1, 8.2, 8.4**

### Property 3: Entity Propagation in Context

*For any* agent that successfully completes an operation creating or modifying an entity (student, session, payment), the agent should include the entity's ID and key fields in Shared_Context for downstream agents.

**Validates: Requirements 2.7, 3.7, 4.8, 5.7, 7.7**

### Property 4: Intent-Based Handoff Routing

*For any* user message containing student-related keywords (register, add, new student), the Coordinator_Agent should hand off to Student_Agent; for session keywords (schedule, book, reschedule), hand off to Session_Agent; for payment keywords (payment, paid, receipt), hand off to Payment_Agent.

**Validates: Requirements 2.3, 2.6, 3.6, 4.6**

### Property 5: Phone Number Validation

*For any* student registration or update attempt, phone numbers not in E.164 format (+[country][number]) should be rejected with a descriptive error message.

**Validates: Requirements 3.2, 3.5**

### Property 6: Multi-Tenant Data Isolation

*For any* two different trainer_ids, data queries (students, sessions, payments) for one trainer should never return data belonging to the other trainer.

**Validates: Requirements 3.3, 12.1, 12.2, 12.3, 12.4**

### Property 7: Tool Parameter Validation

*For any* tool function call, the trainer_id parameter should be sourced from Invocation_State (not Shared_Context or user input), and attempts to access data with mismatched trainer_id should be rejected.

**Validates: Requirements 12.5, 12.6**

### Property 8: Student Existence Validation

*For any* session scheduling or payment registration attempt, the system should validate that the referenced student exists and belongs to the trainer's workspace before proceeding.

**Validates: Requirements 3.2, 4.4, 5.2**

### Property 9: Session Conflict Detection

*For any* session scheduling attempt, if another session exists for the same trainer with overlapping time (session_datetime to session_datetime + duration_minutes), the system should reject the scheduling and propose alternative times.

**Validates: Requirements 4.2, 4.3**

### Property 10: ISO 8601 DateTime Format

*For any* session operation (create, update, query), session_datetime should be stored and returned in ISO 8601 format with timezone information.

**Validates: Requirements 4.7**

### Property 11: Terminal Agent Behavior

*For any* terminal agent (Payment_Agent, Calendar_Agent, Notification_Agent), after completing its operation successfully, the agent should not initiate further handoffs and should conclude the conversation.

**Validates: Requirements 5.8, 6.8, 7.8**

### Property 12: Receipt Storage and URL Generation

*For any* payment registration with a receipt image, the system should store the image in S3 and save a presigned URL in the payment record.

**Validates: Requirements 5.3**

### Property 13: Payment Statistics Calculation

*For any* set of payments for a trainer, the calculated statistics (total_revenue, outstanding_amount) should equal the sum of confirmed payments and pending payments respectively.

**Validates: Requirements 5.6**

### Property 14: Session Statistics Calculation

*For any* set of sessions for a trainer, the attendance_rate should equal completed_sessions / (completed_sessions + missed_sessions), and should be 0.0 if no sessions are completed or missed.

**Validates: Requirements 4.11**

### Property 15: OAuth Token Encryption

*For any* calendar connection (Google or Outlook), OAuth refresh tokens should be encrypted using KMS before storage in DynamoDB, and should never appear in logs or LLM prompts.

**Validates: Requirements 6.2**

### Property 16: Calendar Sync Graceful Degradation

*For any* session creation followed by calendar sync, if calendar sync fails, the session should still be created successfully and the user should be informed of both the successful session creation and the calendar sync failure.

**Validates: Requirements 6.7, 13.8**

### Property 17: Notification Recipient Validation

*For any* broadcast notification, all recipient students should belong to the trainer's workspace (validated via Invocation_State trainer_id), and attempts to send to students from other trainers should be rejected.

**Validates: Requirements 7.2**

### Property 18: Message Template Variable Substitution

*For any* notification with template variables (student_name, session_datetime), the rendered message should contain the actual values substituted for the placeholders.

**Validates: Requirements 7.4**

### Property 19: Confirmation Message Timing

*For any* session with confirmation_status="scheduled", a confirmation request should be sent to the student exactly 1 hour after (session_datetime + duration_minutes).

**Validates: Requirements 7.1.1, 7.1.7**

### Property 20: Confirmation Message Recipient

*For any* session confirmation request, the message should be sent to the student's phone number (not the trainer's phone number).

**Validates: Requirements 7.1.2**

### Property 21: Confirmation Message Format

*For any* session confirmation request, the message should include the session date, time, trainer name, and the text "Did this session happen? Reply YES to confirm or NO if it was missed".

**Validates: Requirements 7.1.3**

### Property 22: YES Response Processing

*For any* student response of "YES" (case-insensitive) to a pending confirmation, the system should update confirmation_status to "completed", set confirmed_at to current timestamp, and store the exact response in confirmation_response.

**Validates: Requirements 7.1.4**

### Property 23: NO Response Processing

*For any* student response of "NO" (case-insensitive) to a pending confirmation, the system should update confirmation_status to "missed", set confirmed_at to current timestamp, and store the exact response in confirmation_response.

**Validates: Requirements 7.1.5**

### Property 24: Confirmation Data Persistence

*For any* session confirmation (completed or missed), the confirmation data (confirmation_status, confirmation_requested_at, confirmed_at, confirmation_response) should be persisted in the Session entity and remain unchanged even if the session is later rescheduled.

**Validates: Requirements 7.1.6, 7.1.10, 7.2.6**

### Property 25: Default Confirmation Status

*For any* newly created session, the confirmation_status field should default to "scheduled".

**Validates: Requirements 7.2.7**

### Property 26: Cancelled Session Confirmation Suppression

*For any* session that is cancelled before its scheduled time, the confirmation_status should be updated to "cancelled" and no confirmation request should be sent.

**Validates: Requirements 7.2.8**

### Property 27: Confirmation Status in Query Responses

*For any* session query (view_calendar, view_session_history), the response should include the confirmation_status field for each session.

**Validates: Requirements 7.2.9, 7.2.10**

### Property 28: Context Size Management

*For any* Shared_Context exceeding 50KB, the system should compress older conversation turns while preserving the original_request and extracted_entities fields.

**Validates: Requirements 8.6**

### Property 29: Invocation_State Visibility Isolation

*For any* swarm execution, Invocation_State data (trainer_id, db_client, phone_number) should never appear in LLM prompts or Shared_Context visible to the LLM.

**Validates: Requirements 8.5, 8.7, 12.8, 15.10**

### Property 30: Shared_Context Serialization Round-Trip

*For any* Shared_Context object, serializing to JSON and then deserializing should produce an equivalent object with all fields preserved.

**Validates: Requirements 8.8, 15.5**

### Property 31: Max Handoffs Enforcement

*For any* conversation that would exceed max_handoffs (configured value), the swarm should terminate and return an error message indicating the limit was reached.

**Validates: Requirements 13.2, 13.9, 15.7**

### Property 32: Agent Response Format Validation

*For any* agent response, the response should be valid JSON and contain the required fields: success (boolean), and either 'data' or 'error' (string).

**Validates: Requirements 15.4**

### Property 33: Feature Flag Routing

*For any* trainer, when enable_multi_agent feature flag is False, the system should use the single AIAgent class; when True, the system should use the SwarmOrchestrator.

**Validates: Requirements 20.6, 20.8, 20.9**

