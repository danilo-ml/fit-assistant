# Requirements Document: Strands Multi-Agent Simplification

## Introduction

This feature replaces the over-engineered custom Strands implementation with a simple, clean architecture using the official Strands Agents SDK. The current system has custom SDK code (src/services/strands_sdk.py), a complex orchestrator (src/services/swarm_orchestrator.py), and potentially unnecessary complexity in src/services/ai_agent.py.

Since this is NOT a production system, we can delete and recreate files without migration concerns. The goal is aggressive simplification: use the official strands-agents package, create 1-3 agents maximum (possibly just 1), follow Strands best practices, and maintain core FitAgent functionality (student/session/payment management) with proper multi-tenancy security.

## Glossary

- **Strands_SDK**: Official Python package (strands-agents) providing agent orchestration
- **Agent**: AI component with tools and system prompt from Strands SDK
- **Tool**: Python function decorated with @tool that agents can call
- **Bedrock**: AWS service providing LLM inference (Claude models)
- **Multi_Tenancy**: Isolation of trainer data using trainer_id validation
- **PT-BR**: Portuguese (Brazil) language - all WhatsApp conversations must be in Brazilian Portuguese

## Requirements

### Requirement 1: Install Official Strands Agents SDK

**User Story:** As a developer, I want to use the official Strands Agents SDK, so that I have a simple, supported implementation.

#### Acceptance Criteria

1. THE System SHALL add strands-agents to requirements.txt
2. THE System SHALL import Agent and tool from strands_agents package
3. THE System SHALL verify the SDK works with AWS Bedrock Claude models

### Requirement 2: Delete Custom Implementation Files

**User Story:** As a developer, I want to remove over-engineered custom code, so that the codebase is simple and maintainable.

#### Acceptance Criteria

1. THE System SHALL delete src/services/strands_sdk.py
2. THE System SHALL delete src/services/swarm_orchestrator.py
3. IF src/services/ai_agent.py is not needed, THEN THE System SHALL delete it
4. THE System SHALL remove all imports of deleted modules

### Requirement 3: Create Simple Agent Architecture

**User Story:** As a developer, I want a minimal agent architecture, so that the system is easy to understand.

#### Acceptance Criteria

1. THE System SHALL create 1-3 agents maximum (consider if 1 agent is sufficient)
2. IF multiple agents are needed, THEN THE System SHALL document clear rationale
3. THE System SHALL use Strands native Agent class
4. THE System SHALL keep agent system prompts concise and focused
5. THE System SHALL avoid unnecessary agent handoffs

### Requirement 4: Implement Core FitAgent Tools

**User Story:** As a trainer, I want to manage students, sessions, and payments, so that I can run my training business.

#### Acceptance Criteria

1. THE System SHALL implement student management tools (register_student, view_students, update_student)
2. THE System SHALL implement session management tools (schedule_session, reschedule_session, cancel_session, view_calendar)
3. THE System SHALL implement payment tools (register_payment, view_payments)
4. THE System SHALL use @tool decorator from strands-agents package
5. FOR ALL tools, execution with valid inputs SHALL produce expected outputs

### Requirement 5: Enforce Multi-Tenancy Security

**User Story:** As a trainer, I want my data isolated from other trainers, so that my information remains private.

#### Acceptance Criteria

1. THE System SHALL inject trainer_id into every tool execution
2. THE System SHALL validate trainer_id before accessing DynamoDB
3. IF trainer_id is missing or invalid, THEN THE System SHALL reject the tool execution with error
4. THE System SHALL scope all database queries to the authenticated trainer_id
5. FOR ALL tool executions, data SHALL be isolated by trainer_id

### Requirement 6: Handle Errors Simply

**User Story:** As a trainer, I want clear error messages, so that I understand what went wrong.

#### Acceptance Criteria

1. WHEN a tool execution fails, THE System SHALL return a descriptive error message
2. WHEN DynamoDB is unavailable, THE System SHALL return a user-friendly error
3. WHEN invalid input is provided, THE System SHALL explain what is wrong
4. THE System SHALL log errors with structured logging
5. THE System SHALL avoid exposing internal implementation details in error messages

### Requirement 7: Integrate with Existing Lambda Handlers

**User Story:** As a developer, I want the agent system to work with existing Lambda handlers, so that the WhatsApp integration continues working.

#### Acceptance Criteria

1. THE System SHALL provide a simple interface for message processing
2. THE System SHALL accept phone_number and message as inputs
3. THE System SHALL return response text for WhatsApp in PT-BR (Brazilian Portuguese)
4. THE System SHALL complete execution within 10 seconds for WhatsApp compatibility
5. THE System SHALL work with src/handlers/message_processor.py
6. FOR ALL agent responses, the language SHALL be PT-BR (Brazilian Portuguese)

### Requirement 8: Test Core Functionality

**User Story:** As a developer, I want tests for the agent system, so that I can verify it works correctly.

#### Acceptance Criteria

1. THE System SHALL include unit tests for each tool function
2. THE System SHALL include integration tests for end-to-end message processing
3. THE System SHALL test multi-tenancy isolation (trainer A cannot access trainer B data)
4. THE System SHALL test error scenarios (invalid inputs, missing trainer_id, DynamoDB errors)
5. THE System SHALL achieve minimum 70% code coverage

### Requirement 9: Use Strands Best Practices

**User Story:** As a developer, I want to follow Strands SDK patterns, so that the implementation is idiomatic and maintainable.

#### Acceptance Criteria

1. THE System SHALL use Strands native tool decorator pattern
2. THE System SHALL use Strands Agent class without custom wrappers
3. THE System SHALL follow Strands documentation for Bedrock integration
4. THE System SHALL keep tool functions simple and focused
5. THE System SHALL avoid reimplementing SDK functionality
