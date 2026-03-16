# Implementation Plan

- [ ] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - Message Ordering and Language Issues
  - **CRITICAL**: These tests MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: These tests encode the expected behavior - they will validate the fixes when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate both bugs exist
  - **Scoped PBT Approach**: For deterministic bugs, scope properties to concrete failing cases to ensure reproducibility

  - [x] 1.1 Message ordering bug exploration test
    - Test that rapid sequential messages from same phone number are processed in order
    - Send 3 messages from same phone number with 100ms delay between each
    - Assert responses arrive in same order as questions (from Bug Condition 1 in design)
    - Assert conversation state reflects all messages in sequence without race conditions
    - Run test on UNFIXED code
    - **EXPECTED OUTCOME**: Test FAILS (responses out of order, state race conditions)
    - Document counterexamples found (e.g., "Message 3 response arrived before Message 2 response")
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 1.2 Language bug exploration test
    - Test that onboarding flow and AI responses are in Brazilian Portuguese
    - Send first message from unregistered number to trigger onboarding
    - Assert welcome message is in Portuguese (from Bug Condition 2 in design)
    - Assert AI agent responses are in Portuguese
    - Assert error messages are in Portuguese
    - Run test on UNFIXED code
    - **EXPECTED OUTCOME**: Test FAILS (all messages in English)
    - Document counterexamples found (e.g., "Welcome message: 'Welcome to FitAgent!' instead of 'Bem-vindo ao FitAgent!'")
    - _Requirements: 1.4, 1.5, 1.6_

- [ ] 2. Write preservation property tests (BEFORE implementing fixes)
  - **Property 2: Preservation** - Parallel Processing and Developer Language
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)

  - [x] 2.1 Parallel processing preservation test
    - Observe: Messages from different phone numbers process in parallel on unfixed code
    - Write property-based test: for all message pairs from different phone numbers, processing can overlap
    - Assert messages from different phone numbers are not artificially serialized
    - Assert throughput remains high for non-conflicting messages
    - Verify test passes on UNFIXED code
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 2.2 Tool function preservation test
    - Observe: All 10 tool functions execute with same parameters and validation on unfixed code
    - Write property-based test: for all tool invocations, parameters and return values unchanged
    - Assert register_student, schedule_session, etc. work identically
    - Assert DynamoDB queries and data structures unchanged
    - Verify test passes on UNFIXED code
    - _Requirements: 3.5, 3.6, 3.7, 3.8_

  - [x] 2.3 Developer language preservation test
    - Observe: Code, comments, logs remain in English on unfixed code
    - Write property-based test: for all code files and logs, language is English
    - Assert function names, variables, comments in English
    - Assert CloudWatch logs in English
    - Assert documentation in English
    - Verify test passes on UNFIXED code
    - _Requirements: 3.9, 3.10, 3.11_

- [ ] 3. Fix for message ordering and language support

  - [x] 3.1 Implement message ordering fix (SQS FIFO Queue)
    - Convert SQS queue to FIFO type in infrastructure/template.yml
    - Add `.fifo` suffix to queue name
    - Set `FifoQueue: true` and `ContentBasedDeduplication: true` properties
    - Update Dead Letter Queue to FIFO type as well
    - Add MessageGroupId to webhook_handler.py (set to phone number)
    - Add MessageDeduplicationId to webhook_handler.py (set to message_sid)
    - Update message_processor.py batch size to 1 for FIFO queues
    - Add logging for message group ID in message_processor.py
    - _Bug_Condition: isBugCondition_Ordering(messages) where messages from same phone number have overlapping processing windows_
    - _Expected_Behavior: Messages from same phone number processed sequentially in arrival order (Property 1)_
    - _Preservation: Parallel processing for different phone numbers, tool functions unchanged, DynamoDB schema unchanged (Preservation Requirements)_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [x] 3.2 Implement language support fix (Brazilian Portuguese)
    - Update ai_agent.py system prompt with Portuguese language instruction
    - Add: "IMPORTANT: You MUST respond in Brazilian Portuguese (pt-BR) for all user-facing messages"
    - Translate system prompt content to Portuguese
    - Translate OnboardingHandler welcome message to Portuguese
    - Translate user type selection prompts to Portuguese
    - Translate registration flow prompts to Portuguese
    - Translate validation messages to Portuguese
    - Translate TrainerHandler and StudentHandler menu messages to Portuguese
    - Add Portuguese response formatting to all tool functions
    - Create Portuguese error message templates in validation.py
    - Keep code, comments, logs, and documentation in English
    - _Bug_Condition: isBugCondition_Language(output) where user-facing text is in English instead of Portuguese_
    - _Expected_Behavior: All user-facing text in Brazilian Portuguese (pt-BR) with culturally appropriate phrasing (Property 2)_
    - _Preservation: Code, comments, logs, documentation remain in English (Preservation Requirements)_
    - _Requirements: 2.5, 2.6, 2.7, 2.8, 3.9, 3.10, 3.11_

  - [x] 3.3 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - Message Ordering and Language Fixes
    - **IMPORTANT**: Re-run the SAME tests from task 1 - do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the expected behavior is satisfied
    - Run message ordering exploration test from step 1.1
    - Run language exploration test from step 1.2
    - **EXPECTED OUTCOME**: Tests PASS (confirms bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [x] 3.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Parallel Processing and Developer Language
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run parallel processing preservation test from step 2.1
    - Run tool function preservation test from step 2.2
    - Run developer language preservation test from step 2.3
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fixes (no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise
