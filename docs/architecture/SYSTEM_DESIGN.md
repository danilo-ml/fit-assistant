# FitAgent System Architecture

## Overview

FitAgent is a serverless, event-driven multi-tenant SaaS platform built on AWS that enables personal trainers to manage their business through an AI-powered WhatsApp assistant.

## Architecture Diagram

```
┌─────────────┐
│   Trainer   │
│  (WhatsApp) │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                      Twilio WhatsApp API                     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │  API Gateway     │
                    │  /webhook        │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Webhook Handler  │
                    │    (Lambda)      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   SQS Queue      │
                    │  (Messages)      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Message Processor│
                    │    (Lambda)      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Message Router  │
                    │ (Phone Routing)  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  AWS Strands     │
                    │  Swarm Agent     │
                    │  (6 Agents)      │
                    └────────┬─────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
    ┌─────────┐        ┌─────────┐        ┌─────────┐
    │DynamoDB │        │   S3    │        │ Secrets │
    │  Table  │        │ Bucket  │        │ Manager │
    └─────────┘        └─────────┘        └─────────┘
```

## Core Components

### 1. API Gateway + Webhook Handler
- **Purpose**: Receive incoming WhatsApp messages from Twilio
- **Technology**: AWS API Gateway + Lambda
- **Responsibilities**:
  - Validate Twilio webhook signatures
  - Queue messages to SQS for async processing
  - Return 200 OK immediately to Twilio

### 2. Message Processor
- **Purpose**: Process queued messages asynchronously
- **Technology**: Lambda triggered by SQS
- **Responsibilities**:
  - Retrieve conversation context from DynamoDB
  - Route to appropriate handler based on phone number
  - Invoke AI agent for response generation
  - Handle retries and dead-letter queue

### 3. Message Router
- **Purpose**: Identify user type and route to correct handler
- **Technology**: Python service layer
- **Responsibilities**:
  - Query phone-number-index GSI
  - Determine if trainer or student
  - Load conversation state
  - Route to appropriate agent

### 4. AWS Strands Multi-Agent System
- **Purpose**: Conversational AI orchestration
- **Technology**: AWS Strands SDK + AWS Bedrock
- **Agents**:
  1. **Coordinator Agent** (Amazon Nova Micro) - Intent routing
  2. **Student Agent** (Amazon Nova Lite) - Student management
  3. **Session Agent** (Amazon Nova Pro) - Session scheduling
  4. **Payment Agent** (Amazon Nova Lite) - Payment tracking
  5. **Calendar Agent** (Claude 3 Haiku) - Calendar integration
  6. **Notification Agent** (Amazon Nova Micro) - Broadcast messages

### 5. DynamoDB Single-Table Design
- **Purpose**: Store all entities in one table
- **Technology**: DynamoDB with GSIs
- **Entities**: Trainers, Students, Sessions, Payments, Conversations
- **GSIs**:
  - `phone-number-index`: User identification
  - `session-date-index`: Calendar queries
  - `payment-status-index`: Payment tracking

### 6. S3 Receipt Storage
- **Purpose**: Store payment receipt images
- **Technology**: S3 with presigned URLs
- **Flow**:
  - Trainer sends receipt image via WhatsApp
  - Twilio provides media URL
  - Lambda downloads and uploads to S3
  - Presigned URL stored in DynamoDB

### 7. EventBridge Schedulers
- **Purpose**: Automated reminders and notifications
- **Technology**: EventBridge + Lambda
- **Schedules**:
  - Session reminders (24h before)
  - Payment reminders (monthly)
  - Session confirmations (48h before)

## Data Flow

### Incoming Message Flow
1. User sends WhatsApp message
2. Twilio forwards to API Gateway webhook
3. Webhook handler validates and queues to SQS
4. Message processor retrieves from queue
5. Router identifies user and loads context
6. Strands agent processes message
7. Response sent back via Twilio

### Session Scheduling Flow
1. Trainer: "Schedule session with John tomorrow at 3pm"
2. Session Agent extracts entities (student, date, time)
3. Validates student exists and no conflicts
4. Creates session in DynamoDB
5. Syncs to Google Calendar (if connected)
6. Schedules EventBridge reminder
7. Confirms to trainer via WhatsApp

### Payment Tracking Flow
1. Trainer sends receipt image
2. Receipt storage service downloads from Twilio
3. Uploads to S3 with encryption
4. Creates payment record in DynamoDB
5. Generates presigned URL for viewing
6. Confirms receipt to trainer

## Security Architecture

### Authentication & Authorization
- **Phone Number-Based**: Users identified by WhatsApp phone number
- **Multi-Tenant Isolation**: Trainer ID in all queries
- **OAuth 2.0**: Calendar integrations use OAuth tokens
- **Token Storage**: Encrypted in AWS Secrets Manager

### Data Protection
- **Encryption at Rest**: DynamoDB and S3 use AWS KMS
- **Encryption in Transit**: TLS for all API calls
- **Presigned URLs**: Time-limited S3 access
- **Secret Rotation**: Automated via Secrets Manager

### Network Security
- **API Gateway**: Rate limiting and throttling
- **Lambda**: VPC isolation (optional)
- **SQS**: Dead-letter queue for failed messages
- **CloudWatch**: Audit logging for all operations

## Scalability & Performance

### Horizontal Scaling
- **Lambda**: Auto-scales to handle load
- **DynamoDB**: On-demand capacity mode
- **SQS**: Unlimited throughput
- **S3**: Unlimited storage

### Performance Optimizations
- **Async Processing**: SQS decouples webhook from processing
- **Conversation Caching**: Recent context in DynamoDB
- **GSI Queries**: Optimized for common access patterns
- **Presigned URLs**: Direct S3 access without Lambda

### Cost Optimization
- **Model Selection**: Use cheaper models for simple tasks
- **DynamoDB TTL**: Auto-delete old conversations
- **S3 Lifecycle**: Archive old receipts to Glacier
- **Lambda Memory**: Right-sized for each function

## Monitoring & Observability

### Metrics
- **CloudWatch Metrics**: Lambda duration, errors, throttles
- **Custom Metrics**: Message processing time, agent invocations
- **DynamoDB Metrics**: Read/write capacity, throttles
- **SQS Metrics**: Queue depth, message age

### Logging
- **Structured Logging**: JSON logs with context
- **CloudWatch Logs**: Centralized log aggregation
- **Log Insights**: Query and analyze logs
- **Correlation IDs**: Track requests across services

### Alerting
- **CloudWatch Alarms**: Error rate, latency, queue depth
- **SNS Notifications**: Alert on critical issues
- **Dead-Letter Queue**: Monitor failed messages

## Disaster Recovery

### Backup Strategy
- **DynamoDB**: Point-in-time recovery enabled
- **S3**: Versioning and cross-region replication
- **Secrets Manager**: Automatic replication

### Recovery Procedures
- **RTO**: 1 hour (Recovery Time Objective)
- **RPO**: 5 minutes (Recovery Point Objective)
- **Runbooks**: Documented recovery procedures
- **Testing**: Quarterly DR drills

## Deployment Architecture

### Environments
- **Local**: LocalStack + Twilio sandbox
- **Staging**: AWS with test data
- **Production**: AWS with live data

### CI/CD Pipeline
- **GitHub Actions**: Automated testing and deployment
- **OIDC Authentication**: No long-lived credentials
- **CloudFormation**: Infrastructure as Code
- **Blue-Green Deployment**: Zero-downtime updates

## Future Enhancements

- **Multi-Region**: Deploy to multiple AWS regions
- **GraphQL API**: Real-time subscriptions for web dashboard
- **ML Models**: Custom models for intent classification
- **Voice Integration**: Twilio voice calls for reminders
- **Analytics Dashboard**: Business intelligence for trainers
