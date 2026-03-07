# Requirements Document

## Introduction

FitAgent is a multi-tenant SaaS platform that enables personal trainers to manage their students, schedule training sessions, track payments, and send notifications through an AI-powered conversational assistant on WhatsApp. The system uses AWS Strands for agentic orchestration and AWS Bedrock for LLM inference, providing a natural language interface for both trainers and students to interact with the platform without requiring a web dashboard or mobile app.

## Glossary

- **FitAgent_Platform**: The complete SaaS system including WhatsApp interface, AI agent, and backend services
- **WhatsApp_Gateway**: The Twilio-based service that receives and sends WhatsApp messages
- **AI_Agent**: The AWS Strands orchestrated agent using AWS Bedrock for natural language understanding and tool execution
- **Trainer**: A personal trainer user who manages students and sessions through WhatsApp
- **Student**: A client of a trainer who receives training sessions and interacts through WhatsApp
- **Session**: A scheduled training appointment between a trainer and student
- **Payment_Record**: A record of payment confirmation with optional receipt media
- **Calendar_Sync**: Integration with Google Calendar or Microsoft Outlook via OAuth2
- **Conversation_State**: The current state of a WhatsApp conversation (UNKNOWN, ONBOARDING, TRAINER_MENU, STUDENT_MENU)
- **Message_Router**: Component that identifies users by phone number and routes messages to appropriate handlers
- **Receipt_Media**: Image or PDF payment receipt stored in S3
- **Reminder_Service**: EventBridge-based scheduler for automated notifications
- **Local_Environment**: LocalStack, moto, and Docker Compose setup for local development

## Requirements

### Requirement 1: Trainer Registration and Onboarding

**User Story:** As a new trainer, I want to register through WhatsApp, so that I can start managing my students and sessions.

#### Acceptance Criteria

1. WHEN an unregistered phone number sends a message, THE AI_Agent SHALL initiate the onboarding conversation
2. THE AI_Agent SHALL collect trainer name, email, and business name during onboarding
3. WHEN onboarding is complete, THE FitAgent_Platform SHALL create a trainer record in DynamoDB
4. THE FitAgent_Platform SHALL assign a unique trainer identifier to each registered trainer
5. WHEN a trainer completes onboarding, THE AI_Agent SHALL present the main menu options

### Requirement 2: Student Management

**User Story:** As a trainer, I want to register and manage students via WhatsApp, so that I can track my client base without using a separate application.

#### Acceptance Criteria

1. WHEN a trainer requests to register a student, THE AI_Agent SHALL collect student name, phone number, email, and training goal
2. THE FitAgent_Platform SHALL validate that the phone number follows E.164 format before creating a student record
3. THE FitAgent_Platform SHALL support many-to-many relationships where one student can be linked to multiple trainers
4. WHEN a student is registered, THE FitAgent_Platform SHALL create a Trainer-Student link record in DynamoDB
5. WHEN a trainer requests student information, THE AI_Agent SHALL retrieve and display student details including training goal and payment status
6. THE AI_Agent SHALL allow trainers to update student information through conversational commands

### Requirement 3: Session Scheduling

**User Story:** As a trainer, I want to schedule training sessions via WhatsApp, so that I can manage my calendar conversationally.

#### Acceptance Criteria

1. WHEN a trainer requests to schedule a session, THE AI_Agent SHALL collect student name, date, time, and duration
2. THE FitAgent_Platform SHALL validate that the session time does not conflict with existing sessions for the trainer
3. WHEN a session is scheduled, THE FitAgent_Platform SHALL create a session record in DynamoDB with status "scheduled"
4. THE FitAgent_Platform SHALL store session datetime in ISO 8601 format with timezone information
5. WHEN a trainer requests to reschedule a session, THE AI_Agent SHALL update the session record and maintain audit history
6. WHEN a trainer requests to cancel a session, THE FitAgent_Platform SHALL update the session status to "cancelled"
7. THE AI_Agent SHALL allow trainers to view sessions by day, week, or month through conversational queries

### Requirement 4: Calendar Integration

**User Story:** As a trainer, I want my sessions automatically synced to Google Calendar or Outlook, so that I can see my schedule in my preferred calendar application.

#### Acceptance Criteria

1. WHEN a trainer initiates calendar connection, THE FitAgent_Platform SHALL generate an OAuth2 authorization URL for Google Calendar or Microsoft Outlook
2. THE FitAgent_Platform SHALL store OAuth2 refresh tokens encrypted in DynamoDB per trainer
3. WHEN a session is scheduled, THE Calendar_Sync SHALL create a calendar event in the trainer's connected calendar within 30 seconds
4. WHEN a session is rescheduled, THE Calendar_Sync SHALL update the corresponding calendar event within 30 seconds
5. WHEN a session is cancelled, THE Calendar_Sync SHALL delete the corresponding calendar event within 30 seconds
6. IF calendar API calls fail, THEN THE FitAgent_Platform SHALL retry up to 3 times with exponential backoff
7. IF calendar sync fails after retries, THEN THE FitAgent_Platform SHALL log the error and continue session creation without blocking the user

### Requirement 5: Payment Receipt Handling

**User Story:** As a trainer, I want to receive and confirm payment receipts via WhatsApp, so that I can track which students have paid without manual record-keeping.

#### Acceptance Criteria

1. WHEN a student or trainer sends an image or PDF via WhatsApp, THE WhatsApp_Gateway SHALL forward the media to the FitAgent_Platform
2. THE FitAgent_Platform SHALL store receipt media in S3 with a unique key containing trainer ID, student ID, and timestamp
3. WHEN receipt media is stored, THE FitAgent_Platform SHALL create a Payment_Record with status "pending" in DynamoDB
4. WHEN a trainer confirms a payment, THE FitAgent_Platform SHALL update the Payment_Record status to "confirmed" and record the confirmation timestamp
5. THE AI_Agent SHALL allow trainers to view payment status per student through conversational queries
6. THE FitAgent_Platform SHALL generate S3 presigned URLs with 1 hour expiration when trainers request to view receipt media
7. THE FitAgent_Platform SHALL support manual payment registration without receipt media when trainers provide payment details conversationally

### Requirement 6: Message Routing and User Identification

**User Story:** As a user, I want the system to recognize me by my phone number, so that I can interact with the appropriate interface without manual authentication.

#### Acceptance Criteria

1. WHEN a message is received, THE Message_Router SHALL extract the sender phone number from the WhatsApp webhook payload
2. THE Message_Router SHALL query DynamoDB using a GSI on phone number to identify if the sender is a trainer, student, or unknown
3. WHEN a trainer is identified, THE Message_Router SHALL route the message to the trainer conversation handler
4. WHEN a student is identified, THE Message_Router SHALL route the message to the student conversation handler
5. WHEN an unknown phone number is detected, THE Message_Router SHALL route the message to the onboarding handler
6. THE FitAgent_Platform SHALL complete phone number lookup and routing within 200 milliseconds

### Requirement 7: Student Session Viewing and Confirmation

**User Story:** As a student, I want to view my upcoming sessions and confirm attendance via WhatsApp, so that I can manage my training schedule easily.

#### Acceptance Criteria

1. WHEN a student requests upcoming sessions, THE AI_Agent SHALL retrieve sessions scheduled within the next 30 days for that student
2. THE AI_Agent SHALL display session information including trainer name, date, time, and location if provided
3. WHEN a student confirms attendance, THE FitAgent_Platform SHALL update the session record with confirmation status and timestamp
4. WHEN a student requests to cancel attendance, THE AI_Agent SHALL notify the associated trainer via WhatsApp within 5 minutes
5. THE AI_Agent SHALL display sessions in chronological order with the nearest session first

### Requirement 8: Automated Session Reminders

**User Story:** As a trainer, I want automated session reminders sent to students, so that I can reduce no-shows without manual follow-up.

#### Acceptance Criteria

1. WHERE reminder configuration is enabled, THE Reminder_Service SHALL send session reminders to students at the configured hours before the session
2. THE FitAgent_Platform SHALL allow trainers to configure reminder timing between 1 and 48 hours before sessions
3. THE Reminder_Service SHALL use EventBridge scheduled rules to trigger reminder Lambda functions
4. WHEN a reminder is triggered, THE FitAgent_Platform SHALL send a WhatsApp message to the student including session details
5. THE FitAgent_Platform SHALL not send reminders for sessions with status "cancelled"
6. THE FitAgent_Platform SHALL record reminder delivery status in DynamoDB for audit purposes

### Requirement 9: Automated Payment Reminders

**User Story:** As a trainer, I want automated monthly payment reminders sent to students, so that I can maintain consistent cash flow without manual collection efforts.

#### Acceptance Criteria

1. WHERE payment reminders are enabled, THE Reminder_Service SHALL send payment reminders on the configured day of each month
2. THE FitAgent_Platform SHALL allow trainers to configure the reminder day between 1 and 28 of the month
3. WHEN a payment reminder is triggered, THE FitAgent_Platform SHALL send a WhatsApp message to students who have unpaid sessions in the previous month
4. THE FitAgent_Platform SHALL include the total amount due and number of unpaid sessions in the reminder message
5. THE FitAgent_Platform SHALL not send payment reminders to students with all payments confirmed for the previous month

### Requirement 10: Custom Trainer Notifications

**User Story:** As a trainer, I want to send custom broadcast messages to my students, so that I can communicate schedule changes or announcements efficiently.

#### Acceptance Criteria

1. WHEN a trainer requests to send a notification, THE AI_Agent SHALL collect the message content and target recipients
2. THE AI_Agent SHALL allow trainers to select all students, specific students, or students with upcoming sessions as recipients
3. WHEN notification recipients are confirmed, THE FitAgent_Platform SHALL queue individual WhatsApp messages for each recipient in SQS
4. THE FitAgent_Platform SHALL process notification messages at a rate not exceeding 10 messages per second to comply with WhatsApp rate limits
5. THE FitAgent_Platform SHALL record notification delivery status per recipient in DynamoDB
6. IF a notification fails to deliver, THEN THE FitAgent_Platform SHALL retry up to 2 times with 5 minute delays between attempts

### Requirement 11: Conversation State Management

**User Story:** As a user, I want the system to remember the context of our conversation, so that I can complete multi-step tasks naturally without repeating information.

#### Acceptance Criteria

1. THE FitAgent_Platform SHALL maintain conversation state per phone number in DynamoDB with TTL of 24 hours
2. WHEN a user starts a conversation, THE FitAgent_Platform SHALL initialize conversation state to UNKNOWN
3. WHEN a trainer is identified, THE FitAgent_Platform SHALL transition conversation state to TRAINER_MENU
4. WHEN a student is identified, THE FitAgent_Platform SHALL transition conversation state to STUDENT_MENU
5. THE AI_Agent SHALL use conversation state to provide contextually appropriate responses and menu options
6. WHEN 24 hours pass without messages, THE FitAgent_Platform SHALL expire the conversation state and start fresh on next message

### Requirement 12: AI Agent Tool Execution

**User Story:** As a user, I want the AI to execute actions based on my natural language requests, so that I can interact conversationally without learning specific commands.

#### Acceptance Criteria

1. THE AI_Agent SHALL use AWS Bedrock with Claude models for natural language understanding
2. THE AI_Agent SHALL implement tool-calling architecture with functions for register_student, schedule_session, register_payment, send_notification, view_calendar, and view_payments
3. WHEN the AI_Agent determines a tool should be called, THE FitAgent_Platform SHALL execute the tool function and return results to the AI_Agent within 5 seconds
4. THE AI_Agent SHALL validate tool parameters before execution and request clarification for missing or invalid parameters
5. WHEN a tool execution fails, THE AI_Agent SHALL provide a user-friendly error message and suggest corrective actions
6. THE AI_Agent SHALL maintain conversation context across multiple tool executions within a single user request

### Requirement 13: WhatsApp Message Processing

**User Story:** As a user, I want my WhatsApp messages processed reliably, so that I can trust the system to handle my requests even during high traffic.

#### Acceptance Criteria

1. WHEN a WhatsApp message is received, THE WhatsApp_Gateway SHALL send a webhook POST request to API Gateway
2. THE FitAgent_Platform SHALL validate the Twilio webhook signature to ensure message authenticity
3. WHEN a webhook is validated, THE FitAgent_Platform SHALL enqueue the message to SQS within 100 milliseconds
4. THE FitAgent_Platform SHALL process messages from SQS using Lambda functions with concurrency limit of 10
5. WHEN message processing fails, THE SQS queue SHALL retry with exponential backoff up to 3 times
6. IF message processing fails after all retries, THEN THE FitAgent_Platform SHALL move the message to a dead-letter queue for manual review
7. THE FitAgent_Platform SHALL send WhatsApp responses within 10 seconds of receiving the original message

### Requirement 14: Data Storage and Retrieval

**User Story:** As a system administrator, I want data stored efficiently in DynamoDB, so that the platform can scale to thousands of trainers while maintaining fast query performance.

#### Acceptance Criteria

1. THE FitAgent_Platform SHALL use single-table design in DynamoDB with composite primary key (PK, SK)
2. THE FitAgent_Platform SHALL implement GSI for phone number lookups with partition key "phone_number"
3. THE FitAgent_Platform SHALL implement GSI for session date queries with partition key "trainer_id" and sort key "session_date"
4. THE FitAgent_Platform SHALL complete single-item reads from DynamoDB within 50 milliseconds at p99
5. THE FitAgent_Platform SHALL complete query operations returning up to 100 items within 200 milliseconds at p99
6. THE FitAgent_Platform SHALL use DynamoDB TTL for automatic cleanup of expired conversation state records
7. THE FitAgent_Platform SHALL enable point-in-time recovery for the DynamoDB table

### Requirement 15: Local Development Environment

**User Story:** As a developer, I want to run the entire platform locally, so that I can develop and test without incurring AWS costs or requiring internet connectivity.

#### Acceptance Criteria

1. THE Local_Environment SHALL use LocalStack to emulate DynamoDB, S3, SQS, Lambda, API Gateway, and EventBridge
2. THE Local_Environment SHALL use moto for AWS SDK mocking where LocalStack is insufficient
3. THE Local_Environment SHALL provide a docker-compose.yml file that starts all required services with a single command
4. WHEN docker-compose is started, THE Local_Environment SHALL initialize DynamoDB tables with the production schema
5. WHEN docker-compose is started, THE Local_Environment SHALL create S3 buckets matching the production configuration
6. THE Local_Environment SHALL expose API Gateway on localhost port 4566 for webhook testing
7. THE Local_Environment SHALL provide environment variables to configure AWS SDK clients to use LocalStack endpoints

### Requirement 16: Infrastructure as Code

**User Story:** As a DevOps engineer, I want infrastructure defined in CloudFormation, so that I can deploy the platform consistently across environments.

#### Acceptance Criteria

1. THE FitAgent_Platform SHALL provide CloudFormation templates for all AWS resources
2. THE CloudFormation templates SHALL define DynamoDB tables, S3 buckets, Lambda functions, API Gateway, SQS queues, and EventBridge rules
3. THE CloudFormation templates SHALL use parameters for environment-specific values such as Twilio credentials and OAuth client IDs
4. THE CloudFormation templates SHALL define IAM roles with least-privilege permissions for each Lambda function
5. THE CloudFormation templates SHALL enable CloudWatch Logs for all Lambda functions with 7-day retention
6. THE CloudFormation templates SHALL output API Gateway endpoint URL and S3 bucket names for reference

### Requirement 17: Deployment Automation

**User Story:** As a developer, I want automated deployment via GitHub Actions, so that I can deploy changes to production with confidence and minimal manual steps.

#### Acceptance Criteria

1. THE FitAgent_Platform SHALL provide GitHub Actions workflows for CI/CD
2. WHEN code is pushed to the main branch, THE GitHub Actions workflow SHALL run all tests and linting checks
3. WHEN tests pass, THE GitHub Actions workflow SHALL package Lambda functions and upload to S3
4. WHEN Lambda packages are uploaded, THE GitHub Actions workflow SHALL deploy CloudFormation stacks using AWS CLI
5. THE GitHub Actions workflow SHALL validate CloudFormation templates before deployment
6. IF deployment fails, THEN THE GitHub Actions workflow SHALL rollback to the previous stack version
7. THE GitHub Actions workflow SHALL require manual approval for production deployments

### Requirement 18: Testing and Quality Assurance

**User Story:** As a developer, I want comprehensive test coverage, so that I can refactor code confidently and catch bugs before production.

#### Acceptance Criteria

1. THE FitAgent_Platform SHALL achieve minimum 70% code coverage across all Python modules
2. THE FitAgent_Platform SHALL include unit tests for all AI_Agent tool functions
3. THE FitAgent_Platform SHALL include integration tests for WhatsApp message processing end-to-end
4. THE FitAgent_Platform SHALL include integration tests for calendar sync with mocked OAuth responses
5. THE FitAgent_Platform SHALL use pytest as the testing framework with fixtures for DynamoDB and S3 mocking
6. THE FitAgent_Platform SHALL run tests in GitHub Actions on every pull request
7. THE FitAgent_Platform SHALL fail the build if code coverage drops below 70%

### Requirement 19: Error Handling and Logging

**User Story:** As a system administrator, I want comprehensive error logging, so that I can diagnose and resolve issues quickly when they occur in production.

#### Acceptance Criteria

1. WHEN an error occurs in any Lambda function, THE FitAgent_Platform SHALL log the error to CloudWatch with ERROR level
2. THE FitAgent_Platform SHALL include request ID, user phone number, and stack trace in error logs
3. THE FitAgent_Platform SHALL log all AI_Agent tool executions with INFO level including tool name and parameters
4. THE FitAgent_Platform SHALL log all external API calls (WhatsApp, Calendar) with INFO level including response status
5. THE FitAgent_Platform SHALL use structured JSON logging for all log entries to enable CloudWatch Insights queries
6. THE FitAgent_Platform SHALL not log sensitive information such as OAuth tokens or full phone numbers in plain text
7. WHEN critical errors occur, THE FitAgent_Platform SHALL publish metrics to CloudWatch for alerting

### Requirement 20: Security and Data Protection

**User Story:** As a platform owner, I want user data protected and access controlled, so that I can maintain trust and comply with data protection regulations.

#### Acceptance Criteria

1. THE FitAgent_Platform SHALL encrypt all data at rest in DynamoDB using AWS managed keys
2. THE FitAgent_Platform SHALL encrypt all data at rest in S3 using AWS managed keys
3. THE FitAgent_Platform SHALL encrypt OAuth refresh tokens before storing in DynamoDB using AWS KMS
4. THE FitAgent_Platform SHALL validate and sanitize all user inputs before processing to prevent injection attacks
5. THE FitAgent_Platform SHALL use HTTPS for all external API communications including WhatsApp and Calendar APIs
6. THE FitAgent_Platform SHALL implement API Gateway request validation to reject malformed webhook payloads
7. THE FitAgent_Platform SHALL verify Twilio webhook signatures to prevent unauthorized message injection
8. THE FitAgent_Platform SHALL implement rate limiting on API Gateway to prevent abuse with limit of 100 requests per minute per IP
