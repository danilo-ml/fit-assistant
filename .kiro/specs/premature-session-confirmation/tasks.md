# Implementation Plan

- [x] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - Timezone Mismatch Causes Premature Session Confirmation
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the timezone mismatch bug
  - **Scoped PBT Approach**: Use Hypothesis to generate session times and UTC offsets that expose the mismatch
  - **Bug 1 - Premature Confirmation (Timezone Mismatch)**:
    - Mock `datetime.utcnow()` to return a known UTC time (e.g., 11:00 UTC = 08:00 local)
    - Create a session at 09:00 local time (60min duration, `confirmation_status = scheduled`)
    - Call `query_sessions_for_confirmation()` with the UTC-derived time window
    - Assert that the session is NOT matched (expected behavior) — this will FAIL because the unfixed code compares UTC window against local-time session_datetime
    - Property: for all sessions where `session_end_local > now_local`, the session should NOT be in the confirmation results
  - **Bug 2 - Confirmation Response Fallthrough**:
    - Create a session with `confirmation_status = 'pending_confirmation'` (simulating premature confirmation was sent)
    - Simulate trainer replying "Sim" and verify `process_confirmation_response()` returns `True`
    - If the lookup fails (returns `False`), document that the "Sim" falls through to AI agent
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct - it proves the bugs exist)
  - Document counterexamples found to understand root cause
  - Mark task complete when tests are written, run, and failure is documented
  - Test file: `tests/property/test_premature_confirmation_bugfix.py`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Legitimate Confirmation Flow and Message Routing
  - **IMPORTANT**: Follow observation-first methodology
  - **Observe on UNFIXED code first, then write properties**:
    - Observe: Sessions whose end time (in the SAME timezone as the time window) falls within the 55-65 min window are correctly matched
    - Observe: Regular trainer messages are routed to the AI agent normally
    - Observe: "Sim"/"Não" without a pending confirmation returns `False` from `process_confirmation_response()`
    - Observe: `format_confirmation_message()` output format remains consistent
    - Observe: `find_pending_confirmation_session_for_trainer()` returns a session when one exists with `pending_confirmation` status
  - **Property-based tests to write**:
    - For all sessions where `session_end` falls within the time window (using consistent timezone), `query_sessions_for_confirmation()` returns those sessions (test with both times in the same reference frame to isolate the timezone bug)
    - For all non-confirmation messages, `process_confirmation_response()` returns `False`
    - For all valid `(student_name, session_datetime, duration_minutes)` inputs, `format_confirmation_message()` produces consistent output
    - For all trainers with exactly one `pending_confirmation` session, `find_pending_confirmation_session_for_trainer()` returns that session
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - Test file: `tests/property/test_premature_confirmation_preservation.py`
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3. Fix timezone mismatch and confirmation response robustness

  - [x] 3.1 Fix time window calculation in `session_confirmation.py` `lambda_handler()`
    - Replace `now = datetime.utcnow()` with local time calculation: `now = datetime.utcnow() - timedelta(hours=3)` or use `zoneinfo.ZoneInfo('America/Sao_Paulo')` if available
    - The resulting `check_time_start` and `check_time_end` will be in local time, matching the stored `session_datetime` values
    - Update code comments to clarify the timezone handling
    - Also update `send_confirmation_request()` where `datetime.utcnow()` is used for `confirmation_requested_at` and `updated_at` — ensure these timestamps are consistent
    - _Bug_Condition: isBugCondition_TimezoneMismatch(now_utc, session) where datetime.utcnow() is compared against local-time session_datetime_
    - _Expected_Behavior: time window is calculated in local time (UTC-3), only sessions genuinely ended 55-65 min ago are matched_
    - _Preservation: Sessions that genuinely ended in the correct window continue to be matched_
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 3.1_

  - [x] 3.2 Harden `find_pending_confirmation_session_for_trainer()` in `message_processor.py`
    - Change sort order from ascending to descending (`reverse=True`) so the most recently scheduled pending session is returned first
    - Add debug logging: log the count of pending sessions found and the selected session_id
    - This makes the function more robust when multiple pending sessions exist
    - _Bug_Condition: isBugCondition_ConfirmationFallthrough where oldest session is returned instead of most recent_
    - _Expected_Behavior: most recent pending session is returned, with logging for observability_
    - _Preservation: When exactly one pending session exists, behavior is unchanged_
    - _Requirements: 1.3, 1.4, 2.4, 3.3, 3.4_

  - [x] 3.3 Add warning logging in `process_confirmation_response()` when no pending session found
    - When `find_pending_confirmation_session_for_trainer()` returns `None` for a confirmation keyword message, log a warning with `trainer_id` and the message text
    - This enables monitoring/alerting for premature confirmation issues
    - File: `src/handlers/message_processor.py`
    - _Requirements: 1.3, 1.4_

  - [x] 3.4 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - Timezone-Consistent Time Window
    - **IMPORTANT**: Re-run the SAME tests from task 1 - do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the timezone mismatch is fixed
    - Run bug condition exploration tests from step 1
    - **EXPECTED OUTCOME**: Tests PASS (confirms bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Legitimate Confirmation Flow and Message Routing
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - Run full test suite: `make test` or `pytest tests/property/test_premature_confirmation_bugfix.py tests/property/test_premature_confirmation_preservation.py`
  - Ensure all property-based tests pass (both bug condition and preservation)
  - Ensure existing tests are not broken by the changes
  - Ask the user if questions arise
