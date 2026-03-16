# Implementation Plan: Strands Multi-Agent Simplification

## Overview

This implementation replaces ~2,500 lines of custom Strands code with ~200 lines using the official strands-agents SDK. The approach is aggressive simplification: delete custom files, install the official SDK, create a single agent with all tools, and maintain multi-tenancy security. Since this is not production, we can freely delete and recreate files.

## Tasks

- [x] 1. Install official Strands Agents SDK and verify compatibility
  - Add strands-agents to requirements.txt
  - Verify SDK works with AWS Bedrock Claude models
  - Test basic Agent and @tool imports
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Delete custom implementation files
  - Delete src/services/strands_sdk.py (~600 lines)
  - Delete src/services/swarm_orchestrator.py (~1,100 lines)
  - Delete src/services/ai_agent.py (~800 lines)
  - Remove feature_flags.py references to multi-agent feature flag
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 3. Create new StrandsAgentService with single agent
  - [x] 3.1 Create src/services/strands_agent_service.py
    - Implement StrandsAgentService class with __init__ and process_message methods
    - Initialize single Strands Agent with Bedrock configuration and PT-BR system prompt
    - Implement trainer_id injection into tool execution context
    - Add timeout protection (10-second limit)
    - Add structured logging for all operations
    - Ensure all agent responses are in PT-BR (Brazilian Portuguese)
    - _Requirements: 3.1, 3.3, 5.1, 6.4, 7.1, 7.4, 7.6_

  - [ ]* 3.2 Write property test for multi-tenancy injection
    - **Property 2: Multi-Tenancy Injection**
    - **Validates: Requirements 5.1**

  - [ ]* 3.3 Write property test for execution timeout
    - **Property 8: Execution Timeout**
    - **Validates: Requirements 7.4**

  - [ ]* 3.4 Write property test for response format
    - **Property 7: Response Format**
    - Verify responses are in PT-BR (Brazilian Portuguese)
    - **Validates: Requirements 7.3, 7.6**

- [x] 4. Update tool functions to use Strands @tool decorator
  - [x] 4.1 Update src/tools/student_tools.py
    - Add @tool decorator to register_student, view_students, update_student
    - Ensure trainer_id parameter is first in all functions
    - Add docstrings for agent understanding
    - _Requirements: 4.1, 4.4, 9.1_

  - [x] 4.2 Update src/tools/session_tools.py
    - Add @tool decorator to schedule_session, reschedule_session, cancel_session, view_calendar
    - Ensure trainer_id parameter is first in all functions
    - Add docstrings for agent understanding
    - _Requirements: 4.2, 4.4, 9.1_

  - [x] 4.3 Update src/tools/payment_tools.py
    - Add @tool decorator to register_payment, view_payments
    - Ensure trainer_id parameter is first in all functions
    - Add docstrings for agent understanding
    - _Requirements: 4.3, 4.4, 9.1_

  - [ ]* 4.4 Write property test for tool execution correctness
    - **Property 1: Tool Execution Correctness**
    - **Validates: Requirements 4.5**

  - [ ]* 4.5 Write property test for multi-tenancy validation
    - **Property 3: Multi-Tenancy Validation**
    - **Validates: Requirements 5.2, 5.3**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Update message_processor.py to use new service
  - [x] 6.1 Replace SwarmOrchestrator/AIAgent calls with StrandsAgentService
    - Import StrandsAgentService
    - Remove feature flag logic for multi-agent
    - Update message processing to call agent_service.process_message()
    - Keep existing phone number routing and error handling
    - _Requirements: 2.4, 7.1, 7.2, 7.5_

  - [ ]* 6.2 Write integration test for end-to-end message processing
    - Test message_processor.py Lambda handler with StrandsAgentService
    - Test successful message processing flow
    - Test error handling flow
    - _Requirements: 8.2_

- [x] 7. Implement comprehensive error handling
  - [x] 7.1 Add error handling in StrandsAgentService
    - Handle validation errors (invalid trainer_id, missing fields)
    - Handle system errors (DynamoDB throttling, Bedrock API errors)
    - Handle timeout errors
    - Convert exceptions to user-friendly messages
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [ ]* 7.2 Write property test for error message quality
    - **Property 5: Error Message Quality**
    - **Validates: Requirements 6.1, 6.3, 6.5**

  - [ ]* 7.3 Write property test for error logging
    - **Property 6: Error Logging**
    - **Validates: Requirements 6.4**

  - [ ]* 7.4 Write unit tests for error scenarios
    - Test invalid trainer_id handling
    - Test missing required fields
    - Test DynamoDB unavailable scenario
    - Test Bedrock timeout scenario
    - _Requirements: 8.4_

- [x] 8. Test multi-tenancy data isolation
  - [ ]* 8.1 Write property test for multi-tenancy data isolation
    - **Property 4: Multi-Tenancy Data Isolation**
    - **Validates: Requirements 5.4, 5.5, 8.3**

  - [ ]* 8.2 Write unit tests for multi-tenancy scenarios
    - Test trainer A cannot access trainer B's students
    - Test trainer A cannot access trainer B's sessions
    - Test trainer A cannot access trainer B's payments
    - _Requirements: 8.3_

- [x] 9. Update imports and remove dead code
  - [x] 9.1 Update all imports across codebase
    - Remove imports of deleted modules (strands_sdk, swarm_orchestrator, ai_agent)
    - Add imports for StrandsAgentService where needed
    - Verify no broken imports remain
    - _Requirements: 2.4_

  - [x] 9.2 Remove feature flag references
    - Remove multi-agent feature flag from feature_flags.py
    - Remove feature flag checks from message_processor.py
    - _Requirements: 2.4_

- [x] 10. Final checkpoint - Ensure all tests pass and coverage meets requirements
  - Run full test suite (unit + property tests)
  - Verify minimum 70% code coverage for strands_agent_service.py
  - Verify 100% coverage for multi-tenancy validation logic
  - Ensure all 8 correctness properties have passing tests
  - Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis library with minimum 100 iterations
- This is NOT production - can freely delete and recreate files
- Single agent architecture is sufficient for FitAgent's use case
- All multi-tenancy security enforced at tool execution layer
