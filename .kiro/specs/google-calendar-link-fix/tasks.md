# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - OAuth URL Lost in Orchestrator Response
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the orchestrator drops OAuth URLs from tool results
  - **Scoped PBT Approach**: Scope the property to calendar connection requests where `calendar_agent` returns a response containing an OAuth URL but the orchestrator's `response_text` omits it
  - Create test file `tests/property/test_calendar_link_bug.py`
  - Use Hypothesis to generate random trainer_ids, providers (google/outlook), and OAuth state tokens
  - Mock the Strands Agent orchestrator to simulate the bug: `calendar_agent` tool result contains OAuth URL, but `AgentResult.text` paraphrases without the URL (e.g., "Clique no link acima para autorizar")
  - Bug condition from design: `isBugCondition(input, tool_results, final_response)` returns true when `extractOAuthURL(tool_results) IS NOT None AND oauth_url NOT IN final_response`
  - Assert expected behavior: for all inputs satisfying the bug condition, `response['response']` MUST contain the complete OAuth URL (matching `https://accounts.google.com/o/oauth2/` or `https://login.microsoftonline.com/`)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists because `process_message` has no post-processing to recover dropped URLs)
  - Document counterexamples found (e.g., "process_message returns 'Clique no link acima para autorizar' without the actual OAuth URL")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Calendar Message Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Create test file `tests/property/test_calendar_link_preservation.py`
  - Observe on UNFIXED code: non-calendar messages (student management, session scheduling, payments, greetings) route correctly and return expected responses
  - Observe on UNFIXED code: calendar connection errors (invalid provider, missing credentials) return error messages without URLs
  - Use Hypothesis to generate random non-calendar messages from various domains (student, session, payment, greeting categories)
  - Write property-based test: for all inputs where `isBugCondition` returns false (no OAuth URL in tool results), `process_message` response is unchanged
  - Mock the Strands Agent orchestrator for non-calendar flows: verify response_text passes through unmodified
  - Mock calendar error flows: verify error messages (no URL generated) pass through unmodified
  - Verify tests pass on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix for OAuth URL lost in orchestrator response

  - [x] 3.1 Add `_extract_oauth_url_from_messages` helper method to `StrandsAgentService`
    - Add a private method that scans the orchestrator's `messages` list for tool results from `calendar_agent` containing OAuth URLs
    - Match URLs starting with `https://accounts.google.com/o/oauth2/` or `https://login.microsoftonline.com/`
    - Return a tuple of (oauth_url, full_tool_result_text) or (None, None) if no OAuth URL found
    - _Bug_Condition: isBugCondition(input, tool_results, final_response) where extractOAuthURL(tool_results) IS NOT None AND oauth_url NOT IN final_response_
    - _Requirements: 2.3_

  - [x] 3.2 Add post-processing URL verification in `process_message`
    - After extracting `response_text` from `AgentResult`, call `_extract_oauth_url_from_messages` on `orchestrator.messages`
    - If an OAuth URL exists in tool results AND is NOT present in `response_text`, replace `response_text` with the original `calendar_agent` tool result string (which contains the URL in a well-formatted message)
    - If `response_text` already contains the OAuth URL, leave it unchanged
    - If no OAuth URL exists in tool results (non-calendar flow or error flow), leave `response_text` unchanged
    - Preserve existing fallback logic for empty `response_text`
    - _Bug_Condition: isBugCondition(input, tool_results, final_response) where extractOAuthURL(tool_results) IS NOT None AND oauth_url NOT IN final_response_
    - _Expected_Behavior: When calendar_agent returns OAuth URL, final response MUST contain that URL verbatim_
    - _Preservation: Non-calendar messages, calendar errors, greetings all unchanged per design Preservation Requirements_
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4_

  - [x] 3.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - OAuth URL Present in Final Response
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior: response must contain the OAuth URL
    - When this test passes, it confirms the post-processing fix correctly recovers dropped URLs
    - Run bug condition exploration test from step 1 (`tests/property/test_calendar_link_bug.py`)
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Calendar Message Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2 (`tests/property/test_calendar_link_preservation.py`)
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - Run full test suite: `make test` to ensure no regressions across the project
  - Ensure all property tests pass: `make test-property`
  - Ensure all unit tests pass: `make test-unit`
  - Ask the user if questions arise
