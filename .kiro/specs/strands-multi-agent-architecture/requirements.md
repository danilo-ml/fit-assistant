# Requirements Document

## Introduction

This document specifies the requirements for migrating FitAgent from a single-agent architecture to a multi-agent architecture using AWS Bedrock Agents (Strands Agents SDK). The migration will transform the current monolithic AI agent into a coordinated team of specialized agents that handle student management, session scheduling, payment tracking, calendar integration, and notifications through WhatsApp conversations.

Based on analysis of the official Strands documentation and FitAgent's use case characteristics, the multi-agent architecture will use the **Swarm pattern** as the primary orchestration mechanism. This pattern is optimal for FitAgent because:

1. **Multidisciplinary Task Handling**: FitAgent's operations (student management, scheduling, payments, calendar sync) benefit from specialized agent perspectives, similar to the "multidisciplinary incident response" example in Strands documentation
2. **Emergent Conversation Flow**: WhatsApp conversations are naturally exploratory - users may start discussing scheduling and shift to payments, requiring autonomous agent handoffs
3. **Shared Context**: All agents need access to trainer workspace, conversation history, and extracted entities (student names, dates, amounts)
4. **Specialization with Collaboration**: Each domain (students, sessions, payments) requires specialized tools and knowledge, but agents must collaborate seamlessly
5. **Sequential Task Execution**: Most operations are sequential (e.g., verify student exists → schedule session → sync calendar) rather than parallel

The Swarm pattern's autonomous handoff mechanism (`handoff_to_agent` tool) allows agents to dynamically transfer control based on conversation context, making it ideal for conversational AI assistants. The Graph pattern would require pre-defining all conversation paths (impractical for natural language), while Workflow pattern is too rigid for interactive conversations.

## Glossary

- **Swarm**: A Strands multi-agent pattern where specialized agents autonomously hand off tasks to each other using the `handoff_to_agent` tool
- **Entry_Agent**: The first agent in the swarm that receives the user's message and begins processing (typically the Coordinator_Agent)
- **Coordinator_Agent**: Entry point agent that analyzes user intent and hands off to the appropriate specialized agent
- **Student_Agent**: Specialized agent responsible for student registration, updates, and queries
- **Session_Agent**: Specialized agent responsible for scheduling, rescheduling, and canceling training sessions
- **Payment_Agent**: Specialized agent responsible for payment registration, confirmation, and tracking
- **Calendar_Agent**: Specialized agent responsible for calendar integration with Google and Outlook
- **Notification_Agent**: Specialized agent responsible for sending broadcast messages to students
- **Strands_SDK**: AWS Bedrock Agents SDK (open source framework) for building multi-agent systems
- **Agent_Handoff**: The process of transferring conversation control from one agent to another using `handoff_to_agent` tool
- **Shared_Context**: Working memory available to all agents containing the original request, task history, and knowledge from previous agents
- **Invocation_State**: Configuration and objects (trainer_id, db_connection) passed via kwargs, not visible in LLM prompts
- **Tool_Function**: Python function callable by agents to execute business logic
- **Conversation_Session**: Multi-turn interaction state maintained across WhatsApp messages
- **Trainer_Workspace**: Isolated data and agent instances for a specific trainer (multi-tenancy)
- **Response_Time_Budget**: Maximum 10 seconds for WhatsApp message processing
- **Nova_Model**: Amazon Nova family of cost-efficient LLMs for agent inference
- **Max_Handoffs**: Configuration limit to prevent infinite handoff loops in the swarm
- **Handoff_Timeout**: Maximum time an agent can execute before timing out

## Requirements

### Requirement 1: Swarm Pattern Implementation

**User Story:** As a system architect, I want to use the Swarm pattern for multi-agent orchestration, so that agents can autonomously collaborate and hand off tasks based on conversation context.

#### Acceptance Criteria

1. THE System SHALL implement the Swarm pattern from Strands SDK for multi-agent coordination
2. THE Swarm SHALL consist of 6 specialized agents: Coordinator, Student, Session, Payment, Calendar, and Notification agents
3. THE Coordinator_Agent SHALL be configured as the Entry_Agent that receives all incoming WhatsApp messages
4. WHEN an agent completes its task, THE Agent SHALL use the `handoff_to_agent` tool to transfer control to the most suitable peer agent
5. THE Swarm SHALL maintain Shared_Context containing the original request, task history, and knowledge from all previous agents
6. THE System SHALL configure max_handoffs parameter to prevent infinite loops (recommended: 5-7 handoffs per conversation)
7. THE System SHALL configure node_timeout parameter for individual agent execution (recommended: 30 seconds)
8. THE System SHALL configure execution_timeout parameter for total swarm execution (recommended: 120 seconds to stay within Response_Time_Budget)

### Requirement 2: Coordinator Agent Implementation

**User Story:** As a trainer or student, I want my messages to be understood and routed to the right specialized agent, so that I get accurate and relevant responses.

#### Acceptance Criteria

1. THE Coordinator_Agent SHALL be the Entry_Agent for all WhatsApp messages in the swarm
2. WHEN a message is received, THE Coordinator_Agent SHALL analyze the user intent and extract key entities (student names, dates, amounts)
3. THE Coordinator_Agent SHALL use the `handoff_to_agent` tool to transfer control to the appropriate specialized agent
4. WHEN intent is ambiguous, THE Coordinator_Agent SHALL ask clarifying questions before handing off
5. THE Coordinator_Agent SHALL have access to all agent names and their capabilities for intelligent handoff decisions
6. THE Coordinator_Agent SHALL handle general conversation (greetings, help requests) directly without handoff
7. THE Coordinator_Agent SHALL include extracted entities in the Shared_Context when handing off
8. THE Coordinator_Agent SHALL preserve Trainer_Workspace isolation by passing trainer_id via Invocation_State

### Requirement 3: Student Agent Implementation

**User Story:** As a trainer, I want a specialized agent to handle student management, so that student operations are handled consistently and accurately.

#### Acceptance Criteria

1. THE Student_Agent SHALL expose Tool_Functions for registering, viewing, and updating students
2. WHEN registering a student, THE Student_Agent SHALL validate phone number format and uniqueness within the Trainer_Workspace
3. WHEN viewing students, THE Student_Agent SHALL query DynamoDB using the trainer's partition key from Invocation_State
4. THE Student_Agent SHALL return structured data in the Shared_Context for other agents to access
5. WHEN a student operation fails validation, THE Student_Agent SHALL return descriptive error messages
6. WHEN the conversation shifts to scheduling topics, THE Student_Agent SHALL use `handoff_to_agent` to transfer control to Session_Agent
7. THE Student_Agent SHALL include student_id and student_name in Shared_Context after successful registration for downstream agents

### Requirement 4: Session Agent Implementation

**User Story:** As a trainer, I want a specialized agent to handle session scheduling, so that conflicts are detected and calendar integration works correctly.

#### Acceptance Criteria

1. THE Session_Agent SHALL expose Tool_Functions for scheduling, rescheduling, canceling, and viewing sessions with confirmation status
2. WHEN scheduling a session, THE Session_Agent SHALL check for time conflicts using the session-date-index GSI
3. WHEN a time conflict exists, THE Session_Agent SHALL propose alternative times to the user
4. THE Session_Agent SHALL validate that the student exists before creating a session by checking Shared_Context or querying DynamoDB
5. WHEN a session is successfully created, THE Session_Agent SHALL use `handoff_to_agent` to transfer control to Calendar_Agent for calendar sync
6. WHEN the conversation shifts to payment topics, THE Session_Agent SHALL use `handoff_to_agent` to transfer control to Payment_Agent
7. FOR ALL session operations, THE Session_Agent SHALL maintain session datetime in ISO 8601 format with timezone
8. THE Session_Agent SHALL include session_id, session_datetime, and student_name in Shared_Context for downstream agents
9. THE Session_Agent SHALL expose a `view_session_history` Tool_Function that returns sessions with confirmation_status (completed, missed, pending_confirmation, scheduled)
10. WHEN viewing session history, THE Session_Agent SHALL support filtering by confirmation_status and date range
11. THE Session_Agent SHALL calculate session statistics (total sessions, completed sessions, missed sessions, attendance rate)

### Requirement 5: Payment Agent Implementation

**User Story:** As a trainer, I want a specialized agent to handle payment tracking, so that I can monitor revenue and outstanding payments.

#### Acceptance Criteria

1. THE Payment_Agent SHALL expose Tool_Functions for registering payments, confirming payments, and viewing payment history
2. WHEN registering a payment, THE Payment_Agent SHALL validate the session exists and belongs to the Trainer_Workspace using Invocation_State
3. WHEN a receipt image is provided, THE Payment_Agent SHALL store it in S3 and save the presigned URL
4. THE Payment_Agent SHALL query payments using the payment-status-index GSI for efficient filtering
5. WHEN viewing payment history, THE Payment_Agent SHALL support filtering by status (pending, confirmed, overdue)
6. THE Payment_Agent SHALL calculate payment statistics (total revenue, outstanding amount) across all payments
7. THE Payment_Agent SHALL include payment_id, amount, and payment_status in Shared_Context for conversation continuity
8. WHEN payment operations are complete and no further action is needed, THE Payment_Agent SHALL conclude the conversation without handoff

### Requirement 6: Calendar Agent Implementation

**User Story:** As a trainer, I want a specialized agent to handle calendar integration, so that my sessions sync with Google Calendar or Outlook.

#### Acceptance Criteria

1. THE Calendar_Agent SHALL expose Tool_Functions for connecting calendars and syncing calendar events
2. WHEN connecting a calendar, THE Calendar_Agent SHALL initiate OAuth2 flow and store encrypted tokens in AWS Secrets Manager
3. THE Calendar_Agent SHALL support both Google Calendar API v3 and Microsoft Graph API
4. WHEN receiving a handoff from Session_Agent, THE Calendar_Agent SHALL create or update calendar events using session data from Shared_Context
5. IF OAuth tokens are expired, THEN THE Calendar_Agent SHALL attempt token refresh before failing
6. THE Calendar_Agent SHALL handle calendar API rate limits with exponential backoff
7. WHEN calendar sync fails, THE Calendar_Agent SHALL log the error but inform the user that the session was created successfully
8. THE Calendar_Agent SHALL conclude the conversation after calendar sync without further handoffs

### Requirement 7: Notification Agent Implementation

**User Story:** As a trainer, I want a specialized agent to handle broadcast notifications, so that I can communicate with multiple students efficiently.

#### Acceptance Criteria

1. THE Notification_Agent SHALL expose Tool_Functions for sending broadcast messages to student groups
2. WHEN sending a notification, THE Notification_Agent SHALL validate that all recipient students belong to the Trainer_Workspace using Invocation_State
3. THE Notification_Agent SHALL queue messages to SQS for asynchronous delivery via Twilio
4. THE Notification_Agent SHALL support message templates with variable substitution (student name, session details)
5. WHEN a broadcast fails for specific recipients, THE Notification_Agent SHALL report partial success with failed recipient list
6. THE Notification_Agent SHALL enforce rate limits to comply with Twilio WhatsApp messaging policies
7. THE Notification_Agent SHALL include notification_id and recipient_count in Shared_Context
8. THE Notification_Agent SHALL conclude the conversation after queuing notifications without further handoffs

### Requirement 7.1: Session Confirmation Feature

**User Story:** As a trainer, I want to confirm completed sessions, so that I can maintain accurate training history and analytics.

#### Acceptance Criteria

1. THE System SHALL send session confirmation messages to students after each scheduled session datetime passes
2. THE Confirmation message SHALL be sent to the student (not the trainer) to verify session attendance
3. THE Confirmation message SHALL include session details (date, time, trainer name) and ask "Did this session happen? Reply YES to confirm or NO if it was missed"
4. WHEN a student replies YES, THE System SHALL update the session status to "completed" in DynamoDB
5. WHEN a student replies NO, THE System SHALL update the session status to "missed" in DynamoDB
6. THE System SHALL create a session_confirmation record with fields: session_id, student_id, trainer_id, confirmation_status (completed/missed/pending), confirmed_at, response_message
7. THE System SHALL send confirmation requests 1 hour after the scheduled session end time
8. IF no response is received within 24 hours, THE System SHALL mark the session as "pending_confirmation" for manual review
9. THE Session_Agent SHALL expose a Tool_Function to view session history with confirmation status
10. THE System SHALL store confirmation data for future analytics (attendance rate, completion trends)
11. THE Confirmation message SHALL be sent via EventBridge scheduled trigger (similar to session_reminder and payment_reminder)
12. THE System SHALL create a new Lambda handler `session_confirmation.py` to process confirmation requests and responses

### Requirement 7.2: Session Confirmation Data Model

**User Story:** As a developer, I want a well-defined data model for session confirmations, so that analytics and reporting are accurate.

#### Acceptance Criteria

1. THE System SHALL extend the Session entity with a `confirmation_status` field with values: "scheduled", "completed", "missed", "pending_confirmation", "cancelled"
2. THE System SHALL add a `confirmation_requested_at` timestamp field to track when confirmation was sent
3. THE System SHALL add a `confirmed_at` timestamp field to track when student responded
4. THE System SHALL add a `confirmation_response` field to store the student's exact response message
5. THE System SHALL create a new GSI `session-confirmation-index` with PK: `trainer_id`, SK: `confirmation_status#session_datetime` for analytics queries
6. THE System SHALL maintain session confirmation history even if sessions are rescheduled or cancelled
7. THE System SHALL default new sessions to `confirmation_status: "scheduled"`
8. WHEN a session is cancelled before it occurs, THE System SHALL update `confirmation_status` to "cancelled" and NOT send confirmation requests
9. THE System SHALL include `confirmation_status` in all session query responses
10. THE System SHALL support querying sessions by confirmation_status for analytics (e.g., "show all missed sessions this month")

### Requirement 8: Shared Context Management

**User Story:** As a system, I want agents to share conversation context, so that users don't need to repeat information across agent handoffs.

#### Acceptance Criteria

1. THE Swarm SHALL maintain Shared_Context containing the original request, task history, and knowledge from all previous agents
2. WHEN an agent hands off to another agent, THE Swarm SHALL automatically propagate Shared_Context to the receiving agent
3. THE Shared_Context SHALL include extracted entities (student_name, session_datetime, payment_amount) from previous agents
4. THE Shared_Context SHALL include a full transcript of agent handoffs and contributions
5. THE System SHALL use Invocation_State (separate from Shared_Context) to pass trainer_id, phone_number, and database connections
6. WHEN Shared_Context exceeds 50KB, THE System SHALL summarize older conversation turns to stay within token limits
7. THE Shared_Context SHALL be visible to the LLM for reasoning, while Invocation_State SHALL NOT be visible in prompts
8. THE System SHALL serialize Shared_Context to DynamoDB for multi-turn conversations spanning multiple Lambda invocations

### Requirement 9: Strands SDK Integration

**User Story:** As a developer, I want to use the Strands Agents SDK, so that I leverage AWS best practices for multi-agent systems.

#### Acceptance Criteria

1. THE System SHALL use Strands_SDK for agent creation, tool registration, and orchestration
2. THE System SHALL configure agents with Nova_Model for cost-efficient inference
3. WHEN creating agents, THE System SHALL register Tool_Functions using Strands_SDK tool decorators
4. THE System SHALL use Strands_SDK session management for Conversation_Session persistence
5. THE System SHALL configure agent prompts and system instructions using Strands_SDK configuration
6. THE System SHALL use Strands_SDK error handling and retry mechanisms for agent invocations

### Requirement 10: Migration Strategy

**User Story:** As a developer, I want a phased migration approach, so that I can validate each agent before full deployment.

#### Acceptance Criteria

1. THE System SHALL support a feature flag to toggle between single-agent and multi-agent architectures
2. WHEN the feature flag is disabled, THE System SHALL use the existing AIAgent class
3. WHEN the feature flag is enabled, THE System SHALL use the Orchestrator_Agent and specialized agents
4. THE Migration SHALL preserve all existing Tool_Function signatures for backward compatibility
5. THE Migration SHALL reuse existing DynamoDB schema without requiring data migration
6. THE System SHALL log agent delegation decisions for monitoring and debugging during migration

### Requirement 11: Performance Requirements

**User Story:** As a user, I want fast responses, so that WhatsApp conversations feel natural and responsive.

#### Acceptance Criteria

1. WHEN processing a WhatsApp message, THE Swarm SHALL respond within the Response_Time_Budget (10 seconds)
2. THE Coordinator_Agent SHALL analyze intent and initiate handoff within 2 seconds of receiving a message
3. THE System SHALL configure execution_timeout to 120 seconds to allow for multiple handoffs while staying within budget
4. THE System SHALL configure node_timeout to 30 seconds for individual agent execution
5. THE System SHALL use DynamoDB single-table design with GSIs to minimize query latency
6. WHEN Shared_Context retrieval exceeds 1 second, THE System SHALL log a performance warning
7. THE System SHALL cache agent instances within Lambda execution contexts to avoid cold start overhead
8. THE System SHALL limit max_handoffs to 5-7 to prevent excessive latency from too many agent transitions

### Requirement 12: Multi-Tenancy and Isolation

**User Story:** As a trainer, I want my data isolated from other trainers, so that my business information remains private.

#### Acceptance Criteria

1. THE System SHALL create isolated Trainer_Workspace instances for each trainer using Invocation_State
2. THE Swarm SHALL pass trainer_id via Invocation_State (not Shared_Context) to all agents
3. THE System SHALL enforce partition key filtering in all DynamoDB queries to prevent cross-tenant data access
4. WHEN a student belongs to multiple trainers, THE System SHALL maintain separate student records per Trainer_Workspace
5. THE System SHALL validate that all Tool_Function calls include trainer_id from Invocation_State as a required parameter
6. IF a Tool_Function attempts cross-tenant access, THEN THE System SHALL reject the operation with an authorization error
7. THE Invocation_State SHALL be accessible to tools via ToolContext when using @tool(context=True) decorator
8. THE Shared_Context SHALL NOT contain trainer_id or other tenant identifiers to prevent LLM confusion

### Requirement 13: Error Handling and Resilience

**User Story:** As a user, I want graceful error handling, so that temporary failures don't break my conversation flow.

#### Acceptance Criteria

1. WHEN a specialized agent fails, THE Swarm SHALL return a user-friendly error message from the last successful agent
2. THE System SHALL configure max_handoffs to prevent infinite handoff loops (recommended: 5-7)
3. THE System SHALL configure node_timeout to prevent individual agents from hanging (recommended: 30 seconds)
4. THE System SHALL configure execution_timeout to prevent the entire swarm from exceeding Response_Time_Budget (recommended: 120 seconds)
5. WHEN DynamoDB throttling occurs, THE System SHALL use exponential backoff with jitter
6. WHEN Twilio API fails, THE System SHALL queue the message to SQS dead-letter queue for manual review
7. THE System SHALL log all agent errors with request_id, phone_number, agent_name, and handoff_count for debugging
8. WHEN Calendar_Agent fails, THE System SHALL allow session operations to complete without calendar sync
9. WHEN max_handoffs is reached, THE Swarm SHALL return the best available response from the last agent

### Requirement 14: Conversation Continuity

**User Story:** As a user, I want seamless conversations across multiple messages, so that I can complete complex tasks naturally.

#### Acceptance Criteria

1. THE System SHALL maintain Conversation_Session state for at least 30 minutes of inactivity
2. WHEN a user sends a follow-up message, THE Coordinator_Agent SHALL retrieve the previous Shared_Context from DynamoDB
3. THE System SHALL support conversation branching where users switch topics mid-conversation
4. WHEN switching topics, THE Coordinator_Agent SHALL hand off to a different specialized agent while preserving Shared_Context
5. THE System SHALL support multi-step workflows (e.g., register student → schedule session → sync calendar) through sequential handoffs
6. WHEN a conversation times out, THE System SHALL start a new Conversation_Session on the next message
7. THE Swarm SHALL maintain full transcript history in Shared_Context showing all agent handoffs and contributions
8. THE System SHALL include handoff_count in Shared_Context to track conversation complexity

### Requirement 15: Testing and Validation

**User Story:** As a developer, I want comprehensive testing, so that I can validate agent behavior and prevent regressions.

#### Acceptance Criteria

1. THE System SHALL include unit tests for each specialized agent's Tool_Functions
2. THE System SHALL include integration tests for swarm handoff scenarios (Coordinator → Student → Session → Calendar)
3. THE System SHALL include property-based tests for swarm coordination invariants
4. FOR ALL agent responses, property tests SHALL verify that responses are valid JSON and contain required fields
5. THE System SHALL include property tests for Shared_Context serialization round-trips (serialize then deserialize equals original)
6. THE System SHALL include property tests for multi-tenant isolation (no cross-tenant data leakage via Invocation_State)
7. THE System SHALL include property tests for handoff limits (max_handoffs prevents infinite loops)
8. THE System SHALL include property tests for timeout behavior (node_timeout and execution_timeout are respected)
9. THE System SHALL achieve minimum 70% code coverage for all agent-related code
10. THE System SHALL include tests verifying Invocation_State is not visible in LLM prompts

### Requirement 16: Monitoring and Observability

**User Story:** As an operator, I want visibility into agent behavior, so that I can troubleshoot issues and optimize performance.

#### Acceptance Criteria

1. THE System SHALL log all agent handoffs with source_agent, target_agent, handoff_reason, and timestamp
2. THE System SHALL emit CloudWatch metrics for swarm invocation count, latency, and error rate
3. THE System SHALL log handoff_count for each conversation to track collaboration complexity
4. THE System SHALL track Response_Time_Budget compliance and alert when execution_timeout is exceeded
5. THE System SHALL log Shared_Context size for monitoring memory usage trends
6. THE System SHALL emit custom metrics for business operations (sessions_scheduled, payments_registered) per agent
7. THE System SHALL log the full handoff path (e.g., Coordinator → Student → Session → Calendar) for each conversation
8. THE System SHALL track max_handoffs violations and alert when conversations hit the limit
9. THE System SHALL monitor node_timeout violations per agent to identify slow agents

### Requirement 17: Cost Optimization

**User Story:** As a business owner, I want cost-efficient AI inference, so that the platform remains profitable at scale.

#### Acceptance Criteria

1. THE System SHALL use Nova_Model as the default model for all agents
2. WHEN Nova_Model is insufficient for complex reasoning, THE System SHALL allow per-agent model configuration
3. THE System SHALL cache agent responses for identical queries within a 5-minute window
4. THE System SHALL use prompt compression techniques to minimize token usage
5. THE System SHALL monitor token usage per agent and emit cost metrics to CloudWatch
6. WHEN token usage exceeds budget thresholds, THE System SHALL alert operators

### Requirement 18: Agent Prompt Engineering

**User Story:** As a developer, I want well-crafted agent prompts, so that agents behave consistently and accurately.

#### Acceptance Criteria

1. THE Coordinator_Agent SHALL have a system prompt that defines its role as intent analyzer and handoff initiator
2. WHEN defining specialized agent prompts, THE System SHALL include agent role, available tools, and handoff guidelines
3. THE System SHALL include few-shot examples in agent prompts for common user intents and handoff scenarios
4. THE System SHALL define clear handoff triggers in agent prompts (e.g., "use handoff_to_agent to transfer to Payment_Agent when user mentions payment")
5. THE System SHALL instruct agents to include relevant data in Shared_Context before handing off
6. THE System SHALL instruct agents when to conclude conversations without further handoffs
7. THE System SHALL version agent prompts and track changes in source control
8. THE System SHALL support A/B testing of agent prompts through configuration
9. THE System SHALL instruct agents to check Shared_Context for previously extracted entities before asking users to repeat information

### Requirement 19: Security and Compliance

**User Story:** As a user, I want my data protected, so that my personal information remains secure.

#### Acceptance Criteria

1. THE System SHALL encrypt OAuth tokens using AWS KMS before storing in Secrets Manager
2. THE System SHALL validate all user inputs in Tool_Functions to prevent injection attacks
3. THE System SHALL sanitize phone numbers and remove PII from CloudWatch logs
4. WHEN storing Shared_Context in DynamoDB, THE System SHALL encrypt sensitive fields at rest
5. THE System SHALL enforce HTTPS for all external API calls (Twilio, Google, Microsoft)
6. THE System SHALL rotate OAuth tokens according to provider requirements (Google: 7 days, Microsoft: 90 days)
7. THE System SHALL ensure Invocation_State (containing trainer_id) is never logged or exposed in LLM prompts
8. THE System SHALL validate that Shared_Context does not contain sensitive credentials or API keys

### Requirement 20: Backward Compatibility

**User Story:** As a developer, I want existing integrations to work unchanged, so that the migration doesn't break dependent systems.

#### Acceptance Criteria

1. THE System SHALL maintain existing Lambda handler signatures (webhook_handler, message_processor)
2. THE System SHALL preserve existing DynamoDB table schema and GSI definitions
3. THE System SHALL maintain existing SQS queue message formats
4. THE System SHALL preserve existing Twilio webhook response format
5. THE System SHALL maintain existing S3 bucket structure for receipt storage
6. THE System SHALL support gradual rollout per trainer using the feature flag mechanism
7. THE System SHALL maintain existing Tool_Function signatures for backward compatibility
8. WHEN the feature flag is disabled, THE System SHALL use the existing single AIAgent class
9. WHEN the feature flag is enabled, THE System SHALL use the Swarm-based multi-agent architecture

