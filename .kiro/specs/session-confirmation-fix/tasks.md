# Implementation Plan

- [x] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - Phantom Session Confirmations & Leaky Confirmation History
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate both bugs exist
  - **Scoped PBT Approach**: Use Hypothesis to generate multi-trainer session configurations and confirmation message flows
  - **Bug 1 - Phantom Confirmations**:
    - Create sessions for multiple trainers (Trainer A and Trainer B) in the same time window with `confirmation_status = scheduled` and `status != cancelled`
    - Call `query_sessions_for_confirmation()` on unfixed code
    - Assert that the result only contains sessions scoped to each trainer (expected behavior) — this will FAIL because the current scan returns cross-trainer sessions
    - Property: for all trainer_id in result sessions, session.trainer_id should match the queried trainer
  - **Bug 2 - Leaky Confirmation History**:
    - Simulate a "Sim" confirmation message flow where `process_confirmation_response()` returns `True`
    - Assert that `_process_message()` returns a sentinel value (e.g., `None`) instead of `""` — this will FAIL because current code returns `""`
    - Assert that the confirmation message is NOT saved to conversation history — verify the flow prevents history leakage
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct - it proves the bugs exist)
  - Document counterexamples found to understand root cause
  - Mark task complete when tests are written, run, and failure is documented
  - Test file: `tests/property/test_session_confirmation_bugfix.py`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Confirmation Message Routing & Session Query Correctness
  - **IMPORTANT**: Follow observation-first methodology
  - **Observe on UNFIXED code first, then write properties**:
    - Observe: Regular trainer messages ("Agendar sessão", "Listar alunos") are routed to the AI agent and saved to conversation history
    - Observe: "Sim"/"Não" messages when NO pending confirmation exists are treated as regular messages and routed to the AI agent
    - Observe: `format_confirmation_message()` output format remains consistent for given inputs
    - Observe: Sessions with `confirmation_status = scheduled` for a SINGLE trainer are correctly returned by the current query (the bug is cross-trainer, not single-trainer)
    - Observe: Confirmation handler returns `{sent: 0, failed: 0}` when no sessions need confirmation
  - **Property-based tests to write**:
    - For all non-confirmation messages (messages not in `['SIM', 'YES', 'S', 'NÃO', 'NAO', 'NO', 'N']` or messages without pending confirmation), `process_confirmation_response()` returns `False` and message is routed normally
    - For all valid `(student_name, session_datetime, duration_minutes)` inputs, `format_confirmation_message()` produces consistent output containing the student name, formatted date, and formatted time
    - For all single-trainer session sets with `confirmation_status = scheduled`, the query returns those sessions correctly (preservation of correct single-trainer behavior)
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - Test file: `tests/property/test_session_confirmation_preservation.py`
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_


- [x] 3. Fix for phantom session confirmations and leaky confirmation history

  - [x] 3.1 Replace table scan with per-trainer GSI queries in `query_sessions_for_confirmation()`
    - Query all trainers by scanning for `SK = METADATA` with `PK begins_with TRAINER#`
    - For each trainer, call `db_client.get_sessions_by_date_range()` using the `session-date-index` GSI with the confirmation time window
    - Apply post-query filter for `confirmation_status = scheduled` and `status != cancelled` (since these are not GSI key attributes)
    - Preserve the in-memory session end time calculation (`session_datetime + duration_minutes` within time window)
    - Remove the `db_client.table.scan()` call entirely
    - _Bug_Condition: isBugCondition_Phantom(queryMethod) where queryMethod == TABLE_SCAN AND NOT usesGSI('session-date-index')_
    - _Expected_Behavior: query uses session-date-index GSI scoped by trainer_id, returns only sessions belonging to queried trainer_
    - _Preservation: Single-trainer session queries continue to return correct results; format_confirmation_message() unchanged_
    - _Requirements: 1.1, 1.2, 1.5, 2.1, 2.2, 3.3, 3.5_

  - [x] 3.2 Prevent confirmation messages from leaking into conversation history
    - In `_process_message()`, return `None` (sentinel value) instead of `""` when `process_confirmation_response()` returns `True`
    - In `lambda_handler()`, detect `None` return from `_process_message()` and skip both `_send_response()` and any history saving
    - Ensure that when a confirmation response is processed, neither the user message ("Sim") nor the acknowledgment is saved to `ConversationStateManager`
    - _Bug_Condition: isBugCondition_LeakyConfirmation(message, phone_number) where message is confirmation keyword AND hasPendingConfirmation_
    - _Expected_Behavior: confirmation messages return None sentinel, _send_response() and history saving are both skipped_
    - _Preservation: Non-confirmation messages continue to be routed to AI agent and saved to history normally_
    - _Requirements: 1.3, 1.4, 2.3, 2.4, 3.1, 3.2_

  - [x] 3.3 Update IAM policy for session confirmation Lambda role (optional)
    - Add `dynamodb:Query` to the `SessionConfirmationLambdaRole` DynamoDB policy if not already covered
    - Verify the `index/*` resource ARN already grants GSI query access
    - Consider removing `dynamodb:Scan` permission in a follow-up (not required for this fix)
    - File: `infrastructure/template.yml`
    - _Requirements: 2.1_

  - [x] 3.4 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - Phantom Session Confirmations & Leaky Confirmation History
    - **IMPORTANT**: Re-run the SAME tests from task 1 - do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the expected behavior is satisfied
    - Run bug condition exploration tests from step 1
    - **EXPECTED OUTCOME**: Tests PASS (confirms bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Confirmation Message Routing & Session Query Correctness
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - Run full test suite: `make test` or `pytest tests/property/test_session_confirmation_bugfix.py tests/property/test_session_confirmation_preservation.py`
  - Ensure all property-based tests pass (both bug condition and preservation)
  - Ensure existing tests are not broken by the changes
  - Ask the user if questions arise
