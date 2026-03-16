# Bugfix Requirements Document

## Introduction

FitAgent's WhatsApp assistant has two critical issues affecting user experience:

1. **Message Ordering Bug**: Messages are arriving out of order in WhatsApp conversations, causing responses to appear before questions. This breaks the conversational flow between trainers/students and the AI assistant, making interactions confusing and unprofessional.

2. **Missing Brazilian Portuguese Language Support**: All WhatsApp conversations must be conducted in Brazilian Portuguese (pt-BR) as this is a core requirement for the target market. Currently, the AI assistant responds in English, making the system unusable for Brazilian users.

The message ordering issue stems from the asynchronous SQS processing architecture where messages can be processed in parallel without ordering guarantees. The language issue is a missing implementation in the AI agent's system prompt and response generation.

## Bug Analysis

### Current Behavior (Defect)

#### Message Ordering Issues

1.1 WHEN a user sends multiple WhatsApp messages in quick succession THEN the system processes them in parallel via SQS, causing responses to arrive out of order

1.2 WHEN a user sends message A followed immediately by message B THEN the system may respond to message B before message A, breaking conversational context

1.3 WHEN the AI agent processes a message THEN it does not wait for previous messages from the same user to complete processing, leading to race conditions

1.4 WHEN conversation state is updated by concurrent message processors THEN the last write wins, potentially losing conversation history or context from earlier messages

#### Language Support Issues

1.5 WHEN the AI agent generates responses THEN it responds in English instead of Brazilian Portuguese (pt-BR)

1.6 WHEN the AI agent uses tool functions THEN the natural language responses are in English, not Portuguese

1.7 WHEN error messages are generated THEN they appear in English instead of Portuguese

1.8 WHEN the onboarding flow guides new trainers THEN all prompts and instructions are in English instead of Portuguese

### Expected Behavior (Correct)

#### Message Ordering Fixes

2.1 WHEN a user sends multiple WhatsApp messages in quick succession THEN the system SHALL process them sequentially in the order they were received

2.2 WHEN a user sends message A followed by message B THEN the system SHALL complete processing and responding to message A before starting to process message B

2.3 WHEN the AI agent processes a message THEN it SHALL wait for any in-flight messages from the same phone number to complete before processing

2.4 WHEN conversation state is updated THEN the system SHALL use optimistic locking or message ordering mechanisms to prevent race conditions and preserve conversation history

#### Language Support Fixes

2.5 WHEN the AI agent generates responses THEN it SHALL respond in Brazilian Portuguese (pt-BR) for all user-facing messages

2.6 WHEN the AI agent uses tool functions THEN it SHALL format natural language responses in Brazilian Portuguese

2.7 WHEN error messages are generated THEN they SHALL appear in Brazilian Portuguese with culturally appropriate phrasing

2.8 WHEN the onboarding flow guides new trainers THEN all prompts, instructions, and confirmations SHALL be in Brazilian Portuguese

### Unchanged Behavior (Regression Prevention)

#### System Architecture

3.1 WHEN messages are processed through the webhook → SQS → Lambda flow THEN the system SHALL CONTINUE TO use the existing architecture without requiring synchronous processing

3.2 WHEN the AI agent calls tool functions THEN the system SHALL CONTINUE TO use the existing tool registry and execution map

3.3 WHEN conversation state is stored in DynamoDB THEN the system SHALL CONTINUE TO use the existing ConversationState entity structure

3.4 WHEN the message router identifies users THEN the system SHALL CONTINUE TO use phone number lookup via the phone-number-index GSI

#### Functionality

3.5 WHEN trainers use any of the 10 tool functions (register_student, schedule_session, etc.) THEN the system SHALL CONTINUE TO execute them correctly with the same parameters and validation

3.6 WHEN students receive session reminders THEN the system SHALL CONTINUE TO send them at the configured times

3.7 WHEN calendar integration is used THEN the system SHALL CONTINUE TO sync with Google Calendar and Outlook

3.8 WHEN payment receipts are uploaded THEN the system SHALL CONTINUE TO store them in S3 with presigned URLs

#### Code and Documentation

3.9 WHEN developers read code, comments, and documentation THEN they SHALL CONTINUE TO be in English

3.10 WHEN infrastructure configuration files are written THEN they SHALL CONTINUE TO use English for parameter names and descriptions

3.11 WHEN log messages are generated THEN they SHALL CONTINUE TO be in English for developer debugging
